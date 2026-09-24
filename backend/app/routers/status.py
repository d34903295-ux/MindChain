"""Estado operacional: precio, watchlist, cachés y agentes. Para auditar sin logs."""
from fastapi import APIRouter

import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents import price, watchlist
from agents.fetcher import cache_stats
from agents.chains import supported

router = APIRouter()


@router.get("/status")
def status():
    price.get_price_usd()  # calienta la caché para reportar el estado real
    return {
        "ok": True,
        "chains": supported(),
        "price": price.cache_info(),
        "watchlist": watchlist.info(),
        "fetch_cache": cache_stats(),
    }
