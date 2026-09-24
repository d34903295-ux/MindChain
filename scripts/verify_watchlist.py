"""Verifica que cada dirección de agents/data/watchlist.json exista on-chain.

Uso:
    python scripts/verify_watchlist.py

Regla: una dirección sin bytecode (EOA) o con formato inválido se descarta:
un EOA no puede ser un contrato mixer, así que meterlo genera ruido.
"""
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.chains import rpc_list

WATCHLIST = ROOT / "agents" / "data" / "watchlist.json"


def rpc_code(rpc: str, address: str) -> str:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getCode", "params": [address, "latest"]}).encode()
    req = urllib.request.Request(rpc, data=body, headers={"Content-Type": "application/json", "User-Agent": "ChainMind/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r).get("result", "") or "0x"


def main() -> int:
    data = json.loads(WATCHLIST.read_text(encoding="utf-8"))
    entries = data.get("addresses", [])
    if not entries:
        print("Watchlist vacía: nada que verificar.")
        print("Añade direcciones con etiqueta y vuelve a ejecutar.")
        return 0
    rpcs = rpc_list("ethereum")
    bad = []
    for entry in entries:
        addr = entry if isinstance(entry, str) else entry.get("address", "")
        label = "watchlist" if isinstance(entry, str) else entry.get("label", "")
        if not (addr.startswith("0x") and len(addr) == 42):
            bad.append((addr, label, "formato inválido"))
            continue
        code = ""
        for r in rpcs:
            try:
                code = rpc_code(r, addr)
                if code and code != "0x":
                    break
            except Exception:
                continue
        nbytes = max(len(code) - 2, 0) // 2
        status = "OK" if nbytes > 0 else "SIN BYTECODE (descartar)"
        print(f"{addr} {label:24} bytes={nbytes:<6} {status}")
        if nbytes == 0:
            bad.append((addr, label, "sin bytecode"))
    if bad:
        print(f"\n{len(bad)} entrada(s) inválida(s). No añadas direcciones sin verificar.")
        return 1
    print(f"\n{len(entries)} entrada(s) verificada(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
