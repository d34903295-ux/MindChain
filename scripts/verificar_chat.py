"""Comprobación en vivo del nodo de chat por HTTP.

    python scripts/verificar_chat.py ["pregunta" ...]
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"
PREGUNTAS = sys.argv[1:] or [
    "como va el sistema",
    "que pasa en base",
    "que wallets vigilamos",
    "analiza 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 en ethereum",
]


def post(ruta, cuerpo, timeout=300):
    req = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return {"HTTP_" + str(e.code): json.load(e).get("detail")}


st = json.load(urllib.request.urlopen(API + "/status", timeout=90))
print(f"IA: {st['ia']['provider']} / {st['ia']['model']}  coste: {st['ia']['estadisticas']['usd']} USD")
print("AGENTES:")
for a in st["agentes"]:
    print(f"   {a['nombre']:14} {a['modelo']:13} T={a['temperatura']:<5} "
          f"tok={a['tokens_max']:<4} reglas={a['reglas_propias']}")

for q in PREGUNTAS:
    t = time.time()
    r = post("/chat", {"mensaje": q})
    if "respuesta" not in r:
        print(f"\n--- {q!r} ERROR {r}")
        continue
    print(f"\n--- {q!r}  herramienta={r['herramienta']} fuente={r['source']} {round(time.time()-t,1)}s")
    print("   ", r["respuesta"][:260].replace("\n", " "))
    if r["source"] == "determinista":
        print("    (fallback:", r["motivo"], ")")
