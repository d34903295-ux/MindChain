import sys, pathlib
from fastapi import APIRouter
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.anomaly import scan_wallets

router = APIRouter()

class WalletItem(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    profile: dict = {}

class ScanRequest(BaseModel):
    items: list[WalletItem]
    contamination: float = 0.1

@router.post("/anomaly-scan")
def anomaly_scan(payload: ScanRequest):
    flags = scan_wallets([{"address": it.address, "profile": it.profile} for it in payload.items],
                         contamination=max(0.01, min(payload.contamination, 0.5)))
    return {"model": "isolation-forest", "n": len(flags),
            "anomalies": [f for f in flags if f.get("is_anomaly")], "all": flags}
