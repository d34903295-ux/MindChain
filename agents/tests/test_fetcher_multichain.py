from agents.fetcher import fetch_wallet_data, normalize_txs
import agents.fetcher as F

BS_ADDR = {"hash": "0xabc", "is_contract": False, "is_verified": False,
           "coin_balance": "1000000000000000000", "name": ""}
BS_TXS = {"items": [{"hash": "0x11", "from": {"hash": "0x" + "1" * 40},
                     "to": {"hash": "0x" + "2" * 40}, "value": "1000",
                     "timestamp": "2026-09-20T10:00:00Z", "block_number": 1}]}

def _fake_get(url, timeout=8):
    if url.endswith("/counters"):
        return {"transactions_count": 42}
    if url.endswith("/transactions"):
        return dict(BS_TXS)
    return dict(BS_ADDR)

def test_base_blockscout(monkeypatch):
    monkeypatch.setattr(F, "_http_get", _fake_get)
    r = fetch_wallet_data("0x" + "2" * 40, chain="base")
    assert r["source"] == "blockscout" and r["chain"] == "base"
    txs = normalize_txs("0x" + "2" * 40, r["calls"])
    assert txs[0]["from"] == "0x" + "1" * 40 and txs[0]["block"] == 1

def test_cadena_invalida():
    try:
        fetch_wallet_data("0x" + "2" * 40, chain="solana")
        assert False, "debió fallar"
    except ValueError:
        assert True

def test_fallback_rpc_si_blockchair_cae(monkeypatch):
    def boom(url, payload=None, timeout=8):
        raise RuntimeError("caído")
    monkeypatch.setattr(F, "_http_json", boom)
    r = fetch_wallet_data("0x" + "2" * 40, chain="ethereum")
    assert r["source"] == "rpc-fallback"
