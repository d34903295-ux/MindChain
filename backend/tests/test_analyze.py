from fastapi.testclient import TestClient
from app.main import app
import app.routers.analyze as mod

client = TestClient(app)

def fake_fetch(address, chain="ethereum", limit=25):
    return {"raw_address": {"transaction_count": 3, "first_seen_receiving": "2026-01-01 00:00:00",
            "balance": "1000", "balance_usd": 1.0, "type": "account"},
            "calls": [{"transaction_hash": "0x" + "ab" * 32, "sender": "0x1111111111111111111111111111111111111111",
                       "recipient": address.lower(), "value": 100, "value_usd": 1.0,
                       "time": "2026-09-20 10:00:00", "block_id": 1}], "source": "mock", "chain": chain}

def test_analyze_mock(monkeypatch):
    monkeypatch.setattr(mod, "fetch_wallet_data", fake_fetch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    r = client.post("/analyze-wallet", json={"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})
    assert r.status_code == 200
    j = r.json()
    assert "profile" in j and "risk_score" in j and "explanation" in j
    assert "elapsed_s" in j and j["elapsed_s"] < 10
