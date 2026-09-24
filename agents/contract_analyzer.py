"""Smart Contract Agent (Fase 2).
Fuentes: RPC eth_getCode + Sourcify (verificado) + Etherscan source (si hay API key).
Analisis: heuristicas de codigo (estilo Smart-Contract-Risk-Analyzer) + disassembler
de bytecode (DELEGATECALL/SELFDESTRUCT/CALLCODE) + Slither opt-in (CHAINMIND_SLITHER=1).
"""
import os, json, shutil, subprocess, tempfile, urllib.request

SOURCIFY_MATCH = "https://sourcify.dev/server/v2/contract/1"

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

def get_code(address):
    for u in [os.getenv("ETH_RPC_URL", ""), "https://ethereum.publicnode.com", "https://1rpc.io/eth", "https://eth.drpc.org"]:
        if not u:
            continue
        c = _rpc_call(u, "eth_getCode", [address, "latest"])
        if isinstance(c, str) and c:
            return c
    return "0x"

def sourcify_verified(address):
    try:
        d = _http_json(SOURCIFY_MATCH + "/" + address, timeout=6)
        m = str(d.get("match", ""))
        return m in ("match", "perfect", "partial"), "sourcify"
    except Exception:
        return False, "sourcify-unreachable"

def etherscan_source(address):
    key = os.getenv("ETHERSCAN_API_KEY", "")
    if not key:
        return None, "sin-api-key"
    try:
        url = "https://api.etherscan.io/v2/api?chainid=1&module=contract&action=getsourcecode&address=" + address + "&apikey=" + key
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

def fetch_contract(address):
    code = get_code(address)
    if not valid_code(code):
        code = "0x"
    delegate = delegation_7702(code)
    account_type = "eoa_7702" if delegate else ("contract" if len(code) > 2 else "eoa")
    is_contract = account_type == "contract"
    verified, via = (sourcify_verified(address) if is_contract else (False, "n/a-eoa"))
    source, sorigin = (etherscan_source(address) if is_contract else (None, "n/a-eoa"))
    size = max(len(code) - 2, 0) // 2
    return {"address": address, "code": code, "is_contract": is_contract,
            "account_type": account_type, "delegated_to": delegate,
            "code_size_bytes": size, "verified": verified, "verified_via": via,
            "source": source, "source_origin": sorigin}

SOURCE_CHECKS = [
    ("selfdestruct", 30, ["selfdestruct"], "any", "SELFDESTRUCT: el owner puede destruir el contrato y mover fondos"),
    ("delegatecall", 25, ["delegatecall"], "any", "DELEGATECALL: lógica delegada, riesgo de takeover si el destino es mutable"),
    ("tx_origin", 15, ["tx.origin"], "any", "tx.origin en autorización: phishing de firmas"),
    ("owner_mint", 20, ["function mint", "onlyowner"], "all", "Mint privilegiado: el owner puede inflar el supply"),
    ("owner_withdraw", 20, ["onlyowner", "withdraw"], "all", "Withdraw privilegiado: el owner puede extraer fondos"),
    ("pause_control", 10, ["paus", "onlyowner"], "all", "Pausa centralizada: el owner puede congelar transfers"),
    ("blacklist", 15, ["blacklist", "denylist"], "any", "Blacklist: direcciones pueden ser bloqueadas (riesgo censura/SEC-style)"),
    ("upgradeable", 15, ["upgradeable", "uupsupgradeable", "erc1967", "transparentupgradeableproxy"], "any", "Upgradeable/proxy: la lógica puede cambiar tras el deploy"),
    ("owner_admin", 5, ["ownable", "onlyowner"], "any", "Administrado por owner/EOA: poder centralizado"),
]

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
    if os.getenv("CHAINMIND_SLITHER", "") != "1":
        return [], False
    if not source or shutil.which("slither") is None:
        return [], False
    try:
        with tempfile.TemporaryDirectory() as td:
            sol = tempfile.os.path.join(td, "target.sol")
            out = tempfile.os.path.join(td, "out.json")
            with open(sol, "w", encoding="utf-8") as f:
                f.write(source)
            subprocess.run(["slither", sol, "--json", out], capture_output=True, timeout=90)
            with open(out, encoding="utf-8") as f:
                return parse_slither_json(json.load(f)), True
    except Exception:
        return [], False
    return [], False

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
    findings = analyze_source(fetched.get("source"))
    findings += analyze_bytecode(fetched.get("code", ""))
    slither_findings, used = try_slither(fetched.get("source"))
    findings += slither_findings
    if not fetched.get("verified"):
        findings.append({"id": "no_verificado", "weight": 10,
                         "message": "Contrato no verificado en Sourcify: el bytecode no es auditable públicamente",
                         "origin": "meta"})
    score = min(100, sum(f.get("weight", 0) for f in findings))
    perms = sorted(set(f["id"] for f in findings if f["origin"] in ("source", "bytecode")))
    lvl = "bajo" if score < 30 else ("medio" if score < 70 else "alto")
    expl = ("Contrato " + address + ": bytecode de " + str(fetched.get("code_size_bytes")) + " bytes, "
            + ("verificado" if fetched.get("verified") else "NO verificado") + " (" + str(fetched.get("verified_via")) + "). "
            + "Riesgo " + lvl + " (" + str(score) + "/100). "
            + ("Hallazgos: " + "; ".join(f["id"] + " (" + str(f["weight"]) + ")" for f in findings) + "." if findings else "Sin permisos peligrosos detectados."))
    return {"address": address, "is_contract": True, "account_type": "contract", "verified": fetched.get("verified"),
            "verified_via": fetched.get("verified_via"), "code_size_bytes": fetched.get("code_size_bytes"),
            "permissions": perms, "risks": findings, "risk_score": score, "explanation": expl,
            "slither_used": used, "source_origin": fetched.get("source_origin")}
