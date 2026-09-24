from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_analyze_wallet_stub():
    r = client.post("/analyze-wallet", json={"address": "0x0000000000000000000000000000000000000000"})
    assert r.status_code == 200
    assert r.json()["risk_score"] == 0
