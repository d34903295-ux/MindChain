"""Risk Scoring Agent (Fase 1): SOLO heurísticas, sin ML.
+20/+30/+50 calibrado para score 0-100. Sin vectores, sin LLM.
"""
# Mixers / privacy pools conocidos (subset extensible). Incluye el stub de Fase 0 por compat.
MIXERS = {
    "0x4718614cf556ec12b4a07c00eed8d568f719c808",  # stub fase 0 (test)
    "0x722122df12d4e5e958a7e108a0fff2110890c9c83",  # Tornado 0.1 ETH
    "0x4736dcf1b7a3df49bef067744264761ded835f56",  # Tornado 1 ETH
    "0x47ce0c6ed5b0ce8d957605cec3362481446440eaf",  # Tornado 10 ETH
    "0x910cbd523d9720387c958ff6ce4e3ac6ac3e6f11df",  # Tornado DAI
    "0xd4e88c213ae5191228fe776fbd3d0cf0f38c4c1a",  # ejemplo pool adicional
}

def score_wallet(profile: dict, txs: list[dict]) -> tuple[int, list[str]]:
    factors: list[str] = []
    score = 0
    addr = str(profile.get("address", "")).lower()
    tx_count = int(profile.get("tx_count") or 0)
    age = profile.get("age_days")
    # 1) wallet nueva
    if tx_count <= 2 or (isinstance(age, int) and age < 30 and tx_count < 10):
        score += 30; factors.append("wallet_nueva_pocas_txs")
    # 2) mezclador
    for t in txs or []:
        if str(t.get("from", "")).lower() in MIXERS or str(t.get("to", "") or "").lower() in MIXERS:
            score += 50; factors.append("interaccion_mezclador_conocido"); break
    # 3) concentración única fuente (muestra entrante)
    incoming_from: dict[str, int] = {}
    for t in txs or []:
        if str(t.get("to", "")).lower() == addr:
            incoming_from[str(t.get("from", ""))] = incoming_from.get(str(t.get("from", "")), 0) + 1
    total_in = sum(incoming_from.values())
    if total_in >= 3 and max(incoming_from.values(), default=0) / max(total_in, 1) >= 0.8:
        score += 20; factors.append("concentracion_unica_fuente")
    # 4) bot_like alta frecuencia
    if profile.get("bot_like") and float(profile.get("freq_tx_day") or 0) > 20:
        score += 15; factors.append("patron_bot_alta_frecuencia")
    # 5) dormante reactivada
    if "dormant" in (profile.get("labels") or []) and (profile.get("in_count_sample") or 0) > 0:
        score += 10; factors.append("dormante_reactivada")
    # 6) whale nueva (riesgo custodia/leveraging, no acusación)
    try: bal = float(profile.get("balance_usd") or 0)
    except Exception: bal = 0
    if bal > 1_000_000 and (age is None or (isinstance(age, int) and age < 90)):
        score += 10; factors.append("balance_alto_wallet_joven")
    return min(score, 100), factors
