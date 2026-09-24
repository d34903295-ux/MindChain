from agents.investigation import trace_from_txs
from agents.report_agent import build_case_markdown, _esc

A = "0x" + "a" * 40
B = "0x" + "b" * 40


def _wr(**over):
    base = {
        "address": A,
        "chain": "ethereum",
        "profile": {"tx_count": 5, "age_days": 10, "activity": "baja", "balance_usd": 100.0,
                    "labels": ["eoa"], "sample_size": 5, "sample_confidence": "baja"},
        "risk_score": 30,
        "risk_factors": ["wallet_nueva_pocas_txs"],
        "explanation": "Riesgo medio.",
        "source": "mock",
        "elapsed_s": 0.5,
        "data_quality": {},
    }
    base.update(over)
    return base


def test_markdown_contiene_secciones():
    txs = [{"hash": "0x01", "from": A, "to": B, "value_usd": 5.0, "time": "t", "block": 1}]
    md = build_case_markdown(_wr(), trace_from_txs(A, txs))
    assert "# ChainMind" in md and A in md
    assert "30/100" in md and "Trazado" in md
    assert "No constituye acusación" in md


def test_score_none_no_se_inventa_cero():
    md = build_case_markdown(
        _wr(risk_score=None, risk_factors=["datos_insuficientes_no_evaluable"],
            data_quality={"errors": ["rpc: ninguna cadena RPC respondio"]}),
        {"paths": [], "nodes": [], "edges": [], "n_paths": 0, "n_nodes": 0},
    )
    assert "No evaluable" in md
    assert "0/100" not in md
    assert "degradada" in md


def test_escapa_markdown_inyectado():
    """Un flag de la cadena con Markdown no puede romper el reporte."""
    md = build_case_markdown(
        _wr(risk_factors=["interaccion_watchlist:[evil](http://x) **inyectado**"]),
        {"paths": [], "nodes": [], "edges": [], "n_paths": 0, "n_nodes": 0},
    )
    assert "](http://x)" not in md
    assert "\\[evil\\]" in md
    assert "\\*\\*inyectado\\*\\*" in md


def test_escapa_caracteres_basicos():
    assert _esc("a|b") == "a\\|b"
    assert _esc("<script>") == "&lt;script&gt;"
    assert _esc("#titulo") == "\\#titulo"


def test_no_rompe_con_valores_none():
    md = build_case_markdown(
        _wr(profile={"tx_count": None, "age_days": None, "labels": None}),
        {"paths": [], "nodes": [], "edges": [], "n_paths": 0, "n_nodes": 0},
    )
    assert "n/d" in md
    assert "None" not in md


def test_reporta_watchlist_en_ruta():
    txs = [{"hash": "0x01", "from": A, "to": B, "value_usd": 5.0, "time": "t", "block": 1}]
    tr = trace_from_txs(A, txs)
    tr["watchlist_nodes"] = [{"address": B, "label": "pool"}]
    md = build_case_markdown(_wr(), tr)
    assert "watchlist" in md and "pool" in md
