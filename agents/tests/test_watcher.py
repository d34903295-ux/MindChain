from agents.watcher import norm_tx, analyze_tx, scan
import agents.watcher as W

TX = {
    "hash": "0xabc",
    "from": "0x1111111111111111111111111111111111111111",
    "to": "0x2222222222222222222222222222222222222222",
    "value": hex(2 * 10**18),
    "gasPrice": hex(int(30 * 1e9)),
    "nonce": "0x5",
    "input": "0x",
}


def test_norm_wei_a_eth():
    t = norm_tx(TX)
    assert t["value_eth"] == 2.0 and t["gas_price_gwei"] == 30.0
    assert t["to"] == "0x" + "2" * 40


def test_creacion_contrato_to_none():
    t = norm_tx({**TX, "to": None})
    assert t["to"] is None
    _, flags = analyze_tx(t, None)
    assert "creacion_contrato" in flags


def test_mezclador_alerta():
    mixer = next(iter(sorted(__import__("agents.risk_scoring", fromlist=["MIXERS"]).MIXERS)))
    t = norm_tx({**TX, "to": mixer})
    score, flags = analyze_tx(t, None)
    assert score >= 50 and "mezclador_conocido" in flags


def test_ballena_y_outlier():
    t = norm_tx({**TX, "value": hex(150 * 10**18)})
    score, flags = analyze_tx(t, 0.01)
    assert "ballena_100eth+" in flags and score >= 25
    t2 = norm_tx({**TX, "value": hex(5 * 10**18)})
    _, flags2 = analyze_tx(t2, 0.01)
    assert any(f.startswith("outlier_20x_mediana") for f in flags2)


def test_scan_con_bloques_mock(monkeypatch):
    monkeypatch.setattr(W, "get_latest_block", lambda chain: 102)
    monkeypatch.setattr(
        W, "get_block", lambda chain, n, full=True: {"timestamp": "0x1", "transactions": [TX]}
    )
    W._windows.clear()
    r = scan("ethereum", since=100, max_blocks=3)
    assert r["latest"] == 102 and r["n_txs"] == 2
    assert all("score" in t and "flags" in t for t in r["txs"])


def test_scan_cadena_invalida():
    try:
        scan("solana")
        assert False
    except ValueError:
        assert True
