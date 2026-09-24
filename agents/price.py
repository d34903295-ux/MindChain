"""Precio nativo con caché TTL.

Fuente pública sin API key (CoinGecko simple/price) + fallback a null.
Null NO se convierte en 0: los campos USD quedan en None para no mentir.
"""
import json
import os
import threading
import time
import urllib.request

TTL_SECONDS = int(os.getenv("CHAINMIND_PRICE_TTL", "600"))
# Fuentes en orden de preferencia. Todas públicas y sin API key.
SOURCES = (
    ("coingecko", "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"),
    ("coinbase", "https://api.coinbase.com/v2/prices/ETH-USD/spot"),
    ("kraken", "https://api.kraken.com/0/public/Ticker?pair=ETHUSD"),
)

_lock = threading.Lock()
_cache: dict[str, tuple[float, float | None, str]] = {}


def _parse(name: str, data: dict) -> float | None:
    try:
        if name == "coingecko":
            v = data.get("ethereum", {}).get("usd")
        elif name == "coinbase":
            v = data.get("data", {}).get("amount")
        elif name == "kraken":
            result = data.get("result", {})
            pair = next(iter(result.values()))
            v = pair.get("c", [None])[0]
        else:
            v = None
        return float(v) if v else None
    except Exception:
        return None


def _fetch() -> tuple[float | None, str]:
    for name, url in SOURCES:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ChainMind/1.0"})
            with urllib.request.urlopen(req, timeout=4) as r:
                data = json.load(r)
            price = _parse(name, data)
            if price and price > 0:
                return price, name
        except Exception:
            continue
    return None, "sin_fuente"


def get_price_usd(force: bool = False) -> float | None:
    """Precio de ETH en USD, cacheado. None si no hay fuente disponible."""
    now = time.time()
    with _lock:
        hit = _cache.get("eth_usd")
        if hit and not force and now - hit[0] < TTL_SECONDS:
            return hit[1]
    price, source = _fetch()
    with _lock:
        _cache["eth_usd"] = (now, price, source)
    return price


def cache_info() -> dict:
    with _lock:
        hit = _cache.get("eth_usd")
    if not hit:
        return {"cached": False, "price_usd": None, "source": "sin_cargar"}
    return {
        "cached": True,
        "price_usd": hit[1],
        "source": hit[2],
        "age_s": round(time.time() - hit[0], 1),
        "ttl_s": TTL_SECONDS,
    }
