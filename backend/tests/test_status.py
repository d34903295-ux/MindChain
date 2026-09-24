"""Estado operacional: /status y /anomaly/latest.

Regresión: los imports de status.py estaban anidados dentro del `if` que
inserta ROOT en sys.path, así que en el servidor (donde ROOT ya estaba)
`price` quedaba sin definir y /status devolvía 500. En los tests pasaba
porque ROOT no estaba. Estos tests lo cierran.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_status_devuelve_todas_las_secciones(monkeypatch):
    monkeypatch.setattr("app.routers.status.price.get_price_usd", lambda: 2000.0)
    monkeypatch.setattr("app.routers.status.price.cache_info", lambda: {"cached": True})
    r = client.get("/status")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("ok", "chains", "price", "watchlist", "fetch_cache", "guard", "sentinel", "anomaly_job"):
        assert key in body, f"falta {key} en /status"
    assert body["guard"]["max_concurrency"] >= 1
    assert "sentinel" in body and "anomaly_job" in body


def test_status_no_depende_del_orden_de_imports():
    """`app` debe ser importable aunque ROOT ya esté en sys.path (caso servidor)."""
    import sys
    assert str(__import__("pathlib").Path(__file__).resolve().parents[2]) in sys.path
    from app.routers import status as mod
    assert hasattr(mod, "price")
    assert hasattr(mod, "guard_stats")
    assert hasattr(mod, "sentinel")


def test_anomaly_latest_siempre_responde():
    r = client.get("/anomaly/latest")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "exists" in body
    if body["exists"] and "error" not in body:
        assert body.get("model") == "isolation-forest"
