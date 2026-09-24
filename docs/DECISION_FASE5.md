# Fase 5 — Decision de escala: Kafka / ClickHouse

Estado actual: ingesta on-demand (Blockchair/Blockscout/RPC) + indexer Subsquid
por cadena (ethereum + base). Volumen: cientos de wallets por dia, batch nocturno
de anomalias sobre <=500 wallets. Latencia p95 < 2s en endpoints.

Decision: NO adoptar Kafka/Redpanda ni ClickHouse ahora.

Motivos:
- Sin streaming en tiempo real (Fase 3 es batch; Fase 4 es on-demand).
- Postgres + Neo4j absorben el volumen actual con margen (>100x).
- Cada pieza nueva suma operacion (temas, retencion, esquemas, monitoreo).

Umbrales para reconsiderar:
- >100 eventos/s sostenidos o >10M txs/dia indexadas -> Kafka/Redpanda.
- raw_transactions >100M filas o queries analiticas >5s -> ClickHouse.
- Necesidad de features vectoriales (GNN) -> vector DB.

Proxima cadena (Arbitrum): añadir entrada en agents/chains.py con adapter
blockscout (https://arbitrum.blockscout.com/api/v2) + RPC + sourcify 42161.
