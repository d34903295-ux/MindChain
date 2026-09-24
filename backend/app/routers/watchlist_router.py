"""Gestión de la watchlist: el usuario decide a quién se vigila.

Antes la watchlist era de solo lectura (JSON o URL), así que no había forma
de añadir una wallet ni desde la API ni desde la UI: el objetivo del producto
"vigila estas wallets" no se podía cumplir.

Al añadir se verifica el bytecode on-chain: un EOA (sin código) se rechaza
porque no puede ser un contrato y solo genera ruido. Si el RPC no responde se
marca `verificado: null` en vez de inventar un veredicto.
"""
import pathlib
import sys

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import watchlist
from agents.chains import get_chain

router = APIRouter()


class WatchAdd(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    label: str = Field(default="watchlist", max_length=60)
    chain: str = "ethereum"
    verify: bool = True


@router.get("/watchlist")
def list_watchlist():
    return {"addresses": watchlist.entries(), "info": watchlist.info()}


@router.post("/watchlist")
def add_watch(payload: WatchAdd):
    try:
        get_chain(payload.chain)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    res = watchlist.add(payload.address, payload.label, chain=payload.chain, verify=payload.verify)
    if not res.get("added") and "ya estaba" not in str(res.get("reason", "")):
        raise HTTPException(status_code=400, detail=res.get("reason", "no se pudo añadir"))
    return res


@router.delete("/watchlist/{address}")
def remove_watch(address: str):
    return watchlist.remove(address)
