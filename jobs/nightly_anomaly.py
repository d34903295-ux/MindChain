"""Job batch nocturno: Isolation Forest sobre wallets + persistencia local.

Por qué JSON y no solo Postgres: el job debe poder ejecutarse aunque la base de
datos no esté levantada (docker no es requisito para operar ChainMind). Si
DATABASE_URL está disponible, también marca las wallets en Postgres.

Uso:
    python jobs/nightly_anomaly.py --demo
    python jobs/nightly_anomaly.py --input wallets.json
    python jobs/nightly_anomaly.py          # lee de Postgres si existe
"""
import datetime
import json
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.anomaly import scan_wallets

REPORTS = ROOT / "reports"


def demo_items():
    base = {"tx_count": 120, "freq_tx_day": 1.2, "in_usd_sample": 800.0,
            "out_usd_sample": 750.0, "counterparties_sample": 30,
            "balance_usd": 5000.0, "bot_like": False, "age_days": 400}
    items = [{"address": "0x" + format(i, "040x"),
              "profile": dict(base, address="0x" + format(i, "040x"))} for i in range(11)]
    items.append({"address": "0x" + "f" * 40,
                  "profile": {"address": "0x" + "f" * 40, "tx_count": 40000, "freq_tx_day": 900.0,
                              "in_usd_sample": 50000000.0, "out_usd_sample": 1000.0,
                              "counterparties_sample": 3, "balance_usd": 9000000.0,
                              "bot_like": True, "age_days": 2}})
    return items


def from_db():
    """Lee wallets + actividad 24h de Postgres. Devuelve None si no hay DB."""
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return None
    try:
        import psycopg
        from psycopg.rows import dict_row
    except Exception:
        return None
    items = []
    try:
        with psycopg.connect(url, row_factory=dict_row) as c, c.cursor() as cur:
            cur.execute("SELECT address, tx_count, risk_score FROM wallets ORDER BY updated_at DESC LIMIT 500")
            rows = cur.fetchall()
            for r in rows:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM raw_transactions "
                    "WHERE (from_address=%s OR to_address=%s) "
                    "AND block_time > now() - interval '24 hours'",
                    (r["address"], r["address"]),
                )
                n24 = int((cur.fetchone() or {}).get("n") or 0)
                items.append({"address": r["address"], "profile": {
                    "address": r["address"],
                    "tx_count": int(r["tx_count"] or 0),
                    "freq_tx_day": float(n24),
                    "in_usd_sample": 0.0, "out_usd_sample": 0.0,
                    "counterparties_sample": 0, "balance_usd": 0.0,
                    "bot_like": bool(n24 > 500), "age_days": 365,
                    "sample_confidence": "media" if n24 >= 8 else "baja"}})
    except Exception as e:
        print(f"Postgres no disponible ({str(e)[:60]}). Se omite la lectura.")
        return None
    return items or None


def mark_db(flags) -> int:
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return 0
    try:
        import psycopg
    except Exception:
        return 0
    n = 0
    try:
        with psycopg.connect(url) as c, c.cursor() as cur:
            for f in flags:
                if f.get("is_anomaly"):
                    cur.execute(
                        "UPDATE wallets SET labels = array_append(COALESCE(labels, '{}'), 'anomaly_24h'), "
                        "updated_at=now() WHERE address=%s",
                        (f["address"].lower(),),
                    )
                    n += cur.rowcount
        c.commit()
    except Exception as e:
        print(f"No se pudo marcar en Postgres: {str(e)[:60]}")
    return n


def main() -> int:
    args = sys.argv[1:]
    outdir = pathlib.Path(args[args.index("--out") + 1]) if "--out" in args else REPORTS
    outdir.mkdir(parents=True, exist_ok=True)

    if "--demo" in args:
        items, source = demo_items(), "demo"
    elif "--input" in args:
        path = pathlib.Path(args[args.index("--input") + 1])
        items, source = json.loads(path.read_text(encoding="utf-8")), str(path)
    else:
        items, source = from_db(), "postgres"
        if not items:
            print("Sin datos. Opciones: --demo (datos de prueba) o --input wallets.json")
            return 1

    flags = scan_wallets(items)
    anomalies = [f for f in flags if f.get("is_anomaly")]
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        "generated_at": now.isoformat(),
        "source": source,
        "n_wallets": len(flags),
        "n_anomalies": len(anomalies),
        "anomalies": anomalies,
        "all": flags,
    }
    out = outdir / f"anomalies-{now.date().isoformat()}.json"
    out.write_text(json.dumps(payload, indent=1), encoding="utf-8")

    print(f"wallets: {len(flags)} | anomalías: {len(anomalies)} | modelo: isolation-forest")
    print(f"reporte: {out}")
    for f in anomalies:
        print(f"  - {f['address']} score={f['anomaly_score']} factor={f.get('top_feature')}")
    marked = mark_db(flags)
    if marked:
        print(f"marcadas en Postgres: {marked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
