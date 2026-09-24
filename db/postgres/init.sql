-- ChainMind Fase 0 — Schema inicial Postgres
-- users, wallets, reports

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS wallets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  address CHAR(42) NOT NULL UNIQUE CHECK (address ~ '^0x[0-9a-fA-F]{40}$'),
  chain VARCHAR(20) NOT NULL DEFAULT 'ethereum',
  first_seen_at TIMESTAMPTZ,
  last_seen_at TIMESTAMPTZ,
  tx_count INTEGER NOT NULL DEFAULT 0,
  risk_score SMALLINT CHECK (risk_score BETWEEN 0 AND 100),
  labels TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_wallets_address ON wallets(address);
CREATE INDEX IF NOT EXISTS idx_wallets_chain ON wallets(chain);

CREATE TABLE IF NOT EXISTS reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  wallet_id UUID NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
  profile JSONB NOT NULL DEFAULT '{}',
  risk_score SMALLINT NOT NULL CHECK (risk_score BETWEEN 0 AND 100),
  risk_factors JSONB NOT NULL DEFAULT '[]',
  explanation TEXT,
  created_by UUID REFERENCES users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_reports_wallet ON reports(wallet_id);
CREATE INDEX IF NOT EXISTS idx_reports_created ON reports(created_at DESC);

-- Tabla de ingesta del indexer (bloques/txs crudas normalizadas)
CREATE TABLE IF NOT EXISTS raw_transactions (
  hash CHAR(66) PRIMARY KEY CHECK (hash ~ '^0x[0-9a-fA-F]{64}$'),
  block_number BIGINT NOT NULL,
  block_time TIMESTAMPTZ NOT NULL,
  from_address CHAR(42) NOT NULL,
  to_address CHAR(42),
  value_numeric NUMERIC(38,0) NOT NULL DEFAULT 0,
  gas_used BIGINT,
  gas_price NUMERIC(38,0),
  chain VARCHAR(20) NOT NULL DEFAULT 'ethereum',
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_raw_tx_from ON raw_transactions(from_address);
CREATE INDEX IF NOT EXISTS idx_raw_tx_to ON raw_transactions(to_address);
CREATE INDEX IF NOT EXISTS idx_raw_tx_block ON raw_transactions(block_number DESC);
