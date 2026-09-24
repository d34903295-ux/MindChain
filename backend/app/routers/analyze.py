from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()

class AnalyzeRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = "ethereum"

@router.post("/analyze-wallet")
def analyze_wallet(payload: AnalyzeRequest):
    # Stub Fase 0 — la lógica real (Wallet Intelligence + Risk + Explanation) llega en Fase 1.
    return {
        "address": payload.address,
        "chain": payload.chain,
        "profile": {"tx_count": 0, "age_days": None, "counterparties": 0, "status": "stub-fase-0"},
        "risk_score": 0,
        "risk_factors": [],
        "explanation": "Stub Fase 0: backend conectado. Fase 1 implementará el análisis real.",
    }
