from agents.wallet_intelligence import profile_wallet

def test_perfil_basico():
    txs = [{"from": "0xaaa", "to": "0xwallet", "value_usd": 10, "time": "2026-09-20 10:00:00"},
           {"from": "0xwallet", "to": "0xbbb", "value_usd": 5, "time": "2026-09-21 11:00:00"}]
    raw = {"transaction_count": 2, "first_seen_receiving": "2026-09-01 00:00:00",
           "balance": "1000000000000000000", "balance_usd": 2500.0, "type": "account"}
    p = profile_wallet("0xwallet", txs, raw)
    assert p["tx_count"] == 2 and p["counterparties_sample"] == 2
    assert p["age_days"] is not None and "eoa" in p["labels"]
