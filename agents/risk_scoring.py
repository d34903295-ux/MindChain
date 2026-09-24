"""Fase 1 — Risk Scoring Agent: SOLO heurísticas, sin ML.
Reglas Fase 1: mezclador conocido, wallet nueva, concentración de fondos."""
MIXERS = {"0x4718614cf556ec12b4a07c00eed8d568f719c808".lower()}  # Tornado Cash Router ejemplo

def score_wallet(profile: dict, txs: list[dict]) -> tuple[int, list[str]]:
    factors: list[str] = []
    score = 0
    if profile.get("tx_count", 0) <= 2:
        score += 30; factors.append("wallet_nueva_pocas_txs")
    for t in txs:
        if str(t.get("to", "")).lower() in MIXERS or str(t.get("from", "")).lower() in MIXERS:
            score += 50; factors.append("interaccion_mezclador_conocido"); break
    sources: dict[str, int] = {}
    for t in txs:
        if t.get("to") == profile.get("address"):
            sources[t.get("from", "")] = sources.get(t.get("from", ""), 0) + 1
    if txs and max(sources.values(), default=0) == len([t for t in txs if t.get("to") == profile.get("address")]) and len(txs) > 2:
        score += 20; factors.append("concentracion_unica_fuente")
    return min(score, 100), factors
