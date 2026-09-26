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
    # BUG 2: la direccion cero no tiene transacciones. Antes devolvia un 0/100
    # con aspecto de score valido; ahora el endpoint se abstiene y lo dice.
    assert j["risk_score"] is None, "sin datos no puede haber score"
    assert j["alert"]["reason"] in ("sin-datos", "sin-score-no-evaluable")
    assert "profile" in j and "explanation" in j and "elapsed_s" in j
    assert j["elapsed_s"] < 10
