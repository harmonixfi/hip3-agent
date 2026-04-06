-- schema_pm_v3.sql (Position Manager)
-- Tracks positions, legs, snapshots, and cashflows.

PRAGMA foreign_keys = ON;

-- Positions: aggregate of one or more legs
CREATE TABLE IF NOT EXISTS pm_positions (
  position_id TEXT NOT NULL,
  venue TEXT NOT NULL,
  strategy TEXT,
  status TEXT NOT NULL CHECK (status IN ('OPEN', 'PAUSED', 'EXITING', 'CLOSED')),
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL,
  closed_at_ms INTEGER,
  raw_json TEXT,              -- Original API response JSON
  meta_json TEXT,             -- Metadata JSON (e.g., tags, notes)
  PRIMARY KEY (position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_positions_venue ON pm_positions(venue);
CREATE INDEX IF NOT EXISTS idx_pm_positions_status ON pm_positions(status);
CREATE INDEX IF NOT EXISTS idx_pm_positions_created ON pm_positions(created_at_ms);

-- Legs: individual components of a position
CREATE TABLE IF NOT EXISTS pm_legs (
  leg_id TEXT NOT NULL,
  position_id TEXT NOT NULL,
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
  size REAL NOT NULL,
  entry_price REAL,
  current_price REAL,
  unrealized_pnl REAL,
  realized_pnl REAL,
  status TEXT NOT NULL CHECK (status IN ('OPEN', 'CLOSED')),
  opened_at_ms INTEGER NOT NULL,
  closed_at_ms INTEGER,
  raw_json TEXT,              -- Original API response JSON
  meta_json TEXT,             -- Metadata JSON
  account_id TEXT,            -- Wallet/account identifier for multi-wallet support
  PRIMARY KEY (leg_id),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_legs_position_id ON pm_legs(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_legs_venue_inst ON pm_legs(venue, inst_id);
CREATE INDEX IF NOT EXISTS idx_pm_legs_status ON pm_legs(status);

-- Leg Snapshots: append-only historical snapshots of leg state
CREATE TABLE IF NOT EXISTS pm_leg_snapshots (
  snapshot_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  leg_id TEXT NOT NULL,
  position_id TEXT NOT NULL,
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  ts INTEGER NOT NULL,        -- epoch ms UTC
  side TEXT NOT NULL CHECK (side IN ('LONG', 'SHORT')),
  size REAL NOT NULL,
  entry_price REAL,
  current_price REAL,
  unrealized_pnl REAL,
  realized_pnl REAL,
  raw_json TEXT,              -- Full snapshot JSON
  meta_json TEXT,             -- Metadata JSON
  account_id TEXT,            -- Wallet/account identifier for multi-wallet support
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_leg_id ON pm_leg_snapshots(leg_id);
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_position_id ON pm_leg_snapshots(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_ts ON pm_leg_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_venue ON pm_leg_snapshots(venue);
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_account ON pm_leg_snapshots(account_id, leg_id);

-- Account Snapshots: append-only account state snapshots
CREATE TABLE IF NOT EXISTS pm_account_snapshots (
  snapshot_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL,
  account_id TEXT NOT NULL,
  ts INTEGER NOT NULL,        -- epoch ms UTC
  total_balance REAL,
  available_balance REAL,
  margin_balance REAL,
  unrealized_pnl REAL,
  position_value REAL,
  raw_json TEXT,              -- Full account snapshot JSON
  meta_json TEXT              -- Metadata JSON (e.g., account type, tier)
);

CREATE INDEX IF NOT EXISTS idx_pm_account_snapshots_venue ON pm_account_snapshots(venue);
CREATE INDEX IF NOT EXISTS idx_pm_account_snapshots_account_id ON pm_account_snapshots(account_id);
CREATE INDEX IF NOT EXISTS idx_pm_account_snapshots_ts ON pm_account_snapshots(ts);
CREATE INDEX IF NOT EXISTS idx_pm_account_snapshots_venue_ts ON pm_account_snapshots(venue, ts);

-- Cashflows: financial events (pnl, fees, funding, transfers)
CREATE TABLE IF NOT EXISTS pm_cashflows (
  cashflow_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  position_id TEXT,           -- NULL for non-position cashflows (e.g., deposit/withdraw)
  leg_id TEXT,
  venue TEXT,                 -- NULL allowed (e.g. strategy-scoped manual dual-write)
  account_id TEXT NOT NULL,
  ts INTEGER NOT NULL,        -- epoch ms UTC
  cf_type TEXT NOT NULL CHECK (cf_type IN ('REALIZED_PNL', 'FEE', 'FUNDING', 'TRANSFER', 'DEPOSIT', 'WITHDRAW', 'OTHER')),
  amount REAL NOT NULL,       -- Positive = credit, Negative = debit
  currency TEXT NOT NULL,
  description TEXT,
  raw_json TEXT,              -- Original event JSON
  meta_json TEXT,             -- Metadata JSON
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_cashflows_position_id ON pm_cashflows(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_leg_id ON pm_cashflows(leg_id);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_venue ON pm_cashflows(venue);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_account_id ON pm_cashflows(account_id);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_ts ON pm_cashflows(ts);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_venue_ts ON pm_cashflows(venue, ts);
CREATE INDEX IF NOT EXISTS idx_pm_cashflows_type ON pm_cashflows(cf_type);
