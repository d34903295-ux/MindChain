"""Estado operacional: precio, watchlist, cachés, centinela y job ML.

Existe para auditar el sistema sin abrir logs: qué fuente responde, cuánto
tiempo lleva el centinela corriendo y qué anomalías encontró el último job.
"""
import json
import pathlib
import sys

from fastapi import APIRouter

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from agents import price, sentinel, watchlist
from agents import llm
from agents.chains import supported
from agents.fetcher import cache_stats
from app.guard import stats as guard_stats

router = APIRouter()


def latest_anomaly_job() -> dict:
    """Último reporte del job nocturno (Isolation Forest)."""
    reports = sorted((ROOT / "reports").glob("anomalies-*.json"), reverse=True)
    if not reports:
        return {"exists": False, "hint": "python jobs/nightly_anomaly.py"}
    try:
        data = json.loads(reports[0].read_text(encoding="utf-8"))
        return {
            "exists": True,
            "file": reports[0].name,
            "generated_at": data.get("generated_at"),
            "n_wallets": data.get("n_wallets"),
            "n_anomalies": data.get("n_anomalies"),
            "model": "isolation-forest",
            "top": (data.get("anomalies") or [])[:3],
        }
    except Exception as e:
        return {"exists": True, "file": reports[0].name, "error": str(e)[:80]}


@router.get("/status")
def status():
    price.get_price_usd()  # calienta la caché para reportar el estado real
    return {
        "ok": True,
        "chains": supported(),
        "price": price.cache_info(),
        "watchlist": watchlist.info(),
        "fetch_cache": cache_stats(),
        "guard": guard_stats(),
        "ia": llm.status(),
        "sentinel": sentinel.status(),
        "anomaly_job": latest_anomaly_job(),
    }


@router.get("/anomaly/latest")
def anomaly_latest():
    return latest_anomaly_job()
