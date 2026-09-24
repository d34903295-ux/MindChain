"""Comprueba el comportamiento de la clave: en local no hace falta, fuera sí.

    python scripts/probar_api_key.py [cm_...] [http://host:8000]

Si le pasas una URL que no sea 127.0.0.1, la prueba se hace como lo haría
alguien externo: sin clave debe recibir 401 y con clave 200.
"""
import json
import sys
import urllib.error
import urllib.request

API = sys.argv[2] if len(sys.argv) > 2 else "http://127.0.0.1:8000"
CUERPO = {"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045", "chain": "ethereum"}


def llamar(clave=None):
    headers = {"Content-Type": "application/json"}
    if clave:
        headers["X-API-Key"] = clave
    req = urllib.request.Request(API + "/analyze-wallet", data=json.dumps(CUERPO).encode(),
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


print(f"Probando {API}")
cod, cuerpo = llamar()
print(f"1. SIN clave -> HTTP {cod} -> {cuerpo.get('detail', 'ok')}")

if len(sys.argv) > 1:
    cod, cuerpo = llamar(sys.argv[1])
    print(f"2. Con clave correcta -> HTTP {cod} -> "
          f"{'ok, score ' + str(cuerpo.get('risk_score')) if cod == 200 else cuerpo}")
    cod, cuerpo = llamar("cm_inventada_inventada_inventada")
    print(f"3. Con clave inventada -> HTTP {cod} -> {cuerpo.get('detail')}")

print("4. Rutas publicas (no piden clave)")
for ruta in ("/status", "/chains", "/chat/herramientas", "/anomaly/latest"):
    with urllib.request.urlopen(API + ruta, timeout=60) as r:
        print(f"   {ruta:22} HTTP {r.status}")
