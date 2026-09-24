import time, sys, pathlib
from fastapi import APIRouter
from pydantic import BaseModel, Field

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[3] / "agents").replace("\\agents", ""))
# importar agents como paquete desde raíz ChainMind
import os
ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from agents.fetcher import fetch_wallet_data
from agents.wallet_intelligence import build_profile
from agents.risk_scoring import score_wallet
from agents.explanation import explain

router = APIRouter()

class AnalyzeRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = "ethereum"

@router.post("/analyze-wallet")
def analyze_wallet(payload: AnalyzeRequest):
    t0 = time.time()
    fetched = fetch_wallet_data(payload.address)
    profile, txs = build_profile(payload.address, fetched)
    score, factors = score_wallet(profile, txs)
    text = explain(profile, score, factors)
    elapsed = round(time.time() - t0, 2)
    # persistencia best-effort (no romper MVP si DB caída)
    try:
        from app.db.postgres import upsert_wallet_report
        upsert_wallet_report(payload.address, profile, score, factors, text)
    except Exception:
        pass
    try:
        from app.db.neo4j_driver import save_wallet_graph
        save_wallet_graph(payload.address, profile, txs, score)
    except Exception:
        pass
    return {"address": payload.address, "chain": payload.chain, "profile": profile,
            "risk_score": score, "risk_factors": factors, "explanation": text,
            "elapsed_s": elapsed, "source": fetched.get("source")}
