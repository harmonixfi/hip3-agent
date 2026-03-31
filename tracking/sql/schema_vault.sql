-- Vault multi-strategy tracking tables.
-- Run once to create; safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS vault_strategies (
  strategy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'PAUSED', 'CLOSED')),
  wallets_json TEXT,
  target_weight_pct REAL,
  config_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_strategy_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  equity_usd REAL NOT NULL,
  equity_breakdown_json TEXT,
  apr_since_inception REAL,
  apr_30d REAL,
  apr_7d REAL,
  meta_json TEXT,
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_strat_snap_daily
  ON vault_strategy_snapshots(strategy_id, CAST(ts / 86400000 AS INTEGER));
CREATE INDEX IF NOT EXISTS idx_vault_strat_snap_strategy
  ON vault_strategy_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_vault_strat_snap_ts
  ON vault_strategy_snapshots(ts);

CREATE TABLE IF NOT EXISTS vault_cashflows (
  cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  cf_type TEXT NOT NULL
    CHECK (cf_type IN ('DEPOSIT', 'WITHDRAW', 'TRANSFER')),
  amount REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USDC',
  strategy_id TEXT,
  from_strategy_id TEXT,
  to_strategy_id TEXT,
  description TEXT,
  meta_json TEXT,
  created_at_ms INTEGER NOT NULL,
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (from_strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (to_strategy_id) REFERENCES vault_strategies(strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_vault_cf_ts ON vault_cashflows(ts);
CREATE INDEX IF NOT EXISTS idx_vault_cf_strategy ON vault_cashflows(strategy_id);
CREATE INDEX IF NOT EXISTS idx_vault_cf_type ON vault_cashflows(cf_type);

CREATE TABLE IF NOT EXISTS vault_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  total_equity_usd REAL NOT NULL,
  strategy_weights_json TEXT,
  total_apr REAL,
  apr_30d REAL,
  apr_7d REAL,
  net_deposits_alltime REAL,
  meta_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_snap_daily
  ON vault_snapshots(CAST(ts / 86400000 AS INTEGER));
CREATE INDEX IF NOT EXISTS idx_vault_snap_ts
  ON vault_snapshots(ts);
