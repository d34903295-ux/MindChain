from fastapi.testclient import TestClient
from app.main import app
import app.routers.report as mod

client = TestClient(app)

def fake_fetch(address, chain="ethereum", limit=25):
    return {"raw_address": {"transaction_count": 2, "first_seen_receiving": "2026-01-01 00:00:00",
            "balance": "1000", "balance_usd": 1.0, "type": "account"},
            "calls": [{"transaction_hash": "0x" + "ab" * 32, "sender": address.lower(),
                       "recipient": "0x" + "b" * 40, "value": 100, "value_usd": 1.0,
                       "time": "2026-09-20 10:00:00", "block_id": 1}], "source": "mock", "chain": chain}

def test_investigate_mock(monkeypatch):
    monkeypatch.setattr(mod, "fetch_wallet_data", fake_fetch)
    r = client.post("/investigate", json={"address": "0x" + "a" * 40, "max_depth": 2})
    assert r.status_code == 200
    j = r.json()
    assert j["n_paths"] >= 1 and j["nodes"]

def test_report_download_mock(monkeypatch):
    monkeypatch.setattr(mod, "fetch_wallet_data", fake_fetch)
    a = "0x" + "a" * 40
    r = client.get("/report/" + a)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    assert a in r.text and "ChainMind" in r.text
