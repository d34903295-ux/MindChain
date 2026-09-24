"""Watchlist de direcciones sensibles (screening, no veredicto).

Reglas de diseño:
- NO se hardcodean direcciones sin verificar: una dirección inventada genera
  falsos positivos y destruye la confianza en el score.
- Las direcciones se cargan de `agents/data/watchlist.json` o de una URL
  configurada en CHAINMIND_WATCHLIST_URL.
- Toda entrada debe estar normalizada a 42 chars (0x + 40 hex).
- Contexto: interacción con un mixer NO es por sí sola un delito; el factor
  se expresa como "señal de screening" y el reporte lo aclara.
"""
import json
import os
import pathlib
import re
import threading
import time
import urllib.request

ADDR_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
TTL = int(os.getenv("CHAINMIND_WATCHLIST_TTL", "21600"))
LOCAL = pathlib.Path(__file__).with_name("data") / "watchlist.json"

_lock = threading.Lock()
_cache: dict[str, object] = {"addresses": {}, "source": "vacio", "loaded_at": 0.0}


def _normalize(raw: dict) -> dict[str, str]:
    out: dict[str, str] = {}
    for entry in raw.get("addresses", []) or []:
        if isinstance(entry, str):
            addr, label = entry, "watchlist"
        elif isinstance(entry, dict):
            addr, label = entry.get("address", ""), entry.get("label", "watchlist")
        else:
            continue
        addr = str(addr).strip().lower()
        if not ADDR_RE.match(addr):
            continue
        out[addr] = str(label)[:60]
    return out


def _load_local() -> dict[str, str]:
    try:
        if LOCAL.exists():
            return _normalize(json.loads(LOCAL.read_text(encoding="utf-8")))
    except Exception:
        return {}
    return {}


def _load_remote(url: str) -> dict[str, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ChainMind/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return _normalize(json.load(r))
    except Exception:
        return {}


def refresh(force: bool = False) -> dict[str, str]:
    now = time.time()
    try:
        mtime = LOCAL.stat().st_mtime
    except OSError:
        mtime = 0.0
    with _lock:
        fresh = (now - float(_cache.get("loaded_at") or 0)) < TTL
        # El JSON se puede editar a mano (flujo documentado): si cambia el
        # fichero, la caché se invalida al instante en vez de esperar 6 horas.
        unchanged = _cache.get("mtime") == mtime
        if fresh and unchanged and not force:
            return _cache["addresses"]  # type: ignore[return-value]
    remote_url = os.getenv("CHAINMIND_WATCHLIST_URL", "")
    remote = _load_remote(remote_url) if remote_url else {}
    local = _load_local()
    merged = {**remote, **local}
    with _lock:
        _cache.update({
            "addresses": merged,
            "source": ("remote+local" if remote and local else "remote" if remote else "local" if local else "vacio"),
            "loaded_at": now,
            "mtime": mtime,
        })
    return merged


def get(address: str) -> str | None:
    """Devuelve la etiqueta si la dirección está en la watchlist."""
    if not address:
        return None
    return refresh().get(str(address).strip().lower())


def entries() -> list[dict]:
    """Entradas locales con metadatos de verificación (para la UI)."""
    return _load_meta().get("addresses", [])


def _read_file() -> dict:
    if not LOCAL.exists():
        return {"addresses": []}
    try:
        data = json.loads(LOCAL.read_text(encoding="utf-8"))
    except Exception:
        return {"addresses": []}
    if not isinstance(data, dict):
        return {"addresses": []}
    data.setdefault("addresses", [])
    return data


def _load_meta() -> dict:
    return _read_file()


def _atomic_write(data: dict) -> None:
    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    tmp = LOCAL.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(LOCAL)


DELEGATION_PREFIX = "0xef0100"  # EIP-7702: EOA delegado, NO es codigo de contrato


def classify_code(code: str) -> tuple[str, int]:
    """Clasifica lo que devuelve eth_getCode: ('contrato'|'delegado'|'eoa', bytes).

    Desde EIP-7702 (marzo 2025) una EOA puede delegar y eth_getCode devuelve
    `0xef0100||direccion` (23 bytes). Confundir eso con codigo de contrato
    meteria EOAs en la watchlist, que es justo lo que esta lista evita.
    """
    raw = (code or "0x").strip()
    nbytes = max(len(raw) - 2, 0) // 2 if raw.startswith("0x") else 0
    if nbytes == 0:
        return "eoa", 0
    if nbytes == 23 and raw[:len(DELEGATION_PREFIX)].lower() == DELEGATION_PREFIX:
        return "delegado", nbytes
    return "contrato", nbytes


def has_contract_code(address: str, chain: str = "ethereum") -> tuple[bool, int]:
    """¿Es un contrato con bytecode real? (EOA y EIP-7702 delegado: False).

    Devuelve (es_contrato, bytes) para poder explicar el motivo del rechazo.
    """
    from .chains import rpc_list
    mejor_tipo, mejor_bytes = "eoa", 0
    for rpc in rpc_list(chain):
        try:
            body = json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "eth_getCode",
                "params": [address, "latest"],
            }).encode()
            req = urllib.request.Request(
                rpc, data=body,
                headers={"Content-Type": "application/json", "User-Agent": "ChainMind/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                tipo, nbytes = classify_code(json.load(r).get("result") or "0x")
            if tipo == "contrato":
                return True, nbytes
            if tipo == "delegado" and nbytes > mejor_bytes:
                mejor_tipo, mejor_bytes = tipo, nbytes
        except Exception:
            continue
    if mejor_tipo == "delegado":
        return False, -mejor_bytes  # negativo: marca que es delegation, no EOA
    return False, mejor_bytes


def add(address: str, label: str, chain: str = "ethereum", verify: bool = True) -> dict:
    """Añade una dirección verificando que exista on-chain.

    No falla si el RPC no responde: marca `verificado: null` en vez de
    inventar un veredicto. Se rechaza toda direccion que no sea un contrato
    con bytecode real (EOA o EIP-7702), porque solo genera ruido.
    """
    addr = str(address or "").strip().lower()
    if not ADDR_RE.match(addr):
        return {"added": False, "reason": "formato inválido: se espera 0x + 40 hex"}
    with _lock:
        data = _read_file()
        current = {str(e.get("address", "")).lower(): e for e in data["addresses"] if isinstance(e, dict)}
        if addr in current:
            return {"added": False, "reason": "ya estaba en la watchlist", "entry": current[addr]}
    verified, nbytes = (None, None) if not verify else has_contract_code(addr, chain)
    if verify and verified is False:
        if nbytes is not None and nbytes < 0:
            return {
                "added": False,
                "reason": "es una EOA delegada (EIP-7702), no un contrato con bytecode",
                "code_bytes": abs(nbytes),
            }
        return {
            "added": False,
            "reason": "sin bytecode on-chain (EOA o inexistente): no se añade",
            "code_bytes": 0,
        }
    entry = {
        "address": addr,
        "label": str(label or "watchlist")[:60],
        "chain": chain,
        "code_bytes": nbytes,
        "verificado": bool(verified) if verify else None,
        "added_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    with _lock:
        data = _read_file()
        data["addresses"] = [e for e in data["addresses"]
                             if not (isinstance(e, dict) and str(e.get("address", "")).lower() == addr)]
        data["addresses"].append(entry)
        data["addresses"].sort(key=lambda e: e.get("address", ""))
        _atomic_write(data)
        _cache.update({"addresses": _normalize(data), "source": "local", "loaded_at": time.time()})
    return {"added": True, "entry": entry, "size": len(_cache["addresses"])}


def remove(address: str) -> dict:
    addr = str(address or "").strip().lower()
    if not ADDR_RE.match(addr):
        return {"removed": False, "reason": "formato inválido"}
    with _lock:
        data = _read_file()
        before = len(data["addresses"])
        data["addresses"] = [e for e in data["addresses"]
                             if not (isinstance(e, dict) and str(e.get("address", "")).lower() == addr)]
        removed = before - len(data["addresses"])
        if removed:
            _atomic_write(data)
            _cache.update({"addresses": _normalize(data), "source": "local", "loaded_at": time.time()})
    return {"removed": removed > 0, "size": len(_cache["addresses"])}


def size() -> int:
    return len(refresh())


def info() -> dict:
    refresh()
    with _lock:
        return {
            "size": len(_cache["addresses"]),
            "source": _cache["source"],
            "age_s": round(time.time() - float(_cache["loaded_at"]), 1),
        }
