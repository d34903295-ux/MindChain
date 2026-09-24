import pytest
from agents import chains
from agents.chains import get_chain, supported, rpc_list

def test_soportadas():
    assert "ethereum" in supported() and "base" in supported()

def test_base_config():
    cfg = get_chain("base")
    assert cfg["chain_id"] == 8453 and cfg["adapter"] == "blockscout"

def test_desconocida_error():
    with pytest.raises(ValueError):
        get_chain("solana")

def test_rpc_list_no_vacia():
    assert len(rpc_list("ethereum")) >= 1 and len(rpc_list("base")) >= 1
