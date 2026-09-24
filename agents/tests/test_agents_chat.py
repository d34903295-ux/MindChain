"""Tests de los agentes especializados y del nodo de chat.

Lo que se protege aquí:
- un agente no puede salirse de su rol ni publicar una cifra que contradiga
  los datos que recibió
- el chat ejecuta herramientas reales y nunca inventa un score
- el chat responde aunque no haya modelo (el determinista es la red de seguridad)
"""
import json
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, ".")
from agents import agents, chat, llm


@pytest.fixture(autouse=True)
def sin_ia(monkeypatch):
    # La IA queda ENCENDIDA pero con urlopen mockeado: aquí se prueba el
    # camino del modelo, no una llamada real. Los tests que necesitan "sin
    # proveedor" lo apagan explícitamente.
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "0")
    llm.clear_cache()
    yield
    llm.clear_cache()


class Respuesta:
    def __init__(self, payload):
        self.p = payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.p).encode()


def _mock_ollama(monkeypatch, texto, truncado=False):
    def urlopen(req, timeout=0):
        return Respuesta({"response": texto, "done_reason": "length" if truncado else "stop",
                          "prompt_eval_count": 50, "eval_count": 30})
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)


# ------------------------------------------------------------------ registro
def test_cada_agente_tiene_su_prompt_y_su_modelo():
    for nombre, a in agents.REGISTRY.items():
        assert a.name == nombre
        assert a.system.strip(), f"{nombre} sin prompt propio"
        assert a.model, f"{nombre} sin modelo"
        assert "REGLAS INNEGOCIABLES" in a.prompt(), f"{nombre} sin las reglas comunes"
        assert a.role


def test_inventario_para_la_ui():
    inv = agents.describe()
    assert len(inv) == len(agents.REGISTRY)
    assert {"nombre", "rol", "modelo", "temperatura"} <= set(inv[0])
    assert any(a["herramientas"] for a in inv), "el chat debe declarar sus herramientas"


def test_agente_desconocido_falla():
    with pytest.raises(KeyError):
        agents.get("no-existe")


# ---------------------------------------------------------------- ejecución
def test_run_devuelve_texto_del_modelo(monkeypatch):
    _mock_ollama(monkeypatch, "El patrón muestra muchas contrapartes en poco tiempo. Revisa on-chain.")
    r = agents.run("explicacion", "datos", "fallback")
    assert r["source"] == "llm" and r["agente"] == "explicacion"
    assert r["text"].startswith("El patrón")


def test_run_cae_al_fallback_sin_modelo(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "1")
    r = agents.run("explicacion", "datos", "texto-fijo")
    assert r["text"] == "texto-fijo" and r["source"] == "determinista"


def test_run_cae_al_fallback_si_el_agente_se_pasa(monkeypatch):
    _mock_ollama(monkeypatch, "Esto es claramente un delito de lavado de dinero para todos.")
    r = agents.run("explicacion", "datos", "texto-fijo")
    assert r["text"] == "texto-fijo" and "filtro" in r["motivo"]


def test_veta_propia_del_agente(monkeypatch):
    """El agente de contratos no puede inventar vulnerabilidades."""
    _mock_ollama(monkeypatch, "El contrato tiene una vulnerabilidad crítica explotable. Revísalo.")
    r = agents.run("contratos", "datos", "texto-fijo")
    assert r["text"] == "texto-fijo" and "veta" in r["motivo"]


def test_veta_de_vacio_generico(monkeypatch):
    """La explicación no puede quedarse en 'es una wallet activa'."""
    _mock_ollama(monkeypatch, "Esta es una wallet activa con mucho movimiento en la red.")
    r = agents.run("explicacion", "datos", "texto-fijo")
    assert r["text"] == "texto-fijo" and "veta" in r["motivo"]


def test_verifica_score_inventado(monkeypatch):
    _mock_ollama(monkeypatch, "El riesgo es alto, con un score de 91/100 según el análisis.")
    r = agents.run("explicacion", "datos", "texto-fijo", score=12)
    assert r["text"] == "texto-fijo" and "cifra" in r["motivo"]


def test_acepta_score_correcto(monkeypatch):
    _mock_ollama(monkeypatch, "El score es de 12/100 y no muestra señales de riesgo relevantes.")
    r = agents.run("explicacion", "datos", "texto-fijo", score=12)
    assert r["source"] == "llm"


# ------------------------------------------------------------------- chat
def test_detecta_intenciones():
    assert chat._intencion("analiza 0x" + "a" * 40) == "wallet"
    assert chat._intencion("audita el contrato 0x" + "b" * 40) == "contrato"
    assert chat._intencion("rastrea los fondos de 0x" + "c" * 40) == "rastreo"
    assert chat._intencion("que pasa en base") == "feed"
    assert chat._intencion("como va el sistema") == "estado"
    assert chat._intencion("que vigilamos") == "watchlist"
    assert chat._intencion("hola") == "libre"


def test_detecta_direccion_y_cadena():
    t = "mira 0xD8DA6BF26964AF9D7EED9E03E53415D37AA96045 en base"
    assert chat._direccion(t) == "0xd8da6bf26964af9d7eed9e03e53415d37aa96045"
    assert chat._cadena(t) == "base"


def test_pide_direccion_si_falta():
    paso = chat.ejecutar("analiza esta wallet")
    assert paso["herramienta"] is None
    assert "dirección" in paso["respuesta"].lower()


def test_chat_usa_herramienta_real(monkeypatch):
    """El chat no simula: llama a la función que consulta la cadena."""
    llamado = {}

    def fake_wallet(args):
        llamado.update(args)
        return {"direccion": args.get("address"), "cadena": "ethereum", "score": 7,
                "nivel": "bajo", "factores": [], "transacciones": 10,
                "confianza_muestra": "baja", "explicacion": "Sin señales relevantes."}

    monkeypatch.setitem(chat.HERRAMIENTAS, "wallet", fake_wallet)
    paso = chat.ejecutar("analiza 0x" + "d" * 40)
    assert paso["herramienta"] == "wallet"
    assert llamado["address"] == "0x" + "d" * 40
    assert paso["datos"]["score"] == 7


def test_chat_no_inventa_score_si_la_herramienta_falla(monkeypatch):
    def rota(args):
        raise RuntimeError("RPC caído")
    monkeypatch.setitem(chat.HERRAMIENTAS, "wallet", rota)
    paso = chat.ejecutar("analiza 0x" + "e" * 40)
    assert paso["datos"]["error"]
    assert "No pude completar" in paso["respuesta"]


def test_chat_responde_sin_datos_no_inventa(monkeypatch):
    def sin_datos(args):
        return {"direccion": args["address"], "score": None}
    monkeypatch.setitem(chat.HERRAMIENTAS, "wallet", sin_datos)
    paso = chat.ejecutar("analiza 0x" + "f" * 40)
    assert "suficientes" in paso["respuesta"]
    assert "datos insuficientes" in paso["respuesta"] or "suficientes" in paso["respuesta"]


def test_chat_redacta_con_el_agente(monkeypatch):
    monkeypatch.setitem(chat.HERRAMIENTAS, "estado",
                        lambda a: {"ia": {"proveedor": "ollama", "modelo": "phi4-mini",
                                          "local": True, "rechazados": 0},
                                   "centinela": {"activo": True, "ciclos": 3, "alertas": 1,
                                                 "error": None},
                                   "cadenas": ["ethereum"], "agentes": ["chat"]})
    _mock_ollama(monkeypatch, "Todo va bien: el centinela lleva 3 ciclos y la IA es local.")
    r = chat.responder("como va el sistema")
    assert r["herramienta"] == "estado" and r["source"] == "llm"


def test_chat_si_la_ia_falla_devuelve_el_determinista(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "1")  # sin IA: el chat debe seguir respondiendo
    monkeypatch.setitem(chat.HERRAMIENTAS, "estado",
                        lambda a: {"ia": {"proveedor": "ollama"}, "cadenas": ["ethereum"]})
    r = chat.responder("como va el sistema")
    assert r["source"] == "determinista"
    assert r["respuesta"] == r["determinista"]


def test_chat_nunca_devuelve_credenciales(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secreto")
    monkeypatch.setitem(chat.HERRAMIENTAS, "estado",
                        lambda a: {"ia": {"proveedor": "anthropic"}, "cadenas": []})
    r = chat.ejecutar("como va el sistema")
    assert "sk-ant-secreto" not in json.dumps(r["datos"], ensure_ascii=False)


def test_followup_de_red_usa_el_feed(monkeypatch):
    """Tras preguntar por el sistema, '¿y en base?' quiere el feed de base."""
    monkeypatch.setitem(chat.HERRAMIENTAS, "feed",
                        lambda a: {"cadena": "base", "bloque": 1, "transacciones": 2, "alertas": 0})
    hist = [{"role": "user", "content": "como va el sistema"}]
    paso = chat.ejecutar("¿y en base?", hist)
    assert paso["herramienta"] == "feed" and paso["datos"]["cadena"] == "base"


def test_sin_historial_no_inventa_intencion():
    paso = chat.ejecutar("¿y en base?")
    assert paso["herramienta"] is None


def test_herramientas_publicas_no_exponen_secretos():
    for h in chat.herramientas_publicas():
        assert {"nombre", "args", "descripcion"} <= set(h)
        assert not any("key" in a.lower() or "token" in a.lower() for a in h["args"])
