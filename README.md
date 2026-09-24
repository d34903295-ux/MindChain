# ChainMind — Blockchain Intelligence Multi-Agent System
Fase 0: Setup monorepo + Postgres + Neo4j + Indexer Subsquid EVM

## Estructura
- `/frontend` — Next.js + React + TS + Tailwind + shadcn/ui
- `/backend` — FastAPI (Python)
- `/agents` — LangGraph (Wallet Intelligence, Risk, Explanation)
- `/indexer` — Subsquid EVM template (Ethereum mainnet)
- `/db/postgres/init.sql` — users, wallets, reports, raw_transactions
- `/db/neo4j/init.cypher` — Wallet, Contract, Transaction

## Quickstart
1. Copiar env: `cp .env.example .env` y rellenar `ETH_RPC_URL`, `ANTHROPIC_API_KEY`
2. Levantar stack: `docker compose up --build`
3. Backend: http://localhost:8000/docs — `GET /health`, `POST /analyze-wallet` (stub Fase 0)
4. Neo4j browser: http://localhost:7474 — user/pass de `.env`
5. Indexer: plantilla Subsquid EVM, ver `/indexer/README.md`

## Criterio salida Fase 0
`docker-compose up` levanta Postgres+Neo4j+backend+indexer y el indexer escribe bloques recientes a Postgres/Neo4j.

> Sin Docker en esta máquina: el scaffold está listo para `docker compose config` + `up` en dev.
