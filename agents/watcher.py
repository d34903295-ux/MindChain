"""Watcher en vivo (vigilancia autónoma): lee los últimos bloques por RPC,
normaliza cada transacción y los agentes la puntúan solos (mixer, ballena,
outlier vs mediana móvil, gas alto). Sin intervención del usuario.
"""
import time
import statistics
from collections import deque, defaultdict

from .chains import get_chain, chain_key, rpc_list
from .fetcher import _http_json
from . import watchlist

WEI = 10 ** 18
ALERT_SCORE = 50
MAX_BLOCKS = 3
MIN_MEDIAN_SAMPLES = 30
MAD_Z_THRESHOLD = 12.0
MAD_MIN_VALUE_ETH = 1.0

# mediana móvil por cadena con los últimos valores vistos
_windows: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
# hashes ya alertados (evita duplicar alertas entre polls)
_alerted: dict[str, set] = defaultdict(set)


def robust_z(value: float, median: float, mad: float) -> float:
    """z-score robusto (basado en mediana y MAD). Resiste outliers extremos.

    Se usa en vez del z-score clásico porque un solo movimiento enorme
    deformaría la media y la desviación estándar de toda la ventana.
    """
    if mad <= 0:
        return 0.0
    return (value - median) / (1.4826 * mad)


def window_stats(values) -> tuple[float | None, float | None]:
    """(mediana, MAD) de una ventana de valores; None si no hay muestra suficiente."""
    data = [float(v) for v in values if v is not None]
    if len(data) < MIN_MEDIAN_SAMPLES:
        return None, None
    med = statistics.median(data)
    mad = statistics.median([abs(v - med) for v in data])
    return med, mad


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


def analyze_tx(tx: dict, median_eth: float | None, mad: float | None = None) -> tuple[int, list[str]]:
    """Score heurístico por transacción. Solo escala a alerta con evidencia clara.

    Combina dos señales:
    - absoluta: movimientos enormes ( ETH) son relevantes en cualquier cadena
    - relativa: outlier frente a la distribución actual de ESA red (MAD)
    """
    flags: list[str] = []
    score = 0
    wl = watchlist.get(tx["from"]) or watchlist.get(tx["to"] or "")
    if wl:
        score += 60
        flags.append("watchlist:" + wl)
    v = tx["value_eth"]
    if v >= 1_000:
        # movimientos de 6 cifras en ETH: deben cruzar el umbral de alerta solos
        score += 60
        flags.append("ballena_1000eth+")
    elif v >= 100:
        score += 30
        flags.append("ballena_100eth+")
    if median_eth and median_eth > 0 and v >= 1:
        ratio = v / median_eth
        if ratio >= 100:
            score += 25
            flags.append(f"outlier_{int(ratio)}x_mediana")
        elif ratio >= 20:
            score += 15
            flags.append(f"outlier_{int(ratio)}x_mediana")
    # señal estadística robusta: se adapta a la red (en Base 100 ETH es normal)
    if mad is not None and v >= MAD_MIN_VALUE_ETH:
        z = robust_z(v, median_eth or 0.0, mad)
        if z >= MAD_Z_THRESHOLD:
            score += 20
            flags.append(f"outlier_estadistico_z{z:.0f}")
    if tx["to"] is None:
        score += 5
        flags.append("creacion_contrato")
    if tx["gas_price_gwei"] >= 300:
        score += 12
        flags.append("gas_muy_alto")
    elif tx["gas_price_gwei"] >= 150:
        score += 6
        flags.append("gas_alto")
    if tx["input_len"] >= 1_000:
        score += 5
        flags.append("payload_grande")
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
    med, mad = window_stats(win)
    seen_in_batch = set()
    for tx in txs:
        h = tx.get("hash")
        if h and h in seen_in_batch:
            continue
        if h:
            seen_in_batch.add(h)
        score, flags = analyze_tx(tx, med, mad)
        if tx["value_eth"] > 0:
            win.append(tx["value_eth"])
        out.append({**tx, "score": score, "flags": flags, "alert": score >= ALERT_SCORE})
    out.sort(key=lambda x: -x["score"])
    # conserva hashes vistos para no re-alertar en el siguiente poll
    newly_alerted = []
    alerted = _alerted[key]
    for t in out:
        if t["alert"] and t["hash"] not in alerted:
            newly_alerted.append(t)
            alerted.add(t["hash"])
        if len(alerted) > 2000:
            alerted.clear()
    return {
        "chain": key,
        "latest": latest,
        "blocks": blocks,
        "txs": out,
        "alerts": [t for t in out if t["alert"]],
        "new_alerts": newly_alerted,
        "n_txs": len(out),
        "n_alerts": sum(1 for t in out if t["alert"]),
        "n_new_alerts": len(newly_alerted),
        "median_eth": round(med, 6) if med is not None else None,
        "mad_eth": round(mad, 6) if mad is not None else None,
        "baseline_samples": len(win),
        "detectors": ["absoluto", "mediana-red", "mad-z-robusto", "watchlist"],
        "elapsed_s": round(time.time() - t0, 2),
    }
