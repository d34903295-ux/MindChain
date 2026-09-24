"""Anomaly Detection v1 (Fase 3): Isolation Forest sobre features de wallets.
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
