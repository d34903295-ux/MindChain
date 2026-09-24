from agents.contract_analyzer import analyze_source, analyze_bytecode, analyze_contract, disassemble, parse_slither_json, delegation_7702, valid_code

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
