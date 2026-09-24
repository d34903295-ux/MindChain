# Fase 0 — Checklist
- [x] Monorepo: /frontend, /backend, /agents, /indexer
- [x] docker-compose.yml con Postgres + Neo4j
- [x] Adaptar plantilla EVM de Subsquid como base del indexer
- [x] Schema inicial: Postgres (users, wallets, reports) y Neo4j (Wallet, Contract, Transaction)
Criterio salida: `docker compose up` levanta todo y el indexer escribe bloques recientes a Postgres/Neo4j.
