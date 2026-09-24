"""Tests del guard de carga: concurrencia, 429 honesto y dedupe."""
import sys
import threading
import time

import pytest

sys.path.insert(0, ".")
from app import guard


@pytest.fixture(autouse=True)
def clean():
    guard.reset()
    yield
    guard.reset()


def test_permite_hasta_el_tope_y_encola_el_resto():
    """La concurrencia manda: el exceso espera en cola, no se rechaza."""
    holders = [guard.work("feed:ethereum") for _ in range(guard.MAX_CONCURRENCY)]
    for h in holders:
        h.__enter__()
    encolado = threading.Event()
    liberado = threading.Event()

    def espera():
        try:
            with guard.work("feed:ethereum"):
                encolado.set()
                liberado.wait(5)
        finally:
            liberado.set()

    t = threading.Thread(target=espera, daemon=True)
    t.start()
    time.sleep(0.3)
    assert encolado.is_set() is False, "no debe entrar mientras hay slots ocupados"
    for h in holders:
        h.__exit__()
    t.join(5)
    assert encolado.is_set() is True, "debe entrar en cuanto se libera un slot"


def test_429_lleva_retry_after():
    """Saturado: se rechazan con 429 en vez de esperar indefinidamente."""
    for i in range(guard.MAX_CONCURRENCY + guard.QUEUE_MAX):
        guard._slots["feed:base"] += 1  # simula saturación ya occurida
    try:
        with pytest.raises(guard.Busy) as exc:
            with guard.work("feed:base"):
                pass
        assert exc.value.retry_after > 0
    finally:
        guard._slots["feed:base"] = 0


def test_stats_refleja_el_trabajo():
    with guard.work("feed:ethereum"):
        st = guard.stats()
        assert st["in_flight"]["feed:ethereum"] == 1
        assert st["max_blocks"] >= 1
    assert guard.stats()["in_flight"].get("feed:ethereum", 0) == 0


def test_el_slot_se_libera_aunque_falle_el_bloque():
    with pytest.raises(RuntimeError):
        with guard.work("feed:ethereum"):
            raise RuntimeError("RPC caído")
    with guard.work("feed:ethereum"):
        pass


def test_liberar_el_slot_permite_otro():
    with guard.work("analyze:wallet"):
        pass
    with guard.work("analyze:wallet"):
        pass


def test_workloads_distintos_no_se_bloquean():
    with guard.work("analyze:wallet"), guard.work("feed:ethereum"):
        pass


def test_dedupe_no_vuelve_a_trabajar():
    """Regresión: antes se marcaba from_cache pero el trabajo se hacia igual."""
    llamadas = []

    def trabajo():
        llamadas.append(1)
        return {"ok": True}

    with guard.work("feed:ethereum", key="0:2") as slot:
        slot.remember(trabajo())
    with guard.work("feed:ethereum", key="0:2") as slot:
        cached = slot.reuse()
        assert cached == {"ok": True}
        if cached is None:
            trabajo()
    assert len(llamadas) == 1, "no debe repetir el trabajo dentro del TTL"


def test_claves_distintas_si_se_recalculan():
    with guard.work("feed:ethereum", key="0:2") as slot:
        slot.remember({"bloque": 100})
    with guard.work("feed:ethereum", key="200:2") as slot:
        assert slot.reuse() is None
