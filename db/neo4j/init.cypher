// ChainMind Fase 0 — Constraints e índices Neo4j
// Nodos: Wallet, Contract, Transaction

CREATE CONSTRAINT wallet_address_chain IF NOT EXISTS
FOR (w:Wallet) REQUIRE (w.address, w.chain) IS UNIQUE;

CREATE CONSTRAINT contract_address_chain IF NOT EXISTS
FOR (c:Contract) REQUIRE (c.address, c.chain) IS UNIQUE;

CREATE CONSTRAINT tx_hash_chain IF NOT EXISTS
FOR (t:Transaction) REQUIRE (t.hash, t.chain) IS UNIQUE;

CREATE INDEX tx_block_time IF NOT EXISTS FOR (t:Transaction) ON (t.blockTime);
CREATE INDEX wallet_risk IF NOT EXISTS FOR (w:Wallet) ON (w.riskScore);
