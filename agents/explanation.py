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

    # Sin datos no hay veredicto: se dice explícitamente.
    if score is None:
        errores = profile.get("data_errors") or []
        detalle = (" No se pudieron obtener datos de la cadena"
                   + (f" ({errores[0]})" if errores else "")
                   + ", por lo que esta wallet no se evalúa. Reintenta en unos segundos.")
        if profile.get("insufficient_data"):
            return f"Wallet {a} ({chain_label}): sin datos suficientes para analizarla." + detalle
        return f"Wallet {a} ({chain_label}): la evaluación no está disponible." + detalle

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


def explain(profile: dict, score: int | None, factors: list[str]) -> str:
    key = os.getenv("ANTHROPIC_API_KEY", "")
    if not key or score is None:
        return _fallback(profile, score, factors)
    try:
        readable = "; ".join(_factor_text(f) for f in factors) or "sin factores"
        payload = {
            "model": MODEL,
            "max_tokens": 320,
            "system": (
                "Eres analista on-chain. Explicas riesgo de forma neutra y factual, "
                "sin acusar delitos ni afirmar intenciones. Responde en español claro. "
                "Una heurística es una señal para investigar, nunca un veredicto."
            ),
            "messages": [{
                "role": "user",
                "content": (
                    f"Wallet {profile.get('address')} ({profile.get('chain', 'ethereum')}). "
                    f"Perfil: {json.dumps(profile, ensure_ascii=False)[:1400]}. "
                    f"Score {score}/100. Factores: {readable}. "
                    f"Confianza de la muestra: {profile.get('sample_confidence', 'n/d')}. "
                    "Explica en 4-6 líneas qué significa y qué conviene verificar."
                ),
            }],
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            d = json.load(r)
        parts = d.get("content", [])
        txt = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        return txt or _fallback(profile, score, factors)
    except Exception:
        return _fallback(profile, score, factors)
