from agents.contract_analyzer import analyze_source, analyze_bytecode, analyze_contract, disassemble, parse_slither_json, delegation_7702, valid_code, detect_proxy, is_proxy, _unflatten_source

RISKY = "contract T { address owner; modifier onlyOwner { _; } function mint(uint n) public onlyOwner {} function withdraw() public onlyOwner {} function pause() public onlyOwner { paused = true; } function setBlacklist(address a) public { blacklist[a] = true; } function kill() public { selfdestruct(payable(owner)); } function fwd(address t, bytes memory d) public { t.delegatecall(d); } if (tx.origin != msg.sender) {} }"
SAFE = "contract T { mapping(address=>uint) b; function transfer(address to, uint n) public { b[msg.sender] -= n; b[to] += n; } }"

def test_source_risky():
    f = analyze_source(RISKY)
    ids = [x["id"] for x in f]
    assert "selfdestruct" in ids and "delegatecall" in ids and "owner_mint" in ids
    assert sum(x["weight"] for x in f) >= 70

def test_source_safe():
    assert analyze_source(SAFE) == []

def test_bytecode_disasm_preciso():
    con_pushdata = bytes([96, 244, 86]).hex()
    assert "bytecode_delegatecall" not in [x["id"] for x in analyze_bytecode("0x" + con_pushdata)]
    con_opcode = bytes([244]).hex()
    assert "bytecode_delegatecall" in [x["id"] for x in analyze_bytecode("0x" + con_opcode)]

def test_disassemble_push_skip():
    assert disassemble("0x60f45b") == [96, 91]

def test_eoa_no_contrato():
    r = analyze_contract("0xabc", {"is_contract": False, "source_origin": "x"})
    assert r["risk_score"] == 0 and r["is_contract"] is False

def test_push17_32_no_falsos_positivos():
    code = "0x73" + "ff" * 20 + "7f" + "f4" * 32 + "5b"
    ids = [x["id"] for x in analyze_bytecode(code)]
    assert "bytecode_selfdestruct" not in ids and "bytecode_delegatecall" not in ids

def test_eip7702_delegacion():
    code = "0xef01005a7fc11397e9a8ad41bf10bf13f22b0a63f96f6d"
    assert delegation_7702(code) == "0x5a7fc11397e9a8ad41bf10bf13f22b0a63f96f6d"
    r = analyze_contract("0xabc", {"is_contract": False, "account_type": "eoa_7702",
                                   "delegated_to": "0x5a7f", "source_origin": "x"})
    assert r["risk_score"] == 5 and r["account_type"] == "eoa_7702"

def test_valid_code_rechaza_basura():
    assert valid_code("0x") is False and valid_code("0xzz") is False
    assert valid_code("0x6001") is True and valid_code(None) is False

def test_slither_parser():
    d = {"detectors": {"results": [{"check": "suicidal", "impact": "High", "description": "x"},
                                   {"check": "nuevo-check", "impact": "Low", "description": "y"}]}}
    f = parse_slither_json(d)
    assert f[0]["weight"] == 30 and f[1]["weight"] == 5


def test_proxy_por_fuente_verificada():
    src = "contract Proxy is TransparentUpgradeableProxy { function upgrade() public {} }"
    assert is_proxy(src) is True
    proxy, method = detect_proxy(src, "0x6001")
    assert proxy is True and method == "source-verificada"


def test_proxy_por_bytecode_eip1967():
    slot = "360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
    proxy, method = detect_proxy(None, "0x" + slot)
    assert proxy is True and method == "bytecode-eip1967"


def test_sin_prueba_no_se_afirma_proxy():
    """USDC usa slot propio: sin fuente no se puede afirmar. Honestidad > certeza."""
    proxy, method = detect_proxy(None, "0x6080604052f4")
    assert proxy is False and "no-detectado" in method


def test_analyze_no_penaliza_proxy():
    src = "contract Proxy is TransparentUpgradeableProxy { function upgrade() public { address.delegatecall(msg.data); } }"
    r = analyze_contract("0xabc", {"is_contract": True, "code": "0x6001", "verified": True,
                                   "verified_via": "test", "code_size_bytes": 2, "source": src,
                                   "source_origin": "test"})
    ids = [x["id"] for x in r["risks"]]
    assert "proxy_detectado" in ids
    assert "delegatecall" not in ids and "bytecode_delegatecall" not in ids
    assert r["risk_score"] <= 5


def test_slither_multi_archivo(tmp_path):
    payload = """{"language":"Solidity","sources":{"contracts/A.sol":{"content":"contract A {}"},"contracts/B.sol":{"content":"contract B {}"}},"settings":{"compilationTarget":{"contracts/A.sol":"A"}}}"""
    written = _unflatten_source(payload, str(tmp_path))
    assert len(written) == 2
    assert written[0].endswith("A.sol")  # el compilationTarget va primero
    assert (tmp_path / "contracts" / "B.sol").exists()


def test_slither_fuente_plana(tmp_path):
    written = _unflatten_source("contract A {}", str(tmp_path))
    assert len(written) == 1 and written[0].endswith("target.sol")
