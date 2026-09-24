from fastapi.testclient import TestClient
from app.main import app
import app.routers.feed as mod

client = TestClient(app)


def test_chains():
    r = client.get("/chains")
    assert r.status_code == 200
    assert "ethereum" in r.json()["chains"] and "base" in r.json()["chains"]


def test_feed_mock(monkeypatch):
    def fake_scan(chain="ethereum", since=None, max_blocks=2):
        assert chain == "base"
        return {
            "chain": "base", "latest": 10, "blocks": [{"number": 10, "tx_count": 1}],
            "txs": [{"hash": "0x1", "from": "0x" + "1" * 40, "to": None,
                     "value_eth": 0.0, "gas_price_gwei": 1.0, "score": 5,
                     "flags": ["creacion_contrato"], "alert": False}],
            "alerts": [], "n_txs": 1, "n_alerts": 0, "elapsed_s": 0.1,
        }

    monkeypatch.setattr(mod.watcher, "scan", fake_scan)
    r = client.get("/feed/base")
    assert r.status_code == 200
    assert r.json()["n_txs"] == 1


def test_feed_cadena_invalida():
    assert client.get("/feed/solana").status_code == 400
