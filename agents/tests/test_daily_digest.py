"""Tests del digest diario: acumula el día, no solo el último barrido."""
import json
import sys

import pytest

sys.path.insert(0, ".")
from agents import obsidian


@pytest.fixture(autouse=True)
def vault(tmp_path, monkeypatch):
    """Vault falso y acumulador en temporal."""
    v = tmp_path / "vault"
    v.mkdir()
    monkeypatch.setenv("CHAINMIND_OBSIDIAN_VAULT", str(v))
    monkeypatch.setattr(obsidian, "_daily_state_path", lambda day: tmp_path / f"daily-{day}.json")
    yield v / "ChainMind"


def _feed(chain="ethereum", block=100, n=2, alerts=1, first="0x" + "a" * 40):
    txs = [{"from": first, "to": "0x" + "b" * 40, "value_eth": 10.0, "score": 50, "hash": f"0x{block}1"}]
    al = [{"from": first, "value_eth": 500.0, "score": 70, "flags": ["ballena_1000eth+"], "hash": f"0x{block}9", "block": block}]
    return {
        "chain": chain, "latest": block, "n_txs": n, "n_alerts": alerts,
        "alerts": al[:alerts], "txs": txs, "median_eth": 0.5, "mad_eth": 0.1,
        "baseline_samples": 100, "detectors": ["absoluto"],
    }


def test_acumula_entre_barridos(vault):
    obsidian.sync_daily_digest(_feed(block=100))
    obsidian.sync_daily_digest(_feed(block=101))
    nota = (vault / "daily").glob("*.md")
    text = next(nota).read_text(encoding="utf-8")
    assert "2 barridos" in text
    assert "4 transacciones" in text
    assert "bloque 101" in text


def test_no_duplica_la_misma_alerta(vault):
    """El centinela corre cada 60s: la misma alerta no puede repetirse."""
    for _ in range(4):
        obsidian.sync_daily_digest(_feed(block=100))
    text = next((vault / "daily").glob("*.md")).read_text(encoding="utf-8")
    seccion = text.split("## Alertas del día")[1].split("## Movimientos")[0]
    assert len([l for l in seccion.splitlines() if l.startswith("- ")]) == 1
    assert "4 barridos" in text, "los barridos sí se acumulan aunque la alerta sea la misma"


def test_suma_varias_redes(vault):
    obsidian.sync_daily_digest(_feed(chain="ethereum", block=100))
    obsidian.sync_daily_digest(_feed(chain="base", block=200))
    text = next((vault / "daily").glob("*.md")).read_text(encoding="utf-8")
    assert "**base**" in text and "**ethereum**" in text
    assert "2 barridos" in text


def test_sobrevive_al_reinicio_del_proceso(vault, tmp_path):
    obsidian.sync_daily_digest(_feed(block=100))
    estado = json.loads((tmp_path / f"daily-{__import__('datetime').date.today().isoformat()}.json").read_text(encoding="utf-8"))
    assert estado["sweeps"] == 1
    obsidian.sync_daily_digest(_feed(block=101))
    texto = next((vault / "daily").glob("*.md")).read_text(encoding="utf-8")
    assert "2 barridos" in texto, "el acumulador en disco debe rehidratarse"


def test_texto_limpio_para_humanos(vault):
    obsidian.sync_daily_digest(_feed())
    text = next((vault / "daily").glob("*.md")).read_text(encoding="utf-8")
    assert "movimiento de 1.000+ ETH" in text, "las señales van en claro, no en snake_case"
    assert "ballena_1000eth+" not in text
