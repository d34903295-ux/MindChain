from agents.report_agent import build_case_markdown
from agents.investigation import trace_from_txs

def test_markdown_contiene_secciones():
    wr = {"address": "0x" + "a" * 40, "chain": "ethereum",
          "profile": {"tx_count": 5, "age_days": 10, "activity": "baja", "balance_usd": 100.0, "labels": ["eoa"]},
          "risk_score": 30, "risk_factors": ["wallet_nueva_pocas_txs"],
          "explanation": "Riesgo medio.", "source": "mock", "elapsed_s": 0.5}
    txs = [{"hash": "0x01", "from": "0x" + "a" * 40, "to": "0x" + "b" * 40, "value_usd": 5.0, "time": "t", "block": 1}]
    md = build_case_markdown(wr, trace_from_txs("0x" + "a" * 40, txs))
    assert "# ChainMind" in md and "0x" + "a" * 40 in md
    assert "30/100" in md and "Trazado" in md and "Descargo" in md
