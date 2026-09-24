"""ChainMind Fase 3 scaffold — Anomaly Detection Isolation Forest + batch + endpoint."""
import pathlib
ROOT = pathlib.Path(__file__).parent
FILES = {}

FILES["agents/anomaly.py"] = '''"""Anomaly Detection v1 (Fase 3): Isolation Forest sobre features de wallets.
Features: frecuencia, montos in/out, contrapartes, balance, edad, bot_like.
Batch nocturno (jobs/nightly_anomaly.py). Referencia:
https://github.com/epicprojects/blockchain-anomaly-detection
"""
import math
import statistics

FEATURE_NAMES = ["log_tx", "log_freq", "log_in_usd", "log_out_usd",
                 "log_cps", "log_balance", "bot_like", "log_age"]
MIN_SAMPLES = 5

def _num(x, default=0.0):
    try:
        v = float(x)
        if v != v:
            return default
        return v
    except Exception:
        return default

def features_from_profile(profile):
    p = profile or {}
    age = p.get("age_days")
    return [
        math.log1p(max(_num(p.get("tx_count")), 0.0)),
        math.log1p(max(_num(p.get("freq_tx_day")), 0.0)),
        math.log1p(max(_num(p.get("in_usd_sample")), 0.0)),
        math.log1p(max(_num(p.get("out_usd_sample")), 0.0)),
        math.log1p(max(_num(p.get("counterparties_sample")), 0.0)),
        math.log1p(max(_num(p.get("balance_usd")), 0.0)),
        1.0 if p.get("bot_like") else 0.0,
        math.log1p(max(_num(age, 0.0), 0.0)),
    ]

def top_deviation(vec, medians):
    best, best_v = FEATURE_NAMES[0], -1.0
    for name, x, m in zip(FEATURE_NAMES, vec, medians):
        d = abs(x - m) / (1.0 + abs(m))
        if d > best_v:
            best, best_v = name, d
    return best, round(best_v, 3)

def scan_wallets(items, contamination=0.1):
    """items: [{address, profile}]. Devuelve flags deterministicos (random_state=42)."""
    addrs = [it.get("address", "") for it in items]
    vecs = [features_from_profile(it.get("profile", {})) for it in items]
    if len(items) < MIN_SAMPLES:
        return [{"address": a, "is_anomaly": False, "anomaly_score": 0.0,
                 "reason": "muestra_insuficiente", "top_feature": None} for a in addrs]
    from sklearn.ensemble import IsolationForest
    import numpy as np
    X = np.array(vecs, dtype=float)
    medians = [statistics.median(X[:, j].tolist()) for j in range(X.shape[1])]
    clf = IsolationForest(n_estimators=100, contamination=contamination, random_state=42)
    preds = clf.fit_predict(X)
    raw = (-clf.score_samples(X)).tolist()
    out = []
    for a, p, s, v in zip(addrs, preds.tolist(), raw, vecs):
        feat, dev = top_deviation(v, medians)
        out.append({"address": a, "is_anomaly": bool(p == -1),
                    "anomaly_score": round(float(s), 4),
                    "reason": "isolation-forest-24h" if p == -1 else "normal",
                    "top_feature": feat if p == -1 else None,
                    "top_deviation": dev if p == -1 else 0.0})
    return out
'''

FILES["jobs/__init__.py"] = ''''''

FILES["jobs/nightly_anomaly.py"] = '''"""Job batch nocturno Fase 3: marca wallets con actividad anómala últimas 24h.
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
'''

FILES["backend/app/routers/anomaly.py"] = '''import sys, pathlib
from fastapi import APIRouter
from pydantic import BaseModel, Field

ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from agents.anomaly import scan_wallets

router = APIRouter()

class WalletItem(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    profile: dict = {}

class ScanRequest(BaseModel):
    items: list[WalletItem]
    contamination: float = 0.1

@router.post("/anomaly-scan")
def anomaly_scan(payload: ScanRequest):
    flags = scan_wallets([{"address": it.address, "profile": it.profile} for it in payload.items],
                         contamination=max(0.01, min(payload.contamination, 0.5)))
    return {"model": "isolation-forest", "n": len(flags),
            "anomalies": [f for f in flags if f.get("is_anomaly")], "all": flags}
'''

FILES["agents/tests/test_anomaly.py"] = '''from agents.anomaly import scan_wallets, features_from_profile

def _normal(i):
    return {"address": "0x" + format(i, "040x"),
            "profile": {"tx_count": 100 + i * 3, "freq_tx_day": 1.0 + i * 0.05,
                        "in_usd_sample": 500.0 + i * 10, "out_usd_sample": 480.0,
                        "counterparties_sample": 25 + i, "balance_usd": 4000.0,
                        "bot_like": False, "age_days": 300 + i}}

def test_outlier_detectado():
    items = [_normal(i) for i in range(10)]
    items.append({"address": "0x" + "f" * 40,
                  "profile": {"tx_count": 60000, "freq_tx_day": 1200.0,
                              "in_usd_sample": 80000000.0, "out_usd_sample": 10.0,
                              "counterparties_sample": 2, "balance_usd": 20000000.0,
                              "bot_like": True, "age_days": 1}})
    flags = scan_wallets(items)
    by = {f["address"]: f for f in flags}
    assert by["0x" + "f" * 40]["is_anomaly"] is True
    assert by["0x" + "f" * 40]["top_feature"] is not None

def test_determinista():
    items = [_normal(i) for i in range(8)]
    assert scan_wallets(items) == scan_wallets(items)

def test_muestra_pequena():
    flags = scan_wallets([_normal(0), _normal(1)])
    assert all(f["is_anomaly"] is False for f in flags)
    assert flags[0]["reason"] == "muestra_insuficiente"

def test_features_robusto_a_none():
    v = features_from_profile({"tx_count": None, "age_days": None})
    assert len(v) == 8 and all(isinstance(x, float) for x in v)
'''

FILES["backend/tests/test_anomaly_ep.py"] = '''from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def _item(i, **kw):
    p = {"tx_count": 100 + i, "freq_tx_day": 1.0, "in_usd_sample": 500.0,
         "out_usd_sample": 480.0, "counterparties_sample": 20,
         "balance_usd": 3000.0, "bot_like": False, "age_days": 200}
    p.update(kw)
    return {"address": "0x" + format(i + 1, "040x"), "profile": p}

def test_anomaly_scan_ep():
    items = [_item(i) for i in range(7)]
    r = client.post("/anomaly-scan", json={"items": items})
    assert r.status_code == 200
    j = r.json()
    assert j["model"] == "isolation-forest" and j["n"] == 7 and "anomalies" in j
'''

for rel, content in FILES.items():
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print("wrote", rel)
