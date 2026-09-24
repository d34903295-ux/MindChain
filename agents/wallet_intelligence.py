"""Fase 1 — Wallet Intelligence Agent (perfil básico).
Inspiración: Gator (conductual), bitguard (Neo4j -> features).
Fase 0: solo firma + stub para no bloquear el grafo LangGraph."""
def profile_wallet(address: str, txs: list[dict]) -> dict:
    if not txs:
        return {"address": address, "tx_count": 0, "age_days": None, "counterparties": 0, "activity": "unknown"}
    counterparties = set()
    for t in txs:
        counterparties.add(t.get("from")); counterparties.add(t.get("to"))
    counterparties.discard(address); counterparties.discard(None)
    return {"address": address, "tx_count": len(txs), "age_days": 0, "counterparties": len(counterparties), "activity": "stub"}
