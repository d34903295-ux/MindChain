"""Tests de la capa LLM: adapters, validación, cache, breaker y trazabilidad.

La rama de IA no tenía ni un test: por eso se pudo publicar un sistema donde
Claude nunca se había ejecutado. Aquí se cubre con HTTP mockeado, sin gastar
tokens y sin depender de que haya un modelo local encendido.
"""
import json
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, ".")
from agents import llm


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "0")
    llm.clear_cache()
    llm._breaker.clear()
    for k, v in llm._stats.items():
        llm._stats[k] = 0 if isinstance(v, int) else ([] if isinstance(v, list) else 0.0)
    llm._stats["circuits"] = {}
    yield
    llm.clear_cache()
    llm._breaker.clear()


class RespuestaFalsa:
    def __init__(self, payload):
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._payload).encode()


def _mock(monkeypatch, payload, captured=None):
    def urlopen(req, timeout=0):
        if captured is not None:
            # urllib normaliza los nombres de cabecera (X-api-key), se comparan sin mayúsculas
            captured["url"] = req.full_url
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["body"] = json.loads(req.data.decode())
        return RespuestaFalsa(payload)
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


# ------------------------------------------------------------ autodetección
def test_detecta_ollama_sin_clave(monkeypatch):
    assert "ollama" in llm.available()
    assert llm.active() == "ollama"
    assert llm.is_local() is True


def test_proveedor_explicito_manda(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "anthropic")
    assert llm.active() == "anthropic"
    assert llm.is_local() is False


def test_proveedor_explicito_sin_credencial_no_inventa(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "groq")
    assert llm.active() is None


def test_desactivado_no_llama(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "1")
    assert llm.active() is None
    assert llm.complete("s", "u")["ok"] is False


# ----------------------------------------------------------------- adapters
def test_adapter_ollama(monkeypatch):
    cap = {}
    _mock(monkeypatch, {"response": "hola", "prompt_eval_count": 10, "eval_count": 5}, cap)
    r = llm.complete("sys", "user", max_tokens=99, temperature=0.3)
    assert r["ok"] and r["text"] == "hola"
    assert cap["url"].endswith("/api/generate")
    assert cap["body"]["system"] == "sys" and cap["body"]["prompt"] == "user"
    assert cap["body"]["options"]["num_predict"] == 99
    assert (r["tokens_in"], r["tokens_out"]) == (10, 5)


def test_adapter_anthropic(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
    cap = {}
    _mock(monkeypatch, {"content": [{"type": "text", "text": "respuesta"}],
                        "usage": {"input_tokens": 7, "output_tokens": 3}}, cap)
    r = llm.complete("sys", "user")
    assert r["ok"] and r["text"] == "respuesta"
    assert cap["url"] == "https://api.anthropic.com/v1/messages"
    assert cap["headers"]["x-api-key"] == "sk-ant-fake"
    assert cap["headers"]["anthropic-version"] == "2023-06-01"
    assert (r["tokens_in"], r["tokens_out"]) == (7, 3)


def test_adapter_openai_compatible(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
    cap = {}
    _mock(monkeypatch, {"choices": [{"message": {"content": "respuesta"}}],
                        "usage": {"prompt_tokens": 11, "completion_tokens": 4}}, cap)
    r = llm.complete("sys", "user")
    assert r["ok"] and r["text"] == "respuesta"
    assert cap["body"]["messages"][0]["role"] == "system"
    assert cap["headers"]["authorization"] == "Bearer sk-fake"


def test_adapter_gemini(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    cap = {}
    _mock(monkeypatch, {"candidates": [{"content": {"parts": [{"text": "respuesta"}]}}],
                        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 2}}, cap)
    r = llm.complete("sys", "user")
    assert r["ok"] and r["text"] == "respuesta"
    assert cap["url"].endswith(":generateContent")
    assert cap["body"]["systemInstruction"]["parts"][0]["text"] == "sys"


# ------------------------------------------------------------------- cache
def test_cache_evita_la_segunda_llamada(monkeypatch):
    llamadas = []

    def urlopen(req, timeout=0):
        llamadas.append(1)
        return RespuestaFalsa({"response": "hola"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    llm.complete("sys", "user")
    r2 = llm.complete("sys", "user")
    assert len(llamadas) == 1
    assert r2["cached"] is True


def test_prompt_distinto_no_usa_cache(monkeypatch):
    llamadas = []

    def urlopen(req, timeout=0):
        llamadas.append(1)
        return RespuestaFalsa({"response": "hola"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    llm.complete("sys", "user")
    llm.complete("sys", "otro usuario")
    assert len(llamadas) == 2


# ----------------------------------------------------------------- breaker
def test_circuit_breaker_tras_varios_fallos(monkeypatch):
    # el umbral se lee al importar, hay que cambiar la constante, no el entorno
    monkeypatch.setattr(llm, "BREAKER_THRESHOLD", 2)
    monkeypatch.setattr(llm, "MAX_RETRIES", 0)

    def falla(req, timeout=0):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(urllib.request, "urlopen", falla)
    llm.complete("a", "a")
    llm.complete("b", "b")
    assert llm.breaker_open("ollama") is True
    r = llm.complete("c", "c")
    assert r["ok"] is False
    assert "breaker" in r["error"]
    assert llm._stats["errors"] >= 2


def test_error_de_auth_no_reintenta(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "mala")
    intentos = []

    def urlopen(req, timeout=0):
        intentos.append(1)
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    r = llm.complete("s", "u")
    assert r["ok"] is False and r["error"] == "HTTP 401"
    assert len(intentos) == 1, "un 401 no se arregla reintentando"


def test_rate_limit_si_reintenta(monkeypatch):
    intentos = []

    def urlopen(req, timeout=0):
        intentos.append(1)
        if len(intentos) < 2:
            raise urllib.error.HTTPError(req.full_url, 429, "slow down", {}, None)
        return RespuestaFalsa({"response": "reintentado"})

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    r = llm.complete("s", "u")
    assert r["ok"] and r["text"] == "reintentado"
    assert len(intentos) == 2


# -------------------------------------------------------------- validación
@pytest.mark.parametrize("texto,por_que", [
    ("Esto es un delito claro de lavado.", "acusación"),
    ("La dirección quiere blanquear dinero.", "intención"),
    ("Se sabe que esta wallet es un mixer.", "invención"),
    ("Es un ciberdelito!", "acusación"),
    ("Actividad maliciosa evidente.", "acusación"),
    ("Como modelo de IA no puedo ayudarte.", "metatexto"),
])
def test_rechaza_salidas_peligrosas(texto, por_que):
    r, motivo = llm.validate_explanation(texto)
    assert r is None and por_que in motivo


def test_acepta_texto_neutro_y_anade_descargo():
    r, m = llm.validate_explanation("El movimiento es 40x la mediana del bloque. Revisa el destino.")
    assert m == "ok" and r is not None
    assert "no un veredicto" in r


def test_no_duplica_descargo():
    con_descargo = "El patrón es inusual. Es una heurística automatizada, no un veredicto."
    r, _ = llm.validate_explanation(con_descargo)
    assert r.lower().count("no un veredicto") == 1


def test_limpia_ruido_de_markdown():
    r, _ = llm.validate_explanation("## Resumen\nEl movimiento es grande.\n")
    assert r.startswith("El movimiento es grande.")


def test_trunca_textos_absurdos():
    r, _ = llm.validate_explanation("palabra " * 800)
    assert len(r) <= 2300


def test_rechaza_texto_que_invierte_el_score():
    """Un 1.5B local decía 'score 10/100 sugiere una alta confianza'."""
    texto = "El score heurístico de 10/100 sugiere una alta confianza en el patrón."
    r, motivo = llm.validate_explanation(texto, score=10)
    assert r is None


def test_acepta_coherente_con_el_score():
    texto = "Con un score de 10/100 el patrón no muestra señales relevantes en los datos."
    r, m = llm.validate_explanation(texto, score=10)
    assert r is not None and m == "ok"


def test_contradiccion_con_score_alto():
    texto = "No se observan riesgos relevantes en este contrato."
    r, motivo = llm.validate_explanation(texto, score=85)
    assert r is None and "contradice" in motivo


def test_sin_score_no_hay_contradiccion_que_buscar():
    texto = "El riesgo es alto según el análisis."
    r, m = llm.validate_explanation(texto, score=None)
    assert r is not None


def test_rechaza_vacio():
    assert llm.validate_explanation("")[0] is None


def test_recorta_texto_truncado_a_la_ultima_frase():
    truncado = "El patrón es inusual. Conviene revisar el destino. Comprobar si "
    limpio, m = llm.validate_explanation(truncado, truncado=True)
    assert m == "ok"
    assert "Comprobar si" not in limpio, "la frase a medias debe desaparecer"
    assert limpio.startswith("El patrón es inusual. Conviene revisar el destino.")
    assert ".." not in limpio, "no debe quedar doble punto al recortar"


def test_detecta_truncado_en_cada_proveedor(monkeypatch):
    _mock(monkeypatch, {"response": "texto a medias sin final", "done_reason": "length"})
    assert llm.complete("s", "u")["truncado"] is True
    _mock(monkeypatch, {"content": [{"text": "x"}], "stop_reason": "max_tokens"})
    llm.clear_cache()
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    assert llm.complete("s2", "u2")["truncado"] is True
    _mock(monkeypatch, {"response": "completo.", "done_reason": "stop"})
    llm.clear_cache()
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "ollama")
    assert llm.complete("s3", "u3")["truncado"] is False


# ------------------------------------------------------------ explain_with
def test_explain_with_llm_usa_el_modelo(monkeypatch):
    _mock(monkeypatch, {"response": "El flujo es inusual respecto a la mediana. Revisa el destino."})
    r = llm.explain_with_llm("sys", "user", "texto-fijo", purpose="explanation")
    assert r["source"] == "llm"
    assert "texto-fijo" not in r["text"]


def test_explain_with_llm_cae_al_fallback_si_acusa(monkeypatch):
    _mock(monkeypatch, {"response": "Esto es una lotion de|delito grave."})
    r = llm.explain_with_llm("sys", "user", "texto-fijo")
    assert r["text"] == "texto-fijo"
    assert r["source"] == "determinista" and "rechazado" in r["motivo"]
    assert llm._stats["rejected"] == 1


def test_explain_with_llm_cae_al_fallback_si_falla(monkeypatch):
    def falla(req, timeout=0):
        raise urllib.error.URLError("sin red")
    monkeypatch.setattr(urllib.request, "urlopen", falla)
    r = llm.explain_with_llm("sys", "user", "texto-fijo")
    assert r["text"] == "texto-fijo" and r["source"] == "determinista"


# ----------------------------------------------------------------- status
def test_status_es_auditable(monkeypatch):
    _mock(monkeypatch, {"response": "hola", "prompt_eval_count": 1000, "eval_count": 500})
    llm.complete("s", "u")
    st = llm.status()
    assert st["provider"] == "ollama"
    assert st["local"] is True
    assert st["estadisticas"]["tokens_in"] == 1000
    assert st["precio_por_1m_tokens"]["entrada_usd"] == 0.0


def test_el_ultimo_error_no_filtra_credenciales(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secreto-real")

    def falla(req, timeout=0):
        raise urllib.error.URLError("sin red")

    monkeypatch.setattr(urllib.request, "urlopen", falla)
    llm.complete("s", "u")
    assert "sk-ant-secreto-real" not in llm.status()["estadisticas"]["last_error"]
