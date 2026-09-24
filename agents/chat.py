"""Nodo de chat: el sistema respondiendo preguntas sobre lo que vive en ChainMind.

Dos decisiones que separan esto de un chatbot de adorno:

1. **Herramientas de verdad.** No simula: llama a los mismos `fetcher`,
   `wallet_intelligence`, `risk_scoring`, `investigation` y `watchlist` que
   usan los endpoints. Si el chat dice un score, ese score está calculado.

2. **Router determinista primero.** Un modelo de 3B no es fiable decidiendo
   tool calls en JSON, así que no se lo pide. El enrutado lo hace una tabla de
   patrones: detecta la dirección, la red y la intención. El LLM solo redacta
   la respuesta final con los datos ya en la mano. Si el modelo falla, el
   chat sigue respondiendo con el resumen determinista.

El LLM nunca ve claves: las herramientas le devuelven un resumen recortado, no
el objeto interno completo.
"""
from __future__ import annotations

import json
import re

from . import agents, chains, watchlist

ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")
MAX_HISTORIAL = 6

RED_POR_PALABRA = (
    (r"\bbase\b|\bbase chain\b", "base"),
    (r"\bethereum\b|\beth\b", "ethereum"),
)


def _direccion(texto: str) -> str | None:
    m = ADDR_RE.search(texto or "")
    return m.group(0).lower() if m else None


def _cadena(texto: str, por_defecto: str = "ethereum") -> str:
    t = (texto or "").lower()
    for patron, nombre in RED_POR_PALABRA:
        if re.search(patron, t):
            return nombre
    return por_defecto


def _intencion(texto: str) -> str:
    t = (texto or "").lower()
    if re.search(r"\bcontrato\b|\bcontract\b|\bslither\b|\bauditar\b|\bauditor", t):
        return "contrato"
    if re.search(r"\brastr\w*|\bruta\w*\b|\bseguir (?:los )?fondos\b|\bde d[oó]nde\b"
                 r"|\b[aá] d[oó]nde (?:fue|vino|va)\b|\bflujo\b|\borigen de los fondos\b", t):
        return "rastreo"
    if re.search(r"\bestado\b|\bstatus\b|\bfunciona\w*\b|\bcentinela\b|\bproveedor\w*\b"
                 r"|\bqu[eé] ia\b|\bmodelo\b|\bsistema\b|\bcomo va\b|\bva bien\b|\bfuncionando\b", t):
        return "estado"
    if re.search(r"\bwatchlist\b|\bvigil\w*|\bcontrolad\w*|\bmonitoriz\w*", t):
        return "watchlist"
    if re.search(r"\bfeed\b|\b[úu]ltim\w* (?:transacciones|bloques)\b|\bactividad\b"
                 r"|\balertas?\b|\bqu[eé] (?:pasa|viendo|sucede)\b|\bnovedades\b", t):
        return "feed"
    if _direccion(texto):
        return "wallet"
    return "libre"


# ------------------------------------------------------------------ herramientas
def _herramienta_wallet(args: dict) -> dict:
    from .fetcher import fetch_wallet_data
    from .investigation import narrarize_trace, trace_from_txs
    from .risk_scoring import score_wallet
    from .wallet_intelligence import build_profile

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    fetched = fetch_wallet_data(addr, chain=chain)
    profile, txs = build_profile(addr, fetched)
    score, factors = score_wallet(profile, txs)
    trace = trace_from_txs(addr, txs, max_depth=2, direction="out")
    narr = narrarize_trace(trace)
    return {
        "direccion": addr, "cadena": chain,
        "score": score, "nivel": ("n/d" if score is None else
                                 "bajo" if score < 30 else "medio" if score < 70 else "alto"),
        "factores": list(factors)[:6],
        "transacciones": profile.get("tx_count"),
        "confianza_muestra": profile.get("sample_confidence"),
        "antiguedad_dias": profile.get("age_days"),
        "balance_usd": profile.get("balance_usd"),
        "contrapartes": profile.get("counterparties"),
        "etiquetas": profile.get("labels"),
        "calidad_datos": (fetched.get("data_quality") or {}).get("degraded", False),
        "narrativa_trazado": narr["narrative"],
        "explicacion": agents.run(
            "explicacion",
            f"Wallet {addr} ({chain}). Perfil: {json.dumps(profile, ensure_ascii=False, default=str)[:1200]}. "
            f"Score {score}/100. Factores: {'; '.join(factors) or 'ninguno'}. "
            f"Confianza de muestra: {profile.get('sample_confidence', 'n/d')}. "
            "Explica el patrón y qué conviene verificar.",
            "Sin datos suficientes para evaluar esta wallet.", score=score,
        )["text"],
    }


def _herramienta_contrato(args: dict) -> dict:
    from .contract_analyzer import analyze_contract, fetch_contract

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    fetched = fetch_contract(addr, chain=chain)
    r = analyze_contract(addr, fetched)
    return {
        "direccion": addr, "cadena": chain, "es_contrato": r.get("is_contract"),
        "score": r.get("risk_score"), "es_proxy": r.get("is_proxy"),
        "verificado": r.get("verified"),
        "hallazgos": [f.get("id") for f in (r.get("risks") or [])][:8],
        "explicacion": r.get("explanation"),
    }


def _herramienta_rastreo(args: dict) -> dict:
    from .fetcher import fetch_wallet_data
    from .investigation import narrarize_trace, trace_from_txs
    from .wallet_intelligence import build_profile

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    fetched = fetch_wallet_data(addr, chain=chain)
    _, txs = build_profile(addr, fetched)
    profundidad = max(1, min(int(args.get("max_depth") or 2), 4))
    trace = trace_from_txs(addr, txs, max_depth=profundidad,
                           direction=args.get("direction") or "out")
    narr = narrarize_trace(trace)
    return {
        "direccion": addr, "cadena": chain, "rutas": trace.get("n_paths"),
        "nodos": trace.get("n_nodes"), "usd_trazado": trace.get("total_traced_usd"),
        "en_watchlist": trace.get("watchlist_nodes"),
        "narrativa": narr["narrative"],
    }


def _herramienta_feed(args: dict) -> dict:
    from .watcher import scan

    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    feed = scan(chain, max_blocks=1)
    alertas = [{
        "valor_eth": t.get("value_eth"), "score": t.get("score"),
        "senales": t.get("flags"), "bloque": t.get("block"),
    } for t in (feed.get("alerts") or [])[:3]]
    return {
        "cadena": chain, "bloque": feed.get("latest"),
        "transacciones": feed.get("n_txs"), "alertas": feed.get("n_alerts"),
        "mediana_eth": feed.get("median_eth"), "ejemplos": alertas,
    }


def _herramienta_estado(args: dict) -> dict:
    from . import llm, sentinel
    from .fetcher import cache_stats

    st = llm.status()
    s = sentinel.status()
    return {
        "ia": {"proveedor": st.get("provider"), "modelo": st.get("model"),
               "local": st.get("local"), "rechazados": st["estadisticas"].get("rejected")},
        "centinela": {"activo": s.get("enabled"), "ciclos": s.get("cycles"),
                      "alertas": s.get("alerts_delivered"), "error": s.get("last_error")},
        "cadenas": chains.supported(),
        "agentes": [a["nombre"] for a in agents.describe()],
        "cache_datos": cache_stats(),
    }


def _herramienta_watchlist(args: dict) -> dict:
    info = watchlist.info()
    return {"total": info["size"], "direcciones": [
        {"direccion": e.get("address"), "etiqueta": e.get("label"),
         "verificado": e.get("verificado")} for e in watchlist.entries()[:20]]}


HERRAMIENTAS = {
    "wallet": _herramienta_wallet,
    "contrato": _herramienta_contrato,
    "rastreo": _herramienta_rastreo,
    "feed": _herramienta_feed,
    "estado": _herramienta_estado,
    "watchlist": _herramienta_watchlist,
}


# ------------------------------------------------------------------- ejecución
class ErrorChat(Exception):
    pass


def ejecutar(texto: str, historial: list[dict] | None = None) -> dict:
    """Decide la herramienta, la ejecuta y devuelve datos + contexto para el LLM.

    Devuelve `{"respuesta": str, "datos": dict, "herramienta": str|None}` donde
    `respuesta` ya es utilizable aunque el modelo falle.
    """
    addr = _direccion(texto)
    intencion = _intencion(texto)
    chain = _cadena(texto)
    hist = (historial or [])[-MAX_HISTORIAL:]

    elegido: str | None = None
    args: dict = {"address": addr, "chain": chain}

    if intencion == "contrato" and addr:
        elegido = "contrato"
    elif intencion == "rastreo" and addr:
        elegido = "rastreo"
        m = re.search(r"(\d)\s*saltos?", texto, re.I)
        args["max_depth"] = int(m.group(1)) if m else 2
        if re.search(r"\bentrantes?\b|\bde d[oó]nde\b", texto, re.I):
            args["direction"] = "in"
    elif intencion in ("estado", "watchlist", "feed"):
        elegido = intencion
        if intencion == "feed" and addr:
            elegido = "wallet"
    elif intencion == "wallet" and addr:
        elegido = "wallet"

    if not addr and intencion == "wallet":
        return {
            "herramienta": None, "datos": {},
            "respuesta": "Necesito una dirección para mirarla. Pásame una del tipo 0x seguida "
                         "de 40 caracteres.",
        }

    datos: dict = {}
    if elegido:
        try:
            datos = HERRAMIENTAS[elegido](args)
        except Exception as e:  # una herramienta caída no tumba el chat
            datos = {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    resumen = _determinista(elegido, datos, addr, chain, intencion)
    if not elegido:
        return {"herramienta": None, "datos": {}, "respuesta": resumen,
                "contexto": _contexto_libre(hist)}
    return {"herramienta": elegido, "datos": datos, "respuesta": resumen,
            "contexto": json.dumps(datos, ensure_ascii=False, default=str)[:2200]}


def _contexto_libre(hist: list[dict]) -> str:
    partes = []
    for h in hist:
        if h.get("role") == "user":
            partes.append(f"Usuario preguntó: {str(h.get('content'))[:300]}")
        elif h.get("role") == "assistant":
            partes.append(f"Respuesta previa: {str(h.get('content'))[:300]}")
    return "\n".join(partes[-4:])


def _determinista(herramienta: str | None, datos: dict, addr: str | None,
                  chain: str, intencion: str) -> str:
    """Respuesta sin IA. Es la que se devuelve si el modelo no está o falla."""
    if herramienta is None:
        return (
            "Puedo mirar wallets, contratos, rutas de fondos, el feed en vivo, el estado del "
            "sistema y la watchlist. Dime una dirección 0x… y qué quieres saber de ella."
        )
    if datos.get("error"):
        return f"No pude completar la consulta: {datos['error']}"

    if herramienta == "wallet":
        if datos.get("score") is None:
            return (f"No hay datos suficientes para evaluar {addr} en {chain}. "
                    "Sin datos no doy un score: reintenta en unos segundos.")
        return (
            f"{addr} ({chain}): riesgo {datos['nivel']} ({datos['score']}/100). "
            f"{datos.get('transacciones')} transacciones, confianza de muestra "
            f"{datos.get('confianza_muestra')}"
            + (f", {datos.get('contrapartes')} contrapartes" if datos.get("contrapartes") else "")
            + ". " + (datos.get("explicacion") or "")
        )
    if herramienta == "contrato":
        if not datos.get("es_contrato"):
            return f"{addr} no tiene bytecode: es una EOA, no un contrato."
        return (f"{addr}: riesgo {datos.get('score')}/100"
                + (f", proxy ({datos['es_proxy']})" if datos.get("es_proxy") else "")
                + ". " + (datos.get("explicacion") or ""))
    if herramienta == "rastreo":
        return (f"Trazado de {addr}: {datos.get('rutas')} rutas, {datos.get('nodos')} nodos, "
                f"{datos.get('usd_trazado')} USD. " + (datos.get("narrativa") or ""))
    if herramienta == "feed":
        return (f"{chain}: bloque {datos.get('bloque')}, {datos.get('transacciones')} transacciones, "
                f"{datos.get('alertas')} alertas en el último bloque. "
                f"Mediana {datos.get('mediana_eth')} ETH.")
    if herramienta == "watchlist":
        if not datos.get("total"):
            return "La watchlist está vacía: no hay direcciones vigiladas ahora mismo."
        return (f"{datos['total']} direcciones vigiladas: "
                + ", ".join(f"{d['direccion'][:12]}… ({d['etiqueta']})" for d in datos.get("direcciones", [])[:5]))
    if herramienta == "estado":
        ia = datos.get("ia", {})
        cen = datos.get("centinela", {})
        return (f"IA: {ia.get('proveedor')} ({ia.get('modelo')}"
                + (", local" if ia.get("local") else "") + f"), {len(datos.get('agentes') or [])} agentes. "
                f"Centinela {'activo' if cen.get('activo') else 'apagado'} con {cen.get('ciclos')} ciclos. "
                f"Redes: {', '.join(datos.get('cadenas') or [])}.")
    return "No tengo datos para eso."


def responder(texto: str, historial: list[dict] | None = None) -> dict:
    """Chat completo: ejecuta la herramienta y redacta con el agente `chat`."""
    paso = ejecutar(texto, historial)
    agente = agents.get("chat")
    # el score es la cifra que este nodo más falsea: se le pasa para verificar
    score = (paso.get("datos") or {}).get("score")
    if paso.get("herramienta"):
        user = (
            f"Pregunta del usuario: {texto}\n\n"
            f"Datos reales que acabo de obtener con la herramienta "
            f"'{paso['herramienta']}':\n{paso.get('contexto')}\n\n"
            f"Redacta la respuesta en español. Usa solo esos datos, sé breve (máximo 6 líneas) "
            f"y no prometas nada que no esté en ellos."
        )
    else:
        user = (
            f"Pregunta del usuario: {texto}\n\n"
            f"Contexto de la conversación:\n{paso.get('contexto', '(sin historial)')}\n\n"
            "Responde en español y sé breve. Si el usuario pregunta por datos de una wallet o "
            "contrato y no ha dado una dirección, pídela."
        )
    res = agents.run("chat", user, paso["respuesta"], score=score if isinstance(score, int) else None)
    return {
        "respuesta": res["text"],
        "determinista": paso["respuesta"],
        "herramienta": paso.get("herramienta"),
        "datos": paso.get("datos", {}),
        "agente": res.get("agente"),
        "source": res.get("source"),
        "motivo": res.get("motivo"),
        "modelo": res.get("modelo"),
        "latency_s": res.get("latency_s"),
    }


def herramientas_publicas() -> list[dict]:
    """Para documentar la API: qué puede hacer el chat."""
    return [
        {"nombre": "analizar_wallet", "args": ["address", "chain"],
         "descripcion": "Perfil, score y señales de una wallet"},
        {"nombre": "analizar_contrato", "args": ["address", "chain"],
         "descripcion": "Permisos y hallazgos de un contrato"},
        {"nombre": "investigar", "args": ["address", "max_depth", "direction"],
         "descripcion": "Trazado de fondos"},
        {"nombre": "feed", "args": ["chain"], "descripcion": "Actividad y alertas recientes"},
        {"nombre": "estado", "args": [], "descripcion": "IA, centinela, guard y agentes"},
        {"nombre": "watchlist", "args": [], "descripcion": "Direcciones vigiladas"},
    ]
