"""Investigation Agent: trazado de rutas de fondos.

- BFS en memoria sobre las txs disponibles (siempre funciona)
- Enriquecido con Cypher/Neo4j si hay base de datos
- Anota los nodos que caen en la watchlist y el valor total por ruta
"""
from collections import deque

from . import watchlist


def _low(a):
    return str(a or "").lower()


def build_edges(txs):
    edges = []
    seen_hashes = set()
    for t in txs or []:
        f, to = _low(t.get("from")), _low(t.get("to"))
        if not f or not to or f == to:
            continue
        h = t.get("hash") or ""
        if h and h in seen_hashes:
            continue  # misma tx duplicada por varias fuentes
        if h:
            seen_hashes.add(h)
        edges.append({"from": f, "to": to, "hash": h,
                      "value_usd": float(t.get("value_usd") or 0),
                      "time": t.get("time", ""), "block": t.get("block")})
    return edges


def trace_from_txs(address, txs, max_depth=3, max_paths=50, direction="out", min_value_usd=0.0):
    """BFS desde `address`. direction: out | in | both.

    `min_value_usd` filtra aristas: por defecto 0 (no filtra) para no perder
    movimientos pequeños que conectan la ruta.
    """
    start = _low(address)
    all_edges = build_edges(txs)
    edges = [e for e in all_edges if e["value_usd"] >= min_value_usd] if min_value_usd else all_edges
    fwd, bwd = {}, {}
    for e in edges:
        fwd.setdefault(e["from"], []).append(e)
        bwd.setdefault(e["to"], []).append(e)
    paths = []
    q = deque()
    q.append([start])
    seen_paths = set()
    while q and len(paths) < max_paths:
        path = q.popleft()
        last = path[-1]
        if len(path) > 1:
            key = tuple(path)
            if key not in seen_paths:
                seen_paths.add(key)
                paths.append(list(path))
        if len(path) - 1 >= max_depth:
            continue
        nxt = []
        if direction in ("out", "both"):
            nxt += [e["to"] for e in fwd.get(last, []) if e["to"] not in path]
        if direction in ("in", "both"):
            nxt += [e["from"] for e in bwd.get(last, []) if e["from"] not in path]
        for n in nxt:
            q.append(path + [n])
    nodes = sorted(set([start] + [n for p in paths for n in p]))
    used = set()
    for p in paths:
        for a, b in zip(p, p[1:]):
            used.add((a, b))
    kept = [e for e in edges if (e["from"], e["to"]) in used]
    # valor de cada ruta (suma de sus saltos) para priorizar las importantes
    edge_value = {(e["from"], e["to"]): e["value_usd"] for e in kept}
    path_values = []
    for p in paths:
        total = sum(edge_value.get((a, b), 0.0) for a, b in zip(p, p[1:]))
        path_values.append(total)
    order = sorted(range(len(paths)), key=lambda i: -path_values[i])
    paths = [paths[i] for i in order]
    path_values = [path_values[i] for i in order]
    flagged = []
    for n in nodes:
        label = watchlist.get(n)
        if label:
            flagged.append({"address": n, "label": label})
    return {
        "start": start,
        "direction": direction,
        "max_depth": max_depth,
        "nodes": nodes,
        "edges": kept,
        "paths": paths,
        "path_values_usd": path_values,
        "watchlist_nodes": flagged,
        "n_paths": len(paths),
        "n_nodes": len(nodes),
        "total_traced_usd": round(sum(e["value_usd"] for e in kept), 2),
    }

def neo4j_expand(address, max_depth=2, limit=100):
    """Expande 1..N saltos vía Cypher. Best-effort: {} con error si no hay Neo4j."""
    try:
        import sys as _s
        import pathlib as _p
        _s.path.insert(0, str(_p.Path(__file__).resolve().parents[1]))
        from backend.app.db.neo4j_driver import get_driver
        d = get_driver()
        edges = []
        frontier = [_low(address)]
        seen = set(frontier)
        for _ in range(max_depth):
            nxt = []
            with d.session() as s:
                for node in frontier:
                    rows = s.run("MATCH (a:Wallet {address:$a})-[:SENT]->(t:Transaction)-[:TO]->(b:Wallet) "
                                 "RETURN t.hash AS h, b.address AS to, t.valueUsd AS v LIMIT 25", a=node)
                    for r in rows:
                        to = _low(r["to"])
                        edges.append({"from": node, "to": to, "hash": r["h"] or "",
                                      "value_usd": float(r["v"] or 0), "time": "", "block": None})
                        if to not in seen:
                            seen.add(to)
                            nxt.append(to)
            frontier = nxt
            if not frontier:
                break
        return {"source": "neo4j", "edges": edges[:limit]}
    except Exception as e:
        return {"source": "neo4j-error", "error": str(e)[:200], "edges": []}


TRACE_SYSTEM = (
    "Eres un analista de trazabilidad de fondos. Describes grafos de transacciones.\n"
    "REGLAS INNEGOCIABLES:\n"
    "- Describe SOLO lo que aparece en el grafo. No inventes nodos, rutas ni importes.\n"
    "- No afirmes intención ni responsabilidad penal de ninguna dirección.\n"
    "- Señalar una coincidencia con una lista de screening no es una acusación: es un punto de partida.\n"
    "- Si el grafo está incompleto, dilo: el trazado solo cubre las transacciones disponibles.\n"
    "Responde en español, máximo 6 líneas."
)


def _fallback_narrative(trace: dict) -> str:
    """Resumen determinista: siempre disponible, nunca inventado."""
    lineas = [
        f"Trazado desde {trace.get('start', 'n/d')}: {trace.get('n_paths', 0)} rutas, "
        f"{trace.get('n_nodes', 0)} direcciones, {trace.get('total_traced_usd', 0)} USD en juego. "
        f"Cobertura: máximo {trace.get('max_depth', '?')} saltos en dirección {trace.get('direction', 'out')}. "
        "El trazado solo incluye las transacciones disponibles, no el histórico completo."
    ]
    marcados = trace.get("watchlist_nodes") or []
    if marcados:
        lineas.append(
            "Coincidencias con la watchlist (señal de screening, no veredicto): "
            + "; ".join(f"{m['address']} ({m['label']})" for m in marcados[:5]) + "."
        )
    else:
        lineas.append("Ninguna dirección del trazado aparece en la watchlist.")
    return " ".join(lineas)


def narrarize_trace(trace: dict) -> dict:
    """Explica el trazado con el agente `investigacion` sin inventar nodos.

    `trace` sale de `trace_from_txs()`, así que todo lo que se le da al modelo
    es lo que el BFS encontró de verdad. Hereda el filtro global de seguridad.
    """
    from . import agents
    fallback = _fallback_narrative(trace)
    paths = trace.get("paths") or []
    if not paths:
        return {"narrative": fallback, "ai": {"source": "determinista", "motivo": "sin rutas que explicar"}}
    muestras = [
        " → ".join(p[:5]) + (f" (valor {v} USD)" if i < len(trace.get("path_values_usd") or []) else "")
        for i, (p, v) in enumerate(zip(paths[:5], trace.get("path_values_usd") or []))
    ]
    user = (
        f"Dirección inicial: {trace.get('start')}\n"
        f"Rutas encontradas: {trace.get('n_paths')} · nodos: {trace.get('n_nodes')} · "
        f"total trazado: {trace.get('total_traced_usd')} USD\n"
        f"Coincidencias con watchlist: {len(trace.get('watchlist_nodes') or [])}\n"
        "Primeras rutas:\n" + "\n".join(f"- {m}" for m in muestras) + "\n\n"
        "Explica en español qué patrón muestran estas rutas, qué conviene mirar a "
        "continuación y qué limitaciones tiene este trazado. No concluyas nada que no "
        "salga de los datos."
    )
    res = agents.run("investigacion", user, fallback, max_tokens=380)
    return {"narrative": res["text"], "ai": {k: v for k, v in res.items() if k != "text"}}
