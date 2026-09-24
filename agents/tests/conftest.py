"""Aísla los tests de la IA real.

Sin esto, los tests de `agents` llamaban a un modelo de verdad (Ollama no
necesita clave, así que `active()` lo encontraba siempre) y quedaban lentos,
no deterministas y capaces de fallar por contenido. Aquí la IA queda apagada
por defecto; los tests que la necesitan la encienden y mockean explícitamente.
"""
import os

os.environ["CHAINMIND_LLM_DISABLED"] = "1"
for _var in (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "GROQ_API_KEY", "OPENROUTER_API_KEY", "CHAINMIND_LLM_PROVIDER",
):
    os.environ.pop(_var, None)
