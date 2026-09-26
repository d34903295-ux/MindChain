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


def test_sin_base_de_datos_lo_dice_con_el_motivo(wallet_con_datos):
    """No hay Postgres ni Neo4j: el estado es 'failed' y con razón."""
    r = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    persist = r.json()["persistence"]
    for destino in ("postgres", "neo4j"):
        estado = persist[destino]
        assert estado.startswith("failed: "), f"{destino}: {estado}"
        # el motivo tiene que decir algo, no un "failed:" a secas
        assert len(estado) > len("failed: ")
        assert ":" in estado[len("failed: "):], "el motivo incluye el tipo de error"


def test_el_error_real_aparece_en_el_log(wallet_con_datos, caplog):
    """El error se loguea con su tipo y su mensaje. Antes no se logueaba nada."""
    with caplog.at_level(logging.WARNING, logger="chainmind.persistence"):
        client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
    textos = [r.getMessage() for r in caplog.records]
    assert any("persistencia" in t and "fallo" in t for t in textos), \
        f"no se registró ningún fallo: {textos}"
    # y el motivo del log es el mismo que va en la respuesta
    assert any(("postgres" in t or "neo4j" in t) for t in textos)


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


# ------------------------------------------------------------- el log existe
def test_el_logger_esta_configurado():
    """Un warning sin configurar no llega a chainmind_backend.log con formato."""
    import app.main as M
    assert logging.getLogger("chainmind.persistence").handlers or logging.getLogger().handlers, \
        "no hay ningun handler: los fallos se perderian"
    assert M is not None
