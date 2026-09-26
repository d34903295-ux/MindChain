"""Risk Scoring Agent: SOLO heurísticas, sin ML.

Reglas calibradas 0-100. Cada factor requiere evidencia suficiente:
si la muestra es pequeña el factor NO se dispara (evita falsos positivos).
"""
from collections import defaultdict

from . import watchlist

# Contratos sistemicos que APORTAN fondos y no son fuentes sospechosas por si solas.
INFRA_LABELS = {
    "0x0000000000000000000000000000000000000000": "null",
    "0x000000000000000000000000000000000000dead": "burn",
}


def _lower(v) -> str:
    return str(v or "").strip().lower()


def score_wallet(profile: dict, txs: list[dict]) -> tuple[int | None, list[str]]:
    """Devuelve (score 0-100 o None si no hay datos, factores).

    None significa "no se puede evaluar": preferimos no puntuar a puntuar sobre
    datos inventados. Un sistema de riesgo que devuelve 0 cuando falló la red
    es peor que uno que devuelve "no sé".
    """
    factors: list[str] = []
    score = 0
    addr = _lower(profile.get("address"))
    txs = [t for t in (txs or []) if isinstance(t, dict)]

    # --- abstención: no hay datos suficientes para juzgar
    if profile.get("insufficient_data"):
        return None, ["datos_insuficientes_no_evaluable"]

    # BUG B: una muestra de 0 a 7 transacciones no sostiene un score. Antes se
    # puntuaba igual y solo se añadía un factor informativo
    # ("datos_insuficientes_score_provisional"), así que el endpoint devolvía
    # una cifra con aspecto de válido sobre una base de evidencia que no la
    # respaldaba. Con bloque en 0 se llegaba a "risk_score: 0" para una wallet
    # de la que no se había visto ni una transacción.
    # Se abstiene ANTES de acumular: con la muestra vacía, las reglas de
    # balance y antigüedad no sumaban nada (bal = 0), y con muestra baja
    # sumaban sobre datos que no dan soporte a la conclusión.
    # La ausencia del campo no es "muestra nula": es un perfil que no lo trae,
    # y esas llamadas internas siguen puntuando.
    if str(profile.get("sample_confidence") or "").strip().lower() in ("nula", "baja"):
        return None, ["datos_insuficientes_no_evaluable"]
    try:
        tx_count = profile.get("tx_count")
        tx_count = int(tx_count) if tx_count is not None else None
    except Exception:
        tx_count = None
    # Si el adaptador no da un histórico fiable, las reglas que dependen de él
    # NO se aplican: es preferible no puntuar antes que puntuar sobre un dato falso.
    tx_known = tx_count is not None and profile.get("tx_count_reliable", True)
    age = profile.get("age_days")
    age = age if isinstance(age, int) else None

    # ---------------------------------------------------------------- 1) watchlist
    hit = None
    for t in txs:
        for side in ("from", "to"):
            label = watchlist.get(_lower(t.get(side)))
            if label:
                hit = label
                break
        if hit:
            break
    if hit:
        score += 50
        factors.append(f"interaccion_watchlist:{hit}")

    # ------------------------------------------- 2) concentración de fondos
    # Exige: muestra suficiente, varias fuentes, valor material y wallet establecida.
    # Sin el mínimo de valor, una muestra de céntimos dispara la regla.
    incoming = [t for t in txs if _lower(t.get("to")) == addr and _lower(t.get("from")) != addr]
    by_source: dict[str, float] = defaultdict(float)
    for t in incoming:
        by_source[_lower(t.get("from"))] += float(t.get("value_usd") or t.get("value_eth") or 0)
    total_in = sum(by_source.values())
    is_contract = "contract" in (profile.get("labels") or [])
    if (
        len(incoming) >= 10
        and len(by_source) >= 4
        and total_in >= 1_000
        and (not tx_known or tx_count >= 50)
        and not is_contract
    ):
        top_src, top_val = max(by_source.items(), key=lambda kv: kv[1])
        if top_val / total_in >= 0.9 and top_src not in INFRA_LABELS:
            score += 20
            factors.append("concentracion_fondos_una_fuente")

    # --------------------------------------------------- 3) wallet nueva
    if tx_known and tx_count <= 2:
        score += 30
        factors.append("wallet_nueva_pocas_txs")
    elif tx_known and age is not None and age < 30 and tx_count < 10:
        score += 20
        factors.append("wallet_reciente_poca_actividad")

    # ------------------------------------------------ 4) patrón bot + alta frec.
    try:
        freq = profile.get("freq_tx_day")
        freq = float(freq) if freq is not None else 0.0
    except Exception:
        freq = 0.0
    if profile.get("bot_like") and freq > 20:
        score += 15
        factors.append("patron_bot_alta_frecuencia")

    # ------------------------------------------- 5) dormida que vuelve a moverse
    labels = profile.get("labels") or []
    if "dormant" in labels and (profile.get("in_count_sample") or 0) > 0:
        score += 10
        factors.append("dormante_reactivada")

    # ------------------------------------- 6) balance alto y wallet poco Consolidada
    try:
        bal = float(profile.get("balance_usd") or 0)
    except Exception:
        bal = 0.0
    if bal > 1_000_000 and (age is None or age < 90):
        score += 10
        factors.append("balance_alto_wallet_reciente")

    # ------------------------------------ 7) convoy: muchas tx del mismo origen
    burst = defaultdict(int)
    for t in txs:
        src = _lower(t.get("from"))
        if src and src != addr:
            burst[src] += 1
    # 8+ en la muestra y wallet madura: por debajo es ruido de exchange/bridge
    if burst and max(burst.values()) >= 8 and len(txs) >= 12 and (not tx_known or tx_count >= 200):
        score += 10
        factors.append("patron_convoy_mismo_origen")

    return min(score, 100), factors
