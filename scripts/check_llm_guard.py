"""Prueba manual de la validación: qué se acepta y qué se rechaza."""
import sys

sys.path.insert(0, ".")
from agents import llm

CASOS = [
    ("maliciosa (la del modelo real)",
     "Una wallet ha realizado una transferencia significativa de 500 ETH, lo cual podria indicar actividad no convencional o maliciosa."),
    ("neutra (debe pasar)",
     "El movimiento es 40 veces la mediana de la red en ese bloque. Conviene revisar el contrato de destino y la procedencia de los fondos."),
    ("ciberdelito", "Esto es un ciberdelito claro."),
    ("blanqueamiento", "Movimiento tipico de blanqueamiento."),
    ("intencion", "La direccion quiere blanquear capital."),
    ("sancion screening", "Coincide con una direccion sancionada por OFAC."),
    ("metatexto", "Como un modelo de IA, no puedo ayudar con esto."),
    ("invencion", "Se sabe que esta direccion es un mixer."),
]

for nombre, txt in CASOS:
    r, m = llm.validate_explanation(txt)
    veredicto = "RECHAZADO (" + m + ")" if r is None else "aceptado"
    print(f"{nombre:32} -> {veredicto}")
