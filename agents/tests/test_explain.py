import os

from agents.explanation import explain, _factor_text


def test_fallback_sin_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = explain({"address": "0xabc", "tx_count": 1, "age_days": 2, "activity": "baja", "balance_usd": 0}, 30, ["wallet_nueva_pocas_txs"])
    assert "0xabc" in t and "30/100" in t


def test_todo_factor_tiene_texto_legible():
    """Ningún factor puede llegar al usuario como snake_case crudo."""
    factores = [
        "wallet_nueva_pocas_txs",
        "wallet_reciente_poca_actividad",
        "concentracion_fondos_una_fuente",
        "patron_convoy_mismo_origen",
        "patron_bot_alta_frecuencia",
        "dormante_reactivada",
        "balance_alto_wallet_reciente",
        "interaccion_watchlist:tornado-eth-1",
    ]
    for f in factores:
        txt = _factor_text(f)
        assert "_" not in txt, f"factor sin traducir: {f} -> {txt}"
        assert len(txt) > 10


def test_explicacion_avisa_de_muestra_debilidad(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = explain({"address": "0xabc", "tx_count": 3, "age_days": None, "activity": "baja",
                 "balance_usd": 0, "sample_confidence": "baja"}, 20, [])
    assert "poco fiable" in t


def test_explicacion_no_promete_veredicto(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    t = explain({"address": "0xabc", "tx_count": 100, "age_days": 500, "activity": "alta",
                 "balance_usd": 1000, "sample_confidence": "alta"}, 50,
                ["concentracion_fondos_una_fuente"])
    assert "no un veredicto" in t
