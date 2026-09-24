from fastapi.testclient import TestClient
from app.main import app
import app.routers.contract as mod

client = TestClient(app)

def fake_fetch(address):
    return {"address": address, "code": "0x6001", "is_contract": True, "code_size_bytes": 2,
            "verified": True, "verified_via": "mock", "source": "contract T { function transfer(address to) public {} }",
            "source_origin": "mock"}

def test_analyze_contract_mock(monkeypatch):
    monkeypatch.setattr(mod, "fetch_contract", fake_fetch)
    r = client.post("/analyze-contract", json={"address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"})
    assert r.status_code == 200
    j = r.json()
    assert j["is_contract"] is True and j["verified"] is True
    assert 0 <= j["risk_score"] <= 100 and "permissions" in j and "explanation" in j
    assert j["elapsed_s"] < 10
