"""Endpoints de sincronización con el vault de Obsidian.

Principio: Obsidian es un extra. Si el vault no existe o falla, el análisis
sigue funcionando; reportamos el estado en lugar de romper.
"""
import pathlib
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import obsidian
from agents.fetcher import fetch_wallet_data
from agents.wallet_intelligence import build_profile
from agents.risk_scoring import score_wallet
from agents.explanation import explain
from agents import watcher

router = APIRouter()


class AddressBody(BaseModel):
    address: str
    chain: str = "ethereum"


@router.get("/obsidian/status")
def obsidian_status():
    return obsidian.status()


@router.post("/obsidian/sync/wallet")
def sync_wallet(body: AddressBody):
    if not body.address.lower().startswith("0x") or len(body.address) != 42:
        raise HTTPException(status_code=400, detail="dirección inválida")
    fetched = fetch_wallet_data(body.address, chain=body.chain)
    profile, txs = build_profile(body.address, fetched)
    score, factors = score_wallet(profile, txs)
    report = {
        "address": body.address,
        "chain": body.chain.lower(),
        "profile": profile,
        "risk_score": score,
        "risk_factors": factors,
        "explanation": explain(profile, score, factors),
        "elapsed_s": 0,
        "source": fetched.get("source"),
    }
    res = obsidian.sync_wallet(report)
    res["risk_score"] = score
    res["annotations"] = obsidian.read_annotations(body.address)
    return res


@router.post("/obsidian/sync/contract")
def sync_contract(body: AddressBody):
    from agents.contract_analyzer import fetch_contract, analyze_contract

    fetched = fetch_contract(body.address, chain=body.chain)
    rep = analyze_contract(body.address, fetched)
    rep["chain"] = body.chain.lower()
    rep["source_origin"] = fetched.get("source_origin")
    return obsidian.sync_contract(rep)


@router.post("/obsidian/sync/digest")
def sync_digest(chain: str = "ethereum"):
    try:
        feed = watcher.scan(chain, max_blocks=2)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"no se pudo leer la red: {str(e)[:80]}")
    res = obsidian.sync_daily_digest(feed)
    alerts = []
    for tx in (feed.get("alerts") or [])[:5]:
        try:
            r = obsidian.sync_alert(tx, chain)
            if r.get("written"):
                alerts.append(r.get("path"))
        except Exception:
            pass
    res["alerts_written"] = alerts
    res["n_alerts"] = feed.get("n_alerts")
    return res


@router.post("/obsidian/sync/index")
def sync_index():
    return obsidian.build_index()


@router.get("/obsidian/annotations/{address}")
def annotations(address: str):
    return {"address": address, "annotations": obsidian.read_annotations(address)}
