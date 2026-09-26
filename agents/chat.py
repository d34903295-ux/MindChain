"""Nodo de chat: el sistema respondiendo preguntas sobre lo que vive en ChainMind.

Dos decisiones que separan esto de un chatbot de adorno:

1. **Herramientas de verdad.** No simula: llama a los mismos `fetcher`,
   `wallet_intelligence`, `risk_scoring`, `investigation` y `watchlist` que
   usan los endpoints. Si el chat dice un score, ese score está calculado.

2. **Router determinista primero.** Un modelo de 3B no es fiable decidiendo
   tool calls en JSON, así que no se lo pide. El enrutado lo hace una tabla de
   patrones: detecta la dirección, la red y la intención. El LLM solo redacta
   la respuesta final con los datos ya en la mano. Si el modelo falla, el
   chat sigue respondiendo con el resumen determinista.

3. **Red de seguridad: el modelo elige, el código calcula.** Cuando la tabla
   no reconoce la pregunta («muéstrame la más activa»), se leense al modelo el
   catálogo y contesta qué herramienta usar en JSON. Pero sus argumentos se
   sanean (direcciones con formato 0x…, cadenas del catálogo, saltos acotados)
   y nunca se ejecuta una herramienta que no exista. Si el JSON no es válido,
   se cae al determinista. El modelo nunca calcula un score ni un ranking.

4. **Los datos vienen con serie temporal.** Las herramientas de agregado
   (`top_wallets`, `resumen`, `comparar`) devuelven una `serie` por bloque: es
   lo que la interfaz dibuja como gráfico. El texto es el resumen; el gráfico
   es el dato.

El LLM nunca ve claves: las herramientas le devuelven un resumen recortado, no
el objeto interno completo.
"""
from __future__ import annotations

import json
import re
import unicodedata

from . import agents, chains, watchlist

ADDR_RE = re.compile(r"0x[0-9a-fA-F]{40}")
MAX_HISTORIAL = 6

# El destino 0x0 no es una wallet: es un despliegue de contrato. Contarlo como
# «dirección más activa» del bloque sería el peor error posible en un ranking.
ADDR_CERO = "0x" + "0" * 40
MAX_BLOQUES_CHAT = 10
MAX_TOP_CHAT = 25
MAX_COMPARAR = 4
# Herramientas que no hacen nada útil sin una dirección válida.
NECESITA_DIRECCION = ("wallet", "contrato", "rastreo")

RED_POR_PALABRA = (
    (r"\bbase\b|\bbase chain\b", "base"),
    (r"\bethereum\b|\beth\b", "ethereum"),
)


def _direccion(texto: str) -> str | None:
    m = ADDR_RE.search(texto or "")
    return m.group(0).lower() if m else None


def _direcciones(texto: str) -> list[str]:
    """Todas las direcciones de la frase, en orden y sin repetir."""
    vistas: set[str] = set()
    out: list[str] = []
    for m in ADDR_RE.finditer(texto or ""):
        addr = m.group(0).lower()
        if addr not in vistas:
            vistas.add(addr)
            out.append(addr)
    return out


def _cadena(texto: str, por_defecto: str = "ethereum") -> str:
    t = (texto or "").lower()
    for patron, nombre in RED_POR_PALABRA:
        if re.search(patron, t):
            return nombre
    return por_defecto


def _intencion(texto: str) -> str:
    t = (texto or "").lower()
    if re.search(r"\bcontrato\b|\bcontract\b|\bslither\b|\bauditar\b|\bauditor", t):
        return "contrato"
    if re.search(r"\brastr\w*|\bruta\w*\b|\bseguir (?:los )?fondos\b|\bde d[oó]nde\b"
                 r"|\b[aá] d[oó]nde (?:fue|vino|va)\b|\bflujo\b|\borigen de los fondos\b", t):
        return "rastreo"
    # «la wallet que más movimientos hizo» va antes que feed: la palabra
    # «actividad» también aparece ahí y sin este orden acabaría en el feed.
    if re.search(r"\btop\b|\branking\b|\bqui[eé]n se movi[óo] m[áa]s\b|\bm[óo]vil se movi[óo] m[áa]s\b"
                 r"|\bse movi[óo] m[áa]s\b|\bm[áa]s (?:movimientos|movimiento|transacciones|operaciones|actividad|volumen)\b"
                 r"|\bm[áa]s (?:se movi[óo]|se movio|activa|activas)\b"
                 r"|\bwallets? m[áa]s\b|\bbusca\w*\b[^?]*\bwallet\b", t):
        return "top"
    if re.search(r"\bcompar\w*\b|\bdiferencia entre\b|\bversus\b|\bvs\b"
                 r"|\bcual es m[áa]s (?:riesgosa|segura|activa)\b", t):
        return "comparar"
    if re.search(r"\bresumen (?:de|del) (?:la |las |los )?(?:cadena|red|redes|mercado|actividad)\b"
                 r"|\bestad[ií]sticas\b|\bpanorama\b|\bcomo est[áa] la (?:cadena|red)\b"
                 r"|\bvolumen (?:total|de la red)\b|\bm[ée]tricas\b"
                 r"|\bactividad de la cadena\b", t):
        return "resumen"
    if re.search(r"\bestado\b|\bstatus\b|\bfunciona\w*\b|\bcentinela\b|\bproveedor\w*\b"
                 r"|\bqu[eé] ia\b|\bmodelo\b|\bsistema\b|\bcomo va\b|\bva bien\b|\bfuncionando\b", t):
        return "estado"
    if re.search(r"\bwatchlist\b|\bvigil\w*|\bcontrolad\w*|\bmonitoriz\w*", t):
        return "watchlist"
    if re.search(r"\bfeed\b|\b[úu]ltim\w* (?:transacciones|bloques)\b|\bactividad\b"
                 r"|\balertas?\b|\bqu[eé] (?:pasa|viendo|sucede)\b|\bnovedades\b", t):
        return "feed"
    if _direccion(texto):
        return "wallet"
    return "libre"


# ------------------------------------------------------------------ herramientas
def _herramienta_wallet(args: dict) -> dict:
    from .fetcher import fetch_wallet_data
    from .investigation import narrarize_trace, trace_from_txs
    from .risk_scoring import score_wallet
    from .wallet_intelligence import build_profile

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    fetched = fetch_wallet_data(addr, chain=chain)
    profile, txs = build_profile(addr, fetched)
    score, factors = score_wallet(profile, txs)
    trace = trace_from_txs(addr, txs, max_depth=2, direction="out")
    narr = narrarize_trace(trace)
    return {
        "direccion": addr, "cadena": chain,
        "score": score, "nivel": ("n/d" if score is None else
                                 "bajo" if score < 30 else "medio" if score < 70 else "alto"),
        "factores": list(factors)[:6],
        "transacciones": profile.get("tx_count"),
        "confianza_muestra": profile.get("sample_confidence"),
        "antiguedad_dias": profile.get("age_days"),
        "balance_usd": profile.get("balance_usd"),
        "contrapartes": profile.get("counterparties"),
        "etiquetas": profile.get("labels"),
        "calidad_datos": (fetched.get("data_quality") or {}).get("degraded", False),
        "narrativa_trazado": narr["narrative"],
        "explicacion": agents.run(
            "explicacion",
            f"Wallet {addr} ({chain}). Perfil: {json.dumps(profile, ensure_ascii=False, default=str)[:1200]}. "
            f"Score {score}/100. Factores: {'; '.join(factors) or 'ninguno'}. "
            f"Confianza de muestra: {profile.get('sample_confidence', 'n/d')}. "
            "Explica el patrón y qué conviene verificar.",
            "Sin datos suficientes para evaluar esta wallet.", score=score,
        )["text"],
    }


def _herramienta_contrato(args: dict) -> dict:
    from .contract_analyzer import analyze_contract, fetch_contract

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    fetched = fetch_contract(addr, chain=chain)
    r = analyze_contract(addr, fetched)
    return {
        "direccion": addr, "cadena": chain, "es_contrato": r.get("is_contract"),
        "score": r.get("risk_score"), "es_proxy": r.get("is_proxy"),
        "verificado": r.get("verified"),
        "hallazgos": [f.get("id") for f in (r.get("risks") or [])][:8],
        "explicacion": r.get("explanation"),
    }


def _herramienta_rastreo(args: dict) -> dict:
    from .fetcher import fetch_wallet_data
    from .investigation import narrarize_trace, trace_from_txs
    from .wallet_intelligence import build_profile

    addr = (args.get("address") or "").lower()
    if not ADDR_RE.fullmatch(addr):
        return {"error": "dirección inválida"}
    chain = args.get("chain") or "ethereum"
    fetched = fetch_wallet_data(addr, chain=chain)
    _, txs = build_profile(addr, fetched)
    profundidad = max(1, min(int(args.get("max_depth") or 2), 4))
    trace = trace_from_txs(addr, txs, max_depth=profundidad,
                           direction=args.get("direction") or "out")
    narr = narrarize_trace(trace)
    return {
        "direccion": addr, "cadena": chain, "rutas": trace.get("n_paths"),
        "nodos": trace.get("n_nodes"), "usd_trazado": trace.get("total_traced_usd"),
        "en_watchlist": trace.get("watchlist_nodes"),
        "narrativa": narr["narrative"],
    }


def _herramienta_feed(args: dict) -> dict:
    from .watcher import scan

    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    feed = scan(chain, max_blocks=1)
    alertas = [{
        "valor_eth": t.get("value_eth"), "score": t.get("score"),
        "senales": t.get("flags"), "bloque": t.get("block"),
    } for t in (feed.get("alerts") or [])[:3]]
    return {
        "cadena": chain, "bloque": feed.get("latest"),
        "transacciones": feed.get("n_txs"), "alertas": feed.get("n_alerts"),
        "mediana_eth": feed.get("median_eth"), "ejemplos": alertas,
    }


def _herramienta_estado(args: dict) -> dict:
    from . import llm, sentinel
    from .fetcher import cache_stats

    st = llm.status()
    s = sentinel.status()
    return {
        "ia": {"proveedor": st.get("provider"), "modelo": st.get("model"),
               "local": st.get("local"), "rechazados": st["estadisticas"].get("rejected")},
        "centinela": {"activo": s.get("enabled"), "ciclos": s.get("cycles"),
                      "alertas": s.get("alerts_delivered"), "error": s.get("last_error")},
        "cadenas": chains.supported(),
        "agentes": [a["nombre"] for a in agents.describe()],
        "cache_datos": cache_stats(),
    }


def _herramienta_watchlist(args: dict) -> dict:
    info = watchlist.info()
    return {"total": info["size"], "direcciones": [
        {"direccion": e.get("address"), "etiqueta": e.get("label"),
         "verificado": e.get("verificado")} for e in watchlist.entries()[:20]]}


# ------------------------------------------------------- agregación de actividad
def _eth(valor) -> float:
    """Un valor ETH sucio (None, '', '0x..', NaN) nunca rompe una suma."""
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def _acota(valor, minimo: int, maximo: int, defecto: int) -> int:
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return defecto
    return max(minimo, min(n, maximo))


def _agregar_actividad(txs: list[dict], top_n: int = 5) -> tuple[list[dict], list[dict], int]:
    """Cuenta los movimientos por dirección y por bloque.

    Un «movimiento» es una transacción en la que la dirección aparece, salga o
    entre: una wallet que recibe mil veces y envía una también está moviendo
    dinero, y quedarse solo con los envíos la borraría del ranking.

    Devuelve `(ranking, serie, creados)`. La serie es lo que la interfaz
    dibuja: un punto por bloque, de más antiguo a más reciente.
    """
    por: dict[str, dict] = {}
    bloques: dict[int, dict] = {}
    creados = 0

    for t in txs or []:
        bloque = t.get("block")
        if not isinstance(bloque, int):
            continue
        eth = _eth(t.get("value_eth"))
        origen = (t.get("from") or "").lower() or None
        destino = (t.get("to") or "").lower() or None
        senal = bool(t.get("alert")) or bool(t.get("flags"))

        fila_bloque = bloques.setdefault(bloque, {
            "bloque": bloque, "transacciones": 0, "volumen_eth": 0.0,
            "direcciones": set(), "alertas": 0})
        fila_bloque["transacciones"] += 1
        fila_bloque["volumen_eth"] += eth
        fila_bloque["alertas"] += 1 if senal else 0
        if destino == ADDR_CERO:
            creados += 1
        for addr in (origen, destino):
            if addr and addr != ADDR_CERO:
                fila_bloque["direcciones"].add(addr)

        for rol, addr, contraparte in (("out", origen, destino), ("in", destino, origen)):
            if not addr or addr == ADDR_CERO:
                continue
            fila = por.get(addr)
            if fila is None:
                fila = por[addr] = {
                    "direccion": addr, "movimientos": 0, "envios": 0, "recibos": 0,
                    "enviado_eth": 0.0, "recibido_eth": 0.0, "alertas": 0,
                    "score_max": 0, "_bloques": set(), "_contrapartes": set(),
                }
            fila["movimientos"] += 1
            if rol == "out":
                fila["envios"] += 1
                fila["enviado_eth"] += eth
            else:
                fila["recibos"] += 1
                fila["recibido_eth"] += eth
            if contraparte and contraparte != addr and contraparte != ADDR_CERO:
                fila["_contrapartes"].add(contraparte)
            fila["_bloques"].add(bloque)
            fila["alertas"] += 1 if senal else 0
            score = t.get("score")
            if isinstance(score, (int, float)):
                fila["score_max"] = max(fila["score_max"], int(score))

    ranking: list[dict] = []
    for fila in por.values():
        vistos = sorted(fila["_bloques"])
        fila["enviado_eth"] = round(fila["enviado_eth"], 6)
        fila["recibido_eth"] = round(fila["recibido_eth"], 6)
        fila["total_eth"] = round(fila["enviado_eth"] + fila["recibido_eth"], 6)
        fila["contrapartes"] = len(fila["_contrapartes"])
        fila["bloques_activos"] = len(vistos)
        fila["primer_bloque"] = vistos[0]
        fila["ultimo_bloque"] = vistos[-1]
        del fila["_bloques"], fila["_contrapartes"]
        ranking.append(fila)

    # Desempate por volumen y, aun así, por dirección: dos ejecuciones sobre
    # los mismos datos tienen que devolver el ranking en el mismo orden.
    ranking.sort(key=lambda f: (-f["movimientos"], -f["total_eth"], f["direccion"]))

    serie = [{"bloque": b, "transacciones": bloques[b]["transacciones"],
              "volumen_eth": round(bloques[b]["volumen_eth"], 6),
              "direcciones": len(bloques[b]["direcciones"]),
              "alertas": bloques[b]["alertas"]}
             for b in sorted(bloques)]
    return ranking[:max(1, top_n)], serie, creados


def _explica_ranking(cadena: str, ranking: list[dict], serie: list[dict], n_txs: int,
                     metrica: str = "movimientos") -> str:
    """Explicación en lenguaje llano, con el texto determinista de red de seguridad."""
    if not ranking:
        return (f"Escaneé {n_txs} transacciones en {cadena} y ninguna dirección mueve valor "
                f"en ese rango. Sin actividad no hay ranking que dar.")
    g = ranking[0]
    segundo = ranking[1] if len(ranking) > 1 else None
    con_pico = max((p["transacciones"] for p in serie), default=0)
    base = (
        f"En {cadena}, {g['direccion']} encabeza por {metrica}: {g['movimientos']} transacciones "
        f"en {g['bloques_activos']} bloques, {g['enviado_eth']} ETH enviados, "
        f"{g['recibido_eth']} ETH recibidos y {g['contrapartes']} contrapartes distintas. "
        f"El bloque con más actividad del rango trajo {con_pico} transacciones."
        + (f" Le sigue {segundo['direccion']} con {segundo['movimientos']} movimientos." if segundo else "")
        + " Mucho movimiento no es culpa: lo que importa es de dónde sale el dinero."
    )
    return agents.run(
        "explicacion",
        f"Red {cadena}. Escaneé {n_txs} transacciones de {len(serie)} bloques, ordenadas por {metrica}. "
        f"Ranking: {json.dumps(ranking[:5], ensure_ascii=False, default=str)}. "
        f"Explica en español qué está pasando en la red y qué convendría mirar de esta "
        f"dirección concreta. No inventes motivos: no sabemos quién es.",
        base, score=g.get("score_max") or None)["text"]


def _agrega_por(datos: dict, metrica: str = "movimientos") -> list[dict]:
    """Reordena el ranking por la métrica pedida, sin perder los datos.

    «Movimientos» y «valor» son preguntas distintas: la wallet que más toca la
    cadena suele ser un exchange (cero valor, muchas llamadas) y la que más
    plata mueve suele ser un puente. Contestar una con la otra sería mentir.
    """
    filas = list(datos.get("ranking") or [])
    if metrica == "valor":
        filas.sort(key=lambda f: (-float(f.get("total_eth") or 0),
                                  -f.get("movimientos", 0), f["direccion"]))
    return filas


def _contexto_herramienta(herramienta: str, datos: dict) -> str:
    """Texto compacto con lo que el modelo necesita para redactar.

    Antes se volcaba el dict entero a json y se cortaba a 2200 caracteres: con
    diez wallets en el ranking la serie se caía del contexto y el modelo se
    inventaba que no había volumen. Aquí se decide qué campos importan.
    """
    if herramienta in ("top_wallets", "resumen"):
        serie = datos.get("serie") or []
        lineas = [
            f"cadena: {datos.get('cadena')}",
            f"bloques: {datos.get('desde')}–{datos.get('hasta')} ({datos.get('bloques')} escaneados)",
            f"transacciones: {datos.get('transacciones')} en {datos.get('direcciones')} direcciones",
            f"mediana: {datos.get('mediana_eth')} ETH · ordenado por: {datos.get('metrica')}",
            "serie por bloque (bloque: tx, ETH, direcciones): "
            + " | ".join(f"{p['bloque']}: {p['transacciones']}, {p['volumen_eth']}, {p['direcciones']}"
                         for p in serie),
            "ranking (dirección, movimientos, enviado, recibido, contrapartes, bloques):",
        ]
        for f in (datos.get("ranking") or []):
            lineas.append(f"- {f['direccion']}: {f['movimientos']} movs, {f['enviado_eth']} ETH fuera, "
                          f"{f['recibido_eth']} ETH dentro, {f['contrapartes']} cp, "
                          f"{f['bloques_activos']} bloques")
        if datos.get("contratos_creados"):
            lineas.append(f"despliegues de contrato en el rango: {datos['contratos_creados']}")
        return "\n".join(lineas)[:2000]

    if herramienta == "comparar":
        filas = datos.get("tabla") or []
        lineas = [f"cadena: {datos.get('cadena')}",
                  "comparativa (dirección, score, nivel, transacciones, contrapartes, balance, muestra):"]
        for f in filas:
            lineas.append(f"- {f['direccion']}: score {f['score']}/100 ({f['nivel']}), "
                          f"{f['transacciones']} tx, {f['contrapartes']} cp, "
                          f"{f['balance_usd']} USD, muestra {f['confianza_muestra']}")
        if datos.get("mas_riesgosa"):
            lineas.append(f"la que más riesgo puntúa: {datos['mas_riesgosa']['direccion']}")
        if datos.get("mas_activa"):
            lineas.append(f"la que más se movió: {datos['mas_activa']['direccion']}")
        return "\n".join(lineas)[:2000]

    return json.dumps(datos, ensure_ascii=False, default=str)[:2000]


def _herramienta_top_wallets(args: dict) -> dict:
    """«¿Qué wallet se movió más?» — ranking real, con serie por bloque."""
    from .watcher import scan

    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    bloques = _acota(args.get("bloques") or 3, 1, MAX_BLOQUES_CHAT, 3)
    top_n = _acota(args.get("top") or 5, 1, MAX_TOP_CHAT, 5)
    metrica = "valor" if str(args.get("metrica") or "").lower() in ("valor", "eth", "plata") else "movimientos"
    feed = scan(chain, max_blocks=bloques)
    txs = feed.get("txs") or []
    ranking, serie, creados = _agregar_actividad(txs, MAX_TOP_CHAT)
    ranking = _agrega_por({"ranking": ranking}, metrica)[:top_n]
    direcciones = {a for t in txs for a in ((t.get("from") or "").lower(), (t.get("to") or "").lower())
                   if a and a != ADDR_CERO}
    return {
        "cadena": chain, "bloques": bloques, "metrica": metrica,
        "desde": serie[0]["bloque"] if serie else None,
        "hasta": serie[-1]["bloque"] if serie else None,
        "transacciones": len(txs), "direcciones": len(direcciones),
        "contratos_creados": creados, "mediana_eth": feed.get("median_eth"),
        "ranking": ranking, "serie": serie,
        "ganador": ranking[0] if ranking else None,
        "explicacion": _explica_ranking(chain, ranking, serie, len(txs), metrica),
    }


def _herramienta_resumen(args: dict) -> dict:
    """Resumen de la cadena: totales, serie y ranking de direcciones."""
    datos = _herramienta_top_wallets(args)
    if datos.get("error"):
        return datos
    return {
        "cadena": datos["cadena"], "bloques": datos["bloques"],
        "desde": datos["desde"], "hasta": datos["hasta"],
        "transacciones": datos["transacciones"], "direcciones": datos["direcciones"],
        "contratos_creados": datos["contratos_creados"], "mediana_eth": datos["mediana_eth"],
        "serie": datos["serie"], "ranking": datos["ranking"],
        "explicacion": datos["explicacion"],
    }


def _herramienta_comparar(args: dict) -> dict:
    """Dos o más wallets en la misma tabla, con su serie para el gráfico."""
    chain = args.get("chain") or "ethereum"
    if chain not in chains.supported():
        return {"error": f"cadena no soportada: {chain}"}
    pedidos = [str(a or "").lower() for a in (args.get("addresses") or [])]
    validas = list(dict.fromkeys(a for a in pedidos if ADDR_RE.fullmatch(a)))[:MAX_COMPARAR]
    if len(validas) < 2:
        return {"error": "Necesito al menos dos direcciones válidas (0x seguido de 40 "
                         "hexadecimales) para compararlas."}

    tabla, errores = [], {}
    for addr in validas:
        datos = HERRAMIENTAS["wallet"]({"address": addr, "chain": chain})
        if datos.get("error"):
            errores[addr] = datos["error"]
            continue
        tabla.append({
            "direccion": addr, "score": datos.get("score"), "nivel": datos.get("nivel"),
            "transacciones": datos.get("transacciones"),
            "contrapartes": datos.get("contrapartes"),
            "balance_usd": datos.get("balance_usd"),
            "confianza_muestra": datos.get("confianza_muestra"),
            "etiquetas": datos.get("etiquetas") or [],
            "calidad_datos": datos.get("calidad_datos"),
            "factores": list(datos.get("factores") or [])[:4],
            "explicacion": datos.get("explicacion"),
        })
    if not tabla:
        return {"error": "Ninguna de esas direcciones devolvió datos: no hay nada que comparar."}

    con_score = [f for f in tabla if isinstance(f["score"], int)]
    con_tx = [f for f in tabla if isinstance(f["transacciones"], (int, float))]
    mas_riesgosa = max(con_score, key=lambda f: f["score"]) if con_score else None
    mas_activa = max(con_tx, key=lambda f: f["transacciones"]) if con_tx else None
    etiquetas = [f"{f['direccion'][:6]}…{f['direccion'][-4:]}" for f in tabla]
    resumen = (
        f"Comparativa en {chain}: {len(tabla)} wallets. "
        + (f"La que más riesgo puntúa es {mas_riesgosa['direccion']} "
           f"({mas_riesgosa['score']}/100, {mas_riesgosa['nivel']}). " if mas_riesgosa else
           "Ninguna tiene score calculable: sin datos suficientes no los invento. ")
        + (f"La que más se movió es {mas_activa['direccion']} "
           f"({mas_activa['transacciones']} transacciones). " if mas_activa else "")
        + "Un score alto no significa culpable y uno bajo no significa honesta: "
          "compara también de dónde viene el dinero."
    )
    return {
        "cadena": chain, "tabla": tabla, "errores": errores,
        "mas_riesgosa": mas_riesgosa, "mas_activa": mas_activa,
        "serie": {"etiquetas": etiquetas,
                  "scores": [f["score"] for f in tabla],
                  "transacciones": [f["transacciones"] for f in tabla],
                  "niveles": [f["nivel"] for f in tabla]},
        "explicacion": agents.run(
            "explicacion",
            f"Comparativa en {chain}. Filas: {json.dumps(tabla, ensure_ascii=False, default=str)}. "
            f"Explica en español en qué se diferencian y cuál mirarías antes.",
            resumen)["text"],
    }


HERRAMIENTAS = {
    "wallet": _herramienta_wallet,
    "contrato": _herramienta_contrato,
    "rastreo": _herramienta_rastreo,
    "top_wallets": _herramienta_top_wallets,
    "resumen": _herramienta_resumen,
    "comparar": _herramienta_comparar,
    "feed": _herramienta_feed,
    "estado": _herramienta_estado,
    "watchlist": _herramienta_watchlist,
}


# ------------------------------------------------------------------ enrutado IA
def _json_primero(texto: str) -> object | None:
    """Primer objeto JSON de un texto, aunque venga envuelto o con vallas.

    Se cuenta a mano el nivel de llaves: con un regex se rompe en cuanto el
    modelo escribe un '{' dentro de un texto antes del JSON de verdad.
    """
    s = str(texto or "")
    inicio = s.find("{")
    while inicio != -1:
        nivel, en_cadena, escapado = 0, False, False
        for pos in range(inicio, len(s)):
            c = s[pos]
            if escapado:
                escapado = False
                continue
            if c == "\\" and en_cadena:
                escapado = True
                continue
            if c == '"':
                en_cadena = not en_cadena
                continue
            if en_cadena:
                continue
            if c == "{":
                nivel += 1
            elif c == "}":
                nivel -= 1
                if nivel == 0:
                    try:
                        return json.loads(s[inicio:pos + 1])
                    except json.JSONDecodeError:
                        break
        inicio = s.find("{", inicio + 1)
    return None


def _sanea_args(herramienta: str, args) -> dict:
    """Deja los argumentos en lo que las herramientas saben aceptar.

    Todo lo que venga de más se descarta: el modelo no puede abrir un dict
    de configuración, cambiar el proveedor de IA ni pedir 500 saltos de
    trazado porque se le antojó.
    """
    entrada = args if isinstance(args, dict) else {}
    limpio: dict = {}
    cadena = str(entrada.get("chain") or "").strip().lower()
    limpio["chain"] = cadena if cadena in chains.supported() else "ethereum"

    if herramienta in NECESITA_DIRECCION:
        addr = str(entrada.get("address") or "").strip().lower()
        limpio["address"] = addr if ADDR_RE.fullmatch(addr) else None

    if herramienta == "rastreo":
        limpio["max_depth"] = _acota(entrada.get("max_depth"), 1, 4, 2)
        limpio["direction"] = "in" if str(entrada.get("direction") or "").lower() in (
            "in", "entrante", "entrada") else "out"

    if herramienta in ("top_wallets", "resumen"):
        limpio["bloques"] = _acota(entrada.get("bloques"), 1, MAX_BLOQUES_CHAT, 3)
        limpio["top"] = _acota(entrada.get("top"), 1, MAX_TOP_CHAT, 5)
        limpio["metrica"] = ("valor" if str(entrada.get("metrica") or "").lower()
                             in ("valor", "eth", "plata") else "movimientos")

    if herramienta == "comparar":
        pedidos = [str(a or "").strip().lower() for a in (entrada.get("addresses") or [])]
        limpio["addresses"] = list(dict.fromkeys(
            a for a in pedidos if ADDR_RE.fullmatch(a)))[:MAX_COMPARAR]

    return limpio


def _normaliza(nombre: str) -> str:
    """Minúsculas, sin tildes y sin signos: «Rastrear» y «rastreo» se parecen."""
    plano = unicodedata.normalize("NFKD", str(nombre or "").lower())
    return "".join(c for c in plano if not unicodedata.combining(c) and c.isalnum())


def _distancia(a: str, b: str) -> int:
    """Levenshtein. Cadenas de menos de 30 caracteres: no hace falta más."""
    if a == b:
        return 0
    if not a or not b:
        return max(len(a), len(b))
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(actual[-1] + 1, anterior[j] + 1,
                              anterior[j - 1] + (ca != cb)))
        anterior = actual
    return anterior[-1]


def _coincide_herramienta(nombre) -> str | None:
    """Traduce el nombre que dice el modelo al registro, tolerando erratas.

    Un modelo de 7B contestó «rastrear» cuando la herramienta se llama
    «rastreo». Tirar la pregunta entera por una errata es peor que resolver el
    nombre: el resultado solo puede ser una herramienta que ya existe, y sus
    argumentos se sanean igual. Si dos nombres se parecen lo mismo, no se
    inventa: se descarta.
    """
    if not isinstance(nombre, str):
        return None
    if nombre in HERRAMIENTAS:
        return nombre
    base = _normaliza(nombre)
    if len(base) < 4:
        return None
    exactos = [k for k in HERRAMIENTAS if _normaliza(k) == base]
    if len(exactos) == 1:
        return exactos[0]
    puntuado = sorted((_distancia(base, _normaliza(k)), k) for k in HERRAMIENTAS)
    if puntuado[0][0] <= 2 and (len(puntuado) == 1 or puntuado[1][0] > puntuado[0][0]):
        return puntuado[0][1]
    return None


def _enrutar_con_ia(texto: str, historial: list[dict] | None = None) -> tuple[str, dict] | None:
    """Deja que el modelo elija herramienta cuando la tabla no reconoce la pregunta.

    El modelo solo elige: ni lee la cadena ni calcula. Sus argumentos se
    sanean aquí y, si la herramienta elegida necesita una dirección y no la
    trae válida, se rechaza igual. Cualquier cosa que no sea una herramienta
    del registro devuelve None y el chat contesta con el determinista.
    """
    from . import llm

    catalogo = "\n".join(
        f"- {h['nombre']}({', '.join(h['args']) or 'sin argumentos'}): {h['descripcion']}"
        for h in herramientas_publicas())
    res = llm.complete(
        "Eres un enrutador de herramientas. Solo eliges una herramienta del catálogo y "
        "devuelves JSON. No calculas nada, no respondes a la pregunta, no inventes datos.",
        f"Catálogo de herramientas:\n{catalogo}\n\n"
        f"Pregunta del usuario: {texto}\n\n"
        "El nombre tiene que ser EXACTO, copiado del catálogo. "
        'Responde solo con este JSON y nada más: {"herramienta": "<nombre>", "args": {}}. '
        'Ejemplo válido: {"herramienta": "top_wallets", "args": {"chain": "ethereum", '
        '"bloques": 3, "metrica": "movimientos"}}. '
        "Si ninguna herramienta encaja, devuelve {\"herramienta\": null}.",
        max_tokens=150, temperature=0.0, purpose="enrutado")
    if not res.get("ok"):
        return None
    eleccion = _json_primero(res.get("text"))
    if not isinstance(eleccion, dict):
        return None
    nombre = _coincide_herramienta(eleccion.get("herramienta"))
    if not nombre:
        return None
    args = _sanea_args(nombre, eleccion.get("args"))
    if nombre in NECESITA_DIRECCION and not args.get("address"):
        return None
    if nombre == "comparar" and len(args.get("addresses") or []) < 2:
        return None
    return nombre, args


# ------------------------------------------------------------------- ejecución
class ErrorChat(Exception):
    pass


def ejecutar(texto: str, historial: list[dict] | None = None) -> dict:
    """Decide la herramienta, la ejecuta y devuelve datos + contexto para el LLM.

    Devuelve `{"respuesta": str, "datos": dict, "herramienta": str|None}` donde
    `respuesta` ya es utilizable aunque el modelo falle.
    """
    addr = _direccion(texto)
    intencion = _intencion(texto)
    chain = _cadena(texto)
    t_lower = (texto or "").lower()
    hist = (historial or [])[-MAX_HISTORIAL:]
    dirs = _direcciones(texto)

    elegido: str | None = None
    args: dict = {"address": addr, "chain": chain}

    if intencion == "contrato" and addr:
        elegido = "contrato"
    elif intencion == "rastreo" and addr:
        elegido = "rastreo"
        m = re.search(r"(\d)\s*saltos?", texto, re.I)
        args["max_depth"] = int(m.group(1)) if m else 2
        if re.search(r"\bentrantes?\b|\bde d[oó]nde\b", texto, re.I):
            args["direction"] = "in"
    elif intencion == "top":
        elegido = "top_wallets"
        m = re.search(r"(\d+)\s*bloques?\b", texto, re.I)
        args["bloques"] = int(m.group(1)) if m else 3
        m = re.search(r"\btop\s*(\d+)|\b(\d+)\s*wallets?\b", texto, re.I)
        args["top"] = int(m.group(1) or m.group(2)) if m else 5
        args["metrica"] = ("valor" if re.search(
            r"\bvalor\b|\beth\b|\bplata\b|\bdinero\b|\bvolumen\b|\bc[oó]mo (?:se movi[óo]|movi[óo])\b",
            t_lower) else "movimientos")
    elif intencion == "resumen":
        elegido = "resumen"
        m = re.search(r"(\d+)\s*bloques?\b", texto, re.I)
        args["bloques"] = int(m.group(1)) if m else 3
    elif intencion == "comparar" and len(dirs) >= 2:
        elegido = "comparar"
        args["addresses"] = dirs
    elif intencion in ("estado", "watchlist", "feed"):
        elegido = intencion
        if intencion == "feed" and addr:
            elegido = "wallet"
    elif intencion == "wallet" and addr:
        elegido = "wallet"

    if not addr and intencion == "wallet":
        return {
            "herramienta": None, "datos": {},
            "respuesta": "Necesito una dirección para mirarla. Pásame una del tipo 0x seguida "
                         "de 40 caracteres.",
        }

    # Follow-up corto: «¿y en base?» después de una pregunta sobre el sistema
    # casi siempre es "ahora enséñame el feed de esa red". Sin esto el chat
    # pide una dirección cuando el usuario solo ha cambiado de red.
    if not elegido and hist and len(texto.strip()) < 40 and re.search(r"\bbase\b|\bethereum\b|\beth\b", t_lower):
        elegido = "feed"

    # Última capa: la tabla no resolvió la pregunta (no la entendió, o la
    # entendió a medias y le falta una dirección). El modelo elige herramienta
    # de entre el catálogo, con los argumentos ya saneados. Si no hay modelo, o
    # su JSON no vale, se sigue con la respuesta determinista.
    enrutado = "tabla" if elegido else None
    if not elegido:
        eleccion = _enrutar_con_ia(texto, hist)
        if eleccion:
            elegido, elegidas = eleccion
            args = {**args, **elegidas}
            enrutado = "ia"

    datos: dict = {}
    if elegido:
        try:
            datos = HERRAMIENTAS[elegido](args)
        except Exception as e:  # una herramienta caída no tumba el chat
            datos = {"error": f"{type(e).__name__}: {str(e)[:120]}"}

    resumen = _determinista(elegido, datos, addr, chain, intencion)
    if not elegido:
        if intencion == "comparar":
            resumen = ("Para comparar necesito al menos dos direcciones: pásame las dos "
                       "separadas por una coma y las pongo en la misma tabla.")
        return {"herramienta": None, "datos": {}, "respuesta": resumen, "enrutado": None,
                "contexto": _contexto_libre(hist)}
    return {"herramienta": elegido, "datos": datos, "respuesta": resumen, "enrutado": enrutado,
            "contexto": _contexto_herramienta(elegido, datos)}


def _contexto_libre(hist: list[dict]) -> str:
    partes = []
    for h in hist:
        if h.get("role") == "user":
            partes.append(f"Usuario preguntó: {str(h.get('content'))[:300]}")
        elif h.get("role") == "assistant":
            partes.append(f"Respuesta previa: {str(h.get('content'))[:300]}")
    return "\n".join(partes[-4:])


def _determinista(herramienta: str | None, datos: dict, addr: str | None,
                  chain: str, intencion: str) -> str:
    """Respuesta sin IA. Es la que se devuelve si el modelo no está o falla."""
    if herramienta is None:
        return (
            "Puedo mirar wallets, contratos, rutas de fondos, el feed en vivo, el estado del "
            "sistema y la watchlist. Además: «qué wallet se movió más», un resumen de la cadena "
            "y comparar dos direcciones. Dime una dirección 0x… y qué quieres saber de ella, "
            "o pregúntame por la red directamente."
        )
    if datos.get("error"):
        return f"No pude completar la consulta: {datos['error']}"

    if herramienta == "wallet":
        if datos.get("score") is None:
            return (f"No hay datos suficientes para evaluar {addr} en {chain}. "
                    "Sin datos no doy un score: reintenta en unos segundos.")
        return (
            f"{addr} ({chain}): riesgo {datos['nivel']} ({datos['score']}/100). "
            f"{datos.get('transacciones')} transacciones, confianza de muestra "
            f"{datos.get('confianza_muestra')}"
            + (f", {datos.get('contrapartes')} contrapartes" if datos.get("contrapartes") else "")
            + ". " + (datos.get("explicacion") or "")
        )
    if herramienta == "contrato":
        if not datos.get("es_contrato"):
            return f"{addr} no tiene bytecode: es una EOA, no un contrato."
        return (f"{addr}: riesgo {datos.get('score')}/100"
                + (f", proxy ({datos['es_proxy']})" if datos.get("es_proxy") else "")
                + ". " + (datos.get("explicacion") or ""))
    if herramienta == "rastreo":
        return (f"Trazado de {addr}: {datos.get('rutas')} rutas, {datos.get('nodos')} nodos, "
                f"{datos.get('usd_trazado')} USD. " + (datos.get("narrativa") or ""))
    if herramienta in ("top_wallets", "resumen"):
        ranking = datos.get("ranking") or []
        if not ranking:
            return (f"Escaneé {datos.get('transacciones')} transacciones en {datos.get('cadena') or chain} "
                    f"y ninguna dirección movió valor: sin transacciones no hay ranking que dar.")
        ventana = (f"los bloques {datos.get('desde')}–{datos.get('hasta')}"
                   if datos.get("desde") is not None else "los bloques escaneados")
        g = ranking[0]
        cabecera = (f"La dirección con más movimientos en {datos.get('cadena') or chain} es {g['direccion']}: "
                    f"{g['movimientos']} transacciones en {ventana}, {g['enviado_eth']} ETH enviados, "
                    f"{g['recibido_eth']} ETH recibidos y {g['contrapartes']} contrapartes distintas.")
        if len(ranking) > 1:
            resto = ", ".join(f"{r['direccion']} ({r['movimientos']})" for r in ranking[1:4])
            cabecera += f" Después: {resto}."
        if herramienta == "resumen":
            cabecera += (f" En el rango, {datos.get('transacciones')} transacciones entre "
                         f"{datos.get('direcciones')} direcciones, con mediana de "
                         f"{datos.get('mediana_eth')} ETH.")
        return cabecera + " " + (datos.get("explicacion") or "")
    if herramienta == "comparar":
        tabla = datos.get("tabla") or []
        if not tabla:
            return f"No pude comparar: {datos.get('error', 'sin datos')}"
        risky = datos.get("mas_riesgosa")
        activo = datos.get("mas_activa")
        salida = f"Comparativa en {datos.get('cadena') or chain}: " + "; ".join(
            f"{f['direccion']} — riesgo {f['nivel']} ({f['score']}/100), {f['transacciones']} transacciones"
            for f in tabla)
        if risky:
            salida += f" La que más riesgo puntúa es {risky['direccion']}."
        if activo and (not risky or activo["direccion"] != risky["direccion"]):
            salida += f" La que más se movió es {activo['direccion']}."
        return salida + " " + (datos.get("explicacion") or "")
    if herramienta == "feed":
        return (f"{chain}: bloque {datos.get('bloque')}, {datos.get('transacciones')} transacciones, "
                f"{datos.get('alertas')} alertas en el último bloque. "
                f"Mediana {datos.get('mediana_eth')} ETH.")
    if herramienta == "watchlist":
        if not datos.get("total"):
            return "La watchlist está vacía: no hay direcciones vigiladas ahora mismo."
        return (f"{datos['total']} direcciones vigiladas: "
                + ", ".join(f"{d['direccion'][:12]}… ({d['etiqueta']})" for d in datos.get("direcciones", [])[:5]))
    if herramienta == "estado":
        ia = datos.get("ia", {})
        cen = datos.get("centinela", {})
        return (f"IA: {ia.get('proveedor')} ({ia.get('modelo')}"
                + (", local" if ia.get("local") else "") + f"), {len(datos.get('agentes') or [])} agentes. "
                f"Centinela {'activo' if cen.get('activo') else 'apagado'} con {cen.get('ciclos')} ciclos. "
                f"Redes: {', '.join(datos.get('cadenas') or [])}.")
    return "No tengo datos para eso."


def responder(texto: str, historial: list[dict] | None = None) -> dict:
    """Chat completo: ejecuta la herramienta y redacta con el agente `chat`."""
    paso = ejecutar(texto, historial)
    agente = agents.get("chat")
    # el score es la cifra que este nodo más falsea: se le pasa para verificar
    score = (paso.get("datos") or {}).get("score")
    detalle = paso.get("herramienta") in ("top_wallets", "resumen", "comparar", "rastreo")
    if paso.get("herramienta"):
        if detalle:
            # Solo se nombra el gráfico que existe: en una comparativa no hay
            # serie por bloque, y prometerla hacía que el modelo la describiera.
            serie = paso.get("datos", {}).get("serie")
            hay_bloques = (isinstance(serie, list) and bool(serie)
                           and isinstance(serie[0], dict) and "bloque" in serie[0])
            sobre_grafico = (
                "Estos datos traen una serie por bloque que la interfaz ya dibuja como gráfico: "
                "no la repitas con texto, di qué se ve en ella."
                if hay_bloques else
                "La interfaz está comparando estas mismas cifras en un gráfico: no lo describas, "
                "usa los números de abajo."
            )
            user = (
                f"Pregunta del usuario: {texto}\n\n"
                f"Datos reales que acabo de obtener con la herramienta "
                f"'{paso['herramienta']}':\n{paso.get('contexto')}\n\n"
                f"Redacta en español. {sobre_grafico} "
                f"Da las cifras de arriba, di qué significan y qué miraría yo después. "
                f"Un volumen alto no prueba nada y no hay que inventar motivos. Máximo 10 líneas."
            )
        else:
            user = (
                f"Pregunta del usuario: {texto}\n\n"
                f"Datos reales que acabo de obtener con la herramienta "
                f"'{paso['herramienta']}':\n{paso.get('contexto')}\n\n"
                f"Redacta la respuesta en español. Usa solo esos datos, sé breve (máximo 6 líneas) "
                f"y no prometas nada que no esté en ellos."
            )
    else:
        user = (
            f"Pregunta del usuario: {texto}\n\n"
            f"Contexto de la conversación:\n{paso.get('contexto', '(sin historial)')}\n\n"
            "Responde en español y sé breve. Si el usuario pregunta por datos de una wallet o "
            "contrato y no ha dado una dirección, pídela."
        )
    res = agents.run("chat", user, paso["respuesta"], score=score if isinstance(score, int) else None)
    return {
        "respuesta": res["text"],
        "determinista": paso["respuesta"],
        "herramienta": paso.get("herramienta"),
        "enrutado": paso.get("enrutado"),
        "datos": paso.get("datos", {}),
        "agente": res.get("agente"),
        "source": res.get("source"),
        "motivo": res.get("motivo"),
        "modelo": res.get("modelo"),
        "latency_s": res.get("latency_s"),
    }


def herramientas_publicas() -> list[dict]:
    """Catálogo de herramientas: lo lee la API y el enrutado por IA.

    El `nombre` es exactamente la clave en `HERRAMIENTAS`. Que el catálogo y el
    registro no coincidan es como el modelo acabaría pidiendo algo que no existe.
    """
    return [
        {"nombre": "wallet", "args": ["address", "chain"],
         "descripcion": "Perfil, score, señales y explicación de una wallet"},
        {"nombre": "contrato", "args": ["address", "chain"],
         "descripcion": "Permisos, proxy y hallazgos de un contrato"},
        {"nombre": "rastreo", "args": ["address", "max_depth", "direction"],
         "descripcion": "Rastrea por dónde ha pasado el dinero (origen o destino)"},
        {"nombre": "top_wallets", "args": ["chain", "bloques", "top", "metrica"],
         "descripcion": "Qué dirección se ha movido más en los últimos bloques, por "
                        "movimientos o por valor, con serie por bloque"},
        {"nombre": "comparar", "args": ["addresses", "chain"],
         "descripcion": "Pone dos o más wallets en la misma tabla y dice cuál arriesga más"},
        {"nombre": "resumen", "args": ["chain", "bloques"],
         "descripcion": "Resumen de la actividad de la cadena, con serie por bloque"},
        {"nombre": "feed", "args": ["chain"],
         "descripcion": "Actividad y alertas del último bloque"},
        {"nombre": "estado", "args": [],
         "descripcion": "IA, centinela, guard y agentes"},
        {"nombre": "watchlist", "args": [],
         "descripcion": "Direcciones vigiladas"},
    ]
