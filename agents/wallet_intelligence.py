"""Wallet Intelligence Agent (Fase 1 real).
Perfil básico: antigüedad, nº txs, contrapartes, actividad.
Heurística conductual estilo Gator: distribución horaria -> bot vs humano, timezone dominante.
"""
from datetime import datetime, timezone
from collections import Counter

def _parse_time(s: str):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except Exception:
        return None

def profile_wallet(address: str, txs: list[dict], raw: dict | None = None) -> dict:
    addr_l = address.lower()
    raw = raw or {}
    tx_count = int(raw.get("transaction_count") or raw.get("call_count") or len(txs) or 0)
    # edad
    first = raw.get("first_seen_receiving") or raw.get("first_seen_spending")
    last = raw.get("last_seen_receiving") or raw.get("last_seen_spending")
    age_days = None
    try:
        if first:
            dt = _parse_time(first)
            if dt: age_days = max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        pass
    # contrapartes + volúmenes + horarios
    cps: set[str] = set()
    in_n = out_n = 0; in_usd = out_usd = 0.0
    hours: list[int] = []
    for t in txs or []:
        f, to = (t.get("from") or "").lower(), (t.get("to") or "")
        to = to.lower() if to else None
        if f and f != addr_l: cps.add(f)
        if to and to != addr_l: cps.add(to)
        v = float(t.get("value_usd") or 0)
        if to == addr_l: in_n += 1; in_usd += v
        elif f == addr_l: out_n += 1; out_usd += v
        else:
            # muestra blockchair centrada en la wallet: si es recipient -> in
            if to == addr_l: in_n += 1; in_usd += v
        dt = _parse_time(t.get("time", ""))
        if dt: hours.append(dt.hour)
    # actividad: frecuencia + patrón horario
    freq_day = round(tx_count / max(age_days or 1, 1), 2) if tx_count else 0
    bot_like = False; tz_note = "sin_muestra"
    if len(hours) >= 5:
        hist = Counter(hours)
        # bot si cubre >=12 horas distintas o desviación baja entre buckets
        bot_like = len(hist) >= 12 or (max(hist.values()) - min(hist.values()) <= 1 and len(hist) >= 8)
        peak = hist.most_common(1)[0][0]
        tz_note = f"hora_pico_utc_{peak}h_{'24h_uniforme_bot_like' if bot_like else 'concentrado_humano_posible'}"
    activity = "dormant" if (age_days or 0) > 180 and freq_day < 0.05 else ("alta" if freq_day > 20 else ("media" if freq_day > 1 else "baja"))
    try: bal_usd = float(raw.get("balance_usd") or 0)
    except Exception: bal_usd = 0.0
    labels = []
    if (raw.get("type") == "contract"): labels.append("contract")
    else: labels.append("eoa")
    if bal_usd > 1_000_000: labels.append("whale")
    if (age_days is not None and age_days < 30 and tx_count < 10): labels.append("nueva")
    if bot_like: labels.append("bot_like")
    if activity == "dormant": labels.append("dormant")
    return {"address": address, "chain": "ethereum", "tx_count": tx_count,
            "age_days": age_days, "first_seen": first, "last_seen": last,
            "counterparties_sample": len(cps), "in_count_sample": in_n, "out_count_sample": out_n,
            "in_usd_sample": round(in_usd, 2), "out_usd_sample": round(out_usd, 2),
            "balance_wei": str(raw.get("balance") or 0), "balance_usd": bal_usd,
            "freq_tx_day": freq_day, "activity": activity, "bot_like": bot_like,
            "timezone_note": tz_note, "labels": labels,
            "received_total": str(raw.get("received_approximate") or 0),
            "fees_total": str(raw.get("fees_approximate") or 0)}

def build_profile(address: str, fetched: dict) -> tuple[dict, list[dict]]:
    from .fetcher import normalize_txs
    txs = normalize_txs(address, fetched.get("calls", []))
    profile = profile_wallet(address, txs, fetched.get("raw_address", {}))
    profile["chain"] = fetched.get("chain", "ethereum")
    return profile, txs
