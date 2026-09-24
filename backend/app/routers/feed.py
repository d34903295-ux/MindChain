"""Feed de vigilancia en vivo: últimas transacciones de la red, ya analizadas."""
import sys
import pathlib
from fastapi import APIRouter, HTTPException

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.chains import get_chain, supported
from agents import watcher

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
    try:
        return watcher.scan(chain, since=since, max_blocks=max_blocks)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
