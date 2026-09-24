from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

ADDR = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


def test_qr_png():
    r = client.get(f"/qr/{ADDR}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(r.content) > 500


def test_qr_download():
    r = client.get(f"/qr/{ADDR}?download=true")
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")


def test_qr_invalida_400():
    r = client.get("/qr/0xZZZ")
    assert r.status_code == 400
