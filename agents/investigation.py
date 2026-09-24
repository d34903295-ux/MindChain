"""Investigation Agent (Fase 4): trazado de rutas de fondos.
Primario: BFS en memoria sobre txs (siempre disponible).
Enriquecido: Cypher sobre Neo4j cuando hay conexion (best-effort).
"""
from collections import deque

def _low(a):
    return str(a or "").lower()

def build_edges(txs):
    edges = []
    for t in txs or []:
        f, to = _low(t.get("from")), _low(t.get("to"))
        if not f or not to or f == to:
            continue
        edges.append({"from": f, "to": to, "hash": t.get("hash", ""),
                      "value_usd": float(t.get("value_usd") or 0),
                      "time": t.get("time", ""), "block": t.get("block")})
    return edges

def trace_from_txs(address, txs, max_depth=3, max_paths=50, direction="out"):
    """BFS desde address. direction out|in|both. Devuelve nodos, aristas y rutas."""
    start = _low(address)
    edges = build_edges(txs)
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
    return {"start": start, "direction": direction, "max_depth": max_depth,
            "nodes": nodes, "edges": kept, "paths": paths,
            "n_paths": len(paths), "n_nodes": len(nodes)}

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
