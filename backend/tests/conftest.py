"""Hace que `backend/tests` sea autosuficiente.

Sin esto, los tests backend solo pasaban si se ejecutaban después de
`agents/tests` (que insertaba el repo en sys.path). Ejecutarlos solos fallaba
con ModuleNotFoundError: app.
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
for path in (str(BACKEND), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)
