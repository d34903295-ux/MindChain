import os
from agents.explanation import explain
def test_fallback_sin_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = explain({"address": "0xabc", "tx_count": 1, "age_days": 2, "activity": "baja", "balance_usd": 0}, 30, ["wallet_nueva_pocas_txs"])
    assert "0xabc" in t and "30/100" in t
