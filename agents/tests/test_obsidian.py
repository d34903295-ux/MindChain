"""Tests de la integración con Obsidian: no destructiva, idempotente y segura."""
import os
import sys

import pytest

sys.path.insert(0, ".")
from agents import obsidian

ADDR = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"


@pytest.fixture()
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    v.mkdir()
    monkeypatch.setenv("CHAINMIND_OBSIDIAN_VAULT", str(v))
    return v


def _report(score=30, addr=ADDR):
    return {
        "address": addr,
        "chain": "ethereum",
        "profile": {"tx_count": 100, "age_days": 500, "activity": "alta", "balance_usd": 1234.5,
                    "labels": ["eoa"], "sample_size": 25, "sample_confidence": "alta",
                    "counterparties_sample": 8, "tx_count_reliable": True},
        "risk_score": score,
        "risk_factors": ["wallet_nueva_pocas_txs"],
        "explanation": "Wallet de prueba.",
        "elapsed_s": 0.4,
        "source": "mock",
    }


def test_detecta_vault_configurado(vault):
    st = obsidian.status()
    assert st["configured"] is True
    assert st["vault_detected"] == str(vault)


def test_escribe_nota_con_frontmatter(vault):
    res = obsidian.sync_wallet(_report())
    assert res["written"] is True
    note = vault / "ChainMind" / "wallets" / f"{ADDR}.md"
    text = note.read_text(encoding="utf-8")
    assert text.startswith("---")
    assert "cm_address:" in text and "cm_risk_score: 30" in text
    assert obsidian.START in text and obsidian.END in text


def test_es_idempotente(vault):
    """Re-sincronizar sin cambios no debe reescribir (evita reindexar Obsidian)."""
    obsidian.sync_wallet(_report())
    second = obsidian.sync_wallet(_report())
    assert second["written"] is False
    assert second["reason"] in ("sin-cambios", "sin-cambios-salvo-hora")


def test_reescribe_si_cambia_el_score(vault):
    obsidian.sync_wallet(_report(score=30))
    second = obsidian.sync_wallet(_report(score=80))
    assert second["written"] is True
    note = vault / "ChainMind" / "wallets" / f"{ADDR}.md"
    assert "cm_risk_score: 80" in note.read_text(encoding="utf-8")


def test_no_destruye_anotacion_del_usuario(vault):
    obsidian.sync_wallet(_report())
    note = vault / "ChainMind" / "wallets" / f"{ADDR}.md"
    text = note.read_text(encoding="utf-8")
    # el usuario añade una nota manual fuera de nuestro bloque y un campo propio
    text = text.replace(obsidian.END, obsidian.END + "\n\nMi nota: revisar con el equipo.")
    text = text.replace("cm_schema:", "cm_status: revisando\ncm_owner: ana\ncm_schema:")
    note.write_text(text, encoding="utf-8")

    obsidian.sync_wallet(_report(score=45))
    after = note.read_text(encoding="utf-8")
    assert "Mi nota: revisar con el equipo." in after   # preservado
    assert "cm_status: revisando" in after              # campo del usuario preservado
    assert "cm_risk_score: 45" in after                 # nuestro campo sí se actualizó


def test_actualiza_campos_sin_duplicar(tmp_path, vault):
    """Reescribir no debe duplicar claves de nuestro bloque en el frontmatter."""
    obsidian.sync_wallet(_report())
    obsidian.sync_wallet(_report(score=60))
    note = vault / "ChainMind" / "wallets" / f"{ADDR}.md"
    meta, _ = obsidian.split_note(note.read_text(encoding="utf-8"))
    assert meta["cm_risk_score"] == 60
    assert list(meta.keys()).count("cm_risk_score") == 1


def test_lectura_de_anotaciones(vault):
    obsidian.sync_wallet(_report())
    note = vault / "ChainMind" / "wallets" / f"{ADDR}.md"
    text = note.read_text(encoding="utf-8").replace("cm_schema:", "cm_status: vigilando\ncm_schema:")
    note.write_text(text, encoding="utf-8")
    ann = obsidian.read_annotations(ADDR)
    assert ann == {"cm_status": "vigilando"}  # no devuelve nuestros campos


def test_digest_y_alertas_crean_notas_enlazadas(vault):
    feed = {
        "chain": "ethereum", "latest": 100, "n_txs": 5, "n_alerts": 1, "elapsed_s": 0.2,
        "alerts": [{"from": ADDR, "to": "0x" + "b" * 40, "value_eth": 500.0, "score": 60,
                    "flags": ["ballena_1000eth+"], "hash": "0xdeadbeef", "block": 100}],
        "txs": [{"from": ADDR, "to": "0x" + "b" * 40, "value_eth": 500.0, "score": 60, "flags": []}],
        "detectors": ["absoluto", "mad-z-robusto"], "median_eth": 0.5, "mad_eth": 0.1,
        "baseline_samples": 100,
    }
    d = obsidian.sync_daily_digest(feed)
    a = obsidian.sync_alert(feed["alerts"][0])
    assert d["written"] and a["written"]
    alert_note = (vault / "ChainMind" / "alerts" / "0xdeadbeef.md").read_text(encoding="utf-8")
    assert f"[[{ADDR}]]" in alert_note  # wikilink a la wallet
    daily = list((vault / "ChainMind" / "daily").glob("*.md"))
    assert daily and "mad-z-robusto" in daily[0].read_text(encoding="utf-8")


def test_index_lista_wallets(vault):
    obsidian.sync_wallet(_report())
    res = obsidian.build_index()
    assert res["written"] is True
    text = (vault / "ChainMind" / "index.md").read_text(encoding="utf-8")
    assert f"[[{ADDR}]]" in text


def test_sin_vault_no_revienta(monkeypatch):
    monkeypatch.setenv("CHAINMIND_OBSIDIAN_VAULT", "")
    monkeypatch.setattr(obsidian, "detect_vault", lambda: None)
    res = obsidian.sync_wallet(_report())
    assert res["written"] is False and res["reason"] == "sin-vault-configurado"
    assert obsidian.read_annotations(ADDR) == {}


def test_nombre_seguro_evita_travesia():
    nasty = "../../evil/../x"
    name = obsidian.safe_name(nasty)
    assert "/" not in name and ".." not in name


def test_no_escribe_fuera_del_vault(vault, tmp_path):
    fuera = tmp_path / "fuera.md"
    res = obsidian.write_note(fuera, {"cm_kind": "x"}, "contenido")
    assert res["written"] is False
    assert res["reason"] == "ruta-fuera-del-vault"
    assert not fuera.exists()


def test_alerta_crea_stub_para_no_roto_enlaces(vault):
    """Sin nota de la wallet, el wikilink de la alerta quedaría roto."""
    tx = {"from": "0x" + "9" * 40, "to": "0x" + "8" * 40, "value_eth": 500.0, "score": 60,
          "flags": ["ballena_1000eth+", "outlier_estadistico_z95"], "hash": "0xfeed", "block": 7}
    obsidian.sync_alert(tx)
    stub = vault / "ChainMind" / "wallets" / ("0x" + "9" * 40 + ".md")
    assert stub.exists()
    assert "pendiente de análisis" in stub.read_text(encoding="utf-8")
    # el stub no se reescribe si la wallet ya tiene informe
    obsidian.sync_wallet(_report(addr="0x" + "9" * 40))
    again = obsidian.ensure_wallet_stub("0x" + "9" * 40, "otra vez")
    assert again["written"] is False


def test_flags_en_lenguaje_claro(vault):
    """El cuerpo va en claro; el frontmatter conserva el código para Dataview."""
    tx = {"from": ADDR, "to": None, "value_eth": 2.5, "score": 50,
          "flags": ["outlier_140x_mediana", "payload_grande"], "hash": "0xabc123", "block": 3}
    obsidian.sync_alert(tx)
    text = (vault / "ChainMind" / "alerts" / "0xabc123.md").read_text(encoding="utf-8")
    body = text.split(obsidian.START, 1)[1].split(obsidian.END, 1)[0]
    assert "140× la mediana" in body
    assert "payload grande" in body
    assert "outlier_140x_mediana" not in body
    # el frontmatter sí mantiene el valor estructurado
    assert "outlier_140x_mediana" in text.split("---", 2)[1]


def test_score_none_se_refleja_en_la_nota(vault):
    obsidian.sync_wallet(_report(score=None))
    text = (vault / "ChainMind" / "wallets" / f"{ADDR}.md").read_text(encoding="utf-8")
    assert "n/d/100" in text and "no-evaluable" in text
