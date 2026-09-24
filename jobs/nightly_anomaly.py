"""Job batch nocturno Fase 3: marca wallets con actividad anómala últimas 24h.
Uso: python jobs/nightly_anomaly.py [--demo] [--input wallets.json] [--out reports]
Sin DB: usa --demo o --input. Con DB (DATABASE_URL): lee raw_transactions 24h.
"""
import sys, os, json, datetime, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents.anomaly import scan_wallets

def demo_items():
    base = {"tx_count": 120, "freq_tx_day": 1.2, "in_usd_sample": 800.0,
            "out_usd_sample": 750.0, "counterparties_sample": 30,
            "balance_usd": 5000.0, "bot_like": False, "age_days": 400}
    items = [{"address": "0x" + format(i, "040x"), "profile": dict(base, address="0x" + format(i, "040x"))} for i in range(11)]
    items.append({"address": "0x" + "f" * 40,
                  "profile": {"address": "0x" + "f" * 40, "tx_count": 40000, "freq_tx_day": 900.0,
                              "in_usd_sample": 50000000.0, "out_usd_sample": 1000.0,
                              "counterparties_sample": 3, "balance_usd": 9000000.0,
                              "bot_like": True, "age_days": 2}})
    return items

def from_db():
    import psycopg
    from psycopg.rows import dict_row
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return None
    items = []
    with psycopg.connect(url, row_factory=dict_row) as c:
        with c.cursor() as cur:
            cur.execute("SELECT address, tx_count, risk_score FROM wallets ORDER BY updated_at DESC LIMIT 500")
            rows = cur.fetchall()
            for r in rows:
                cur.execute("SELECT COUNT(*) AS n, COALESCE(SUM(value_numeric),0) AS vol FROM raw_transactions WHERE (from_address=%s OR to_address=%s) AND block_time > now() - interval '24 hours'", (r["address"], r["address"]))
                w = cur.fetchone()
                n = int(w["n"] or 0)
                items.append({"address": r["address"], "profile": {
                    "address": r["address"], "tx_count": int(r["tx_count"] or 0),
                    "freq_tx_day": float(n), "in_usd_sample": 0.0, "out_usd_sample": 0.0,
                    "counterparties_sample": 0, "balance_usd": 0.0,
                    "bot_like": bool(n > 500), "age_days": 365}})
    return items

def mark_db(flags):
    import psycopg
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return 0
    n = 0
    with psycopg.connect(url) as c:
        with c.cursor() as cur:
            for f in flags:
                if f.get("is_anomaly"):
                    cur.execute("UPDATE wallets SET labels = array_append(COALESCE(labels, '{}'), 'anomaly_24h'), updated_at=now() WHERE address=%s", (f["address"].lower(),))
                    n += cur.rowcount
        c.commit()
    return n

def main():
    args = sys.argv[1:]
    outdir = pathlib.Path("reports")
    if "--out" in args:
        outdir = pathlib.Path(args[args.index("--out") + 1])
    outdir.mkdir(parents=True, exist_ok=True)
    if "--demo" in args:
        items = demo_items()
    elif "--input" in args:
        items = json.loads(pathlib.Path(args[args.index("--input") + 1]).read_text(encoding="utf-8"))
    else:
        try:
            items = from_db()
        except Exception as e:
            print("DB no disponible:", str(e)[:200])
            items = None
        if not items:
            print("Sin datos: usa --demo o --input wallets.json")
            return 1
    flags = scan_wallets(items)
    anoms = [f for f in flags if f.get("is_anomaly")]
    day = datetime.date.today().isoformat()
    (outdir / ("anomalies-" + day + ".json")).write_text(json.dumps({"date": day, "n": len(flags), "anomalies": anoms, "all": flags}, indent=1), encoding="utf-8")
    try:
        print("marcadas en DB:", mark_db(flags))
    except Exception as e:
        print("mark_db omitido:", str(e)[:200])
    print("wallets:", len(flags), "anomalías:", len(anoms))
    for f in anoms:
        print(" -", f["address"], f["anomaly_score"], f["top_feature"])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
