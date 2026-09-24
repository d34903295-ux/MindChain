import statistics

import agents.watcher as W
from agents.watcher import analyze_tx, norm_tx, robust_z, scan, window_stats

TX = {
    "hash": "0xabc",
    "from": "0x1111111111111111111111111111111111111111",
    "to": "0x2222222222222222222222222222222222222222",
    "value": hex(2 * 10**18),
    "gasPrice": hex(int(30 * 1e9)),
    "nonce": "0x5",
    "input": "0x",
}


def _tx(n, **over):
    t = {**TX, "hash": hex(n), "from": "0x" + f"{n:040x}"}
    t.update(over)
    return t


def test_norm_wei_a_eth():
    t = norm_tx(TX)
    assert t["value_eth"] == 2.0 and t["gas_price_gwei"] == 30.0
    assert t["to"] == "0x" + "2" * 40


def test_creacion_contrato_to_none():
    t = norm_tx({**TX, "to": None})
    assert t["to"] is None
    _, flags = analyze_tx(t, None)
    assert "creacion_contrato" in flags


def test_watchlist_alerta(monkeypatch):
    watched = "0x" + "ab" * 20
    monkeypatch.setattr(W.watchlist, "refresh", lambda: {watched: "pool-verificada"})
    t = norm_tx({**TX, "to": watched})
    score, flags = analyze_tx(t, None)
    assert score >= 50 and "watchlist:pool-verificada" in flags


def test_ballena_y_outlier():
    t = norm_tx({**TX, "value": hex(150 * 10**18)})
    score, flags = analyze_tx(t, 0.01)
    assert "ballena_100eth+" in flags and score >= 20
    t2 = norm_tx({**TX, "value": hex(5 * 10**18)})
    _, flags2 = analyze_tx(t2, 0.01)
    assert any(f.startswith("outlier_") and "mediana" in f for f in flags2)


def test_scan_con_bloques_mock(monkeypatch):
    monkeypatch.setattr(W, "get_latest_block", lambda chain: 102)
    monkeypatch.setattr(W, "get_block", lambda chain, n, full=True: {"timestamp": "0x1", "transactions": [_tx(n)]})
    W._windows.clear()
    W._alerted.clear()
    r = scan("ethereum", since=100, max_blocks=3)
    # since=100 es exclusivo: se leen los bloques 101 y 102
    assert r["latest"] == 102 and r["n_txs"] == 2
    assert all("score" in t and "flags" in t for t in r["txs"])


def test_ballena_grande_alerta_sola(monkeypatch):
    t = norm_tx({**TX, "value": hex(5_000 * 10**18)})
    score, flags = analyze_tx(t, None)
    assert score >= 50, f"5000 ETH debe alertar por sí solo (score={score})"
    assert "ballena_1000eth+" in flags


def test_dedupe_de_alertas(monkeypatch):
    monkeypatch.setattr(W, "get_latest_block", lambda chain: 102)
    monkeypatch.setattr(W, "get_block", lambda chain, n, full=True: {"timestamp": "0x1", "transactions": [_tx(9, to="0x" + "cd" * 20, value=hex(5000 * 10**18))]})
    W._windows.clear()
    W._alerted.clear()
    first = scan("ethereum", since=100, max_blocks=1)
    second = scan("ethereum", since=100, max_blocks=1)
    assert first["n_alerts"] == 1
    assert second["n_new_alerts"] == 0  # no re-alerta lo mismo


def test_scan_cadena_invalida():
    try:
        scan("solana")
        assert False
    except ValueError:
        assert True


def test_mad_se_adapta_a_cada_red():
    """En una red con baseline de 0.5 ETH, 5 ETH debe ser outlier estadístico."""
    W._windows.clear()
    baseline = ([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8] * 6)[:40]  # 40 muestras > mínimo
    for v in baseline:
        W._windows["base"].append(v)
    med, mad = W.window_stats(W._windows["base"])
    assert med == 0.5 and mad is not None and mad > 0
    normal = norm_tx({**TX, "value": hex(int(0.5 * 10**18))})
    raro = norm_tx({**TX, "value": hex(int(5 * 10**18))})
    _, f_normal = analyze_tx(normal, med, mad)
    s_raro, f_raro = analyze_tx(raro, med, mad)
    assert f_normal == []
    assert any("estadistico" in x for x in f_raro)
    assert s_raro >= 20


def test_sin_baseline_no_hay_outlier_estadistico():
    """Con menos de 30 muestras no se afirma nada: el detector se abstiene."""
    W._windows.clear()
    for v in [0.1, 0.2, 0.3] * 5:
        W._windows["ethereum"].append(v)
    med, mad = W.window_stats(W._windows["ethereum"])
    assert med is None and mad is None
    raro = norm_tx({**TX, "value": hex(int(5 * 10**18))})
    _, flags = analyze_tx(raro, med, mad)
    assert not any("estadistico" in f for f in flags)


def test_z_robusto_resiste_outliers_previos():
    """Un movimiento gigante no debe romper la escala de los siguientes."""
    base = [0.4, 0.5, 0.5, 0.6] * 10
    limpio = robust_z(0.5, statistics.median(base), statistics.median([abs(v - 0.5) for v in base]))
    contaminado = base + [5000.0]
    con_outlier = robust_z(0.5, statistics.median(contaminado),
                           statistics.median([abs(v - statistics.median(contaminado)) for v in contaminado]))
    assert abs(limpio) < 2
    assert abs(con_outlier) < 2  # la mediana y el MAD no se mueven


def test_scan_expone_detectores_y_baseline(monkeypatch):
    monkeypatch.setattr(W, "get_latest_block", lambda chain: 5)
    monkeypatch.setattr(W, "get_block", lambda chain, n, full=True: {"timestamp": "0x1", "transactions": [_tx(n)]})
    W._windows.clear()
    W._alerted.clear()
    r = scan("ethereum", since=4, max_blocks=1)
    assert "mad-z-robusto" in r["detectors"]
    assert "baseline_samples" in r
