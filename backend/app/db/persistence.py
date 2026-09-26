"""Intentos de persistencia que no se tragan el error.

El análisis de una wallet o de un contrato no depende de que Postgres o Neo4j
estén levantados: si no lo están, el análisis sigue siendo válido y se
devuelve. Lo que no vale es que el llamante no se entere.

Antes, `analyze.py` tenía dos `except Exception: pass`. Como en esta máquina no
hay ni Postgres ni Neo4j, **todas** las llamadas a `/analyze-wallet` estaban
fallando al guardar y devolviendo 200 sin decirlo: un 200 que no distingue
"guardado" de "no guardado" es un 200 que miente.

Aquí cada intento devuelve su estado como texto y deja el error real en el
log, que es lo que hace falta para poder diagnosticarlo.
"""
import logging

log = logging.getLogger("chainmind.persistence")

OK = "ok"


def attempt(nombre: str, fn, *args, **kwargs) -> str:
    """Ejecuta `fn` y devuelve `"ok"` o `"failed: <tipo>: <mensaje>"`.

    El import va dentro del callable que se le pasa, no aquí fuera: que falte
    `psycopg` o `neo4j` en el entorno es un fallo más que hay que reportar,
    no una razón para callarse.
    """
    try:
        fn(*args, **kwargs)
        return OK
    except Exception as e:
        motivo = f"{type(e).__name__}: {str(e)[:120]}"
        log.warning("persistencia %s fallo: %s", nombre, motivo)
        return f"failed: {motivo}"


def omitida(razon: str) -> str:
    """No se intentó persistir. Distinto de `ok` y distinto de `failed`.

    Se usa cuando no hay nada que guardar (por ejemplo, sin score): reportar
    `ok` ahí sería mentir igual que antes, en la otra dirección.
    """
    log.info("persistencia omitida: %s", razon)
    return f"skipped: {razon}"
