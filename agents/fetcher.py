"""Fetcher on-demand multi-chain (Fase 5; sin duplicar codigo por cadena).
ethereum -> Blockchair (+fallback RPC). base -> Blockscout v2 (+fallback RPC).
Timeout global acotado para criterio <10s.
"""
import os, json, time, threading, urllib.request
from .chains import get_chain, chain_key, rpc_list
from .price import get_price_usd

CACHE_TTL = int(os.getenv("CHAINMIND_FETCH_TTL", "20"))
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()


def _cache_get(key: str):
    with _cache_lock:
        hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    return None


def _cache_put(key: str, value: dict):
    with _cache_lock:
        _cache[key] = (time.time(), value)
    return value


def cache_stats() -> dict:
    with _cache_lock:
        return {"entries": len(_cache), "ttl_s": CACHE_TTL}

def _http_json(url, payload=None, timeout=8):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", "User-Agent": "ChainMind/1.0"}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def _http_get(url, timeout=8):
    req = urllib.request.Request(url, headers={"User-Agent": "ChainMind/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def _rpc_call(rpc_url, method, params, timeout=5):
    try:
        d = _http_json(rpc_url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout)
        if isinstance(d, dict) and "result" in d:
            return d["result"]
    except Exception:
        return None
    return None

def _rpc_first(rpcs, method, params, timeout=5):
    for rpc in rpcs:
        if not rpc:
            continue
        v = _rpc_call(rpc, method, params, timeout)
        if v is not None:
            return v
    return None

def rpc_snapshot(rpcs, address):
    bal = _rpc_first(rpcs, "eth_getBalance", [address, "latest"])
    ntx = _rpc_first(rpcs, "eth_getTransactionCount", [address, "latest"])
    code = _rpc_first(rpcs, "eth_getCode", [address, "latest"])
    def h2i(h):
        try:
            return int(h, 16)
        except Exception:
            return 0
    return {"balance_wei": h2i(bal) if isinstance(bal, str) else 0,
            "tx_count": h2i(ntx) if isinstance(ntx, str) else 0,
            "code": code if isinstance(code, str) else "0x"}

def fetch_blockchair(slug, address, limit=25):
    url = "https://api.blockchair.com/" + slug + "/dashboards/address/" + address + "?limit=" + str(limit)
    d = _http_json(url, timeout=8)
    data = d.get("data", {})
    blob = data.get(address) or data.get(address.lower()) or {}
    if not blob:
        raise RuntimeError("blockchair sin datos")
    return blob.get("address", {}), blob.get("calls", []) or []

def fetch_blockscout(base_url, address, limit=25):
    info = _http_get(base_url + "/addresses/" + address, timeout=8)
    try:
        counters = _http_get(base_url + "/addresses/" + address + "/counters", timeout=8)
    except Exception:
        counters = {}
    txs = _http_get(base_url + "/addresses/" + address + "/transactions", timeout=8)
    items = (txs.get("items", []) or [])[:limit]
    coin = info.get("coin_balance") or "0"
    try:
        n_count = int(counters.get("transactions_count") or 0)
    except Exception:
        n_count = 0
    # El endpoint /counters de Blockscout es inconsistente: el mismo contrato
    # devolvió 2, 9, 43 y 984 en distintas llamadas. No propagamos ese número:
    # el perfil muestra "n/d" y los heurísticos que dependen del histórico se
    # desactivan. La muestra de transacciones sí es real y se sigue usando.
    raw = {"type": "contract" if info.get("is_contract") else "account",
           "balance": str(coin), "balance_usd": 0.0,
           "transaction_count": None,
           "tx_count_reliable": False,
           "counter_raw": n_count,
           "is_verified": bool(info.get("is_verified")),
           "name": info.get("name") or "",
           "token_symbol": (info.get("token") or {}).get("symbol", "") if isinstance(info.get("token"), dict) else ""}
    return raw, items

def fetch_wallet_data(address, chain="ethereum", limit=25, use_cache=True):
    key = chain_key(chain)
    cfg = get_chain(key)
    rpcs = rpc_list(key)
    adapter = cfg.get("adapter", "rpc")
    cache_key = f"wallet:{key}:{address.lower()}:{limit}"
    if use_cache:
        hit = _cache_get(cache_key)
        if hit is not None:
            return {**hit, "cached": True}

    result = None
    if adapter == "blockchair":
        try:
            raw, calls = fetch_blockchair(cfg["blockchair_slug"], address, limit)
            result = {"raw_address": raw, "calls": calls, "rpc": {}, "source": "blockchair", "chain": key}
        except Exception:
            pass
    elif adapter == "blockscout":
        try:
            raw, calls = fetch_blockscout(cfg["blockscout"], address, limit)
            result = {"raw_address": raw, "calls": calls, "rpc": {}, "source": "blockscout", "chain": key}
        except Exception:
            pass

    if result is None:
        snap = rpc_snapshot(rpcs, address)
        code = snap.get("code", "0x")
        raw = {"type": "contract" if isinstance(code, str) and len(code) > 4 else "account",
               "balance": str(snap.get("balance_wei", 0)),
               "transaction_count": int(snap.get("tx_count", 0))}
        result = {"raw_address": raw, "calls": [], "rpc": snap, "source": "rpc-fallback", "chain": key}

    result["cached"] = False
    return _cache_put(cache_key, result)

WEI = 10 ** 18


def _hex_to_int(v, default: int = 0) -> int:
    """Convierte a int aceptando: int, '0x10' o hex sin prefijo (Blockscout: 'ff').

    Blockchair devuelve int; Blockscout devuelve hex sin prefijo. Por eso una
    cadena sin '0x' se interpreta como hex: es el único formato posible ahí.
    """
    if v is None:
        return default
    if isinstance(v, int):
        return v
    s = str(v).strip()
    if not s:
        return default
    try:
        if s.lower().startswith("0x"):
            return int(s, 16)
    except ValueError:
        return default
    try:
        return int(s, 16)  # hex sin prefijo
    except ValueError:
        pass
    try:
        return int(float(s))
    except ValueError:
        return default


def normalize_txs(address, calls):
    """Normaliza llamadas de cualquier adapter a un esquema común.

    - Blockchair: value ya en wei (int), value_usd en USD
    - Blockscout: value en wei HEX, sin value_usd -> se calcula con precio cacheado
    """
    price = get_price_usd()
    out = []
    for c in calls or []:
        if not isinstance(c, dict):
            continue
        if "transaction_hash" in c:
            wei = _hex_to_int(c.get("value"))
            usd = c.get("value_usd")
            eth = wei / WEI
            if usd is None and price:
                usd = eth * price
            out.append({
                "hash": c.get("transaction_hash", ""),
                "from": (c.get("sender") or "").lower(),
                "to": (c.get("recipient") or "").lower() if c.get("recipient") else None,
                "value_wei": str(wei),
                "value_eth": round(eth, 8),
                "value_usd": round(float(usd), 2) if usd is not None else None,
                "time": c.get("time", ""),
                "block": c.get("block_id"),
            })
        else:
            f = c.get("from")
            t = c.get("to")
            f = (f.get("hash") if isinstance(f, dict) else f) or ""
            t = (t.get("hash") if isinstance(t, dict) else t) or ""
            wei = _hex_to_int(c.get("value"))
            eth = wei / WEI
            usd = eth * price if price else None
            out.append({
                "hash": c.get("hash", ""),
                "from": str(f).lower(),
                "to": str(t).lower() if t else None,
                "value_wei": str(wei),
                "value_eth": round(eth, 8),
                "value_usd": round(usd, 2) if usd is not None else None,
                "time": c.get("timestamp", ""),
                "block": c.get("block_number"),
            })
    return out
