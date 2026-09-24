"""El mismo hallazgo no puede leerse de dos formas.

El backend (agents/explanation.py::FLAG_TEXT) y el frontend
(frontend/app/watch/page.tsx::FLAG_TEXT) traducen las señales a texto. Cuando
difieren, el panel dice una cosa y el vault otra, y el usuario pierde la
confianza en el sistema. Este test falla si alguien cambia uno y no el otro.
"""
import pathlib
import re
import sys

sys.path.insert(0, ".")
from agents.explanation import FLAG_TEXT

ROOT = pathlib.Path(__file__).resolve().parents[2]
WATCH_TSX = ROOT / "frontend" / "app" / "watch" / "page.tsx"


def _frontend_map() -> dict[str, str]:
    text = WATCH_TSX.read_text(encoding="utf-8")
    block = re.search(r"const FLAG_TEXT[^=]*= \{(.*?)\n\};", text, re.S)
    assert block, "no se encontró FLAG_TEXT en watch/page.tsx"
    # acepta claves con y sin comillas (JS válido: gas_alto: "...", "ballena_1000eth+": "...")
    encontrados = re.findall(r'(?:"([^"]+)"|(\w+)):\s*"([^"]+)"', block.group(1))
    return {(comilla or suelta): texto for comilla, suelta, texto in encontrados}


def test_los_textos_coinciden():
    front = _frontend_map()
    for flag, texto in FLAG_TEXT.items():
        assert flag in front, f"falta la señal {flag} en el frontend"
        assert front[flag] == texto, (
            f"'{flag}' se dice '{front[flag]}' en la UI y '{texto}' en el backend"
        )


def test_el_frontend_no_inventa_senales():
    front = _frontend_map()
    assert set(front) == set(FLAG_TEXT), (
        f"el frontend define señales que el backend nunca emite: {set(front) - set(FLAG_TEXT)}"
    )
