"""Prueba del flujo completo del chat tal y como lo ve el navegador.

    python scripts/probar_chat_web.py "pregunta"
"""
import json
import sys
import time
import urllib.error
import urllib.request

API = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"


def post(ruta, cuerpo, timeout=300):
    req = urllib.request.Request(API + ruta, data=json.dumps(cuerpo).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=timeout))
    except urllib.error.HTTPError as e:
        return {"HTTP_" + str(e.code): json.load(e).get("detail")}


print("1. La pagina de chat existe")
h = urllib.request.urlopen(WEB + "/chat", timeout=30).read().decode()
print("   /chat:", "OK" if "Pregunta al sistema" in h else "FALTA")

print("\n2. Herramientas declaradas")
for t in json.load(urllib.request.urlopen(API + "/chat/herramientas", timeout=20))["herramientas"]:
    print(f"   {t['nombre']:20} {t['descripcion']}")

print("\n3. Conversación con historial (como el navegador la envía)")
p1 = post("/chat", {"mensaje": "como va el sistema"})
p2 = post("/chat", {"mensaje": "¿y en base?",
                    "historial": [{"role": "user", "content": "como va el sistema"},
                                  {"role": "assistant", "content": p1["respuesta"]}]})
for p in (p1, p2):
    print(f"   [{p.get('herramienta')}] {p.get('source')}: {p['respuesta'][:130]}")

print("\n4. Pregunta sobre datos reales")
p3 = post("/chat", {"mensaje": "audita el contrato 0xC36442b4a4522E871399CD717aBDD847Ab11FE88"})
print(f"   herramienta={p3.get('herramienta')} fuente={p3.get('source')}")
print("  ", p3["respuesta"][:220])

print("\n5. Mensaje sin sentido (no debe romperse)")
p4 = post("/chat", {"mensaje": "qwertyuiop asdfgh"})
print(f"   [{p4.get('herramienta')}] {p4.get('source')}: {p4['respuesta'][:120]}")

print("\n6. Validacion de entrada")
print("   vacio ->", post("/chat", {"mensaje": ""}).get("HTTP_422", "ACEPTADO (mal)"))
print("   3000 chars ->", post("/chat", {"mensaje": "a" * 3000}).get("HTTP_422", "ACEPTADO (mal)"))
