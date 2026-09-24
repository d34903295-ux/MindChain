import os, json
import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://chainmind:chainmind_dev@localhost:5432/chainmind")

def get_conn():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)

def upsert_wallet_report(address: str, profile: dict, score: int, factors: list, explanation: str):
    addr = address.lower()
    with get_conn() as c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO wallets(address, chain, tx_count, risk_score, labels)
                           VALUES(%s,'ethereum',%s,%s,%s)
                           ON CONFLICT(address) DO UPDATE SET tx_count=EXCLUDED.tx_count,
                             risk_score=EXCLUDED.risk_score, labels=EXCLUDED.labels, updated_at=now()
                           RETURNING id""",
                        (addr, int(profile.get("tx_count") or 0), int(score), list(profile.get("labels") or [])))
            wid = cur.fetchone()["id"]
            cur.execute("""INSERT INTO reports(wallet_id, profile, risk_score, risk_factors, explanation)
                           VALUES(%s,%s,%s,%s,%s)""",
                        (wid, json.dumps(profile), int(score), json.dumps(factors), explanation))
        c.commit()
