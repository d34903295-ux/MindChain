"""Prueba manual del nodo de chat contra el sistema real.

    python scripts/chat_demo.py ["pregunta" ...]
"""
import sys
import time

sys.path.insert(0, ".")
from agents import chat

PREGUNTAS = sys.argv[1:] or [
    "como va el sistema",
    "que wallets vigilamos",
    "que pasa en base",
    "analiza 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045 en ethereum",
    "audita el contrato 0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
    "hola",
]

for q in PREGUNTAS:
    t = time.time()
    r = chat.responder(q)
    print(f"--- {q!r}  [{r['herramienta']}] {r['source']} {round(time.time() - t, 1)}s")
    print("   ", r["respuesta"][:300].replace("\n", " "))
    if r["source"] == "determinista":
        print("    (fallback:", r["motivo"], ")")
    print()
