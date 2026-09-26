"""verificar_bases.py — el estado REAL de Postgres y Neo4j, no el que responde la API.

Existe porque `persistence: "ok"` en la respuesta del endpoint es la opinión del
proceso sobre su propio `INSERT`. Esto va a la base y cuenta filas.

    python scripts/verificar_bases.py

Requiere los drivers (`psycopg`, `neo4j`). Si faltan, lo dice: es
precisamente el fallo que hizo que todas las escrituras fallaran en silencio
antes del BUG C.
"""
import json
import sys

sys.path.insert(0, ".")


def _psql_config():
    from app.db.postgres import DATABASE_URL  # noqa: E402
    return DATABASE_URL


def revisar_postgres() -> dict:
    url = "postgresql://chainmind:chainmind_dev@localhost:5432/chainmind"
    try:
        from app.db.postgres import DATABASE_URL
        url = DATABASE_URL
    except Exception:
        pass
    try:
        import psycopg
    except Exception as e:
        return {"estado": "driver-falta", "detalle": f"{type(e).__name__}: {e}"}
    out = {"estado": "ok", "url": url.replace("chainmind_dev", "***")}
    try:
        with psycopg.connect(url, connect_timeout=5) as c:
            with c.cursor() as cur:
                cur.execute("SELECT current_database(), pg_encoding_to_char(encoding) FROM pg_database "
                            "WHERE datname=current_database()")
                db, enc = cur.fetchone()
                out["base"], out["encoding"] = db, enc
                for tabla in ("wallets", "reports", "raw_transactions"):
                    cur.execute(f"SELECT count(*) FROM {tabla}")
                    out[tabla] = cur.fetchone()[0]
                cur.execute("SELECT address, tx_count, risk_score, labels FROM wallets "
                            "ORDER BY updated_at DESC LIMIT 5")
                out["ultimas_wallets"] = [
                    {"address": a, "tx_count": t, "risk_score": s, "labels": list(l or [])}
                    for a, t, s, l in cur.fetchall()]
    except Exception as e:
        out = {"estado": "fallo", "url": url.replace("chainmind_dev", "***"),
               "detalle": f"{type(e).__name__}: {str(e)[:140]}"}
    return out


def revisar_neo4j() -> dict:
    try:
        import neo4j  # noqa: F401
    except Exception as e:
        return {"estado": "driver-falta", "detalle": f"{type(e).__name__}: {e}"}
    uri, user, pwd = "bolt://localhost:7687", "neo4j", "chainmind_dev"
    try:
        from backend.app.db.neo4j_driver import URI, USER, PASSWORD
        uri, user, pwd = URI, USER, PASSWORD
    except Exception:
        pass
    out = {"estado": "ok", "uri": uri}
    try:
        from neo4j import GraphDatabase
        d = GraphDatabase.driver(uri, auth=(user, pwd))
        with d.session() as s:
            def uno(q, **kw):
                r = s.run(q, **kw)
                return r.single()
            out["wallets"] = uno("MATCH (n:Wallet) RETURN count(n) AS c")["c"]
            out["transactions"] = uno("MATCH (n:Transaction) RETURN count(n) AS c")["c"]
            # el tipo de relación que el usuario preguntó por
            out["transacted_with"] = uno(
                "MATCH (:Wallet)-[r:TRANSACTED_WITH]->(:Wallet) RETURN count(r) AS c")["c"]
            # el que el código sí escribe (neo4j_driver.py:26)
            out["sent_to"] = uno(
                "MATCH (:Wallet)-[:SENT]->(:Transaction)-[:TO]->(:Wallet) RETURN count(*) AS c")["c"]
            out["constraints"] = [r["name"] for r in s.run(
                "SHOW CONSTRAINTS YIELD name RETURN name ORDER BY name")]
        d.close()
    except Exception as e:
        out = {"estado": "fallo", "uri": uri,
               "detalle": f"{type(e).__name__}: {str(e)[:140]}"}
    return out


def main() -> int:
    pg = revisar_postgres()
    nj = revisar_neo4j()
    print("=" * 74)
    print("POSTGRES")
    print("=" * 74)
    print(json.dumps(pg, ensure_ascii=False, indent=2))
    print()
    print("=" * 74)
    print("NEO4J")
    print("=" * 74)
    print(json.dumps(nj, ensure_ascii=False, indent=2))
    print()
    print("=" * 74)
    print("OJO: `transacted_with: 0` NO es una base vacia.")
    print("Es que ningun camino del codigo crea ese tipo de relacion: solo se")
    print("escriben SENT y TO (backend/app/db/neo4j_driver.py:26). Una query")
    print("que pregunte por TRANSACTED_WITH dara 0 siempre, con datos o sin ellos.")
    print("=" * 74)
    return 0 if pg.get("estado") == "ok" and nj.get("estado") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
