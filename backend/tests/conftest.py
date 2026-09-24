"""Hace que `backend/tests` sea autosuficiente.

Sin esto, los tests backend solo pasaban si se ejecutaban después de
`agents/tests` (que insertaba el repo en sys.path). Ejecutarlos solos fallaba
con ModuleNotFoundError: app.

Además aísla las credenciales de IA: sin esto, con una clave real en el
entorno, los tests llamaban de verdad a un modelo y gastaban tokens.
"""
import os
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
for path in (str(BACKEND), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

CREDENCIALES_IA = (
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
    "GROQ_API_KEY", "OPENROUTER_API_KEY", "CHAINMIND_LLM_PROVIDER",
)
for _var in CREDENCIALES_IA:
    os.environ.pop(_var, None)
os.environ["CHAINMIND_LLM_DISABLED"] = "1"
# el TestClient se presenta como "testclient": sin esto, el middleware de API
# keys rechazaría todos los tests como si vinieran de fuera
os.environ.setdefault("CHAINMIND_TRUSTED_HOSTS", "testclient")
# las claves se generan en un temporal, nunca en el archivo real
import tempfile as _tempfile
os.environ["CHAINMIND_KEYS_FILE"] = str(
    pathlib.Path(_tempfile.gettempdir()) / "chainmind_test_keys.json"
)
