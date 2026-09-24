import sys

sys.path.insert(0, "..")
import agents.watchlist as watchlist
from agents.risk_scoring import score_wallet

WATCHED = "0x" + "ab" * 20


def test_nueva_wallet_suma_riesgo():
    p = {"address": "0xabc", "tx_count": 1}
    s, f = score_wallet(p, [])
    assert s >= 30 and "wallet_nueva_pocas_txs" in f


def test_watchlist_dispara(monkeypatch):
    # la watchlist está vacía por defecto: inyectamos una entrada en la prueba
    monkeypatch.setattr(watchlist, "refresh", lambda: {WATCHED: "pool-test"})
    p = {"address": "0xabc", "tx_count": 50, "age_days": 400}
    txs = [{"from": "0xabc", "to": WATCHED, "value_usd": 10}]
    s, f = score_wallet(p, txs)
    assert "interaccion_watchlist:pool-test" in f
    assert s >= 50


def test_sin_watchlist_no_hay_factor(monkeypatch):
    monkeypatch.setattr(watchlist, "refresh", lambda: {})
    p = {"address": "0xabc", "tx_count": 50, "age_days": 400}
    txs = [{"from": "0xabc", "to": "0x" + "cd" * 20, "value_usd": 10}]
    s, f = score_wallet(p, txs)
    assert not any(x.startswith("interaccion_watchlist") for x in f)
