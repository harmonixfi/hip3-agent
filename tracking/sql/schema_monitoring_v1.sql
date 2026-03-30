-- schema_monitoring_v1.sql
-- New tables for fill tracking, entry prices, spreads, and portfolio snapshots.
-- Applied as an additive migration on top of schema_pm_v3.sql.

-- Enable WAL mode for concurrent read/write (cron writes, API reads)
PRAGMA journal_mode=WAL;

-- ============================================================
-- pm_fills: Raw trade fills from all venues
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_fills (
  fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  -- Identifiers
  venue TEXT NOT NULL,
  account_id TEXT NOT NULL,
  -- Fill data
  tid TEXT,
  oid TEXT,
  inst_id TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  px REAL NOT NULL,
  sz REAL NOT NULL,
  fee REAL,
  fee_currency TEXT,
  ts INTEGER NOT NULL,
  -- HL-specific fields (nullable for other venues)
  closed_pnl REAL,
  dir TEXT,
  builder_fee REAL,
  -- Position mapping
  position_id TEXT,
  leg_id TEXT,
  -- Raw data
  raw_json TEXT,
  meta_json TEXT,
  -- Constraints
  UNIQUE (venue, account_id, tid),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_fills_venue_account ON pm_fills(venue, account_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_inst_id ON pm_fills(inst_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_ts ON pm_fills(ts);
CREATE INDEX IF NOT EXISTS idx_pm_fills_position_id ON pm_fills(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_leg_id ON pm_fills(leg_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_oid ON pm_fills(oid);

-- ============================================================
-- pm_entry_prices: Materialized VWAP per leg (derived from fills)
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_entry_prices (
  leg_id TEXT NOT NULL,
  position_id TEXT NOT NULL,
  avg_entry_price REAL NOT NULL,
  total_filled_qty REAL NOT NULL,
  total_cost REAL NOT NULL,
  fill_count INTEGER NOT NULL,
  first_fill_ts INTEGER,
  last_fill_ts INTEGER,
  computed_at_ms INTEGER NOT NULL,
  method TEXT NOT NULL DEFAULT 'VWAP',
  meta_json TEXT,
  PRIMARY KEY (leg_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_entry_prices_position ON pm_entry_prices(position_id);

-- ============================================================
-- pm_spreads: Entry/exit basis spread per sub-pair
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_spreads (
  spread_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  position_id TEXT NOT NULL,
  long_leg_id TEXT NOT NULL,
  short_leg_id TEXT NOT NULL,
  entry_spread REAL,
  long_avg_entry REAL,
  short_avg_entry REAL,
  exit_spread REAL,
  long_exit_price REAL,
  short_exit_price REAL,
  spread_pnl_bps REAL,
  computed_at_ms INTEGER NOT NULL,
  meta_json TEXT,
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
  FOREIGN KEY (long_leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (short_leg_id) REFERENCES pm_legs(leg_id),
  UNIQUE (position_id, long_leg_id, short_leg_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_spreads_position ON pm_spreads(position_id);

-- ============================================================
-- pm_portfolio_snapshots: Hourly aggregate portfolio metrics
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_portfolio_snapshots (
  snapshot_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  total_equity_usd REAL NOT NULL,
  equity_by_account_json TEXT,
  total_unrealized_pnl REAL,
  total_funding_today REAL,
  total_funding_alltime REAL,
  total_fees_alltime REAL,
  daily_change_usd REAL,
  cashflow_adjusted_change REAL,
  apr_daily REAL,
  tracking_start_date TEXT,
  meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_ts ON pm_portfolio_snapshots(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_hourly
  ON pm_portfolio_snapshots(CAST(ts / 3600000 AS INTEGER));
