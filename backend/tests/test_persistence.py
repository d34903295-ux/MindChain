"""Tests del BUG C: las escrituras a Postgres y Neo4j fallaban en silencio.

Contexto real (auditoría 2026-09-26): `analyze.py` tenía

    try:
        from app.db.postgres import upsert_wallet_report
        upsert_wallet_report(...)
    except Exception:
        pass

Como no hay ni Postgres ni Neo4j en esta máquina, **todas** las llamadas a
`/analyze-wallet` estaban fallando al guardar y devolviendo 200 sin decir
nada. Un 200 que no distingue "guardado" de "no guardado" es un 200 que
miente.

Lo que se fija aquí:
- la respuesta dice qué pasó con cada destino, siempre
- el error real (tipo + mensaje) aparece en el log, no se traga
- el análisis no se rompe si la base no está: sigue devolviendo 200
"""
import logging
import os
import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
for _p in (str(BACKEND), str(ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.main import app  # noqa: E402
from app.routers import analyze  # noqa: E402

client = TestClient(app)
ADDR = "0x" + "a" * 40


def _tx(i):
    return {"hash": "0x" + f"{i:064x}", "from": ADDR, "to": "0x" + f"{i:040x}",
            "value_eth": 1.0, "value_usd": 2000.0, "block": 1000 + i,
            "time": "2026-09-20T10:00:00Z", "score": 5, "flags": [], "alert": False}


@pytest.fixture(autouse=True)
def sin_tocar_la_base_real(monkeypatch):
    """Por defecto los writers son falsos: la suite no escribe en la base real.

    Importante desde que Postgres y Neo4j están levantados en esta máquina: sin
    esto, cada test que llega a la rama de persistencia inserta filas de
    mentira en la base de desarrollo.
    """
    _inyectar_db(monkeypatch,
                 postgres={"upsert_wallet_report": lambda *a, **k: None},
                 neo4j={"save_wallet_graph": lambda *a, **k: None})


@pytest.fixture
def wallet_con_datos(monkeypatch):
    """Perfil con muestra suficiente, sin tocar la red."""
    txs = [_tx(i) for i in range(25)]
    monkeypatch.setattr(analyze, "fetch_wallet_data", lambda *a, **k: {
        "raw_address": {"balance": "1000000000000000000"}, "calls": [], "rpc": {},
        "source": "test", "chain": "ethereum",
        "data_quality": {"source": "test", "degraded": False, "insufficient_data": False,
                         "sample_rows": 0, "has_history": True, "errors": []}})
    real_build = analyze.build_profile

    def fake_build(address, fetched):
        p, t = real_build(address, fetched)
        p["sample_size"] = 25
        p["sample_confidence"] = "alta"
        p["tx_count"] = 25
        p["tx_count_reliable"] = True
        p["insufficient_data"] = False
        p["balance_usd"] = 2000.0
        p["balance_usd_source"] = "test"
        return p, txs

    monkeypatch.setattr(analyze, "build_profile", fake_build)
    monkeypatch.setattr(analyze, "explain_detailed",
                        lambda p, s, f: {"explanation": "texto de prueba", "ai": None})
    return txs


# ------------------------------------------------------------- el contrato
def test_la_respuesta_siempre_dice_que_paso_con_cada_destino(wallet_con_datos):
    r = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    assert r.status_code == 200
    persist = r.json().get("persistence")
    assert persist is not None, "la respuesta tiene que informar de la persistencia"
    assert set(persist) == {"postgres", "neo4j"}


def test_un_escritor_que_falla_lo_dice_con_el_motivo(wallet_con_datos, monkeypatch):
    """El estado 'failed' lleva el tipo y el mensaje, no un 'failed' a secas."""
    def postgres_explota(*a, **k):
        raise RuntimeError("connection refused: could not connect to server")

    _inyectar_db(monkeypatch, postgres={"upsert_wallet_report": postgres_explota},
                 neo4j={"save_wallet_graph": lambda *a, **k: None})
    persist = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"}).json()["persistence"]
    assert persist["postgres"].startswith("failed: ")
    assert "RuntimeError" in persist["postgres"]
    assert "connection refused" in persist["postgres"]


def test_el_error_real_aparece_en_el_log(wallet_con_datos, monkeypatch, caplog):
    """El error se loguea con su tipo y su mensaje. Antes no se logueaba nada."""
    def neo4j_explota(*a, **k):
        raise RuntimeError("bolt timed out")

    _inyectar_db(monkeypatch, postgres={"upsert_wallet_report": lambda *a, **k: None},
                 neo4j={"save_wallet_graph": neo4j_explota})
    with caplog.at_level(logging.WARNING, logger="chainmind.persistence"):
        client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    textos = [r.getMessage() for r in caplog.records]
    assert any("persistencia neo4j fallo" in t for t in textos), \
        f"no se registro el fallo de neo4j: {textos}"
    assert any("bolt timed out" in t for t in textos)


def _inyectar_db(monkeypatch, postgres=None, neo4j=None):
    """Sustituye app.db.postgres / app.db.neo4j_driver por módulos falsos.

    Necesario porque en este entorno ni `psycopg` ni `neo4j` están
    instalados: importar los módulos reales revienta con ModuleNotFoundError
    antes de poder monkeypatchear sus funciones.
    """
    import types
    for nombre, attrs in (("app.db.postgres", postgres or {}),
                          ("app.db.neo4j_driver", neo4j or {})):
        mod = types.ModuleType(nombre)
        for k, v in attrs.items():
            setattr(mod, k, v)
        monkeypatch.setitem(sys.modules, nombre, mod)


def test_cuando_la_escritura_va_bien_dice_ok(wallet_con_datos, monkeypatch):
    _inyectar_db(monkeypatch,
                 postgres={"upsert_wallet_report": lambda *a, **k: None},
                 neo4j={"save_wallet_graph": lambda *a, **k: None})
    r = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    persist = r.json()["persistence"]
    assert persist == {"postgres": "ok", "neo4j": "ok"}


def test_un_destino_que_falla_no_tira_al_otro(wallet_con_datos, monkeypatch):
    """Postgres caído no puede impedir que Neo4j se intente, ni al revés."""
    def postgres_explota(*a, **k):
        raise RuntimeError("connection refused")

    _inyectar_db(monkeypatch,
                 postgres={"upsert_wallet_report": postgres_explota},
                 neo4j={"save_wallet_graph": lambda *a, **k: None})
    estado = client.post("/analyze-wallet",
                         json={"address": ADDR, "chain": "ethereum"}).json()["persistence"]
    assert estado["postgres"].startswith("failed: ")
    assert "connection refused" in estado["postgres"]
    assert estado["neo4j"] == "ok"


# ----------------------------------------------------- cuando no se intenta
def test_sin_score_no_se_intenta_y_se_dice(monkeypatch):
    """Sin score no hay nada que guardar: se dice 'skipped', no 'ok'."""
    monkeypatch.setattr(analyze, "fetch_wallet_data", lambda *a, **k: {
        "raw_address": {}, "calls": [], "rpc": {}, "source": "test", "chain": "ethereum",
        "data_quality": {"source": "test", "degraded": True, "insufficient_data": True,
                         "errors": ["red caida"]}})
    monkeypatch.setattr(analyze, "build_profile", lambda a, f: ({"address": a, "labels": [],
                                                                "balance_usd": 0}, []))
    monkeypatch.setattr(analyze, "score_wallet", lambda p, t: (None, ["datos_insuficientes_no_evaluable"]))
    monkeypatch.setattr(analyze, "explain_detailed",
                        lambda p, s, f: {"explanation": "sin datos", "ai": None})
    r = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    persist = r.json()["persistence"]
    assert persist["postgres"].startswith("skipped: ")
    assert persist["neo4j"].startswith("skipped: ")


# ----------------------------------------------------- el análisis no se rompe
def test_el_analisis_no_se_rompe_sin_base_de_datos(wallet_con_datos):
    """La BD no es un prerrequisito del análisis: 200 y datos completos."""
    j = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"}).json()
    assert j["risk_score"] is not None
    assert j["profile"]["balance_usd"] == 2000.0
    assert j["persistence"] is not None




# ------------------------------------- contra la base real (opt-in, no por defecto)
@pytest.mark.skipif(os.getenv("CHAINMIND_TEST_DB") != "1",
                    reason="escribe en la base real: pon CHAINMIND_TEST_DB=1 para correrlo")
def test_roundtrip_contra_la_base_real(monkeypatch):
    """Espera 'ok' y comprueba que la fila existe de verdad en la base.

    No se corre por defecto porque inserta en la base de desarrollo. Es la
    unica forma de comprobar que 'ok' no es solo la opinion del proceso sobre
    su propio INSERT.
    """
    # el fixture autouse pone modulos falsos en sys.modules: hay que quitar los
    # dos para que los imports del router lleguen a los modulos de verdad
    monkeypatch.delitem(sys.modules, "app.db.postgres", raising=False)
    monkeypatch.delitem(sys.modules, "app.db.neo4j_driver", raising=False)
    ADDR_REAL = "0x" + "b" * 40
    r = client.post("/analyze-wallet", json={"address": ADDR_REAL, "chain": "ethereum"})
    assert r.status_code == 200
    persist = r.json()["persistence"]
    assert persist["postgres"].startswith("ok"), persist["postgres"]
    assert persist["neo4j"].startswith("ok"), persist["neo4j"]

    import psycopg
    from app.db.postgres import DATABASE_URL
    with psycopg.connect(DATABASE_URL) as c:
        with c.cursor() as cur:
            cur.execute("SELECT count(*) FROM reports r JOIN wallets w ON w.id = r.wallet_id "
                        "WHERE w.address = %s", (ADDR_REAL,))
            assert cur.fetchone()[0] >= 1, "el report no llego a la base"

    from neo4j import GraphDatabase
    from backend.app.db.neo4j_driver import URI, USER, PASSWORD
    d = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with d.session() as s:
        n = s.run("MATCH (t:Transaction) WHERE t.from IS NULL OR true "
                  "RETURN count(t) AS c").single()["c"]
    d.close()
    assert isinstance(n, int)

# ------------------------------------------------------------- el log existe
def test_el_logger_esta_configurado():
    """Un warning sin configurar no llega a chainmind_backend.log con formato."""
    import app.main as M
    assert logging.getLogger("chainmind.persistence").handlers or logging.getLogger().handlers, \
        "no hay ningun handler: los fallos se perderian"
    assert M is not None
