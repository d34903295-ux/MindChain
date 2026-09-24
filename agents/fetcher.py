"""Fetcher on-demand multi-chain (Fase 5; sin duplicar codigo por cadena).
ethereum -> Blockchair (+fallback RPC). base -> Blockscout v2 (+fallback RPC).
Timeout global acotado para criterio <10s.
"""
import os, json, urllib.request
from .chains import get_chain, chain_key, rpc_list

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
    raw = {"type": "contract" if info.get("is_contract") else "account",
           "balance": str(coin), "balance_usd": 0.0,
           "transaction_count": max(n_count, len(items)),
           "is_verified": bool(info.get("is_verified")),
           "name": info.get("name") or "",
           "token_symbol": (info.get("token") or {}).get("symbol", "") if isinstance(info.get("token"), dict) else ""}
    return raw, items

def fetch_wallet_data(address, chain="ethereum", limit=25):
    key = chain_key(chain)
    cfg = get_chain(key)
    rpcs = rpc_list(key)
    adapter = cfg.get("adapter", "rpc")
    if adapter == "blockchair":
        try:
            raw, calls = fetch_blockchair(cfg["blockchair_slug"], address, limit)
            return {"raw_address": raw, "calls": calls, "rpc": {}, "source": "blockchair", "chain": key}
        except Exception:
            pass
    elif adapter == "blockscout":
        try:
            raw, calls = fetch_blockscout(cfg["blockscout"], address, limit)
            return {"raw_address": raw, "calls": calls, "rpc": {}, "source": "blockscout", "chain": key}
        except Exception:
            pass
    snap = rpc_snapshot(rpcs, address)
    code = snap.get("code", "0x")
    raw = {"type": "contract" if isinstance(code, str) and len(code) > 4 else "account",
           "balance": str(snap.get("balance_wei", 0)),
           "transaction_count": int(snap.get("tx_count", 0))}
    return {"raw_address": raw, "calls": [], "rpc": snap, "source": "rpc-fallback", "chain": key}

def normalize_txs(address, calls):
    txs = []
    for c in calls or []:
        if "transaction_hash" in c:
            txs.append({"hash": c.get("transaction_hash", ""),
                        "from": (c.get("sender") or "").lower(),
                        "to": (c.get("recipient") or "").lower() if c.get("recipient") else None,
                        "value_wei": c.get("value", 0), "value_usd": c.get("value_usd", 0),
                        "time": c.get("time", ""), "block": c.get("block_id")})
        else:
            f = c.get("from")
            t = c.get("to")
            f = (f.get("hash") if isinstance(f, dict) else f) or ""
            t = (t.get("hash") if isinstance(t, dict) else t) or ""
            txs.append({"hash": c.get("hash", ""), "from": str(f).lower(),
                        "to": str(t).lower() if t else None,
                        "value_wei": c.get("value", 0), "value_usd": 0,
                        "time": c.get("timestamp", ""), "block": c.get("block_number")})
    return txs
