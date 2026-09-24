import time, sys, pathlib
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.chains import get_chain
from agents.contract_analyzer import fetch_contract, analyze_contract
from agents.alerts import alert_if_risky

router = APIRouter()

class ContractRequest(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    chain: str = "ethereum"

@router.post("/analyze-contract")
def analyze_contract_ep(payload: ContractRequest):
    try:
        get_chain(payload.chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    t0 = time.time()
    fetched = fetch_contract(payload.address, chain=payload.chain)
    rep = analyze_contract(payload.address, fetched)
    rep["chain"] = payload.chain.lower()
    rep["elapsed_s"] = round(time.time() - t0, 2)
    try:
        from app.db.neo4j_driver import get_driver
        d = get_driver()
        with d.session() as s:
            s.run("MERGE (c:Contract {address:$a, chain:$ch}) SET c.riskScore=$s, c.verified=$v",
                  a=payload.address.lower(), ch=payload.chain.lower(),
                  s=int(rep["risk_score"]), v=bool(rep["verified"]))
    except Exception:
        pass
    rep["alert"] = alert_if_risky("contract", payload.address, payload.chain.lower(),
                                  rep["risk_score"], rep.get("permissions", []))
    return rep
