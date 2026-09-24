"""Fetcher on-demand Ethereum mainnet (Fase 1 MVP <10s).
Primaria: Blockchair dashboards/address (sin API key).
Fallback: RPC público eth_getBalance / eth_getTransactionCount / eth_getCode.
Timeout global ~8s para cumplir criterio <10s.
"""
import os, time, json, urllib.request

BLOCKCHAIR = "https://api.blockchair.com/ethereum/dashboards/address"
RPCS = [
    os.getenv("ETH_RPC_URL", ""),
    "https://ethereum.publicnode.com",
    "https://1rpc.io/eth",
    "https://eth.drpc.org",
]
RPCS = [r for r in RPCS if r]

def _http_json(url: str, payload: dict | None = None, timeout: int = 8) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "ChainMind/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def _rpc(method: str, params: list, timeout: int = 5) -> object | None:
    for rpc in RPCS:
        try:
            d = _http_json(rpc, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout)
            if isinstance(d, dict) and "result" in d:
                return d["result"]
        except Exception:
            continue
    return None

def fetch_wallet_data(address: str, limit: int = 25) -> dict:
    """Devuelve {'raw_address': dict|None, 'calls': [..], 'rpc': {...}, 'source': str}."""
    addr_l = address.lower()
    # 1) Blockchair (perfil + muestra de calls)
    try:
        url = f"{BLOCKCHAIR}/{address}?limit={limit}"
        d = _http_json(url, timeout=8)
        blob = d.get("data", {}).get(address) or d.get("data", {}).get(addr_l) or {}
        if blob:
            return {"raw_address": blob.get("address", {}), "calls": blob.get("calls", []) or [],
                    "rpc": {}, "source": "blockchair"}
    except Exception:
        pass
    # 2) Fallback RPC puro
    bal_hex = _rpc("eth_getBalance", [address, "latest"])
    ntx_hex = _rpc("eth_getTransactionCount", [address, "latest"])
    code = _rpc("eth_getCode", [address, "latest"])
    def h2i(h):
        try: return int(h, 16)
        except Exception: return 0
    balance_wei = h2i(bal_hex) if isinstance(bal_hex, str) else 0
    return {"raw_address": {"type": "contract" if isinstance(code, str) and code not in ("0x", "0x0", None) and len(code) > 4 else "account",
                            "balance": str(balance_wei), "transaction_count": h2i(ntx_hex) if isinstance(ntx_hex, str) else 0},
            "calls": [], "rpc": {"balance_wei": balance_wei}, "source": "rpc-fallback"}

def normalize_txs(address: str, calls: list[dict]) -> list[dict]:
    txs = []
    for c in calls or []:
        txs.append({"hash": c.get("transaction_hash", ""), "from": (c.get("sender") or "").lower(),
                    "to": (c.get("recipient") or "").lower() if c.get("recipient") else None,
                    "value_wei": c.get("value", 0), "value_usd": c.get("value_usd", 0),
                    "time": c.get("time", ""), "block": c.get("block_id")})
    return txs
