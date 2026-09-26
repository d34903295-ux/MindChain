"""Tests del BUG B: el scoring devolvía un número con una muestra que no lo sostiene.

Contexto real (auditoría 2026-09-26): con Blockchair en timeout, la wallet
0x28C6…1d60 devolvió

    sample_size: 0
    sample_confidence: "nula"
    risk_score: 0                      <- número con aspecto de válido
    risk_factors: ["datos_insuficientes_score_provisional"]

`risk_scoring.py` se limitaba a *añadir un factor informativo* y devolvía la
cifra igual. El docstring del propio módulo dice:

    "Un sistema de riesgo que devuelve 0 cuando falla la red es peor que uno
     que devuelve 'no sé'."

El código hacía justo lo que el docstring prohíbe. Aquí se cumple.

Umbrales de `sample_confidence` (wallet_intelligence._sample_confidence):
    n >= 20 -> "alta"     n >= 8 -> "media"     0 < n < 8 -> "baja"     n == 0 -> "nula"
"""
import sys

import pytest

sys.path.insert(0, ".")

from agents.risk_scoring import score_wallet

ADDR = "0x" + "a" * 40
OTRO = "0x" + "b" * 40


def _tx(i, valor=10.0):
    return {"hash": "0x" + f"{i:064x}", "from": ADDR, "to": f"0x{i:040x}",
            "value_eth": valor, "value_usd": valor * 2000, "block": 1000 + i,
            "time": "2026-09-20T10:00:00Z", "score": 5, "flags": [], "alert": False}


def _perfil(confianza, **extra):
    p = {"address": ADDR, "chain": "ethereum", "tx_count": 100, "tx_count_reliable": True,
         "balance_usd": 0.0, "age_days": 500, "labels": ["eoa"], "activity": "media",
         "insufficient_data": False, "sample_confidence": confianza}
    p.update(extra)
    return p


# ------------------------------------------------------------- la abstención
@pytest.mark.parametrize("confianza", ["nula", "baja"])
def test_muestra_delgada_no_devuelve_numero(confianza):
    s, f = score_wallet(_perfil(confianza), [])
    assert s is None, f"con muestra '{confianza}' el score debe ser None, no un número"
    assert f == ["datos_insuficientes_no_evaluable"]


def test_la_muestra_delgada_se_distingue_de_sin_datos():
    """'nula'/'baja' es 'no evaluable'; 'sin datos' es 'no llega ni a evaluarse'."""
    a, fa = score_wallet(_perfil("nula"), [])
    b, fb = score_wallet(_perfil("nula", insufficient_data=True), [])
    assert a is None and b is None
    assert "datos_insuficientes_no_evaluable" in fa


def test_ya_no_se_emite_el_marcador_provisional():
    """El factor `datos_insuficientes_score_provisional` queda sin emisor."""
    _, f = score_wallet(_perfil("nula"), [])
    assert "datos_insuficientes_score_provisional" not in f


# ------------------------------------------------------------- sigue puntuando
def test_con_muestra_alta_sigue_habiendoscore():
    txs = [_tx(i) for i in range(25)]
    s, f = score_wallet(_perfil("alta"), txs)
    assert isinstance(s, int) and 0 <= s <= 100
    assert "datos_insuficientes_no_evaluable" not in f


def test_con_muestra_media_sigue_habiendoscore():
    txs = [_tx(i) for i in range(10)]
    s, _ = score_wallet(_perfil("media"), txs)
    assert isinstance(s, int), "8-19 tx son muestra utilizable"


def test_sin_la_clave_no_se_abstiene():
    """Un perfil sin el campo (llamadas internas) no se queda sin score."""
    p = _perfil("alta")
    del p["sample_confidence"]
    s, f = score_wallet(p, [_tx(i) for i in range(25)])
    assert isinstance(s, int)
    assert f != ["datos_insuficientes_no_evaluable"]


def test_la_abstencion_no_depende_del_resto_del_perfil():
    """Aunque el resto del perfil sea impecable, sin muestra no hay score.

    Es lo contrario de lo que hacía antes: acumulaba puntos (balance, edad)
    sobre una muestra vacía y devolvía la suma como si significara algo.
    """
    p = _perfil("nula", balance_usd=50_000_000, age_days=1, tx_count=999_999)
    s, f = score_wallet(p, [])
    assert s is None
    assert "balance_alto_wallet_reciente" not in f


# ------------------------------------------------- el que lo consume lo aguanta
def test_la_explicacion_no_dice_que_faltan_datos_si_no_faltan():
    """Con 1 transacción SÍ hay datos: no se puede decir que no se obtuvieron.

    La explicación determinista es lo que lee el usuario cuando el score es
    None. Si dice «no se pudieron obtener datos» cuando el perfil trae
    sample_size y balance, el arreglo del bug se paga con una mentira nueva.
    """
    from agents import explanation

    perfil = {"address": ADDR, "chain": "ethereum", "sample_size": 1,
              "sample_confidence": "baja", "balance_usd": 80.03, "labels": ["eoa"],
              "insufficient_data": False, "data_errors": []}
    texto = explanation.explain(perfil, None, ["datos_insuficientes_no_evaluable"])
    assert "no se pudieron obtener datos" not in texto.lower()
    assert "muestra" in texto.lower()
    assert "1 transacción" in texto


def test_sin_datos_de_verdad_si_se_dice_que_faltan():
    """Aquí sí faltaron los datos, y el texto tiene que decirlo."""
    from agents import explanation

    perfil = {"address": ADDR, "chain": "ethereum", "sample_size": 0,
              "sample_confidence": "nula", "balance_usd": 0.0,
              "insufficient_data": True, "data_errors": ["blockchair: timeout"]}
    texto = explanation.explain(perfil, None, ["datos_insuficientes_no_evaluable"])
    assert "no se pudieron obtener datos" in texto.lower()
    assert "blockchair: timeout" in texto


def test_ningun_consumidor_rompe_con_score_none():
    """obsidian, alerts y explanation reciben None y no hacen aritmética con él."""
    from agents import alerts, explanation, report_agent

    s, f = score_wallet(_perfil("nula"), [])
    assert s is None
    # explanation.explain acepta score None: no valida cifras contra un score
    texto = explanation.explain({"address": ADDR, "chain": "ethereum", "balance_usd": 0,
                                 "sample_confidence": "nula", "labels": ["eoa"]}, s, f)
    assert isinstance(texto, str) and texto

    # el informe en markdown aguanta score None
    md = report_agent.build_case_markdown({
        "address": ADDR, "chain": "ethereum",
        "profile": {"tx_count": 100, "age_days": 10, "activity": "baja",
                    "balance_usd": 100.0, "labels": ["eoa"], "sample_size": 0,
                    "sample_confidence": "nula"},
        "risk_score": None, "risk_factors": f, "explanation": "sin datos",
        "source": "test", "elapsed_s": 0.1, "data_quality": {},
    }, {"paths": [], "edges": [], "n_paths": 0, "n_nodes": 0, "total_traced_usd": 0,
        "path_values_usd": [], "watchlist_nodes": []})
    assert "ChainMind" in md
    # el alert no dispara con score None, y dice por qué (no "error-interno")
    alerta = alerts.alert_if_risky("wallet", ADDR, "ethereum", s, f)
    assert alerta["sent"] is False
    assert alerta["reason"] == "sin-score-no-evaluable"
