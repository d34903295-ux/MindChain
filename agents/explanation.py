"""Fase 1 — Explanation Agent: ÚNICA pieza que llama al LLM (Claude).
Fase 0: plantilla determinista sin llamada para tests/offline."""
def explain(profile: dict, score: int, factors: list[str]) -> str:
    if not factors:
        return f"Wallet {profile.get('address')} con {profile.get('tx_count',0)} txs analizadas. Riesgo bajo ({score}/100)."
    return f"Wallet {profile.get('address')}: riesgo {score}/100 por {', '.join(factors)}. (Fase 1 conectará Claude aquí.)"
