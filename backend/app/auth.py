"""API keys de ChainMind para usar el sistema desde fuera.

Idea: la interfaz corre en la misma máquina y no necesita clave, pero si
quieres llamar a ChainMind desde otra herramienta (un script, otra IA, un
bot) tienes que poder autorizarte. Reglas:

- ** localhost y 127.0.0.1 se trustsautomáticamente**: el panel no lleva clave
  y el desarrollo no se rompe.
- Todo lo demás (otra máquina, contenedor, servicio) exige `X-API-Key`.
- Se puede endurecer con `CHAINMIND_REQUIRE_KEY=1` para que localhost también
  pida clave.
- Las claves se guardan hasheadas (SHA-256). El archivo no guarda la clave en
  claro, solo se muestra una vez al crearla.
- **Las claves de los proveedores de IA (ANTHROPIC_API_KEY, etc.) nunca se
  exponen por la API.** Esto solo gestiona claves propias de ChainMind.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import secrets
import time

STORE = pathlib.Path(os.getenv(
    "CHAINMIND_KEYS_FILE",
    str(pathlib.Path(__file__).resolve().parents[1] / "data" / "api_keys.json"),
))
PREFIJO = "cm_"


def _hash(clave: str) -> str:
    return hashlib.sha256(("chainmind:" + clave).encode()).hexdigest()


def _cargar() -> dict:
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("claves"), list):
            return data
    except Exception:
        pass
    return {"claves": []}


def _guardar(datos: dict) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(STORE)


def _normalizar(clave: str) -> str:
    return (clave or "").strip()


def es_local(host: str) -> bool:
    h = (host or "").strip().lower()
    if h.startswith("["):          # [::1]
        return h.startswith("[::1]") or h.startswith("[::ffff:127.")
    if h in ("localhost", "127.0.0.1", "::1", ""):
        return True
    if h.startswith("127."):
        return True
    # Hosts extra de confianza: proxy inverso, red de Docker, o el cliente de
    # pruebas. Separados por comas en CHAINMIND_TRUSTED_HOSTS.
    extras = {x.strip().lower() for x in os.getenv("CHAINMIND_TRUSTED_HOSTS", "").split(",") if x.strip()}
    return h in extras


def requiere_clave(host: str) -> bool:
    if os.getenv("CHAINMIND_REQUIRE_KEY", "0") == "1":
        return True
    return not es_local(host)


def crear(nombre: str = "clave", ttl_dias: int | None = None) -> dict:
    """Genera una clave. Se devuelve en claro UNA vez y no se vuelve a guardar."""
    nombre = (nombre or "clave").strip()[:40] or "clave"
    clave = PREFIJO + secrets.token_urlsafe(32)
    registro = {
        "nombre": nombre,
        "hash": _hash(clave),
        "prefijo": clave[:10] + "…",
        "creada": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "expira": (time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                 time.gmtime(time.time() + ttl_dias * 86400))
                   if ttl_dias else None),
        "ultimo_uso": None,
    }
    datos = _cargar()
    datos["claves"].append(registro)
    _guardar(datos)
    return {"clave": clave, **registro, "aviso": "Cópiala ahora: no se vuelve a mostrar"}


def verificar(clave: str) -> dict | None:
    """Devuelve el registro si la clave es válida, y anota el uso."""
    clave = _normalizar(clave)
    if not clave:
        return None
    objetivo = _hash(clave)
    datos = _cargar()
    for reg in datos["claves"]:
        if not secrets.compare_digest(reg.get("hash", ""), objetivo):
            continue
        if reg.get("revocada"):
            return None
        expira = reg.get("expira")
        if expira:
            try:
                import datetime as _dt
                if _dt.datetime.strptime(expira, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=_dt.timezone.utc) < _dt.datetime.now(_dt.timezone.utc):
                    return None
            except Exception:
                pass
        reg["ultimo_uso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        _guardar(datos)
        return {"nombre": reg.get("nombre"), "creada": reg.get("creada"),
                "expira": reg.get("expira")}
    return None


def revocar(nombre: str) -> dict:
    datos = _cargar()
    cambios = 0
    for reg in datos["claves"]:
        if reg.get("nombre") == nombre and not reg.get("revocada"):
            reg["revocada"] = True
            cambios += 1
    if cambios:
        _guardar(datos)
    return {"revocadas": cambios}


def listar() -> list[dict]:
    """Nunca devuelve la clave ni el hash: solo metadatos."""
    return [{k: v for k, v in reg.items() if k != "hash"} for reg in _cargar()["claves"]]
