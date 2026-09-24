"""Compara modelos locales de Ollama con el prompt real de los agentes.

Sirve para elegir el default con datos, no a ojo: ejecuta el mismo prompt que
usa /analyze-wallet y muestra qué texto devolvería cada modelo y si el filtro
de seguridad lo aceptaría.
"""
import json
import sys
import time

sys.path.insert(0, ".")
from agents import llm
from agents.explanation import SYSTEM_PROMPT, _wallet_prompt, _fallback

PROFILE = {
    "address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ethereum",
    "tx_count": 1420, "tx_count_reliable": False, "age_days": 3890,
    "sample_size": 200, "sample_confidence": "media", "activity": "alta",
    "balance_eth": 640.2, "balance_usd": 2150000.0, "counterparties": 380,
    "in_eth": 91000.0, "out_eth": 90120.5, "is_bot": False, "is_contract": False,
}
FACTORS = ["many_counterparties", "burst_activity", "new_address"]
SCORE = 62

modelos = sys.argv[1:] or ["qwen2.5:1.5b", "qwen2.5:7b"]
print(f"score={SCORE}/100 · fallback determinista: {_fallback(PROFILE, SCORE, FACTORS)[:110]}…\n")

for m in modelos:
    llm.PROVIDERS["ollama"]["model"] = m
    llm.clear_cache()
    t = time.time()
    res = llm.complete(SYSTEM_PROMPT, _wallet_prompt(PROFILE, SCORE, FACTORS),
                       max_tokens=420, temperature=0.2, purpose="explanation")
    dt = round(time.time() - t, 2)
    if not res.get("ok"):
        print(f"=== {m} === ERROR: {res.get('error')}\n")
        continue
    ok, motivo = llm.validate_explanation(res["text"], SCORE, truncado=res.get("truncado", False))
    estado = "ACEPTADO" if ok else f"RECHAZADO ({motivo})"
    final = ok or res["text"]
    print(f"=== {m} === {dt}s · {res['tokens_in']}→{res['tokens_out']} tokens · filtro: {estado}")
    print(final[:600])
    # el final es donde se ven los recortes: imprimir solo el principio daba
    # la falsa impresión de que el modelo cortaba a media frase
    if len(final) > 600:
        print(f"…[{len(final) - 600} caracteres]…")
        print("FIN:", final[-260:])
    print()

llm.PROVIDERS["ollama"]["model"] = "qwen2.5:1.5b"
print(json.dumps(llm.status()["estadisticas"], ensure_ascii=False))
