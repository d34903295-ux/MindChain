"""Mide velocidad y calidad de los modelos locales para elegir el default.

Un modelo es "bueno" aquí solo si cumple las dos cosas:
  1. rápido (latencia y tokens/s con la máquina ya caliente)
  2. su respuesta supera el filtro de seguridad sin intervention

Se mide en caliente porque la primera llamada carga el modelo en RAM y no
representa el uso real (el panel y el centinela repiten llamadas).
"""
import json
import statistics
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
REPETICIONES = 2

modelos = sys.argv[1:] or ["qwen2.5:1.5b", "qwen2.5:3b", "llama3.2:3b", "phi4-mini", "qwen2.5:7b"]
resultados = []

for m in modelos:
    llm.PROVIDERS["ollama"]["model"] = m
    tiempos, tps, aceptadas,_long = [], [], 0, []
    for i in range(REPETICIONES + 1):  # la primera es de calentamiento
        llm.clear_cache()
        t = time.time()
        res = llm.complete(SYSTEM_PROMPT, _wallet_prompt(PROFILE, SCORE, FACTORS),
                           max_tokens=420, temperature=0.2, purpose="explanation")
        dt = time.time() - t
        if not res.get("ok"):
            tiempos.append(dt)
            continue
        if i == 0:
            continue
        tiempos.append(dt)
        tps.append(res["tokens_out"] / max(dt, 0.01))
        ok, motivo = llm.validate_explanation(res["text"], SCORE, truncado=res.get("truncado", False))
        if ok:
            aceptadas += 1
            _long.append(len(ok))
    if not tiempos:
        print(f"{m:16} ERROR")
        continue
    fila = {
        "modelo": m,
        "mediana_s": round(statistics.median(tiempos), 2),
        "tokens_s": round(statistics.median(tps), 1) if tps else 0,
        "aceptadas": f"{aceptadas}/{REPETICIONES}",
    }
    resultados.append(fila)
    print(f"{m:16} {fila['mediana_s']:>6}s  {fila['tokens_s']:>6} tok/s  filtro OK {fila['aceptadas']}")

print("\n" + "=" * 74)
print(f"{'modelo':16} {'latencia':>9} {'tok/s':>8} {'filtro':>8}  veredicto")
print("=" * 74)
for f in sorted(resultados, key=lambda x: x["mediana_s"]):
    ok = f["aceptadas"].split("/")[0] != "0"
    if ok and f["mediana_s"] <= 4:
        veredicto = "RAPIDO Y FIABLE"
    elif ok:
        veredicto = "fiable pero lento"
    else:
        veredicto = "descartado: no supera el filtro"
    print(f"{f['modelo']:16} {f['mediana_s']:>8}s {f['tokens_s']:>8} {f['aceptadas']:>8}  {veredicto}")

print("\nJSON:", json.dumps(resultados, ensure_ascii=False))
