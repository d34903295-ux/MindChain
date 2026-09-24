from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _item(i, **kw):
    p = {"tx_count": 100 + i, "freq_tx_day": 1.0, "in_usd_sample": 500.0,
         "out_usd_sample": 480.0, "counterparties_sample": 20,
         "balance_usd": 3000.0, "bot_like": False, "age_days": 200}
    p.update(kw)
    return {"address": "0x" + format(i + 1, "040x"), "profile": p}

def test_anomaly_scan_ep():
    items = [_item(i) for i in range(7)]
    r = client.post("/anomaly-scan", json={"items": items})
    assert r.status_code == 200
    j = r.json()
    assert j["model"] == "isolation-forest" and j["n"] == 7 and "anomalies" in j
