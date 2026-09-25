"""Comprueba que la sala renderiza completa y que hay movimiento real.

    python scripts/verificar_sala.py
"""
import json
import re
import urllib.request

BACK = "http://127.0.0.1:8000"
WEB = "http://127.0.0.1:3000"


def cuenta(pattern, text):
    return len(re.findall(pattern, text))


st = json.load(urllib.request.urlopen(BACK + "/status", timeout=60))
html = urllib.request.urlopen(WEB + "/", timeout=60).read().decode("utf-8")

print(f"backend  : ok · IA {st['ia']['provider']}/{st['ia']['model']} · {len(st['agentes'])} agentes")
print(f"frontend : ok · {len(html)} bytes")
print()
for etiqueta, patron in [
    ("estaciones", r'class="station '),
    ("robots", r'cy="76"'),
    ("nodos svg", r"<circle cx="),
    ("paquetes", r"animateMotion"),
    ("paneles", r'class="panel"'),
    ("barras", r"station-bar"),
    ("logs", r"station-log"),
]:
    print(f"  {etiqueta:12} {cuenta(patron, html)}")
