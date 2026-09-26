"""Tests de las capacidades nuevas del chat: ranking, comparación, resumen y
enrutado flexible con IA.

Lo que se protege aquí:
- «la wallet que más movimientos hizo» se responde con datos REALES del
  escáner, ordenados, y con una serie por bloque para poder dibujar un gráfico
- el enrutado flexible no puede inventar: si el modelo no devuelve JSON
  válido, o pide una herramienta que no existe, o una dirección con formato
  inválido, se cae al determinista y no se ejecuta nada
- el modelo solo *elige* herramienta: los datos los calcula el código
- los argumentos que llegan del modelo se sanean antes de ejecutarse
- al modelo solo se le nombra el gráfico que de verdad se está dibujando
"""
import json
import sys

import pytest

sys.path.insert(0, ".")
from agents import chat, llm

ADDR_A = "0x" + "a" * 40
ADDR_B = "0x" + "b" * 40
ADDR_C = "0x" + "c" * 40
ADDR_D = "0x" + "d" * 40


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    """Sin IA real: `complete` falla cerrado salvo que un test lo sustituya.

    Así los tests delatan el fallback determinista de verdad y no dependen de
    que Ollama esté encendido ni de cuánto tarde.
    """
    llm.clear_cache()
    monkeypatch.setattr(llm, "complete", lambda *a, **k: {"ok": False, "error": "sin proveedor"})
    yield
    llm.clear_cache()


@pytest.fixture
def feed(monkeypatch):
    """Escáner falso: 3 bloques (100, 99, 98) con 5 transacciones conocidas."""
    llamadas = {}

    def _tx(frm, to, eth, bloque, flags=None):
        return {"from": frm, "to": to, "value_eth": eth, "block": bloque,
                "hash": "0x" + f"{bloque:02x}", "score": 10, "flags": flags or [],
                "alert": False}

    txs = [
        _tx(ADDR_A, ADDR_B, 5.0, 100), _tx(ADDR_B, ADDR_C, 1.0, 100),
        _tx(ADDR_A, ADDR_C, 2.0, 99), _tx(ADDR_D, ADDR_A, 0.5, 99),
        _tx(ADDR_A, ADDR_B, 3.0, 98),
    ]
    datos = {"chain": "ethereum", "latest": 100, "since": 98, "txs": txs,
             "alerts": [], "n_txs": len(txs), "n_alerts": 0, "median_eth": 2.0,
             "mad_eth": 1.0, "elapsed_s": 0.1}

    def fake_scan(chain="ethereum", since=None, max_blocks=2):
        llamadas.update({"chain": chain, "since": since, "max_blocks": max_blocks})
        return datos

    monkeypatch.setattr("agents.watcher.scan", fake_scan)
    return llamadas


@pytest.fixture
def feed_vacio(monkeypatch):
    monkeypatch.setattr("agents.watcher.scan", lambda *a, **k: {
        "chain": "ethereum", "latest": 100, "since": 100, "txs": [],
        "alerts": [], "n_txs": 0, "n_alerts": 0, "median_eth": None,
        "mad_eth": None, "elapsed_s": 0.1})


# ------------------------------------------------------------------ intenciones
def test_detecta_la_intencion_de_ranking():
    for frase in ("que wallet se movio mas", "la wallet con mas movimientos",
                  "ranking de wallets activas", "quien se movio mas en base",
                  "top wallets ahora mismo"):
        assert chat._intencion(frase) == "top", frase


def test_detecta_la_intencion_de_comparar():
    assert chat._intencion(f"compara {ADDR_A} y {ADDR_B}") == "comparar"
    assert chat._intencion(f"diferencia entre {ADDR_A} y {ADDR_B}") == "comparar"


def test_detecta_la_intencion_de_resumen():
    assert chat._intencion("resumen de la cadena en base") == "resumen"
    assert chat._intencion("estadisticas de ethereum") == "resumen"


def test_una_direccion_sigue_ganando_a_top():
    assert chat._intencion(f"analiza {ADDR_A}") == "wallet"


# ------------------------------------------------------------------- top_wallets
def test_top_wallets_devuelve_la_mas_activa_ordenada(feed):
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3, "top": 5})
    assert datos["cadena"] == "ethereum"
    assert datos["ranking"][0]["direccion"] == ADDR_A
    # A envía en 100, 99 y 98 y recibe en 99: 3 salidas + 1 entrada = 4
    assert datos["ranking"][0]["movimientos"] == 4
    movs = [r["movimientos"] for r in datos["ranking"]]
    assert movs == sorted(movs, reverse=True)
    assert len(datos["ranking"]) == 4  # aparecen A, B, C y D


def test_top_wallets_devuelve_serie_por_bloque_para_el_grafico(feed):
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3})
    serie = datos["serie"]
    assert len(serie) == 3
    assert {s["bloque"] for s in serie} == {100, 99, 98}
    assert sum(s["transacciones"] for s in serie) == 5
    assert all("volumen_eth" in s for s in serie)
    json.dumps(serie, ensure_ascii=False)  # tiene que poder ir al frontend


def test_top_wallets_distingue_enviado_y_recibido(feed):
    a = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3})["ranking"][0]
    assert a["direccion"] == ADDR_A
    assert a["enviado_eth"] == 10.0   # 5.0 + 2.0 + 3.0
    assert a["recibido_eth"] == 0.5   # desde D
    assert a["contrapartes"] == 3     # B, C y D
    assert a["primer_bloque"] == 98 and a["ultimo_bloque"] == 100
    assert a["bloques_activos"] == 3


def test_top_wallets_pide_los_bloques_que_le_digamos(feed):
    chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 4})
    assert feed["max_blocks"] == 4


def test_top_wallets_acota_lo_absurdo(feed):
    """Un 'top' de 9999 filas no se materializa: se acota."""
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 9999, "top": 9999})
    assert 1 <= len(datos["ranking"]) <= 25


def test_top_wallets_no_inventa_si_no_hay_bloques(feed_vacio):
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 2})
    assert datos["ranking"] == []
    assert "sin transacciones" in chat._determinista("top_wallets", datos, None, "ethereum", "top").lower()


def test_top_wallets_rechaza_cadena_inventada():
    assert "cadena no soportada" in chat.HERRAMIENTAS["top_wallets"]({"chain": "solana"})["error"]


def test_top_wallets_devuelve_explicacion_del_agente(feed, monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "1")
    assert chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3})["explicacion"]


def test_el_ranking_sabe_describir_al_ganador(feed):
    txt = chat._determinista("top_wallets", chat.HERRAMIENTAS["top_wallets"](
        {"chain": "ethereum", "bloques": 3}), None, "ethereum", "top")
    assert ADDR_A[:12] in txt
    assert "movimientos" in txt.lower()


# --------------------------------------------------------------------- comparar
def test_comparar_exige_dos_direcciones():
    assert chat.HERRAMIENTAS["comparar"]({"addresses": [ADDR_A]})["error"]


def test_comparar_filtra_direcciones_invalidas():
    assert chat.HERRAMIENTAS["comparar"]({"addresses": [ADDR_A, "no-es-una-wallet"]})["error"]


def test_comparar_devuelve_tabla_ganador_y_serie(monkeypatch):
    monkeypatch.setitem(chat.HERRAMIENTAS, "wallet", lambda a: {
        "direccion": a["address"], "cadena": "ethereum",
        "score": 80 if a["address"] == ADDR_A else 20,
        "nivel": "alto" if a["address"] == ADDR_A else "bajo",
        "factores": ["señas de riesgo"] if a["address"] == ADDR_A else [],
        "transacciones": 120 if a["address"] == ADDR_A else 5,
        "confianza_muestra": "alta" if a["address"] == ADDR_A else "baja",
        "balance_usd": 1000.0 if a["address"] == ADDR_A else 2.0,
        "contrapartes": 30, "etiquetas": [], "calidad_datos": False,
        "narrativa_trazado": "nada", "explicacion": "sin señales",
    })
    datos = chat.HERRAMIENTAS["comparar"]({"addresses": [ADDR_A, ADDR_B], "chain": "ethereum"})
    assert datos.get("error") is None
    assert [f["direccion"] for f in datos["tabla"]] == [ADDR_A, ADDR_B]
    assert datos["mas_riesgosa"]["direccion"] == ADDR_A
    assert datos["serie"]["scores"] == [80, 20]
    assert len(datos["serie"]["etiquetas"]) == 2


# ---------------------------------------------------------------------- resumen
def test_resumen_trae_totales_serie_y_ranking(feed):
    datos = chat.HERRAMIENTAS["resumen"]({"chain": "ethereum", "bloques": 3})
    assert datos["transacciones"] == 5
    assert datos["direcciones"] == 4
    assert datos["mediana_eth"] == 2.0
    assert len(datos["serie"]) == 3
    assert datos["ranking"][0]["direccion"] == ADDR_A


# -------------------------------------------------------------- enrutado flexible
def _eligir(monkeypatch, payload, ok=True):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: {
        "ok": ok, "text": payload if isinstance(payload, str) else json.dumps(payload)})


def test_el_modelo_puede_elegir_herramienta_cuando_el_router_no_sabe(feed, monkeypatch):
    """«quién está moviendo dinero ahora» no está en la tabla: lo elige el modelo."""
    assert chat._intencion("quién está moviendo dinero ahora mismo") == "libre"
    _eligir(monkeypatch, {"herramienta": "top_wallets",
                          "args": {"chain": "base", "bloques": 2}})
    paso = chat.ejecutar("quién está moviendo dinero ahora mismo")
    assert paso["herramienta"] == "top_wallets"
    assert paso["datos"]["cadena"] == "base"
    assert paso["enrutado"] == "ia"


def test_el_modelo_no_puede_pedir_una_herramienta_inexistente(monkeypatch):
    _eligir(monkeypatch, {"herramienta": "borrar_todo", "args": {}})
    paso = chat.ejecutar("borra todo lo que tengas")
    assert paso["herramienta"] is None
    assert "borrar_todo" not in json.dumps(paso, ensure_ascii=False)


def test_el_modelo_no_puede_inyectar_una_direccion_fuera_de_formato(monkeypatch):
    """El modelo elige la herramienta, pero la dirección la valida el código."""
    llamado = {}

    def wallet(args):
        llamado.update(args)
        return {"score": 1, "nivel": "bajo", "explicacion": "x"}

    monkeypatch.setitem(chat.HERRAMIENTAS, "wallet", wallet)
    _eligir(monkeypatch, {"herramienta": "wallet",
                          "args": {"address": "'; DROP TABLE wallets; --"}})
    paso = chat.ejecutar("mira esa wallet que te dije antes")
    assert not llamado, "no debe ejecutar con una dirección inválida"
    assert paso["herramienta"] is None


def test_json_invalido_del_modelo_cae_al_determinista(monkeypatch):
    pregunta = "quiero un censo de lo que se mueve por la red"
    assert chat._intencion(pregunta) == "libre"
    _eligir(monkeypatch, "creo que es 0xabc y tiene muchos movimientos")
    paso = chat.ejecutar(pregunta)
    assert paso["herramienta"] is None
    assert paso["respuesta"]


def test_sin_proveedor_cae_al_determinista(monkeypatch):
    monkeypatch.setenv("CHAINMIND_LLM_DISABLED", "1")
    paso = chat.ejecutar("dime algo raro que no entienda el router")
    assert paso["herramienta"] is None
    assert paso["respuesta"]


def test_el_router_determinista_manda_y_no_gasta_llm(monkeypatch):
    """Si la tabla ya sabe la intención, no se llama al modelo para elegir."""
    gastado = []
    monkeypatch.setitem(chat.HERRAMIENTAS, "estado",
                        lambda a: {"ia": {"proveedor": "ollama"}, "cadenas": []})
    monkeypatch.setattr(llm, "complete", lambda *a, **k: gastado.append(1))
    paso = chat.ejecutar("como va el sistema")
    assert paso["herramienta"] == "estado"
    assert gastado == []


def test_los_argumentos_del_modelo_se_acotan(monkeypatch):
    """Aunque el modelo pida 500 saltos, el código lo deja en 4."""
    capturado = {}

    def rastreo(args):
        capturado.update(args)
        return {"rutas": 1, "nodos": 1, "usd_trazado": 0}

    monkeypatch.setitem(chat.HERRAMIENTAS, "rastreo", rastreo)
    _eligir(monkeypatch, {"herramienta": "rastreo", "args": {
        "address": ADDR_A, "chain": "base", "max_depth": 500,
        "direction": "lateral", "inventado": "x"}})
    chat.ejecutar("sigue el rastro de aquella wallet")
    assert capturado["max_depth"] <= 4
    assert capturado["direction"] in ("in", "out")
    assert "inventado" not in capturado
    assert capturado["chain"] == "base"


def test_al_pedir_tools_no_se_pasan_secretos(monkeypatch):
    """El prompt del enrutado lleva el catálogo, jamás credenciales."""
    visto = {}
    monkeypatch.setattr(llm, "complete", lambda system, user, **k: visto.update(
        {"system": system, "user": user}) or {"ok": False, "error": "x"})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secreto")
    chat.ejecutar("algo raro")
    assert "sk-ant-secreto" not in visto.get("user", "")
    assert "top_wallets" in visto.get("user", "")


def test_el_ruteo_por_ia_queda_reflejado_en_la_respuesta(monkeypatch):
    _eligir(monkeypatch, {"herramienta": "watchlist", "args": {}})
    paso = chat.ejecutar("hazme un inventario de lo que tenemos fichado")
    assert paso["enrutado"] == "ia"
    assert paso["respuesta"]


def test_comparar_sin_dos_direcciones_pide_dos(monkeypatch):
    _eligir(monkeypatch, {"herramienta": "comparar",
                          "args": {"addresses": [ADDR_A]}})  # el modelo solo da una
    paso = chat.ejecutar("compara " + ADDR_A)
    assert paso["herramienta"] is None
    assert "dos direcciones" in paso["respuesta"]


def test_la_intencion_nueva_llega_a_su_herramienta(feed):
    """La tabla sí reconoce el ranking: no hace falta el modelo para eso."""
    paso = chat.ejecutar("qué wallet se movió más en los últimos 4 bloques")
    assert paso["herramienta"] == "top_wallets"
    assert paso["enrutado"] == "tabla"
    assert paso["datos"]["bloques"] == 4


def test_comparar_recibe_las_direcciones_de_la_frase(monkeypatch):
    capturado = {}

    def comparar(args):
        capturado.update(args)
        return {"tabla": [], "serie": {}}

    monkeypatch.setitem(chat.HERRAMIENTAS, "comparar", comparar)
    chat.ejecutar(f"compara {ADDR_A} y {ADDR_B} en base")
    assert capturado["addresses"] == [ADDR_A, ADDR_B]
    assert capturado["chain"] == "base"


# ------------------------------------------------------------------- inventario
def test_las_nuevas_capacidades_se_publican():
    nombres = {h["nombre"] for h in chat.herramientas_publicas()}
    assert {"top_wallets", "comparar", "resumen"} <= nombres


def test_toda_herramienta_publicada_existe_y_tiene_descripcion():
    for h in chat.herramientas_publicas():
        assert h["nombre"] in chat.HERRAMIENTAS, h["nombre"]
        assert h["descripcion"].strip()
        assert isinstance(h["args"], list)
        assert not any("key" in a.lower() or "token" in a.lower() for a in h["args"])


# ------------------------------------------------- contexto que ve el modelo
def test_el_contexto_del_ranking_llega_entero_al_modelo(feed):
    """El modelo solo puede comentar el gráfico si la serie está en su contexto.

    Volcaba el dict entero recortado a 2200 caracteres: con diez filas del
    ranking la serie se caía, y el modelo acababa diciendo que no había volumen
    cuando sí lo había.
    """
    paso = chat.ejecutar("qué wallet se movió más en los últimos 3 bloques")
    ctx = paso["contexto"]
    for b in (100, 99, 98):
        assert str(b) in ctx, f"el bloque {b} no llega al modelo"
    assert ADDR_A in ctx
    assert len(ctx) <= 2000


def test_el_contexto_aguanta_un_ranking_lleno(feed, monkeypatch):
    """Con 25 filas y 10 bloques, lo que se recorta no es la serie."""
    txs = []
    for i in range(24):
        a = "0x" + format(i, "040x")
        b = "0x" + format(1000 + i, "040x")
        txs.append({"from": a, "to": b, "value_eth": float(i), "block": 90 + (i % 10),
                    "score": 5, "flags": [], "alert": False})
    monkeypatch.setattr("agents.watcher.scan", lambda *a, **k: {
        "chain": "ethereum", "latest": 99, "since": 90, "txs": txs, "alerts": [],
        "n_txs": len(txs), "n_alerts": 0, "median_eth": 1.0, "mad_eth": 0.5})
    paso = chat.ejecutar("top 25 wallets en 10 bloques")
    ctx = paso["contexto"]
    # 48 direcciones distintas en el rango; top 25 las recorta, y aun así la
    # serie de 10 bloques tiene que llegar entera al modelo
    assert len(paso["datos"]["ranking"]) == 25
    assert ctx.count("bloque") >= 10, "la serie debe estar completa"
    assert len(ctx) <= 2000


def test_el_contexto_no_inventa_campos_que_no_estan(feed):
    paso = chat.ejecutar("resumen de la cadena")
    ctx = paso["contexto"]
    assert "serie" in ctx.lower() or "bloque" in ctx.lower()
    assert "error" not in ctx.lower()


# --------------------------------------------------------------- métrica
def test_top_wallets_por_defecto_es_por_movimientos(feed):
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3})
    assert datos["metrica"] == "movimientos"
    assert datos["ranking"][0]["direccion"] == ADDR_A


def test_top_wallets_puede_ordenar_por_valor(feed):
    """«la wallet que más plata movió» es otra pregunta, no la misma."""
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3,
                                              "metrica": "valor"})
    assert datos["metrica"] == "valor"
    eth = [r["total_eth"] for r in datos["ranking"]]
    assert eth == sorted(eth, reverse=True)
    assert datos["ranking"][0]["direccion"] == ADDR_A  # 10.5 ETH


def test_una_metrica_inventada_cae_en_movimientos(feed):
    datos = chat.HERRAMIENTAS["top_wallets"]({"chain": "ethereum", "bloques": 3,
                                              "metrica": "salario"})
    assert datos["metrica"] == "movimientos"


def test_el_roto_va_por_valor_si_lo_pide(monkeypatch, feed):
    _eligir(monkeypatch, {"herramienta": "top_wallets",
                          "args": {"chain": "ethereum", "metrica": "valor"}})
    paso = chat.ejecutar("cuál es la que más plata movió")
    assert paso["herramienta"] == "top_wallets"
    assert paso["datos"]["metrica"] == "valor"


# ------------------------------------------- el prompt no promete gráficos de más
def test_no_se_promete_un_grafico_que_no_existe(monkeypatch):
    """En una comparativa no hay serie por bloque: no se la puede describir.

    El modelo llegaba a decir «el gráfico de la serie por bloque mostrará…»
    sobre un gráfico que compara scores. El prompt tiene que decir la verdad.
    """
    visto = {}

    def espia(nombre, user, fallback, **k):
        visto["user"] = user
        return {"text": fallback, "agente": nombre, "source": "determinista"}

    monkeypatch.setitem(chat.HERRAMIENTAS, "comparar", lambda a: {
        "cadena": "ethereum", "tabla": [{"direccion": ADDR_A, "score": 10, "nivel": "bajo",
                                        "transacciones": 5, "contrapartes": 2, "balance_usd": 1.0,
                                        "confianza_muestra": "alta", "factores": [],
                                        "calidad_datos": False, "explicacion": "x"}],
        "errores": {}, "mas_riesgosa": None, "mas_activa": None,
        "serie": {"etiquetas": ["a"], "scores": [10], "transacciones": [5], "niveles": ["bajo"]},
        "explicacion": "x"})
    monkeypatch.setattr(chat.agents, "run", espia)
    chat.responder(f"compara {ADDR_A} y {ADDR_B}")
    assert "serie por bloque" not in visto["user"]
    assert "comparando estas mismas cifras" in visto["user"]


def test_con_serie_por_bloque_si_se_la_nombra(feed, monkeypatch):
    visto = {}

    def espia(nombre, user, fallback, **k):
        visto["user"] = user
        return {"text": fallback, "agente": nombre, "source": "determinista"}

    monkeypatch.setattr(chat.agents, "run", espia)
    chat.responder("qué wallet se movió más en 3 bloques")
    assert "serie por bloque" in visto["user"]


# ------------------------------------------------- erratas en el nombre
def test_una_errata_no_tira_la_pregunta():
    """El modelo de 7B contesto «rastrear» por «rastreo» y se perdia la pregunta.

    Resolver el nombre es seguro: solo puede acabar en una herramienta que ya
    existe, y los argumentos se sanean igual.
    """
    assert chat._coincide_herramienta("rastrear") == "rastreo"
    assert chat._coincide_herramienta("rastreo") == "rastreo"
    assert chat._coincide_herramienta("Rastreo") == "rastreo"
    assert chat._coincide_herramienta("topwallets") == "top_wallets"
    assert chat._coincide_herramienta("compara") == "comparar"
    assert chat._coincide_herramienta("wallet") == "wallet"


def test_un_nombre_inventado_seguido_se_descarta():
    for nombre in ("borrar_todo", "xx", "hazme_un_ddos", "", None, 42, "wallet_delete"):
        assert chat._coincide_herramienta(nombre) is None, nombre


def test_el_enrutado_tolera_la_errata_y_ejecuta(monkeypatch):
    _eligir(monkeypatch, {"herramienta": "resumen", "args": {"chain": "base"}})
    paso = chat.ejecutar("dime quien se esta moviendo ahora mismo")
    assert paso["herramienta"] == "resumen"
    assert paso["datos"]["cadena"] == "base"
    assert paso["enrutado"] == "ia"


def test_el_prompt_pide_el_nombre_exacto_y_da_un_ejemplo(monkeypatch):
    visto = {}

    def espia(system, user, **k):
        visto["user"] = user
        return {"ok": True, "text": '{"herramienta": null}'}

    monkeypatch.setattr(llm, "complete", espia)
    chat.ejecutar("algo raro de verdad")
    assert "EXACTO" in visto["user"]
    assert '"herramienta": "top_wallets"' in visto["user"]
