"""Wallet Intelligence Agent — perfil con evidencia y confianza explícita.

Fixes aplicados:
- parsea fechas ISO 8601 (Blockscout/Base) y formato Blockchair (Ethereum)
- convierte valor wei hex a ETH y aplica precio con caché
- ignora self-transfers
- reporta tamaño de muestra y confianza (los heurísticos no deben statically mentir)
"""
from collections import Counter
from datetime import datetime, timezone

from .price import get_price_usd


def _parse_time(value):
    """Acepta 'YYYY-MM-DD HH:MM:SS' (Blockchair) e ISO 8601 (Blockscout/RPC)."""
    if not value:
        return None
    s = str(value).strip().replace("T", " ").replace("Z", "").replace("+00:00", "")
    if s.endswith("Z"):
        s = s[:-1]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _num(v, default=0.0) -> float:
    try:
        f = float(v)
        return default if f != f else f
    except Exception:
        return default


def _sample_confidence(n: int) -> str:
    if n >= 20:
        return "alta"
    if n >= 8:
        return "media"
    if n > 0:
        return "baja"
    return "nula"


def profile_wallet(address: str, txs: list[dict], raw: dict | None = None) -> dict:
    addr_l = str(address or "").lower()
    raw = raw or {}
    txs = [t for t in (txs or []) if isinstance(t, dict)]

    try:
        raw_tx_count = raw.get("transaction_count")
        tx_count = int(raw_tx_count) if raw_tx_count is not None else None
    except Exception:
        tx_count = None
    # Blockscout no da un histórico fiable: se marca como desconocido en vez de inventar.
    tx_count_reliable = raw.get("tx_count_reliable", True) and tx_count is not None
    if tx_count is None:
        tx_count = None

    # --- antigüedad (la más antigua conocida entre entrada y salida)
    first_candidates = [raw.get("first_seen_receiving"), raw.get("first_seen_spending")]
    last_candidates = [raw.get("last_seen_receiving"), raw.get("last_seen_spending")]
    parsed_first = [d for d in (_parse_time(x) for x in first_candidates) if d]
    parsed_last = [d for d in (_parse_time(x) for x in last_candidates) if d]
    first_dt = min(parsed_first) if parsed_first else None
    last_dt = max(parsed_last) if parsed_last else None
    age_days = None
    if first_dt:
        age_days = max(0, (datetime.now(timezone.utc) - first_dt).days)

    price = get_price_usd()

    cps: set[str] = set()
    in_n = out_n = 0
    in_eth = out_eth = 0.0
    in_usd = out_usd = 0.0
    usd_priced = 0
    hours: list[int] = []
    self_transfers = 0

    for t in txs:
        f = _lower_addr(t.get("from"))
        to = _lower_addr(t.get("to"))
        if f and to and f == to:
            self_transfers += 1
            continue
        if f and f != addr_l:
            cps.add(f)
        if to and to != addr_l:
            cps.add(to)
        eth = _num(t.get("value_eth"))
        usd = t.get("value_usd")
        usd = None if usd is None else _num(usd)
        if usd is None and eth and price:
            usd = eth * price
        if usd is not None:
            usd_priced += 1
        if to == addr_l:
            in_n += 1
            in_eth += eth
            in_usd += usd or 0.0
        elif f == addr_l:
            out_n += 1
            out_eth += eth
            out_usd += usd or 0.0
        dt = _parse_time(t.get("time"))
        if dt:
            hours.append(dt.hour)

    # --- actividad
    denom = age_days if age_days and age_days > 0 else None
    if tx_count is not None and denom:
        freq_day: float | None = round(tx_count / denom, 2)
    else:
        freq_day = None
    if age_days is not None and age_days > 180 and (freq_day or 0) < 0.05:
        activity = "dormant"
    elif freq_day is None:
        activity = "desconocida"
    elif freq_day > 20:
        activity = "alta"
    elif freq_day > 1:
        activity = "media"
    else:
        activity = "baja"

    # --- patrón horario: exige evidencia suficiente
    bot_like = False
    tz_note = "sin_muestra"
    if len(hours) >= 20:
        hist = Counter(hours)
        uniform = len(hist) >= 14 or (len(hist) >= 10 and max(hist.values()) - min(hist.values()) <= 1)
        bot_like = uniform
        peak = hist.most_common(1)[0][0]
        tz_note = f"hora_pico_utc_{peak}h_{'uniforme_bot_like' if bot_like else 'concentrado_humano_posible'}"
    elif len(hours) >= 8:
        hist = Counter(hours)
        peak = hist.most_common(1)[0][0]
        tz_note = f"hora_pico_utc_{peak}h_muestra_reducida"

    try:
        bal_usd = _num(raw.get("balance_usd"))
    except Exception:
        bal_usd = 0.0

    labels = ["contract" if raw.get("type") == "contract" else "eoa"]
    if bal_usd > 1_000_000:
        labels.append("whale")
    if age_days is not None and age_days < 30 and tx_count is not None and tx_count < 10:
        labels.append("nueva")
    if bot_like:
        labels.append("bot_like")
    if activity == "dormant":
        labels.append("dormant")

    return {
        "address": address,
        "tx_count": tx_count,
        "tx_count_reliable": tx_count_reliable,
        "age_days": age_days,
        "first_seen": first_dt.strftime("%Y-%m-%d %H:%M:%S") if first_dt else None,
        "last_seen": last_dt.strftime("%Y-%m-%d %H:%M:%S") if last_dt else None,
        "sample_size": len(txs),
        "sample_confidence": _sample_confidence(len(txs)),
        "usd_priced_rows": usd_priced,
        "price_usd": price,
        "counterparties_sample": len(cps),
        "in_count_sample": in_n,
        "out_count_sample": out_n,
        "self_transfers_ignored": self_transfers,
        "in_eth_sample": round(in_eth, 6),
        "out_eth_sample": round(out_eth, 6),
        "in_usd_sample": round(in_usd, 2) if usd_priced else None,
        "out_usd_sample": round(out_usd, 2) if usd_priced else None,
        "balance_wei": str(raw.get("balance") or 0),
        "balance_usd": bal_usd,
        "freq_tx_day": freq_day,
        "activity": activity,
        "bot_like": bot_like,
        "timezone_note": tz_note,
        "labels": labels,
        "received_total": str(raw.get("received_approximate") or 0),
        "fees_total": str(raw.get("fees_approximate") or 0),
    }


def _lower_addr(v) -> str:
    return str(v or "").strip().lower()


def build_profile(address: str, fetched: dict) -> tuple[dict, list[dict]]:
    from .fetcher import normalize_txs

    txs = normalize_txs(address, fetched.get("calls", []))
    profile = profile_wallet(address, txs, fetched.get("raw_address", {}))
    profile["chain"] = fetched.get("chain", "ethereum")
    return profile, txs
