"""verificar_balance_usd.py — BUG A — prueba sobre el endpoint real con el camino de fallback forzado.

Reproduce exactamente el fallo de produccion: Blockchair y Blockscout caidos,
el snapshot RPC respondiendo, el precio disponible. Antes de este arreglo la
respuesta traia `balance_usd: 0.0` con 87.174,82 ETH en la wallet.
"""
import os
import pathlib
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[1] / "backend"
ROOT = BACKEND.parent
for p in (str(BACKEND), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)
os.environ["CHAINMIND_LLM_DISABLED"] = "1"
os.environ.setdefault("CHAINMIND_TRUSTED_HOSTS", "testclient")

from fastapi.testclient import TestClient  # noqa: E402

import agents.fetcher as F  # noqa: E402
import agents.wallet_intelligence as WI  # noqa: E402
from agents import price as P  # noqa: E402

ADDR = "0x28C6c06298d514Db089934071355E5743bf21d60"
WEI_ETH = 87174820146890656739388          # 87.174,82 ETH
PRECIO = 2692.47
ESPERADO = round(WEI_ETH / 10 ** 18 * PRECIO, 2)

# --- los dos adaptadores HTTP caen, como en el incidente -------------------
F._http_json = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("The read operation timed out"))
F._http_get = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("The read operation timed out"))
F._cache.clear()
F.rpc_snapshot = lambda rpcs, addr: {
    "balance_wei": WEI_ETH, "balance_known": True,
    "tx_count": 30806669, "tx_count_known": True,
    "code": "0x", "any_rpc": True,
}
P._cache["eth_usd"] = (time.time(), PRECIO, "test")
WI.get_price_usd = lambda *a, **k: PRECIO

from app.main import app  # noqa: E402  (se importa DESPUES de parchear)

client = TestClient(app)
r = client.post("/analyze-wallet", json={"address": ADDR, "chain": "ethereum"})
body = r.json()
p = body.get("profile", {})

print("=" * 78)
print("BUG A — /analyze-wallet con el fallback RPC forzado")
print("=" * 78)
print("HTTP:", r.status_code)
print("source            :", body.get("source"))
print("risk_score        :", body.get("risk_score"))
print("risk_factors      :", body.get("risk_factors"))
print("-" * 78)
print("balance_wei       :", p.get("balance_wei"), "wei")
print("balance_eth       :", round(WEI_ETH / 10 ** 18, 4), "ETH")
print("price_usd         :", p.get("price_usd"))
print("balance_usd       :", p.get("balance_usd"), "  <-- antes era 0.0")
print("balance_usd_source:", p.get("balance_usd_source"))
print("esperado (derivado):", ESPERADO)
print("labels            :", p.get("labels"))
print("-" * 78)
ok = (p.get("balance_usd") not in (0, 0.0, None)
      and abs(p["balance_usd"] - ESPERADO) < 1
      and p.get("balance_usd_source") == "derivado_del_wei")
print("balance_usd correcto :", ok)
print("regla whale (+10)   :", "balance_alto_wallet_reciente" in (body.get("risk_factors") or []))
print("score >= 10         :", (body.get("risk_score") or 0) >= 10)
print("etiqueta 'whale'    :", "whale" in (p.get("labels") or []))
print("=" * 78)
print("VEREDICTO:", "CORREGIDO" if ok else "SIGUE ROTO")
