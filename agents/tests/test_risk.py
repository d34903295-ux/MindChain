import sys; sys.path.insert(0, "..")
from agents.risk_scoring import score_wallet
from agents.wallet_intelligence import profile_wallet

def test_nueva_wallet_suma_riesgo():
    p = {"address": "0xabc", "tx_count": 1}
    s, f = score_wallet(p, [])
    assert s >= 30 and "wallet_nueva_pocas_txs" in f

def test_mixer_dispara():
    p = {"address": "0xabc", "tx_count": 5}
    txs = [{"from": "0xabc", "to": "0x4718614cF556Ec12b4A07C00eED8d568f719c808"}]
    s, f = score_wallet(p, txs)
    assert "interaccion_mezclador_conocido" in f
