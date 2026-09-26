"""Tests de los bugs corregidos: evidencia, parsers y validadores."""
import sys

sys.path.insert(0, ".")

from agents.wallet_intelligence import profile_wallet, build_profile, _parse_time
from agents.fetcher import normalize_txs, _hex_to_int
from agents.risk_scoring import score_wallet
from agents.explanation import explain
from agents.price import get_price_usd


# ----------------------------------------------------------------- fechas ISO
def test_parse_iso_blockscout():
    d = _parse_time("2026-09-20T10:00:00Z")
    assert d is not None and d.hour == 10


def test_parse_iso_con_milisegundos():
    d = _parse_time("2026-09-20T10:00:00.123456Z")
    assert d is not None and d.hour == 10


def test_parse_blockchair():
    d = _parse_time("2026-09-20 10:00:00")
    assert d is not None and d.hour == 10


def test_parse_invalida_no_rompe():
    assert _parse_time("") is None
    assert _parse_time("no-es-fecha") is None


# ------------------------------------------------- perfil: muestra y confianza
def test_perfil_reporta_confianza():
    p = profile_wallet("0x" + "a" * 40, [], {"transaction_count": 100})
    assert p["sample_size"] == 0 and p["sample_confidence"] == "nula"


def test_confianza_alta_con_25_muestras():
    txs = [{"from": "0x" + f"{i:040x}", "to": "0x" + "a" * 40, "value_eth": 0.1, "value_usd": 30, "time": "2026-09-20T10:00:00Z"} for i in range(25)]
    p = profile_wallet("0x" + "a" * 40, txs, {"transaction_count": 100})
    assert p["sample_size"] == 25 and p["sample_confidence"] == "alta"


def test_self_transfer_ignorado():
    a = "0x" + "a" * 40
    txs = [{"from": a, "to": a, "value_eth": 5, "value_usd": 1000, "time": "2026-09-20T10:00:00Z"}]
    p = profile_wallet(a, txs, {"transaction_count": 1})
    assert p["self_transfers_ignored"] == 1
    assert p["in_count_sample"] == 0 and p["out_count_sample"] == 0
    assert p["counterparties_sample"] == 0


def test_bot_like_exige_evidencia():
    a = "0x" + "a" * 40
    pocas = [{"from": "0x" + f"{i:040x}", "to": a, "value_eth": 1, "value_usd": 1, "time": f"2026-09-20T{i:02d}:00:00Z"} for i in range(8)]
    p = profile_wallet(a, pocas, {"transaction_count": 50})
    assert p["bot_like"] is False
    muchas = [{"from": "0x" + f"{i:040x}", "to": a, "value_eth": 1, "value_usd": 1, "time": f"2026-09-20T{i:02d}:30:00Z"} for i in range(20)]
    p2 = profile_wallet(a, muchas, {"transaction_count": 5000, "age_days": 10})
    assert p2["bot_like"] is True


def test_usd_null_si_no_hay_precio(monkeypatch):
    import time as _t
    import agents.price as price_mod
    # precio ausente y cacheado como "recién cargado" para que no vuelva a la red
    monkeypatch.setattr(price_mod, "_cache", {"eth_usd": (_t.time(), None)})
    txs = [{"from": "0x" + "b" * 40, "to": "0x" + "a" * 40, "value_eth": 1, "value_usd": None, "time": "2026-09-20T10:00:00Z"}]
    p = profile_wallet("0x" + "a" * 40, txs, {"transaction_count": 10})
    assert p["in_usd_sample"] is None  # no inventa 0


# --------------------------------------------------------------- normalización
def test_hex_wei_a_eth():
    txs = normalize_txs("0x" + "a" * 40, [{
        "hash": "0x1", "from": {"hash": "0x" + "a" * 40}, "to": {"hash": "0x" + "b" * 40},
        "value": hex(2 * 10 ** 18), "timestamp": "2026-09-20T10:00:00Z", "block_number": 7,
    }])
    assert txs[0]["value_eth"] == 2.0
    assert txs[0]["block"] == 7


def test_hex_sin_prefijo():
    assert _hex_to_int("0x10") == 16
    assert _hex_to_int("ff") == 255
    assert _hex_to_int(None) == 0
    assert _hex_to_int("basura") == 0


def test_normalize_ignora_no_dict():
    assert normalize_txs("0x1", [None, "x", 5]) == []


# ---------------------------------------------------------------- risk scoring
def test_concentracion_exige_muestra():
    addr = "0x" + "a" * 40
    pocas = [{"to": addr, "from": "0x" + "b" * 40, "value_usd": 100}] * 3
    s, f = score_wallet({"address": addr, "tx_count": 3}, pocas)
    assert "concentracion_fondos_una_fuente" not in f


def test_concentracion_por_valor_no_por_conteo():
    addr = "0x" + "a" * 40
    txs = []
    for i in range(9):
        txs.append({"to": addr, "from": "0x" + f"{i:040x}", "value_usd": 10_000})
    txs.append({"to": addr, "from": "0x" + "f" * 40, "value_usd": 5_000_000})
    s, f = score_wallet({"address": addr, "tx_count": 500, "age_days": 800}, txs)
    assert "concentracion_fondos_una_fuente" in f


def test_concentracion_ignora_valor_irrelevante():
    """25 tx de céntimos no pueden disparar una alerta de concentración."""
    addr = "0x" + "a" * 40
    txs = [{"to": addr, "from": "0x" + f"{i:040x}", "value_usd": 0.01} for i in range(9)]
    txs.append({"to": addr, "from": "0x" + "f" * 40, "value_usd": 0.05})
    s, f = score_wallet({"address": addr, "tx_count": 500, "age_days": 800}, txs)
    assert "concentracion_fondos_una_fuente" not in f


def test_concentracion_no_para_contratos():
    """Un contrato recibe de miles de fuentes: la regla no aplica."""
    addr = "0x" + "a" * 40
    txs = [{"to": addr, "from": "0x" + f"{i:040x}", "value_usd": 10_000} for i in range(9)]
    txs.append({"to": addr, "from": "0x" + "f" * 40, "value_usd": 5_000_000})
    s, f = score_wallet({"address": addr, "tx_count": 500, "age_days": 800,
                         "labels": ["contract"]}, txs)
    assert "concentracion_fondos_una_fuente" not in f


def test_concentracion_no_para_wallet_joven():
    addr = "0x" + "a" * 40
    txs = [{"to": addr, "from": "0x" + f"{i:040x}", "value_usd": 10_000} for i in range(9)]
    txs.append({"to": addr, "from": "0x" + "f" * 40, "value_usd": 5_000_000})
    s, f = score_wallet({"address": addr, "tx_count": 12, "age_days": 5}, txs)
    assert "concentracion_fondos_una_fuente" not in f


def test_no_alerta_con_una_sola_contraparte():
    addr = "0x" + "a" * 40
    txs = [{"to": addr, "from": "0x" + "b" * 40, "value_usd": 100_000}] * 10
    s, f = score_wallet({"address": addr, "tx_count": 500, "age_days": 400}, txs)
    assert "concentracion_fondos_una_fuente" not in f


def test_mixer_verificado(monkeypatch):
    import agents.watchlist as wl
    watched = "0x" + "ab" * 20
    monkeypatch.setattr(wl, "refresh", lambda: {watched: "pool-verificada"})
    addr = "0x" + "a" * 40
    s, f = score_wallet({"address": addr, "tx_count": 10, "age_days": 100},
                        [{"from": addr, "to": watched, "value_usd": 5}])
    assert any(x.startswith("interaccion_watchlist:") for x in f)
    assert s >= 50


def test_watchlist_vacia_por_defecto():
    import agents.watchlist as wl
    info = wl.info()
    assert isinstance(info["size"], int)
    # la lista local shippeada está vacía: no inventamos direcciones
    assert info["size"] == 0


def test_score_acotado_0_100(monkeypatch):
    import agents.watchlist as wl
    watched = "0x" + "ab" * 20
    monkeypatch.setattr(wl, "refresh", lambda: {watched: "pool"})
    addr = "0x" + "a" * 40
    txs = [{"from": addr, "to": watched, "value_usd": 10} for _ in range(30)]
    s, _ = score_wallet({"address": addr, "tx_count": 1, "balance_usd": 5_000_000,
                         "bot_like": True, "freq_tx_day": 500, "labels": ["dormant"]}, txs)
    assert 0 <= s <= 100


def test_convoy_detectado():
    addr = "0x" + "a" * 40
    src = "0x" + "c" * 40
    txs = [{"to": addr, "from": src, "value_usd": 1} for _ in range(8)]
    txs += [{"to": "0x" + "d" * 40, "from": "0x" + "e" * 40, "value_usd": 1} for _ in range(4)]
    s, f = score_wallet({"address": addr, "tx_count": 5000, "age_days": 900}, txs)
    assert "patron_convoy_mismo_origen" in f


def test_convoy_no_dispara_en_wallet_joven():
    """6-7 tx del mismo origen en una wallet nueva es ruido, no un patrón."""
    addr = "0x" + "a" * 40
    src = "0x" + "c" * 40
    txs = [{"to": addr, "from": src, "value_usd": 1} for _ in range(7)]
    s, f = score_wallet({"address": addr, "tx_count": 9, "age_days": 4}, txs)
    assert "patron_convoy_mismo_origen" not in f


def test_contador_no_confiable_no_inventa_numero():
    """Blockscout da contadores inconsistentes: preferimos n/d a un número falso."""
    p = profile_wallet("0x" + "a" * 40, [], {"transaction_count": None, "tx_count_reliable": False})
    assert p["tx_count"] is None
    assert p["tx_count_reliable"] is False
    assert p["activity"] == "desconocida"
    assert p["freq_tx_day"] is None


def test_riesgo_no_usa_contador_no_confiable():
    addr = "0x" + "a" * 40
    # sin histórico fiable NO se dispara "wallet nueva" (sería un invento)
    s, f = score_wallet({"address": addr, "tx_count": None, "tx_count_reliable": False,
                        "sample_confidence": "nula"}, [])
    assert "wallet_nueva_pocas_txs" not in f
    # BUG 2: con muestra nula ya no se devuelve un número, sino la abstención
    assert s is None
    assert f == ["datos_insuficientes_no_evaluable"]


def test_score_none_con_poca_muestra():
    """Con 1-7 transacciones el score es None, no un número con aire de válido.

    Antes devolvía un score y solo añadía el factor informativo
    `datos_insuficientes_score_provisional`, así que el endpoint enseñaba una
    cifra que no sostenía la evidencia.
    """
    addr = "0x" + "a" * 40
    s, f = score_wallet({"address": addr, "tx_count": 100, "sample_confidence": "baja"}, [])
    assert s is None, "una muestra de 1-7 tx no sostiene un score"
    assert "datos_insuficientes_no_evaluable" in f
    assert "datos_insuficientes_score_provisional" not in f


def test_score_none_cuando_no_hay_datos():
    """Con la red caída el score debe ser None, nunca un 0/30 inventado."""
    addr = "0x" + "a" * 40
    s, f = score_wallet({"address": addr, "insufficient_data": True, "tx_count": None}, [])
    assert s is None
    assert f == ["datos_insuficientes_no_evaluable"]


def test_explicacion_abstiene_sin_datos(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = explain(
        {"address": "0xabc", "insufficient_data": True, "data_errors": ["rpc: ninguna cadena RPC respondio"]},
        None,
        ["datos_insuficientes_no_evaluable"],
    )
    assert "no se evalúa" in t
    assert "Reintenta" in t


def test_abstencion_impide_llamar_a_wallet_nueva(monkeypatch):
    """Un fallo de red jamás debe producir 'wallet nueva'."""
    import agents.fetcher as F
    monkeypatch.setattr(F, "_http_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("red caida")))
    monkeypatch.setattr(F, "_http_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("red caida")))
    F._cache.clear()
    r = F.fetch_wallet_data("0x" + "d" * 40, use_cache=False)
    dq = r["data_quality"]
    assert dq["insufficient_data"] is True
    assert dq["degraded"] is True
    assert dq["errors"], "debe reportar la causa"
    p, txs = build_profile("0x" + "d" * 40, r)
    assert p["insufficient_data"] is True
    s, f = score_wallet(p, txs)
    assert s is None
    assert "wallet_nueva_pocas_txs" not in f


def test_rpc_snapshot_reporta_si_respondio(monkeypatch):
    import agents.fetcher as F
    monkeypatch.setattr(F, "_rpc_call", lambda *a, **k: None)
    snap = F.rpc_snapshot(["http://x"], "0x" + "a" * 40)
    assert snap["any_rpc"] is False
    assert snap["balance_known"] is False


def test_price_cache_no_rompe():
    p = get_price_usd()
    assert p is None or p > 0
