from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_analyze_wallet_fase1():
    r = client.post("/analyze-wallet", json={"address": "0x0000000000000000000000000000000000000000"})
    assert r.status_code == 200
    j = r.json()
    assert 0 <= j["risk_score"] <= 100
    assert "profile" in j and "explanation" in j and "elapsed_s" in j
    assert j["elapsed_s"] < 10
