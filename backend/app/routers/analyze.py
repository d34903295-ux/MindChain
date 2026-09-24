import time, sys, pathlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.chains import get_chain
from agents.fetcher import fetch_wallet_data
from agents.wallet_intelligence import build_profile
from agents.risk_scoring import score_wallet
from agents.explanation import explain
from agents.alerts import alert_if_risky

router = APIRouter()

class AnalyzeRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = "ethereum"

@router.post("/analyze-wallet")
def analyze_wallet(payload: AnalyzeRequest):
    try:
        get_chain(payload.chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    t0 = time.time()
    fetched = fetch_wallet_data(payload.address, chain=payload.chain)
    profile, txs = build_profile(payload.address, fetched)
    score, factors = score_wallet(profile, txs)
    text = explain(profile, score, factors)
    elapsed = round(time.time() - t0, 2)
    try:
        from app.db.postgres import upsert_wallet_report
        upsert_wallet_report(payload.address, profile, score, factors, text)
    except Exception:
        pass
    try:
        from app.db.neo4j_driver import save_wallet_graph
        save_wallet_graph(payload.address, profile, txs, score, chain=payload.chain.lower())
    except Exception:
        pass
    alert = alert_if_risky("wallet", payload.address, payload.chain.lower(), score, factors)
    return {"address": payload.address, "chain": payload.chain.lower(), "profile": profile,
            "risk_score": score, "risk_factors": factors, "explanation": text,
            "elapsed_s": elapsed, "source": fetched.get("source"),
            "cached": bool(fetched.get("cached")), "alert": alert}
