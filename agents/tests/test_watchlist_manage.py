"""Tests de gestión de la watchlist: verificación on-chain y persistencia."""
import json
import sys

import pytest

sys.path.insert(0, ".")
from agents import watchlist


@pytest.fixture
def local(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    monkeypatch.setattr(watchlist, "LOCAL", path)
    watchlist._cache.update({"addresses": {}, "source": "vacio", "loaded_at": 0.0})
    yield path
    watchlist._cache.update({"addresses": {}, "source": "vacio", "loaded_at": 0.0})


def test_rechaza_formato_invalido(local):
    res = watchlist.add("0x123", "x")
    assert res["added"] is False
    assert "formato" in res["reason"]


def test_rechaza_eoa_sin_bytecode(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (False, 0))
    res = watchlist.add("0x" + "a" * 40, "mixer")
    assert res["added"] is False
    assert "bytecode" in res["reason"]


def test_clasifica_codigo():
    assert watchlist.classify_code("0x") == ("eoa", 0)
    assert watchlist.classify_code("") == ("eoa", 0)
    assert watchlist.classify_code("0xef0100" + "ab" * 20) == ("delegado", 23)
    assert watchlist.classify_code("0x6080") == ("contrato", 2)
    assert watchlist.classify_code(None) == ("eoa", 0)


def test_rechaza_eoa_delegada_eip7702(local, monkeypatch):
    """Regresión: EIP-7702 devuelve 23 bytes y parecia un contrato."""
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (False, -23))
    res = watchlist.add("0x" + "a" * 40, "delegada")
    assert res["added"] is False
    assert "7702" in res["reason"]
    assert res["code_bytes"] == 23


def test_acepta_contrato_verificado(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 2474))
    res = watchlist.add("0x" + "b" * 40, "mixer", chain="ethereum")
    assert res["added"] is True
    assert res["entry"]["code_bytes"] == 2474
    assert res["entry"]["verificado"] is True
    assert json.loads(local.read_text(encoding="utf-8"))["addresses"][0]["label"] == "mixer"


def test_no_inventa_veredicto_si_el_rpc_falla(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (False, 0))
    res = watchlist.add("0x" + "c" * 40, "x", verify=False)
    assert res["added"] is True
    assert res["entry"]["verificado"] is None, "sin verificación no se afirma que exista"


def test_no_duplica(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 100))
    addr = "0x" + "d" * 40
    watchlist.add(addr, "primera")
    res = watchlist.add(addr, "segunda")
    assert res["added"] is False
    assert "ya estaba" in res["reason"]
    assert len(json.loads(local.read_text(encoding="utf-8"))["addresses"]) == 1


def test_actualiza_etiqueta_sin_duplicar(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 100))
    addr = "0x" + "e" * 40
    watchlist.add(addr, "viejo")
    watchlist.remove(addr)
    watchlist.add(addr, "nuevo")
    data = json.loads(local.read_text(encoding="utf-8"))["addresses"]
    assert len(data) == 1 and data[0]["label"] == "nuevo"


def test_remove_de_inexistente_no_rompe(local):
    res = watchlist.remove("0x" + "f" * 40)
    assert res["removed"] is False


def test_entries_y_get_coinciden(local, monkeypatch):
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 42))
    addr = "0x" + "1" * 40
    watchlist.add(addr, "sancionado-testeo")
    assert watchlist.get(addr) == "sancionado-testeo"
    assert watchlist.get(addr.upper()) == "sancionado-testeo"
    assert watchlist.entries()[0]["address"] == addr
    assert watchlist.size() == 1


def test_editar_el_json_a_mano_se_ve_al_instante(local, monkeypatch):
    """Regresión: la caché TTL de 6h ocultaba las ediciones del fichero."""
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 100))
    addr = "0x" + "3" * 40
    watchlist.add(addr, "vigilada")
    assert watchlist.size() == 1
    local.write_text(json.dumps({"addresses": []}), encoding="utf-8")
    assert watchlist.size() == 0, "editar el JSON a mano debe notarse sin esperar al TTL"


def test_roto_no_rompe(tmp_path, monkeypatch):
    path = tmp_path / "watchlist.json"
    path.write_text("{no es json", encoding="utf-8")
    monkeypatch.setattr(watchlist, "LOCAL", path)
    monkeypatch.setattr(watchlist, "has_contract_code", lambda a, c="ethereum": (True, 10))
    assert watchlist.entries() == []
    res = watchlist.add("0x" + "2" * 40, "recuperado")
    assert res["added"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["addresses"][0]["label"] == "recuperado"
