"""Tests de las claves de API propias de ChainMind.

Lo crítico aquí es la frontera: estas claves autorizan llamadas a ChainMind, y
no tienen absolutamente nada que ver con las claves de los proveedores de IA.
Esas no se devuelven por ningún endpoint.
"""
import pathlib

import pytest
from fastapi.testclient import TestClient

from app import auth
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(auth, "STORE", tmp_path / "keys.json")
    return tmp_path


def test_crear_devuelve_la_clave_una_sola_vez():
    r = auth.crear("mi-script")
    assert r["clave"].startswith("cm_")
    assert "Cópiala ahora" in r["aviso"]
    # el almacén solo tiene el hash
    texto = auth.STORE.read_text(encoding="utf-8")
    assert r["clave"] not in texto
    assert r["hash"][:16] in texto


def test_listar_nunca_devuelve_hash_ni_clave():
    creada = auth.crear("mi-script")
    pub = auth.listar()
    assert pub and all("hash" not in k for k in pub)
    assert creada["clave"] not in str(pub)


def test_verificar_acepta_la_clave_correcta():
    creada = auth.crear("x")
    assert auth.verificar(creada["clave"])["nombre"] == "x"


def test_verificar_rechaza_clave_inventada():
    auth.crear("x")
    assert auth.verificar("cm_inventada") is None
    assert auth.verificar("") is None
    assert auth.verificar(None) is None


def test_revocar_invalida():
    creada = auth.crear("temporal")
    assert auth.revocar("temporal")["revocadas"] == 1
    assert auth.verificar(creada["clave"]) is None


def test_clave_caducada_no_sirve():
    creada = auth.crear("vieja", ttl_dias=1)
    import json
    datos = json.loads(auth.STORE.read_text(encoding="utf-8"))
    datos["claves"][0]["expira"] = "2000-01-01T00:00:00Z"
    auth.STORE.write_text(json.dumps(datos), encoding="utf-8")
    assert auth.verificar(creada["clave"]) is None


def test_localhost_no_necesita_clave():
    assert auth.es_local("127.0.0.1") and auth.es_local("localhost") and auth.es_local("::1")
    assert not auth.es_local("10.0.0.5")


def test_hosts_de_confianza_externos(monkeypatch):
    monkeypatch.setenv("CHAINMIND_TRUSTED_HOSTS", "proxy,host.docker.internal")
    assert auth.es_local("proxy") and auth.es_local("host.docker.internal")
    assert not auth.es_local("evil.com")


def test_require_key_aprieta_tambien_local(monkeypatch):
    monkeypatch.setenv("CHAINMIND_REQUIRE_KEY", "1")
    assert auth.requiere_clave("127.0.0.1") is True


# ----------------------------------------------------------------- endpoints
def test_post_keys_desde_local(monkeypatch):
    monkeypatch.setattr(auth, "es_local", lambda h: True)
    r = client.post("/keys", json={"nombre": "mi-bot"})
    assert r.status_code == 200
    assert r.json()["clave"].startswith("cm_")


def test_post_keys_rechazado_desde_fuera(monkeypatch):
    """Desde fuera el middleware corta antes: 401, ni siquiera llega al handler."""
    monkeypatch.setattr(auth, "es_local", lambda h: False)
    assert client.post("/keys", json={"nombre": "x"}).status_code == 401
    assert client.get("/keys").status_code == 401
    assert client.delete("/keys/x").status_code == 401


def test_el_chat_no_pide_clave_desde_local():
    r = client.post("/chat", json={"mensaje": "hola"})
    assert r.status_code == 200
    assert "respuesta" in r.json()


def test_status_no_expone_ninguna_credencial(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-no-debe-aparecer")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-no-debe-aparecer")
    cuerpo = client.get("/status").text
    assert "sk-ant-no-debe-aparecer" not in cuerpo
    assert "sk-openai-no-debe-aparecer" not in cuerpo


def test_herramientas_del_chat_publicas():
    r = client.get("/chat/herramientas")
    assert r.status_code == 200
    nombres = {h["nombre"] for h in r.json()["herramientas"]}
    # El `nombre` publicado es la clave del registro: el catálogo que lee el
    # enrutado por IA y el que se puede ejecutar no pueden ser dos vocabularios.
    assert {"wallet", "contrato", "rastreo", "top_wallets", "comparar",
            "resumen", "feed", "estado", "watchlist"} <= nombres
    assert {"analizar_wallet", "investigar"} & nombres == set(), "nombres antiguos retirados"


def test_middleware_exige_clave_a_un_host_externo(monkeypatch):
    monkeypatch.setattr("app.auth.es_local", lambda h: False)
    r = client.post("/analyze-wallet", json={"address": "0x" + "1" * 40, "chain": "ethereum"})
    assert r.status_code == 401
    assert "X-API-Key" in r.json()["como_conseguirla"] or r.json()["cabecera"].startswith("X-API-Key")


def test_middleware_acepta_clave_valida(monkeypatch):
    creada = auth.crear("externa")
    monkeypatch.setattr("app.auth.es_local", lambda h: False)
    monkeypatch.setattr("app.auth.verificar", lambda k: {"nombre": "externa"} if k == creada["clave"] else None)
    # /analyze-wallet sin datos reales: da 200/4xx de negocio, nunca 401
    r = client.post("/analyze-wallet", json={"address": "0x" + "1" * 40, "chain": "ethereum"},
                    headers={"X-API-Key": creada["clave"]})
    assert r.status_code != 401


def test_rutas_publicas_no_exigen_clave(monkeypatch):
    """Solo lo que no devuelve datos del usuario puede quedar abierto.

    /status y /anomaly/latest se quitaron de SIN_CLAVE: /status lleva la
    watchlist y /anomaly/latest las anomalías de wallets reales. Con el
    servicio en la red, cualquier sitio los leia sin clave.
    """
    monkeypatch.setattr("app.auth.es_local", lambda h: False)
    for ruta in ("/chains", "/health", "/chat/herramientas"):
        assert client.get(ruta).status_code != 401, ruta


def test_rutas_con_datos_exigen_clave_desde_fuera(monkeypatch):
    monkeypatch.setattr("app.auth.es_local", lambda h: False)
    for ruta in ("/status", "/anomaly/latest", "/watchlist"):
        assert client.get(ruta).status_code == 401, ruta


def test_cors_no_deja_origenes_en_comodin():
    """El comodin exponia la API a cualquier pagina que visitara el usuario."""
    from app.main import _origenes_permitidos

    origenes = _origenes_permitidos()
    assert "*" not in origenes
    assert origenes == [o for o in origenes if o]
    assert any("localhost:3000" in o for o in origenes)


def test_cors_responde_con_el_origen_permitido():
    r = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_no_responde_con_un_origen_ajeno():
    r = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
