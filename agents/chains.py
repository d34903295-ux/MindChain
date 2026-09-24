"""Registry multi-chain (Fase 5). Un solo codigo de agentes para N cadenas.
Para agregar Arbitrum u otra: añadir entrada aqui + adapter existente. Sin duplicar agentes.
"""
import os

CHAINS = {
    "ethereum": {
        "label": "Ethereum", "chain_id": 1, "adapter": "blockchair",
        "blockchair_slug": "ethereum",
        "rpcs": ["https://ethereum.publicnode.com", "https://1rpc.io/eth", "https://eth.drpc.org"],
        "rpc_env": "ETH_RPC_URL",
        "sourcify_id": 1, "etherscan_chainid": 1,
        "explorer": "https://etherscan.io",
    },
    "base": {
        "label": "Base", "chain_id": 8453, "adapter": "blockscout",
        "blockscout": "https://base.blockscout.com/api/v2",
        "rpcs": ["https://mainnet.base.org", "https://base.publicnode.com", "https://1rpc.io/base"],
        "rpc_env": "BASE_RPC_URL",
        "sourcify_id": 8453, "etherscan_chainid": 8453,
        "explorer": "https://basescan.org",
    },
}

def supported():
    return sorted(CHAINS.keys())

def get_chain(name):
    key = str(name or "").lower()
    if key not in CHAINS:
        raise ValueError("cadena no soportada: " + str(name) + ". Soportadas: " + ", ".join(supported()))
    return CHAINS[key]

def chain_key(name):
    return str(name or "").lower()

def rpc_list(name):
    cfg = get_chain(name)
    extra = os.getenv(cfg.get("rpc_env", ""), "")
    base = list(cfg.get("rpcs", []))
    return ([extra] + base) if extra else base
