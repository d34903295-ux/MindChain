"""Comprueba el seguimiento conversacional del chat (preguntas de una línea)."""
import sys

sys.path.insert(0, ".")
from agents import chat

HIST = [{"role": "user", "content": "como va el sistema"},
        {"role": "assistant", "content": "todo bien"}]

for q in ["¿y en base?", "y en ethereum", "hola", "que contratos hay", "ahora en base"]:
    paso = chat.ejecutar(q, HIST)
    print(f"  {q!r:20} -> herramienta={paso['herramienta']}")
