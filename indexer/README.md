# Indexer — Subsquid EVM (Ethereum)
Base: https://github.com/subsquid-labs (plantilla evm-example).
- `npm install && npx sqd codegen && npx sqd migration:generate && npm run build && npm start`
- Requiere `DB_URL`, `RPC_ETH_HTTP`, `SQD_GATEWAY` (ver docker-compose).
- Fase 0: escribe a Postgres (TypeORM). El puente a Neo4j se hace en batch desde backend.
