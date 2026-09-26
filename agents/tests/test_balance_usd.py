"""Tests del BUG A: `balance_usd` en 0 cuando sí hay balance y precio.

Contexto real (auditoría 2026-09-26): con Blockchair en timeout la wallet
0x28C6…1d60 devolvía

    balance_wei: "87174820214179648452939"   (87,17 ETH)
    price_usd:  2692.47
    balance_usd: 0.0                        <- mentira

El daño no era solo mostrar $0: `risk_scoring.py` puntúa +10 con
`balance_usd > 1_000_000`, así que esa regla de riesgo **no podía dispararse
nunca** en el camino de fallback.

Las tres fuentes (blockchair, blockscout y el snapshot RPC) dan el balance en
wei — verificado contra la API real de Blockscout, que devuelve
`coin_balance: "1713425000000000000"` = 1,713 ETH — así que derivar
wei/1e18*precio es válido en los tres caminos.
"""
import sys

import pytest

sys.path.insert(0, ".")

import agents.fetcher as F
import agents.wallet_intelligence as WI
from agents.risk_scoring import score_wallet
from agents.wallet_intelligence import build_profile, profile_wallet

WEI = 10 ** 18
BALANCE_WEI = "87174820146890656739388"  # 87.174,82 ETH (no 87,17: son 22 dígitos)
PRECIO = 2692.47
# Se calcula desde el propio wei en vez de a mano: escribir el número a mano
# fue justo lo que me hizo creer que el código dividía mal.
ESPERADO = round(int(BALANCE_WEI) / WEI * PRECIO, 2)


@pytest.fixture
def precio(monkeypatch):
    monkeypatch.setattr(WI, "get_price_usd", lambda *a, **k: PRECIO)


@pytest.fixture
def sin_precio(monkeypatch):
    monkeypatch.setattr(WI, "get_price_usd", lambda *a, **k: None)


# --------------------------------------------------------------- la derivación
def test_balance_usd_se_deriva_del_wei_si_el_adapter_no_lo_da(precio):
    """El caso exacto del bug: raw sin `balance_usd` y con balance en wei."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    assert p["balance_usd"] == pytest.approx(ESPERADO, rel=1e-6)
    assert p["balance_usd"] > 0, "el bug era devolver exactamente 0.0"


def test_un_balance_usd_de_cero_tambien_se_deriva(precio):
    """Blockscout devolvía balance_usd=0.0 explícito; el 0 no es un dato."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI, "balance_usd": 0.0})
    assert p["balance_usd"] == pytest.approx(ESPERADO, rel=1e-6)


def test_el_balance_del_adapter_manda(precio):
    """Si la fuente ya trae el USD, no se recalcula: manda lo que dijo la fuente."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI, "balance_usd": 123.45})
    assert p["balance_usd"] == 123.45


def test_sin_precio_no_se_inventa_un_balance(sin_precio):
    """Sin precio no hay conversión posible: 0 es la respuesta honesta."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    assert p["balance_usd"] == 0.0


def test_sin_balance_tampoco_se_inventa(precio):
    p = profile_wallet("0x" + "a" * 40, [], {})
    assert p["balance_usd"] == 0.0


def test_un_balance_basura_no_revienta(precio):
    """Blockchair y Blockscout devuelven balances en formatos raros."""
    for bruto in ("", "0", "0x0", "not-a-number", None, "-1"):
        p = profile_wallet("0x" + "a" * 40, [], {"balance": bruto})
        assert isinstance(p["balance_usd"], float)


# ------------------------------------------------------- etiquetas y scoring
def test_la_etiqueta_whale_aparece_con_el_balance_derivado(precio):
    """wallet_intelligence marcaba 'whale' a partir de 1M USD: no se disparaba."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    assert "whale" in p["labels"]


def test_la_regla_de_riesgo_de_whale_se_dispara(precio):
    """El bug que de verdad importaba: +10 y factor de balance alto."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    score, factores = score_wallet(p, [])
    assert score is not None
    assert "balance_alto_wallet_reciente" in factores
    assert score >= 10


def test_sin_el_arreglo_la_regla_no_se_dispararia(monkeypatch):
    """Control: con el comportamiento viejo (0.0) el factor no aparece.

    Fija que el test anterior really depende del arreglo y no del azar.
    """
    monkeypatch.setattr(WI, "get_price_usd", lambda *a, **k: None)
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    _, factores = score_wallet(p, [])
    assert "balance_alto_wallet_reciente" not in factores


# ------------------------------------------------- el camino de fallback real
def test_el_fallback_de_rpc_calcula_el_balance(precio, monkeypatch):
    """Simula Blockchair caído: el camino que fallaba en producción."""
    monkeypatch.setattr(F, "_http_json", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("timeout")))
    monkeypatch.setattr(F, "_http_get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("timeout")))
    monkeypatch.setattr(F, "rpc_snapshot", lambda rpcs, addr: {
        "balance_wei": 87174820146890656739388, "balance_known": True,
        "tx_count": 25, "tx_count_known": True, "code": "0x", "any_rpc": True})
    F._cache.clear()
    r = F.fetch_wallet_data("0x" + "a" * 40, chain="ethereum", use_cache=False)
    assert r["source"] == "rpc-fallback"
    p, _ = build_profile("0x" + "a" * 40, r)
    assert p["balance_usd"] == pytest.approx(ESPERADO, rel=1e-6)
    assert p["balance_usd"] != 0.0


def test_el_camino_de_blockscout_tambien_calcula(precio, monkeypatch):
    """Base devolvía balance_usd=0.0 fijo; mismo defecto, mismo arreglo."""
    monkeypatch.setattr(F, "_http_get", lambda url, timeout=8: (
        {"transactions_count": 42} if url.endswith("/counters")
        else {"items": []} if url.endswith("/transactions")
        else {"hash": "0xabc", "is_contract": False, "is_verified": False,
              "coin_balance": BALANCE_WEI, "name": ""}))
    F._cache.clear()
    r = F.fetch_wallet_data("0x" + "a" * 40, chain="base", use_cache=False)
    assert r["source"] == "blockscout"
    p, _ = build_profile("0x" + "a" * 40, r)
    assert p["balance_usd"] == pytest.approx(ESPERADO, rel=1e-6)


# ------------------------------------------------------------- procedencia
def test_la_respuesta_dice_de_onde_sale_el_balance(precio):
    """Sin esto, un $0 y un $234M son indistinguibles para quien lee el JSON."""
    p = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI})
    assert p["balance_usd_source"] == "derivado_del_wei"
    q = profile_wallet("0x" + "a" * 40, [], {"balance": BALANCE_WEI, "balance_usd": 50.0})
    assert q["balance_usd_source"] == "adapter"
    r = profile_wallet("0x" + "a" * 40, [], {}, )
    assert r["balance_usd_source"] == "sin_datos"
