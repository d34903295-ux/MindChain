"""Feed de vigilancia en vivo: últimas transacciones de la red, ya analizadas."""
import pathlib
import sys

from fastapi import APIRouter, HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.guard import Busy, MAX_BLOCKS, work
from agents import watcher
from agents.chains import get_chain, supported

router = APIRouter()


@router.get("/chains")
def list_chains():
    return {"chains": supported()}


@router.get("/feed/{chain}")
def feed(chain: str, since: int | None = None, max_blocks: int = 2):
    try:
        get_chain(chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if max_blocks < 1:
        raise HTTPException(status_code=400, detail="max_blocks debe ser >= 1")
    capped = min(max_blocks, MAX_BLOCKS)
    workload = f"feed:{chain}"
    try:
        with work(workload, key=f"{since or 0}:{capped}") as slot:
            cached = slot.reuse()
            if cached is not None:
                return {**cached, "deduped": True}
            result = watcher.scan(chain, since=since, max_blocks=capped)
            if capped < max_blocks:
                result = {**result, "max_blocks_capped": MAX_BLOCKS}
            return slot.remember(result)
    except Busy as e:
        raise HTTPException(status_code=429, detail=str(e), headers={"Retry-After": str(e.retry_after)})
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
