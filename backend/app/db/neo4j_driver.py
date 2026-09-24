import os
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "chainmind_dev")

_driver = None
def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    return _driver

def save_wallet_graph(address: str, profile: dict, txs: list[dict], score: int, chain: str = "ethereum"):
    d = get_driver()
    with d.session() as s:
        s.run("MERGE (w:Wallet {address:$a, chain:$ch}) SET w.riskScore=$s, w.txCount=$n",
              a=address.lower(), ch=chain, s=int(score), n=int(profile.get("tx_count") or 0))
        for t in (txs or [])[:25]:
            if not t.get("hash"): continue
            s.run("""MERGE (t:Transaction {hash:$h, chain:$ch})
                     SET t.valueUsd=$v
                     MERGE (a:Wallet {address:$f, chain:$ch})
                     MERGE (b:Wallet {address:$t2, chain:$ch})
                     MERGE (a)-[:SENT]->(t)-[:TO]->(b)""",
                  h=t["hash"], ch=chain, v=float(t.get("value_usd") or 0),
                  f=str(t.get("from") or address).lower(),
                  t2=str(t.get("to") or address).lower())
