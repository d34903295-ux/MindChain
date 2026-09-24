"""Watcher en vivo (vigilancia autónoma): lee los últimos bloques por RPC,
normaliza cada transacción y los agentes la puntúan solos (mixer, ballena,
outlier vs mediana móvil, gas alto). Sin intervención del usuario.
"""
import time
import statistics
from collections import deque, defaultdict

from .chains import get_chain, chain_key, rpc_list
from .fetcher import _http_json
from .risk_scoring import MIXERS

WEI = 10 ** 18
ALERT_SCORE = 50
MAX_BLOCKS = 3

# mediana móvil por cadena con los últimos valores vistos
_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=500))


def _rpc(chain: str, method: str, params: list, timeout: int = 8):
    last = None
    for url in rpc_list(chain):
        try:
            d = _http_json(url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout)
            if isinstance(d, dict) and "result" in d and d["result"] is not None:
                return d["result"]
        except Exception as e:
            last = e
    raise RuntimeError(f"RPC {chain} no disponible: {str(last)[:120]}")


def get_latest_block(chain: str) -> int:
    return int(_rpc(chain, "eth_blockNumber", []), 16)


def get_block(chain: str, number: int, full: bool = True) -> dict:
    return _rpc(chain, "eth_getBlockByNumber", [hex(number), full])


def _h2i(h) -> int:
    try:
        return int(h, 16)
    except Exception:
        return 0


def norm_tx(t: dict, block: int | None = None) -> dict:
    value_wei = _h2i(t.get("value"))
    to = t.get("to")
    return {
        "hash": t.get("hash", ""),
        "block": block,
        "from": str(t.get("from", "")).lower(),
        "to": str(to).lower() if to else None,
        "value_wei": str(value_wei),
        "value_eth": round(value_wei / WEI, 6),
        "gas_price_gwei": round(_h2i(t.get("gasPrice")) / 1e9, 3),
        "nonce": _h2i(t.get("nonce")),
        "input_len": max(len(str(t.get("input", "0x"))) - 2, 0) // 2,
    }


def analyze_tx(tx: dict, median_eth: float | None) -> tuple[int, list[str]]:
    flags: list[str] = []
    score = 0
    if tx["from"] in MIXERS or (tx["to"] or "") in MIXERS:
        score += 60
        flags.append("mezclador_conocido")
    v = tx["value_eth"]
    if v >= 100:
        score += 25
        flags.append("ballena_100eth+")
    elif median_eth and median_eth > 0 and v >= 1 and v >= 20 * median_eth:
        score += 20
        flags.append(f"outlier_20x_mediana({median_eth:.4f})")
    if tx["to"] is None:
        score += 5
        flags.append("creacion_contrato")
    if tx["gas_price_gwei"] >= 200:
        score += 10
        flags.append("gas_alto")
    return min(score, 100), flags


def scan(chain: str = "ethereum", since: int | None = None, max_blocks: int = 2) -> dict:
    """Escanea bloques nuevos desde `since` (excluyente). Devuelve feed analizado."""
    key = chain_key(chain)
    get_chain(key)  # valida, lanza ValueError si no existe
    t0 = time.time()
    latest = get_latest_block(key)
    max_blocks = max(1, min(int(max_blocks or 1), MAX_BLOCKS))
    start = latest - max_blocks + 1
    if since is not None:
        try:
            start = max(start, int(since) + 1)
        except Exception:
            pass
    blocks, txs = [], []
    for n in range(max(start, 0), latest + 1):
        try:
            b = get_block(key, n)
        except Exception:
            continue
        items = b.get("transactions", []) or []
        if items and isinstance(items[0], str):
            continue  # llegaron hashes, no txs completas: saltar bloque
        blocks.append({"number": n, "time": b.get("timestamp", ""), "tx_count": len(items)})
        for raw in items:
            try:
                txs.append(norm_tx(raw, block=n))
            except Exception:
                continue
    win = _windows[key]
    out = []
    for tx in txs:
        med = statistics.median(win) if len(win) >= 10 else None
        score, flags = analyze_tx(tx, med)
        if tx["value_eth"] > 0:
            win.append(tx["value_eth"])
        out.append({**tx, "score": score, "flags": flags, "alert": score >= ALERT_SCORE})
    out.sort(key=lambda x: -x["score"])
    return {
        "chain": key,
        "latest": latest,
        "blocks": blocks,
        "txs": out,
        "alerts": [t for t in out if t["alert"]],
        "n_txs": len(out),
        "n_alerts": sum(1 for t in out if t["alert"]),
        "elapsed_s": round(time.time() - t0, 2),
    }
