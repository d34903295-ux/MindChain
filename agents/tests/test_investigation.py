from agents.investigation import trace_from_txs

def _tx(f, t, h):
    return {"hash": h, "from": f, "to": t, "value_usd": 1.0, "time": "2026-09-20 10:00:00", "block": 1}

A, B, C, D, X, Y = "0x" + "a" * 40, "0x" + "b" * 40, "0x" + "c" * 40, "0x" + "d" * 40, "0x" + "x" * 40, "0x" + "y" * 40
TXS = [_tx(A, B, "0x01"), _tx(B, C, "0x02"), _tx(A, D, "0x03"), _tx(X, Y, "0x04")]

def test_rutas_profundidad2():
    t = trace_from_txs(A, TXS, max_depth=2)
    assert [A, B, C] in t["paths"] and [A, D] in t["paths"]
    assert t["n_nodes"] == 4 and X not in t["nodes"]

def test_profundidad1_corta():
    t = trace_from_txs(A, TXS, max_depth=1)
    assert [A, B, C] not in t["paths"] and [A, B] in t["paths"]

def test_direccion_in():
    t = trace_from_txs(C, TXS, max_depth=2, direction="in")
    assert [C, B, A] in t["paths"]

def test_desconocida_vacia():
    t = trace_from_txs("0x" + "9" * 40, TXS)
    assert t["paths"] == [] and t["n_nodes"] == 1
