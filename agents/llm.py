"""Capa de LLM: proveedores reales, con red de seguridad.

Por qué existe esto como módulo aparte: antes había una sola llamada HTTP a
Anthropic incrustada en `explanation.py`, sin reintentos, sin caché, sin
circuit breaker, sin validación de la salida y sin forma de saber desde
fuente si la respuesta venía de un modelo o del texto determinista. Aquí se
resuelve todo eso y se añaden proveedores reales de verdad.

Proveedores soportados:
  ollama      local, sin clave, sin coste (ideal para datos sensibles)
  anthropic   Claude
  openai      GPT
  gemini      Google
  groq        modelos abiertos muy rápidos
  openrouter  pasarela a muchos modelos
  cualquiera compatible con OpenAI (base_url configurable)

Principio innegociable: una respuesta de modelo NUNCA se publica sin pasar
`validate_explanation`. Un LLM pequeño (qwen2.5:1.5b local) es realista que
se invente una acusación; el texto determinista no puede. Cuando la salida no
super la validación se devuelve el determinista y el usuario nunca ve la
alucinación.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request

CACHE_TTL = float(os.getenv("CHAINMIND_LLM_CACHE_TTL", "3600"))
TIMEOUT = float(os.getenv("CHAINMIND_LLM_TIMEOUT", "45"))
MAX_RETRIES = int(os.getenv("CHAINMIND_LLM_RETRIES", "2"))
BREAKER_THRESHOLD = int(os.getenv("CHAINMIND_LLM_BREAKER", "3"))
BREAKER_COOLDOWN = float(os.getenv("CHAINMIND_LLM_BREAKER_COOLDOWN", "120"))
DISCLAIMER = ("Es una heurística automatizada, no un veredicto: confirma siempre "
              "on-chain antes de actuar.")

# Prioridad de auto-detección: local primero porque es gratis, privado y ya
# está disponible; la nube solo entra si hay credencial puesta.
PRIORITY = ("ollama", "anthropic", "openai", "gemini", "groq", "openrouter")

PROVIDERS: dict[str, dict] = {
    "ollama": {
        "url": os.getenv("OLLAMA_URL", "http://127.0.0.1:11434"),
        # Medido en esta máquina (scripts/bench_models.py): phi4-mini 3,3 s y
        # siempre supera el filtro; qwen2.5:7b 7,5 s. Los agentes pueden pedir
        # otro modelo cada uno (agents.agents).
        "model": os.getenv("CHAINMIND_LLM_MODEL_OLLAMA", "phi4-mini"),
        "style": "ollama",
        "env": None,
        "price_in": 0.0, "price_out": 0.0,
    },
    "anthropic": {
        "url": "https://api.anthropic.com/v1/messages",
        "model": os.getenv("CHAINMIND_LLM_MODEL_ANTHROPIC", "claude-3-5-sonnet-20241022"),
        "style": "anthropic",
        "env": "ANTHROPIC_API_KEY",
        "price_in": 3e-6, "price_out": 15e-6,
    },
    "openai": {
        "url": os.getenv("CHAINMIND_LLM_BASE_URL", "https://api.openai.com/v1/chat/completions"),
        "model": os.getenv("CHAINMIND_LLM_MODEL_OPENAI", "gpt-4o-mini"),
        "style": "openai",
        "env": "OPENAI_API_KEY",
        "price_in": 0.15e-6, "price_out": 0.6e-6,
    },
    "gemini": {
        "url": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": os.getenv("CHAINMIND_LLM_MODEL_GEMINI", "gemini-2.0-flash"),
        "style": "gemini",
        "env": "GEMINI_API_KEY",
        "price_in": 0.1e-6, "price_out": 0.4e-6,
    },
    "groq": {
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": os.getenv("CHAINMIND_LLM_MODEL_GROQ", "llama-3.3-70b-versatile"),
        "style": "openai",
        "env": "GROQ_API_KEY",
        "price_in": 0.59e-6, "price_out": 0.79e-6,
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "model": os.getenv("CHAINMIND_LLM_MODEL_OPENROUTER", "anthropic/claude-3.5-sonnet"),
        "style": "openai",
        "env": "OPENROUTER_API_KEY",
        "price_in": 3e-6, "price_out": 15e-6,
    },
}

_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
_stats: dict[str, dict] = {
    "calls": 0, "ok": 0, "errors": 0, "cached": 0, "rejected": 0,
    "tokens_in": 0, "tokens_out": 0, "usd": 0.0, "last_provider": None,
    "last_latency_s": 0.0, "last_error": None,
}
_breaker: dict[str, dict] = {}


# ------------------------------------------------------------------ estado
def has_credentials(provider: str) -> bool:
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return False
    env = cfg.get("env")
    return True if env is None else bool(os.getenv(env, "").strip())


def available() -> list[str]:
    if os.getenv("CHAINMIND_LLM_DISABLED", "0") == "1":
        return []
    return [p for p in PRIORITY if has_credentials(p)]


def active() -> str | None:
    """Proveedor efectivo: el explícito si está, si no el primero disponible.

    `CHAINMIND_LLM_DISABLED=1` lo apaga por completo: así los tests no gastan
    tokens ni dependen de que haya un modelo local encendido.
    """
    if os.getenv("CHAINMIND_LLM_DISABLED", "0") == "1":
        return None
    elegido = os.getenv("CHAINMIND_LLM_PROVIDER", "").strip().lower()
    if elegido:
        return elegido if has_credentials(elegido) else None
    disponibles = available()
    return disponibles[0] if disponibles else None


def model_of(provider: str | None = None) -> str | None:
    provider = provider or active()
    return PROVIDERS.get(provider, {}).get("model") if provider else None


def is_local(provider: str | None = None) -> bool:
    provider = provider or active()
    return provider == "ollama"


def breaker_open(provider: str) -> bool:
    with _lock:
        b = _breaker.get(provider)
        if not b or b["failures"] < BREAKER_THRESHOLD:
            return False
        if time.time() - b["opened_at"] < BREAKER_COOLDOWN:
            return True
        _breaker.pop(provider, None)
        return False


def _record_failure(provider: str, error: str) -> None:
    with _lock:
        b = _breaker.setdefault(provider, {"failures": 0, "opened_at": 0.0})
        b["failures"] += 1
        if b["failures"] >= BREAKER_THRESHOLD:
            b["opened_at"] = time.time()
        _stats["errors"] += 1
        _stats["last_error"] = f"{provider}: {error[:160]}"


def _record_success(provider: str) -> None:
    with _lock:
        _breaker.pop(provider, None)
        _stats["ok"] += 1


_ollama_cache: dict[str, object] = {"at": 0.0, "models": []}
MODELS_TTL = float(os.getenv("CHAINMIND_OLLAMA_MODELS_TTL", "60"))


def ollama_models() -> list[str]:
    """Modelos instalados en Ollama. Permite avisar si el configurado no existe.

    Con caché: /status lo consulta en cada refresco del panel y sin esto cada
    visita sería una llamada de red a Ollama.
    """
    ahora = time.time()
    if ahora - float(_ollama_cache["at"]) < MODELS_TTL:
        return list(_ollama_cache["models"])  # type: ignore[arg-type]
    try:
        url = PROVIDERS["ollama"]["url"].rstrip("/") + "/api/tags"
        req = urllib.request.Request(url, headers={"User-Agent": "ChainMind/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.load(r)
        modelos = [m.get("name", "") for m in (data.get("models") or []) if m.get("name")]
    except Exception:
        modelos = []
    _ollama_cache.update({"at": ahora, "models": modelos})
    return modelos


def ollama_sugerido() -> str | None:
    """Si el modelo configurado no está, propone el más grande instalado."""
    instalados = ollama_models()
    if not instalados:
        return None
    if PROVIDERS["ollama"]["model"] in instalados:
        return None
    generadores = [m for m in instalados if "embed" not in m.lower() and "vision" not in m.lower()]
    if not generadores:
        return None

    def tamano(nombre: str) -> float:
        m = re.search(r"(\d+(?:\.\d+)?)\s*b\b", nombre.lower())
        return float(m.group(1)) if m else 0.0

    return max(generadores, key=tamano)


def status() -> dict:
    """Auditable desde /status: qué IA está activa, cuánto costó y si falla."""
    with _lock:
        stats = dict(_stats)
        # OJO: breaker_open() vuelve a tomar el lock, así que se evalúa fuera.
        # Meterlo aquí dentro era un deadlock en cuanto un proveedor fallaba.
        pendientes = [(p, b["failures"]) for p, b in _breaker.items()]
        cache_n = len(_cache)
    breakers = {p: {"failures": f, "abierta": breaker_open(p)} for p, f in pendientes}
    act = active()
    out = {
        "provider": act,
        "model": model_of(act),
        "local": is_local(act),
        "disponibles": available(),
        "cache_ttl_s": CACHE_TTL,
        "timeout_s": TIMEOUT,
        "entradas_cache": cache_n,
        "circuits": breakers,
        "estadisticas": stats,
        "precio_por_1m_tokens": (
            {"entrada_usd": PROVIDERS[act]["price_in"] * 1e6, "salida_usd": PROVIDERS[act]["price_out"] * 1e6}
            if act else None
        ),
    }
    if act == "ollama":
        instalados = ollama_models()
        out["modelos_instalados"] = instalados
        if instalados and model_of(act) not in instalados:
            sugerencia = ollama_sugerido()
            out["aviso"] = (
                f"el modelo '{model_of(act)}' no está instalado; "
                + (f"usa `{sugerencia}` (CHAINMIND_LLM_MODEL_OLLAMA) o `ollama pull {model_of(act)}`"
                   if sugerencia else "los agentes caerán al texto determinista")
            )
    return out


# ------------------------------------------------------------------ payload
def _payload(provider: str, system: str, user: str, max_tokens: int, temperature: float,
             modelo: str | None = None) -> tuple[dict, dict, str]:
    cfg = PROVIDERS[provider]
    modelo = modelo or cfg["model"]
    if cfg["style"] == "anthropic":
        return {
            "model": modelo, "max_tokens": max_tokens, "temperature": temperature,
            "system": system, "messages": [{"role": "user", "content": user}],
        }, {
            "Content-Type": "application/json",
            "x-api-key": os.getenv("ANTHROPIC_API_KEY", ""),
            "anthropic-version": "2023-06-01",
        }, "https://api.anthropic.com/v1/messages"
    if cfg["style"] == "gemini":
        return {
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": temperature},
        }, {
            "Content-Type": "application/json",
            "x-goog-api-key": os.getenv("GEMINI_API_KEY", ""),
        }, f"{cfg['url']}/{modelo}:generateContent"
    if cfg["style"] == "ollama":
        return {
            "model": modelo, "system": system, "prompt": user, "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }, {"Content-Type": "application/json"}, f"{cfg['url']}/api/generate"
    return {
        "model": modelo, "max_tokens": max_tokens, "temperature": temperature,
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }, {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {os.getenv(cfg['env'] or '', '')}",
    }, cfg["url"]


def _extract(provider: str, data: dict) -> tuple[str, int, int, bool]:
    """Texto + tokens de entrada/salida + si el modelo cortó por límite.

    El 4º valor importa: un texto truncado a media frase parece un fallo, así
    que el validador lo recorta a la última oración completa.
    """
    cfg = PROVIDERS[provider]
    if cfg["style"] == "anthropic":
        txt = "".join(p.get("text", "") for p in data.get("content", []) if isinstance(p, dict))
        uso = data.get("usage") or {}
        stop = data.get("stop_reason")
        return txt.strip(), int(uso.get("input_tokens") or 0), int(uso.get("output_tokens") or 0), stop == "max_tokens"
    if cfg["style"] == "gemini":
        cand = ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
        txt = "".join(p.get("text", "") for p in cand if isinstance(p, dict))
        uso = data.get("usageMetadata") or {}
        motivo = (data.get("candidates") or [{}])[0].get("finishReason")
        return txt.strip(), int(uso.get("promptTokenCount") or 0), int(uso.get("candidatesTokenCount") or 0), motivo == "MAX_TOKENS"
    if cfg["style"] == "ollama":
        return (str(data.get("response") or "").strip(),
                int(data.get("prompt_eval_count") or 0), int(data.get("eval_count") or 0),
                data.get("done_reason") == "length")
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    uso = data.get("usage") or {}
    return (str(msg.get("content") or "").strip(),
            int(uso.get("prompt_tokens") or 0), int(uso.get("completion_tokens") or 0),
            choice.get("finish_reason") == "length")


# ------------------------------------------------------------------ cache
def _key(provider: str, modelo: str, system: str, user: str, max_tokens: int, temperature: float) -> str:
    raw = json.dumps([provider, modelo, system, user, max_tokens, temperature],
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def clear_cache() -> int:
    with _lock:
        n = len(_cache)
        _cache.clear()
        return n


# ----------------------------------------------------------------- llamada
def complete(system: str, user: str, *, max_tokens: int = 400, temperature: float = 0.2,
             purpose: str = "generic", model: str | None = None) -> dict:
    """Llama al proveedor activo. Nunca lanza: devuelve dict con `ok`.

    `ok=False` significa que el llamador debe usar su texto determinista.
    `model` permite que cada agente use el suyo sin tocar el global.
    """
    provider = active()
    if not provider:
        return {"ok": False, "error": "sin proveedor configurado"}
    if breaker_open(provider):
        return {"ok": False, "error": f"circuit breaker abierto para {provider}"}

    modelo = model or PROVIDERS[provider]["model"]
    ck = _key(provider, modelo, system, user, max_tokens, temperature)
    with _lock:
        hit = _cache.get(ck)
        if hit and (time.time() - hit[0]) < CACHE_TTL:
            _stats["cached"] += 1
            return {**hit[1], "cached": True}

    cfg = PROVIDERS[provider]
    cuerpo, headers, url = _payload(provider, system, user, max_tokens, temperature, modelo)
    ultimo_error = ""
    for intento in range(MAX_RETRIES + 1):
        t0 = time.time()
        try:
            req = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                data = json.load(r)
            texto, tin, tout, truncado = _extract(provider, data)
            if not texto:
                raise RuntimeError("respuesta vacía del modelo")
            latencia = round(time.time() - t0, 3)
            coste = (tin * cfg["price_in"] + tout * cfg["price_out"])
            with _lock:
                _stats["calls"] += 1
                _stats["tokens_in"] += tin
                _stats["tokens_out"] += tout
                _stats["usd"] = round(_stats["usd"] + coste, 8)
                _stats["last_provider"] = provider
                _stats["last_latency_s"] = latencia
            _record_success(provider)
            salida = {
                "ok": True, "text": texto, "provider": provider, "model": modelo,
                "latency_s": latencia, "tokens_in": tin, "tokens_out": tout,
                "usd": round(coste, 8), "purpose": purpose, "cached": False,
                "truncado": truncado,
            }
            with _lock:
                _cache[ck] = (time.time(), salida)
            return salida
        except urllib.error.HTTPError as e:
            ultimo_error = f"HTTP {e.code}"
            if e.code not in (408, 409, 425, 429, 500, 502, 503, 504):
                break  # 4xx de auth o prompt: reintentar no sirve
        except Exception as e:
            ultimo_error = f"{type(e).__name__}: {e}"
        if intento < MAX_RETRIES:
            time.sleep(min(2 ** intento, 4))

    _record_failure(provider, ultimo_error)
    return {"ok": False, "error": ultimo_error or "fallo desconocido", "provider": provider}


# ---------------------------------------------------------------- seguridad
# Un LLM puede acusar. Este producto no: una heurística es una señal para
# investigar. Se buscan raíces, no palabras sueltas: "delito/delitos/delictiva/
# ciberdelito" y "malicioso/maliciosa" son el mismo fallo.
ACUSACIONES = (
    r"\w*delit\w*", r"\bdelincuente\w*", r"\bcrimen\w*", r"\bcriminal\w*",
    r"\bculpable\w*", r"\binfringi\w*", r"\bdenunciad[oa]\w*", r"\bmalicios[oa]\w*",
    r"\bilegal\w*", r"\bdelictiv\w*", r"\bestafa\w*", r"\bfraude\w*",
    r"\blavador(?:a|es)?\b", r"\blavapi\w*", r"\bblanqueo\b", r"\bblanqueamiento\b",
    r"\bterrorista\w*", r"\bmoney laundering\b", r"\bsancci[óo]n definitiva\b",
    r"\bproveedor de servicios agregadores?\b", r"\bsancionado por (?:ofac|ofac\b|el treasury)",
)
INTENCIONES = (
    r"\bquiere (?:robar|blanquear|estafar|fugarse)\b",
    r"\bintenta(?:ndo|n)? (?:robar|blanquear|estafar|fugarse|evadir)\b",
    r"\bplanea(?:ndo|n)? (?:robar|blanquear|estafar)\b",
    r"\best[áa] (?:planeando|-planeada)\b", r"\bcon el prop[óo]sito de\b",
    r"\bes una trampa\b", r"\bpara evadir (?:el |las )?(?:control|reglas|sanciones)\b",
    r"\bcon el fin de (?:blanquear|robar|estafar)\b",
)
INVENTADAS = (
    r"\bse sabe que\b", r"\bpublicamente conocid\w*", r"\btodos saben que\b",
    r"\bseg[úu]n (?:los|las) (?:medios|noticias|informes)\b", r"\bse ha documentado que\b",
    r"\bpresuntamente es\b", r"\bse presume que\b", r"\bevidentemente es\b",
    r"\btal como muestra el gr[áa]fico\b",
)

# Coherencia: el análisis es aprovechable aunque quite una frase. Se eliminan
# en vez de tirar la respuesta entera; si no queda nada útil, cae al texto fijo.
INCOHERENTES = (
    # la confianza sale de `sample_confidence` en nuestros datos, nunca del score
    r"\bscore\b[^\.]{0,50}\bconfianza\b", r"\bconfianza\b[^\.]{0,30}\bscore\b",
)
META = (
    r"\bcomo (?:un |una )?(?:modelo|ia|asistente)\b", r"\bno puedo (?:ayudar|proporcionar|analizar)\b",
    r"\bi (?:cannot|can't|am unable)\b", r"\bas an ai\b", r"\bcomo modelo de lenguaje\b",
    r"\bmi objetivo es (?:ayudar|informar)\b",
)
RUIDO = re.compile(r"^\s*(?:[>#*-]+\s*)+|^\s*\*{0,2}(?:resumen|análisis|respuesta)\*{0,2}\s*:?\s*", re.I)

# Un LLM pequeño invierte el sentido del score ("10/100" como "alta confianza").
# Estas frases contradicen la banda del score, así que se rechazan.
RIESGO_ALTO = (
    r"\briesgo (?:muy )?(?:alto|elevado|grave)\b", r"\briesgo alto\b",
    r"\bpeligro (?:alto|elevado)\b", r"\bextremadamente riesgoso\b",
)
RIESGO_BAJO = (
    r"\briesgo (?:muy )?bajo\b", r"\briesgo min[ií]mo\b", r"\bcasi sin riesgo\b",
    r"\bpoco riesgoso\b", r"\bsin riesgos relevantes\b", r"\bno se observan riesgos\b",
    r"\bno hay riesgos\b", r"\bsin se[ñn]ales de riesgo\b", r"\bno presenta riesgos\b",
)


def _contradice_score(texto: str, score: int | None) -> str | None:
    """Devuelve el motivo si el texto se contradice con la banda del score."""
    if score is None:
        return None
    if score < 30:
        for p in RIESGO_ALTO:
            if re.search(p, texto, re.I):
                return f"contradice el score {score}/100 (riesgo bajo) con '{p}'"
    elif score >= 70:
        for p in RIESGO_BAJO:
            if re.search(p, texto, re.I):
                return f"contradice el score {score}/100 (riesgo alto) con '{p}'"
    return None


def _limpiar_texto(text: str) -> str:
    """Quita prefijos de formato ('## Resumen:', viñetas) hasta que se estabiliza."""
    limpio = text.strip()
    for _ in range(3):
        nuevo = RUIDO.sub("", limpio).strip()
        if nuevo == limpio:
            break
        limpio = nuevo
    return limpio


def _oraciones(texto: str) -> list[str]:
    partes = re.split(r"(?<=[.!?…])\s+", texto.replace("\n", " "))
    return [p for p in (x.strip() for x in partes) if p]


def _quitar_incoherentes(texto: str, score: int | None) -> tuple[str, int]:
    """Elimina las frases que contradicen el score o le atribuyen confianza.

    Se descartan en lugar de rechazar todo el texto: el resto del análisis sigue
    siendo válido y el score lo calcula nuestro código, no el modelo.
    """
    if score is None and not any(re.search(p, texto, re.I) for p in INCOHERENTES):
        return texto, 0
    patrones = list(INCOHERENTES)
    if score is not None:
        if score < 30:
            patrones += list(RIESGO_ALTO)
        elif score >= 70:
            patrones += list(RIESGO_BAJO)
    quitadas = 0
    quedan = []
    for oracion in _oraciones(texto):
        if any(re.search(p, oracion, re.I) for p in patrones):
            quitadas += 1
            continue
        quedan.append(oracion)
    if not quitadas:
        return texto, 0
    return " ".join(quedan).strip(), quitadas


def _cortar_en_oracion(texto: str) -> str:
    """Deja el texto en la última oración completa: 'Comprobar si ' no es una frase."""
    if re.search(r"[.!?…:;)\]]\s*$", texto):
        return texto
    partes = re.split(r"(?<=[.!?…])\s+", texto)
    if len(partes) > 1:
        ultimo = " ".join(partes[:-1]).rstrip()
        return ultimo if re.search(r"[.!?…]$", ultimo) else ultimo + "."
    return texto.rstrip(" ,;:-–—") + "."


def validate_explanation(text: str, score: int | None = None, truncado: bool = False) -> tuple[str | None, str]:
    """Devuelve (texto_aprobado, motivo). None = rechazado, usar el determinista.

    Rechaza por acusación o intención (inaceptable en un producto de
    screening), por invención de hechos y por metatexto. Lo que solo sea
    mejorable (falta el descargo, sobra formato, quedó cortado) se corrige en
    lugar de tirar la respuesta entera.
    """
    if not text or not text.strip():
        return None, "vacío"
    limpio = _limpiar_texto(text)
    limpio = re.sub(r"\n{3,}", "\n\n", limpio)
    # No basta con el aviso del proveedor: un modelo puede detenerse él mismo a
    # media palabra y reportar "stop". Si no acaba en puntuación, se recorta.
    if truncado or not re.search(r"[.!?:…»)\]]\s*$", limpio):
        limpio = _cortar_en_oracion(limpio)
    for etiqueta, patrones in (("acusación", ACUSACIONES), ("intención", INTENCIONES),
                               ("invención", INVENTADAS), ("metatexto", META)):
        for p in patrones:
            if re.search(p, limpio, re.I):
                return None, f"{etiqueta}:{p}"
    limpio, quitadas = _quitar_incoherentes(limpio, score)
    if not limpio:
        return None, "incoherencia: todas las frases contradicen el score"
    if quitadas:
        limpio = re.sub(r"\n{3,}", "\n\n", limpio).strip()
    if len(limpio) > 2200:
        limpio = limpio[:2200].rsplit(".", 1)[0] + "."
    if "no un veredicto" not in limpio.lower() and "no es asesoramiento" not in limpio.lower():
        limpio = f"{limpio}\n\n{DISCLAIMER}"
    return limpio, "ok"


def explain_with_llm(system: str, user: str, fallback: str, *, max_tokens: int = 400,
                     temperature: float = 0.2, purpose: str = "explanation",
                     score: int | None = None) -> dict:
    """Atajo usado por los agentes: LLM si pasa la validación, si no el texto dado.

    Devuelve siempre texto usable, más la trazabilidad de por qué.
    """
    res = complete(system, user, max_tokens=max_tokens, temperature=temperature, purpose=purpose)
    if not res.get("ok"):
        return {"text": fallback, "source": "determinista", "motivo": res.get("error", "sin proveedor")}
    aprobado, motivo = validate_explanation(res["text"], score, truncado=bool(res.get("truncado")))
    if aprobado is None:
        with _lock:
            _stats["rejected"] += 1
        return {"text": fallback, "source": "determinista", "motivo": f"rechazado ({motivo})",
                "provider": res.get("provider"), "model": res.get("model")}
    return {"text": aprobado, "source": "llm", "motivo": "ok", "provider": res.get("provider"),
            "model": res.get("model"), "latency_s": res.get("latency_s"),
            "tokens_in": res.get("tokens_in"), "tokens_out": res.get("tokens_out"),
            "usd": res.get("usd"), "cached": res.get("cached", False)}


if __name__ == "__main__":
    print(json.dumps(status(), ensure_ascii=False, indent=2))
