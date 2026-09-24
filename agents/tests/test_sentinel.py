"""Tests del centinela: vigilancia autónoma opt-in, sin spam y a prueba de fallos."""
import sys

import pytest

sys.path.insert(0, ".")
from agents import sentinel


@pytest.fixture(autouse=True)
def clean_state(monkeypatch):
    sentinel.state.clear()
    sentinel.state.update({
        "enabled": False, "running": False, "cycles": 0, "alerts_found": 0,
        "alerts_delivered": 0, "last_block": {}, "last_run": None, "last_error": None,
        "chains": [], "started_at": None,
    })
    # parar antes de limpiar: si el hilo de un test anterior siguiera vivo,
    # escribiría en este estado compartido y fallaría el caso siguiente
    sentinel.stop(timeout=10)
    sentinel._stop.clear()
    yield
    sentinel.stop(timeout=10)


def _feed(n_alerts=1, new_alerts=None, block=100):
    return {
        "chain": "ethereum", "latest": block, "n_txs": 10, "n_alerts": n_alerts,
        "new_alerts": new_alerts if new_alerts is not None else [
            {"from": "0x" + "a" * 40, "to": "0x" + "b" * 40, "value_eth": 500.0,
             "score": 60, "flags": ["ballena_1000eth+"], "hash": "0xabc", "block": block}
        ][:n_alerts],
        "elapsed_s": 0.1, "detectors": ["absoluto"], "median_eth": 0.5, "mad_eth": 0.1,
        "baseline_samples": 100,
    }


def test_desactivado_por_defecto(monkeypatch):
    monkeypatch.setenv("CHAINMIND_SENTINEL", "0")
    res = sentinel.start()
    assert res["started"] is False
    assert sentinel.status()["enabled"] is False


def test_arranca_cuando_se_pide(monkeypatch):
    monkeypatch.setenv("CHAINMIND_SENTINEL", "1")
    monkeypatch.setenv("CHAINMIND_SENTINEL_INTERVAL", "3600")
    monkeypatch.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed(n_alerts=0, new_alerts=[]))
    res = sentinel.start()
    assert res["started"] is True
    assert sentinel.status()["enabled"] is True
    sentinel.stop()
    assert sentinel.status()["enabled"] is False


def test_ciclo_entrega_alertas(monkeypatch):
    monkeypatch.setattr(sentinel, "CHAINS", ["ethereum"])
    monkeypatch.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed())
    enviados = []
    monkeypatch.setattr(sentinel.alerts, "send_telegram",
                        lambda text: enviados.append(text) or {"sent": True, "reason": "ok"})
    monkeypatch.setattr(sentinel.obsidian, "sync_alert", lambda tx, chain: {"written": True})
    res = sentinel.run_cycle()
    assert res["delivered"] == 1
    assert res["new_alerts"] == 1
    assert "ChainMind" in enviados[0] and "500.0 ETH" in enviados[0]
    assert sentinel.state["last_block"]["ethereum"] == 100


def test_no_spamea_por_cooldown(monkeypatch):
    monkeypatch.setattr(sentinel, "CHAINS", ["ethereum"])
    monkeypatch.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed(block=101))
    monkeypatch.setattr(sentinel.alerts, "send_telegram", lambda text: {"sent": True})
    monkeypatch.setattr(sentinel.obsidian, "sync_alert", lambda tx, chain: {"written": True})
    sentinel.run_cycle()
    segunda = sentinel.run_cycle()
    assert segunda["delivered"] == 0
    assert segunda["chains"]["ethereum"].get("cooldown") is True


def test_el_centinela_realmente_cicla(monkeypatch):
    """Regresión: el hilo arrancaba pero no completaba ningún ciclo."""
    import time as _t
    monkeypatch.setenv("CHAINMIND_SENTINEL", "1")
    monkeypatch.setattr(sentinel, "INTERVAL", 5)
    monkeypatch.setattr(sentinel, "CHAINS", ["ethereum"])
    monkeypatch.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed(n_alerts=0, new_alerts=[]))
    sentinel.start()
    try:
        deadline = _t.time() + 6
        while _t.time() < deadline and sentinel.state["cycles"] == 0:
            _t.sleep(0.2)
        assert sentinel.state["cycles"] >= 1, "el centinela no completó ningún ciclo"
        assert sentinel.state["last_block"].get("ethereum") == 100
    finally:
        sentinel.stop()


def test_una_cadena_fallida_no_rompe_la_otra(monkeypatch):
    def scan(chain, since=None, max_blocks=2):
        if chain == "base":
            raise RuntimeError("RPC caído")
        return _feed(block=200)

    monkeypatch.setattr(sentinel.watcher, "scan", scan)
    res = sentinel.run_cycle()
    assert "error" in res["chains"]["base"]
    assert res["chains"]["ethereum"]["latest"] == 200
    assert sentinel.state["last_error"]


def test_telegram_sin_config_no_rompe(monkeypatch):
    monkeypatch.setattr(sentinel, "CHAINS", ["ethereum"])
    monkeypatch.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed())
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setattr(sentinel.obsidian, "sync_alert", lambda tx, chain: {"written": True})
    res = sentinel.run_cycle()
    assert res["delivered"] == 1
    assert res["new_alerts"] == 0  # sin Telegram no se cuenta como entregado


def test_usa_since_para_no_releer_bloques(monkeypatch):
    vistos = []

    def scan(chain, since=None, max_blocks=2):
        vistos.append((chain, since))
        return _feed(block=300)

    monkeypatch.setattr(sentinel.watcher, "scan", scan)
    sentinel.run_cycle()
    sentinel.run_cycle()
    eth = [s for c, s in vistos if c == "ethereum"]
    assert eth[0] is None
    assert eth[1] == 300  # segundo ciclo no relee bloques ya vistos


def test_stop_espera_al_hilo():
    """Sin join, el hilo sobrevive al apagado y sigue tocando el estado."""
    import time as _t
    monkey = pytest.MonkeyPatch()
    monkey.setenv("CHAINMIND_SENTINEL", "1")
    monkey.setattr(sentinel, "INTERVAL", 3600)
    monkey.setattr(sentinel, "CHAINS", ["ethereum"])
    monkey.setattr(sentinel.watcher, "scan", lambda *a, **k: _feed(n_alerts=0, new_alerts=[]))
    try:
        sentinel.start()
        _t.sleep(0.2)
        res = sentinel.stop(timeout=10)
        assert res["stopped"] is True
        ciclos = sentinel.state["cycles"]
        _t.sleep(0.4)
        assert sentinel.state["cycles"] == ciclos, "el hilo no debe seguir corriendo tras stop()"
    finally:
        monkey.undo()
