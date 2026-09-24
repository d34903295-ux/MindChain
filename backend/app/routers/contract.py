import time, sys, pathlib
from fastapi import APIRouter
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.contract_analyzer import fetch_contract, analyze_contract

router = APIRouter()

class ContractRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = "ethereum"

@router.post("/analyze-contract")
def analyze_contract_ep(payload: ContractRequest):
    t0 = time.time()
    fetched = fetch_contract(payload.address)
    rep = analyze_contract(payload.address, fetched)
    rep["chain"] = payload.chain
    rep["elapsed_s"] = round(time.time() - t0, 2)
    try:
        from app.db.neo4j_driver import get_driver
        d = get_driver()
        with d.session() as s:
            s.run("MERGE (c:Contract {address:$a, chain:'ethereum'}) SET c.riskScore=$s, c.verified=$v",
                  a=payload.address.lower(), s=int(rep["risk_score"]), v=bool(rep["verified"]))
    except Exception:
        pass
    return rep
