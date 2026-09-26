"""Explanation Agent: ÚNICA pieza que llama al LLM (Claude).

Sin API key -> plantilla determinista (tests/offline). Con key -> Anthropic.
Tono: neutro, sin acusar delitos. Una señal heurística no es un veredicto.
"""
import json
import os
import urllib.request

from .md import safe_label

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

FACTOR_TEXT = {
    "wallet_nueva_pocas_txs": "poco historial: tratarla con cautela hasta que acumule actividad",
    "wallet_reciente_poca_actividad": "wallet creada hace poco con pocas operaciones",
    "concentracion_fondos_una_fuente": "casi todo el valor recibido viene de una sola contraparte: "
                                      "puede ser un proveedor único o fondeo directo",
    "patron_convoy_mismo_origen": "varias operaciones consecutivas desde la misma contraparte: "
                                  "patrón típico de bridge, exchange o automatización",
    "patron_bot_alta_frecuencia": "actividad horaria uniforme y muy frecuente: comportamiento automatizado",
    "dormante_reactivada": "wallet dormida que vuelve a moverse: revisar el motivo",
    "balance_alto_wallet_reciente": "balance alto en una wallet reciente: conviene verificar el origen",
    "datos_insuficientes_score_provisional": "los datos disponibles son pocos: el score es provisional",
    "datos_insuficientes_no_evaluable": "no hay datos suficientes: la wallet no se evalúa",
}

DISCLAIMERS = (
    "Es una heurística automatizada, no un veredicto: confirma siempre on-chain antes de actuar."
)


FLAG_TEXT = {
    "creacion_contrato": "crea un contrato nuevo",
    "gas_alto": "gas por encima de lo normal",
    "gas_muy_alto": "gas muy alto",
    "payload_grande": "payload grande (posible operación compleja)",
    "ballena_100eth+": "movimiento de 100+ ETH",
    "ballena_1000eth+": "movimiento de 1.000+ ETH",
}


def flag_text(flag: str) -> str:
    """Traduce una señal del watcher a lenguaje claro (para vault y UI)."""
    if flag in FLAG_TEXT:
        return FLAG_TEXT[flag]
    if flag.startswith("outlier_") and "mediana" in flag:
        try:
            ratio = flag.split("_")[1].rstrip("x")
            return f"valor {ratio}× la mediana de la red"
        except Exception:
            return "valor muy por encima de la mediana"
    if flag.startswith("outlier_estadistico_z"):
        return "outlier estadístico respecto a la red"
    if flag.startswith("watchlist:"):
        return f"interacción con dirección listada ({safe_label(flag.split(':', 1)[1])})"
    return flag.replace("_", " ")


def _factor_text(factor: str) -> str:
    if factor in FACTOR_TEXT:
        return FACTOR_TEXT[factor]
    if factor.startswith("interaccion_watchlist:"):
        # la etiqueta puede venir de una watchlist remota: se sanea aquí
        label = safe_label(factor.split(":", 1)[1].replace("-", " "))
        return f"interacción con una dirección listada ({label}): es una señal de screening, no una prueba"
    return factor.replace("_", " ")


def _fmt_money(v) -> str:
    try:
        return f"${float(v):,.2f}"
    except Exception:
        return "n/d"


def _fallback(profile: dict, score: int | None, factors: list[str]) -> str:
    a = profile.get("address")
    n = profile.get("tx_count", 0)
    age = profile.get("age_days")
    chain = profile.get("chain", "ethereum")
    chain_label = {"ethereum": "Ethereum", "base": "Base"}.get(str(chain).lower(), str(chain))

    # Sin score no hay veredicto: se dice explícitamente. Y se distingue POR
    # QUÉ no lo hay, porque no es lo mismo y decir «no se pudieron obtener
    # datos» cuando sí los hay es mentira: una wallet con 1 transacción
    # provides datos, lo que no tiene es muestra para puntuar.
    if score is None:
        errores = profile.get("data_errors") or []
        if profile.get("insufficient_data"):
            detalle = (" No se pudieron obtener datos de la cadena"
                       + (f" ({errores[0]})" if errores else "")
                       + ", por lo que esta wallet no se evalúa. Reintenta en unos segundos.")
            return f"Wallet {a} ({chain_label}): sin datos suficientes para analizarla." + detalle
        conf = str(profile.get("sample_confidence") or "").lower()
        if conf in ("nula", "baja"):
            n_muestra = profile.get("sample_size")
            if isinstance(n_muestra, int):
                muestra_txt = "1 transacción" if n_muestra == 1 else f"{n_muestra} transacciones"
            else:
                muestra_txt = "sin transacciones en el histórico consultado"
            return (f"Wallet {a} ({chain_label}): hay datos, pero la muestra es demasiado pequeña "
                    f"para puntuar con criterio ({muestra_txt} en la muestra, confianza "
                    f"'{conf}'). No se le pone score a propósito: un número aquí sería "
                    f"apariencia de análisis, no análisis. Con más actividad se podrá evaluar.")
        return (f"Wallet {a} ({chain_label}): la evaluación no está disponible. "
                f"Sin datos suficientes y sin motivo concreto registrado.")

    lvl = "bajo" if score < 30 else ("medio" if score < 70 else "alto")
    age_txt = f"{age} días" if isinstance(age, int) else "sin fecha de primera actividad conocida"
    tx_txt = f"{n} transacciones históricas" if n is not None else "histórico de transacciones no disponible"
    base = (
        f"Wallet {a} ({chain_label}): {tx_txt}, antigüedad {age_txt}, "
        f"actividad {profile.get('activity')}, balance {_fmt_money(profile.get('balance_usd'))}. "
        f"Riesgo {lvl} ({score}/100)."
    )
    conf = profile.get("sample_confidence")
    if conf and conf in ("baja", "nula"):
        base += f" Muestra analizada: {conf} — con pocos datos el score es poco fiable."
    if not factors:
        return base + " Sin señales de riesgo en las heurísticas actuales. " + DISCLAIMERS
    return base + " Factores: " + "; ".join(_factor_text(f) for f in factors) + ". " + DISCLAIMERS


SYSTEM_PROMPT = (
    "Eres un analista on-chain. Explicas señales de riesgo de forma neutra y factual.\n"
    "REGLAS INNEGOCIABLES:\n"
    "- No afirmes ni insinúes responsabilidad penal ni intención deliberada.\n"
    "- No uses palabras como delito, fraude, culpable ni money laundering, ni\n"
    "  siquiera como hipótesis o advertencia.\n"
    "- No inventes datos que no estén en el perfil. Si no está, no lo menciones.\n"
    "- Una heurística es una señal para investigar, nunca un veredicto.\n"
    "- Si los datos son insuficientes, dilo: no rellenes.\n"
    "Responde en español claro, 4-6 líneas, terminando con la idea de que hay que "
    "confirmar on-chain antes de actuar."
)

def _safe_profile(profile: dict) -> str:
    """Perfil para el prompt: sin volcar campos de control ni datos ajenos."""
    permitidos = (
        "address", "chain", "tx_count", "tx_count_reliable", "age_days", "first_seen",
        "last_seen", "sample_size", "sample_confidence", "activity", "type", "labels",
        "balance_eth", "balance_usd", "eth_price_usd", "counterparties", "in_count",
        "out_count", "in_eth", "out_eth", "fees_eth", "is_bot", "is_contract",
        "insufficient_data", "data_quality", "data_errors",
    )
    limpio = {k: profile[k] for k in permitidos if k in profile}
    return json.dumps(limpio, ensure_ascii=False, default=str)[:1800]


def _wallet_prompt(profile: dict, score: int | None, factors: list[str]) -> str:
    readable = "; ".join(_factor_text(f) for f in factors) or "sin factores"
    return (
        f"Wallet {profile.get('address')} ({profile.get('chain', 'ethereum')}).\n"
        f"Perfil: {_safe_profile(profile)}\n"
        f"Score heurístico: {score}/100.\n"
        f"Factores: {readable}.\n"
        f"Confianza de la muestra: {profile.get('sample_confidence', 'n/d')}.\n"
        "Explica qué significa este patrón, qué conviene verificar on-chain y qué "
        "limitaciones tiene el score. No adelantes conclusiones que no salen de los datos."
    )


def explain(profile: dict, score: int | None, factors: list[str]) -> str:
    """Explicación del score. Delega en el agente especializado `explicacion`.

    Sin proveedor, con score `None` o si la salida no supera el filtro, devuelve
    siempre el texto determinista: el usuario nunca ve una alucinación.
    """
    from . import agents
    if score is None:
        return _fallback(profile, score, factors)
    res = agents.run("explicacion", _wallet_prompt(profile, score, factors),
                     _fallback(profile, score, factors), score=score)
    return res["text"]


def explain_detailed(profile: dict, score: int | None, factors: list[str]) -> dict:
    """Como `explain()` pero devuelve la trazabilidad: qué agente y qué IA."""
    from . import agents
    if score is None:
        return {"explanation": _fallback(profile, score, factors),
                "ai": {"source": "determinista", "motivo": "sin score no hay nada que explicar"}}
    res = agents.run("explicacion", _wallet_prompt(profile, score, factors),
                     _fallback(profile, score, factors), score=score)
    return {"explanation": res["text"], "ai": {k: v for k, v in res.items() if k != "text"}}
