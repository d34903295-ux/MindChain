"""Watchlist de direcciones sensibles (screening, no veredicto).

Reglas de diseño:
- NO se hardcodean direcciones sin verificar: una dirección inventada genera
  falsos positivos y destruye la confianza en el score.
- Las direcciones se cargan de `agents/data/watchlist.json` o de una URL
  configurada en CHAINMIND_WATCHLIST_URL.
- Toda entrada debe estar normalizada a 42 chars (0x + 40 hex).
- Contexto: interacción con un mixer NO es por sí sola un delito; el factor
  se expresa como "señal de screening" y el reporte lo aclara.
"""
import json
import os
import pathlib
import re
import threading
import time
import urllib.request

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TTL = int(os.getenv("CHAINMIND_WATCHLIST_TTL", "21600"))
LOCAL = pathlib.Path(__file__).with_name("data") / "watchlist.json"

_lock = threading.Lock()
_cache: dict[str, object] = {"addresses": {}, "source": "vacio", "loaded_at": 0.0}


def _normalize(raw: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in raw.get("addresses", []) or []:
        if isinstance(entry, str):
            addr, label = entry, "watchlist"
        elif isinstance(entry, dict):
            addr, label = entry.get("address", ""), entry.get("label", "watchlist")
        else:
            continue
        addr = str(addr).strip().lower()
        if not ADDR_RE.match(addr):
            continue
        out[addr] = str(label)[:60]
    return out


def _load_local() -> dict[str, str]:
    try:
        if LOCAL.exists():
            return _normalize(json.loads(LOCAL.read_text(encoding="utf-8")))
    except Exception:
        return {}
    return {}


def _load_remote(url: str) -> dict[str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChainMind/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return _normalize(json.load(r))
    except Exception:
        return {}


def refresh(force: bool = False) -> dict[str, str]:
    now = time.time()
    with _lock:
        fresh = (now - float(_cache.get("loaded_at") or 0)) < TTL
        if fresh and not force:
            return _cache["addresses"]  # type: ignore[return-value]
    remote_url = os.getenv("CHAINMIND_WATCHLIST_URL", "")
    remote = _load_remote(remote_url) if remote_url else {}
    local = _load_local()
    merged = {**remote, **local}
    with _lock:
        _cache.update({
            "addresses": merged,
            "source": ("remote+local" if remote and local else "remote" if remote else "local" if local else "vacio"),
            "loaded_at": now,
        })
    return merged


def get(address: str) -> str | None:
    """Devuelve la etiqueta si la dirección está en la watchlist."""
    if not address:
        return None
    return refresh().get(str(address).strip().lower())


def size() -> int:
    return len(refresh())


def info() -> dict:
    refresh()
    with _lock:
        return {
            "size": len(_cache["addresses"]),
            "source": _cache["source"],
            "age_s": round(time.time() - float(_cache["loaded_at"]), 1),
        }
