from fastapi.testclient import TestClient
from app.main import app
import app.routers.analyze as mod

client = TestClient(app)

def fake_fetch(address, chain="ethereum", limit=25):
    assert chain == "base"
    return {"raw_address": {"transaction_count": 5, "balance": "10", "balance_usd": 1.0, "type": "account"},
            "calls": [], "source": "mock", "chain": "base"}

def test_analyze_base_mock(monkeypatch):
    monkeypatch.setattr(mod, "fetch_wallet_data", fake_fetch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    r = client.post("/analyze-wallet", json={"address": "0x" + "3" * 40, "chain": "base"})
    assert r.status_code == 200
    j = r.json()
    assert j["chain"] == "base" and j["profile"]["chain"] == "base" and j["source"] == "mock"

def test_cadena_desconocida_400():
    r = client.post("/analyze-wallet", json={"address": "0x" + "3" * 40, "chain": "solana"})
    assert r.status_code == 400
