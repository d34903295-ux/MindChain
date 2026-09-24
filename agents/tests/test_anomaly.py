from agents.anomaly import scan_wallets, features_from_profile

def _normal(i):
    return {"address": "0x" + format(i, "040x"),
            "profile": {"tx_count": 100 + i * 3, "freq_tx_day": 1.0 + i * 0.05,
                        "in_usd_sample": 500.0 + i * 10, "out_usd_sample": 480.0,
                        "counterparties_sample": 25 + i, "balance_usd": 4000.0,
                        "bot_like": False, "age_days": 300 + i}}

def test_outlier_detectado():
    items = [_normal(i) for i in range(10)]
    items.append({"address": "0x" + "f" * 40,
                  "profile": {"tx_count": 60000, "freq_tx_day": 1200.0,
                              "in_usd_sample": 80000000.0, "out_usd_sample": 10.0,
                              "counterparties_sample": 2, "balance_usd": 20000000.0,
                              "bot_like": True, "age_days": 1}})
    flags = scan_wallets(items)
    by = {f["address"]: f for f in flags}
    assert by["0x" + "f" * 40]["is_anomaly"] is True
    assert by["0x" + "f" * 40]["top_feature"] is not None

def test_determinista():
    items = [_normal(i) for i in range(8)]
    assert scan_wallets(items) == scan_wallets(items)

def test_muestra_pequena():
    flags = scan_wallets([_normal(0), _normal(1)])
    assert all(f["is_anomaly"] is False for f in flags)
    assert flags[0]["reason"] == "muestra_insuficiente"

def test_features_robusto_a_none():
    v = features_from_profile({"tx_count": None, "age_days": None})
    assert len(v) == 8 and all(isinstance(x, float) for x in v)
