"""Smart Contract Agent (Fase 2).
Fuentes: RPC eth_getCode + Sourcify (verificado) + Etherscan source (si hay API key).
Analisis: heuristicas de codigo (estilo Smart-Contract-Risk-Analyzer) + disassembler
de bytecode (DELEGATECALL/SELFDESTRUCT/CALLCODE) + Slither opt-in (CHAINMIND_SLITHER=1).
"""
import os, json, shutil, subprocess, tempfile, urllib.request
from .chains import get_chain, chain_key, rpc_list

SOURCIFY_BASE = "https://sourcify.dev/server/v2/contract/"

def _http_json(url, payload=None, timeout=6, headers=None):
    import json as _j
    data = _j.dumps(payload).encode() if payload is not None else None
    h = {"User-Agent": "ChainMind/2.0"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    if data is not None:
        h["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return _j.load(r)

def _rpc_call(rpc_url, method, params, timeout=5):
    try:
        d = _http_json(rpc_url, {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}, timeout)
        if isinstance(d, dict) and "result" in d:
            return d["result"]
    except Exception:
        return None
    return None

def rpc_url():
    for u in [os.getenv("ETH_RPC_URL", ""), "https://ethereum.publicnode.com", "https://1rpc.io/eth"]:
        if u:
            return u
    return "https://ethereum.publicnode.com"

def get_code(address, chain="ethereum"):
    try:
        rpcs = rpc_list(chain)
    except ValueError:
        rpcs = []
    for u in rpcs:
        if not u:
            continue
        c = _rpc_call(u, "eth_getCode", [address, "latest"])
        if isinstance(c, str) and c:
            return c
    return "0x"

def sourcify_verified(address, chain="ethereum"):
    key = chain_key(chain)
    sid = get_chain(key).get("sourcify_id", 1)
    try:
        d = _http_json(SOURCIFY_BASE + str(sid) + "/" + address, timeout=6)
        m = str(d.get("match", ""))
        return m in ("match", "perfect", "partial"), "sourcify"
    except Exception:
        return False, "sourcify-unreachable"

def etherscan_source(address, chain="ethereum"):
    key = os.getenv("ETHERSCAN_API_KEY", "")
    if not key:
        return None, "sin-api-key"
    cid = get_chain(chain_key(chain)).get("etherscan_chainid", 1)
    try:
        url = "https://api.etherscan.io/v2/api?chainid=" + str(cid) + "&module=contract&action=getsourcecode&address=" + address + "&apikey=" + key
        d = _http_json(url, timeout=6)
        res = (d.get("result") or [{}])[0]
        src = res.get("SourceCode", "")
        if src and len(src) > 50:
            return src, "etherscan"
        return None, "no-publicada"
    except Exception:
        return None, "etherscan-error"

def valid_code(code):
    if not isinstance(code, str) or len(code) <= 2:
        return False
    h = code[2:] if code[:2] == "0x" or code[:2] == "0X" else ""
    if not h or len(h) % 2 == 1:
        return False
    return all(c in "0123456789abcdefABCDEF" for c in h)

def delegation_7702(code):
    """Detecta EIP-7702: codigo 0xef0100 + address delegada (EOA smart-account)."""
    if isinstance(code, str) and code[:8].lower() == "0xef0100" and len(code) >= 48:
        return "0x" + code[8:48]
    return None

def fetch_contract(address, chain="ethereum"):
    key = chain_key(chain)
    get_chain(key)
    code = get_code(address, chain=key)
    if not valid_code(code):
        code = "0x"
    delegate = delegation_7702(code)
    account_type = "eoa_7702" if delegate else ("contract" if len(code) > 2 else "eoa")
    is_contract = account_type == "contract"
    verified, via = (sourcify_verified(address, chain=key) if is_contract else (False, "n/a-eoa"))
    source, sorigin = (etherscan_source(address, chain=key) if is_contract else (None, "n/a-eoa"))
    size = max(len(code) - 2, 0) // 2
    return {"address": address, "code": code, "is_contract": is_contract,
            "account_type": account_type, "delegated_to": delegate,
            "code_size_bytes": size, "verified": verified, "verified_via": via,
            "source": source, "source_origin": sorigin, "chain": key}

SOURCE_CHECKS = [
    ("selfdestruct", 30, ["selfdestruct", "suicide"], "any", "SELFDESTRUCT: el owner puede destruir el contrato y mover fondos"),
    ("delegatecall", 25, ["delegatecall"], "any", "DELEGATECALL: lógica delegada, riesgo de takeover si el destino es mutable"),
    ("tx_origin", 15, ["tx.origin"], "any", "tx.origin en autorización: phishing de firmas"),
    ("owner_mint", 20, ["function mint", "onlyowner"], "all", "Mint privilegiado: el owner puede inflar el supply"),
    ("owner_withdraw", 20, ["onlyowner", "withdraw"], "all", "Withdraw privilegiado: el owner puede extraer fondos"),
    ("pause_control", 10, ["paus", "onlyowner"], "all", "Pausa centralizada: el owner puede congelar transfers"),
    ("blacklist", 15, ["blacklist", "denylist"], "any", "Blacklist: direcciones pueden ser bloqueadas (riesgo censura/SEC-style)"),
    ("upgradeable", 15, ["upgradeable", "uupsupgradeable", "erc1967", "transparentupgradeableproxy"], "any", "Upgradeable/proxy: la lógica puede cambiar tras el deploy"),
    ("owner_admin", 5, ["ownable", "onlyowner"], "any", "Administrado por owner/EOA: poder centralizado"),
]

# Tokens que son proxies por diseño (no son un hallazgo de riesgo por sí mismos).
PROXY_MARKERS = (
    "transparentupgradeableproxy",
    "erc1967proxy",
    "proxyadmin",
    "beaconproxy",
    "upgradeableproxy",
    "initializer",
)


def is_proxy(source: str | None) -> bool:
    if not source:
        return False
    low = source.lower()
    return any(m in low for m in PROXY_MARKERS) and "proxy" in low


def detect_implementation_slot(rpc_code: str) -> str | None:
    """Lee el slot EIP-1967 de implementación si el runtime lo referencia."""
    if not rpc_code or "363d3d373d3d3d363d73" not in rpc_code.lower():
        return None
    return "eip1967-implementation-referenced"


EIP1967_IMPL_SLOT = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"


def detect_proxy(source: str | None, code: str | None) -> tuple[bool, str]:
    """Detección de proxy con nivel de honestidad explícito.

    Devuelve (es_proxy, metodo). La fuente verificada es la señal fuerte; el
    bytecode solo confirma si aparecen los marcadores estándar EIP-1967.
    Muchos proxies (p.ej. FiatTokenProxy de USDC) usan slots propios y NO son
    detectables sin fuente verificada: en ese caso no se afirma nada.
    """
    if is_proxy(source):
        return True, "source-verificada"
    low = (code or "").lower()
    if EIP1967_IMPL_SLOT in low:
        return True, "bytecode-eip1967"
    if "363d3d373d3d3d363d73" in low:
        return True, "bytecode-patron-proxy"
    return False, "no-detectado-sin-fuente"

def analyze_source(source):
    findings = []
    if not source:
        return findings
    low = source.lower()
    for fid, w, needles, mode, msg in SOURCE_CHECKS:
        hit = all(n in low for n in needles) if mode == "all" else any(n in low for n in needles)
        if hit:
            findings.append({"id": fid, "weight": w, "message": msg, "origin": "source"})
    return findings

def disassemble(code_hex):
    h = code_hex or ""
    if h[:2] == "0x" or h[:2] == "0X":
        h = h[2:]
    if len(h) % 2 == 1:
        h = "0" + h
    try:
        raw = bytes.fromhex(h)
    except Exception:
        return []
    ops = []
    i, n = 0, len(raw)
    while i < n:
        op = raw[i]
        ops.append(op)
        if 96 <= op <= 127:
            i += (op - 95)
        i += 1
    return ops

BYTECODE_CHECKS = [
    ("bytecode_delegatecall", 15, 244, "DELEGATECALL en bytecode: contrato delega ejecución (proxy o riesgo)"),
    ("bytecode_selfdestruct", 20, 255, "SELFDESTRUCT en bytecode: contrato autodestruible"),
    ("bytecode_callcode", 10, 242, "CALLCODE en bytecode: primitiva obsoleta y peligrosa"),
]

def analyze_bytecode(code_hex):
    ops = set(disassemble(code_hex))
    out = []
    for fid, w, opcode, msg in BYTECODE_CHECKS:
        if opcode in ops:
            out.append({"id": fid, "weight": w, "message": msg, "origin": "bytecode"})
    return out

SLITHER_MAP = {"suicidal": ("selfdestruct", 30), "controlled-delegatecall": ("delegatecall", 25),
               "tx-origin": ("tx_origin", 15), "arbitrary-send": ("owner_withdraw", 20)}

def parse_slither_json(data):
    out = []
    dets = []
    if isinstance(data, dict):
        dets = data.get("detectors", {}).get("results", []) or data.get("results", {}).get("detectors", [])
    for d in dets:
        check = str(d.get("check", ""))
        impact = str(d.get("impact", "Medium"))
        w = 20 if impact == "High" else (10 if impact == "Medium" else 5)
        fid = SLITHER_MAP.get(check, (check or "slither-finding", w))[0]
        if check in SLITHER_MAP:
            fid, w = SLITHER_MAP[check]
        out.append({"id": "slither_" + fid, "weight": w,
                    "message": "Slither [" + check + "/" + impact + "]: " + str(d.get("description", ""))[:220],
                    "origin": "slither"})
    return out

def try_slither(source):
    """Ejecuta Slither sobre el código fuente.

    Etherscan devuelve en `SourceCode` el JSON de archivos verificados cuando el
    contrato tiene imports. Antes se escribía todo en un .sol y Slither fallaba
    siempre. Ahora se reconstruye el proyecto multi-archivo.
    """
    if os.getenv("CHAINMIND_SLITHER", "") != "1":
        return [], False
    if not source or shutil.which("slither") is None:
        return [], False
    try:
        with tempfile.TemporaryDirectory() as td:
            files = _unflatten_source(source, td)
            if not files:
                return [], False
            entry = files[0]
            out = os.path.join(td, "out.json")
            proc = subprocess.run(
                ["slither", entry, "--json", out, "--solc-remaps", "@openzeppelin/=node_modules/@openzeppelin/"],
                capture_output=True,
                timeout=120,
            )
            if not os.path.exists(out):
                # Slither no produjo JSON: la fuente no compila tal cual
                return [], False
            with open(out, encoding="utf-8") as f:
                findings = parse_slither_json(json.load(f))
            return findings, True
    except Exception:
        return [], False
    return [], False


def _unflatten_source(source: str, target_dir: str) -> list[str]:
    """Escribe los archivos de un SourceCode de Etherscan. Devuelve rutas en orden."""
    text = source.strip()
    data = None
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except Exception:
            data = None
    written: list[str] = []
    if isinstance(data, dict) and isinstance(data.get("sources"), dict):
        for name, body in data["sources"].items():
            safe = name.replace("..", "_").replace("\\", "/").lstrip("/")
            path = os.path.join(target_dir, *safe.split("/"))
            os.makedirs(os.path.dirname(path), exist_ok=True)
            content = body.get("content") if isinstance(body, dict) else str(body)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content or "")
            written.append(path)
        settings = data.get("settings") or {}
        compiler = (settings.get("compilationTarget") or {}).get("")
        if compiler:
            written.sort(key=lambda p: 0 if os.path.basename(p) == os.path.basename(compiler) else 1)
    else:
        path = os.path.join(target_dir, "target.sol")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        written.append(path)
    return written

def analyze_contract(address, fetched):
    if fetched.get("account_type") == "eoa_7702":
        d = fetched.get("delegated_to", "")
        return {"address": address, "is_contract": False, "account_type": "eoa_7702",
                "delegated_to": d, "verified": False,
                "permissions": ["eoa-delegada-7702"], "risks": [
                    {"id": "eoa_delegada_7702", "weight": 5, "origin": "meta",
                     "message": "EOA con delegación EIP-7702 hacia " + d + ": actúa como smart-account; el riesgo depende del contrato delegado"}],
                "risk_score": 5,
                "explanation": "La dirección es una EOA con delegación EIP-7702 al contrato " + d + ". Riesgo bajo (5/100); auditar el contrato delegado.",
                "slither_used": False, "source_origin": fetched.get("source_origin")}
    if not fetched.get("is_contract"):
        return {"address": address, "is_contract": False, "account_type": "eoa",
                "verified": False,
                "permissions": ["eoa-sin-codigo"], "risks": [], "risk_score": 0,
                "explanation": "La dirección no tiene bytecode: es una EOA, no un contrato.",
                "slither_used": False, "source_origin": fetched.get("source_origin")}
    source = fetched.get("source")
    code = fetched.get("code", "")
    proxy, proxy_method = detect_proxy(source, code)
    slot = detect_implementation_slot(code)
    findings = analyze_source(source)
    findings += analyze_bytecode(code)
    slither_findings, used = try_slither(source)
    findings += slither_findings
    if proxy:
        # un proxy delega por diseño: DELEGATECALL no es un hallazgo en sí mismo
        findings = [
            f for f in findings
            if f["id"] not in ("delegatecall", "bytecode_delegatecall", "upgradeable")
        ]
        findings.append({
            "id": "proxy_detectado",
            "weight": 5,
            "origin": "meta",
            "message": "El contrato es un proxy (" + proxy_method + "): delega la lógica a una implementación"
                       + (f" ({slot})" if slot else "") + ". Audita la implementación, no el proxy.",
        })
    else:
        for f in findings:
            if f["id"] in ("delegatecall", "bytecode_delegatecall"):
                f["message"] += " (patrón típico de proxy; sin fuente verificada no se puede confirmar)"
    if not fetched.get("verified"):
        findings.append({"id": "no_verificado", "weight": 10,
                         "message": "Contrato no verificado en Sourcify: el bytecode no es auditable públicamente",
                         "origin": "meta"})
    score = min(100, sum(f.get("weight", 0) for f in findings))
    perms = sorted(set(f["id"] for f in findings if f["origin"] in ("source", "bytecode")))
    perms.append("proxy") if proxy else None
    lvl = "bajo" if score < 30 else ("medio" if score < 70 else "alto")
    deterministic = ("Contrato " + address + ": bytecode de " + str(fetched.get("code_size_bytes")) + " bytes, "
            + ("verificado" if fetched.get("verified") else "NO verificado") + " (" + str(fetched.get("verified_via")) + "). "
            + "Riesgo " + lvl + " (" + str(score) + "/100). "
            + ("Hallazgos: " + "; ".join(f["id"] + " (" + str(f["weight"]) + ")" for f in findings) + "." if findings else "Sin permisos peligrosos detectados."))
    expl, ai = _explain_contract(address, findings, score, lvl, proxy, proxy_method, fetched, deterministic)
    return {"address": address, "is_contract": True, "account_type": "contract", "verified": fetched.get("verified"),
            "verified_via": fetched.get("verified_via"), "code_size_bytes": fetched.get("code_size_bytes"),
            "is_proxy": proxy, "proxy_detection": proxy_method, "permissions": perms, "risks": findings,
            "risk_score": score, "explanation": expl, "ai": ai,
            "slither_used": used, "source_origin": fetched.get("source_origin")}


CONTRACT_SYSTEM = (
    "Eres un auditor de smart contracts. Explicas hallazgos técnicos en lenguaje claro "
    "para quien hace due diligence.\n"
    "REGLAS INNEGOCIABLES:\n"
    "- Explica SOLO los hallazgos que se te dan. No añadas riesgos nuevos, no los omitas.\n"
    "- No afirmes intención ni responsabilidad penal de nadie.\n"
    "- Si no hay hallazgos, dilo claramente en una frase.\n"
    "- No inventes funciones, privilegios o comportamientos que no estén listados.\n"
    "Responde en español, máximo 6 líneas."
)


def _explain_contract(address, findings, score, lvl, proxy, proxy_method, fetched, deterministic) -> tuple[str, dict]:
    """Redacta los hallazgos con el agente `contratos` sin poder inventar nada."""
    from . import agents
    if not findings:
        return deterministic, {"source": "determinista", "agente": "contratos",
                              "motivo": "sin hallazgos que explicar"}
    lista = "\n".join(
        f"- {f['id']} (peso {f.get('weight', 0)}, origen {f.get('origin', '?')}): {f.get('message', '')}"
        for f in findings
    )
    user = (
        f"Contrato: {address}\n"
        f"Tamaño de bytecode: {fetched.get('code_size_bytes')} bytes\n"
        f"Verificado en el explorador: {fetched.get('verified')} ({fetched.get('verified_via')})\n"
        f"Es proxy: {proxy} ({proxy_method or 'sin determinar'})\n"
        f"Slither ejecutado: {fetched.get('slither_used', False)}\n"
        f"Riesgo heurístico total: {score}/100 ({lvl})\n"
        f"Hallazgos detectados:\n{lista}\n\n"
        "Explica en español qué significa este contrato para quien va a interactuar con él: "
        "qué permisos tiene, qué debería comprobar y qué limitaciones tiene este análisis "
        "(Slither no pudo ejecutarse, fuente no verificada, etc.)."
    )
    res = agents.run("contratos", user, deterministic, score=score)
    return res["text"], {k: v for k, v in res.items() if k != "text"}
