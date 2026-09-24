import sys, pathlib, re
from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.chains import get_chain
from agents.fetcher import fetch_wallet_data
from agents.wallet_intelligence import build_profile
from agents.risk_scoring import score_wallet
from agents.explanation import explain
from agents.investigation import trace_from_txs, neo4j_expand, build_edges
from agents.report_agent import build_case_markdown

router = APIRouter()

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BURN = {"0x" + "0" * 40, "0x" + "d" * 40}


def _validate_address(address: str) -> str:
    if not isinstance(address, str) or not ADDR_RE.match(address):
        raise HTTPException(status_code=400, detail="dirección inválida: se espera 0x + 40 caracteres hex")
    low = address.lower()
    if low in BURN:
        raise HTTPException(status_code=400, detail="esa dirección no tiene historial (null/burn)")
    return low


@router.post("/investigate")
def investigate(payload: dict):
    address = _validate_address(str(payload.get("address", "")))
    depth = int(payload.get("max_depth", 3))
    direction = str(payload.get("direction", "both"))
    chain = str(payload.get("chain", "ethereum"))
    try:
        get_chain(chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fetched = fetch_wallet_data(address, chain=chain)
    _, txs = build_profile(address, fetched)
    extra = neo4j_expand(address)
    if extra.get("edges"):
        txs = txs + [{"hash": e["hash"], "from": e["from"], "to": e["to"],
                      "value_usd": e["value_usd"], "time": "", "block": None} for e in extra["edges"]]
    trace = trace_from_txs(address, txs, max_depth=max(1, min(depth, 5)), direction=direction)
    trace["neo4j"] = extra.get("source")
    return trace

@router.get("/report/{address}")
def report(address: str, max_depth: int = 3, chain: str = "ethereum"):
    address = _validate_address(address)
    try:
        get_chain(chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    fetched = fetch_wallet_data(address, chain=chain)
    profile, txs = build_profile(address, fetched)
    score, factors = score_wallet(profile, txs)
    text = explain(profile, score, factors)
    wr = {"address": address, "chain": chain.lower(), "profile": profile,
          "risk_score": score, "risk_factors": factors, "explanation": text,
          "elapsed_s": 0, "source": fetched.get("source")}
    trace = trace_from_txs(address, txs, max_depth=max(1, min(max_depth, 5)), direction="both")
    md = build_case_markdown(wr, trace)
    return PlainTextResponse(content=md, media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": "attachment; filename=case-" + address[:12] + ".md"})
