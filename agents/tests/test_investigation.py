import agents.investigation as I
from agents.investigation import trace_from_txs


def _tx(f, t, h, usd=1.0):
    return {"hash": h, "from": f, "to": t, "value_usd": usd,
            "time": "2026-09-20 10:00:00", "block": 1}


A, B, C, D, X, Y = ("0x" + c * 40 for c in "abcdxy")
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


def test_deduplica_tx_repetidas():
    """La misma tx puede llegar de Blockchair y Neo4j: no debe duplicar aristas."""
    txs = TXS + [_tx(A, B, "0x01")]
    t = trace_from_txs(A, txs, max_depth=1)
    assert len([e for e in t["edges"] if e["hash"] == "0x01"]) == 1


def test_ordena_rutas_por_valor():
    txs = [_tx(A, B, "0x01", usd=10.0), _tx(B, C, "0x02", usd=10.0),
           _tx(A, D, "0x03", usd=99_000.0)]
    t = trace_from_txs(A, txs, max_depth=2)
    assert t["paths"][0] == [A, D]           # la ruta más cara primero
    assert t["path_values_usd"][0] == 99_000.0
    assert t["total_traced_usd"] == 99_020.0


def test_marca_nodos_watchlist(monkeypatch):
    monkeypatch.setattr(I.watchlist, "get", lambda a: "pool" if a == C else None)
    t = trace_from_txs(A, TXS, max_depth=2)
    assert t["watchlist_nodes"] == [{"address": C, "label": "pool"}]


def test_filtro_por_valor_minimo():
    txs = [_tx(A, B, "0x01", usd=1.0), _tx(A, D, "0x03", usd=50_000.0)]
    t = trace_from_txs(A, txs, max_depth=1, min_value_usd=1000.0)
    assert [A, D] in t["paths"] and [A, B] not in t["paths"]
