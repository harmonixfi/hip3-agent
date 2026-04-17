-- schema_monitoring_v2.sql
-- Trade aggregation layer. Layered on top of schema_monitoring_v1.sql and
-- schema_pm_v3.sql. Idempotent (IF NOT EXISTS).

PRAGMA foreign_keys = ON;

-- Extend pm_positions with declarative intent columns (nullable for migration).
-- SQLite has no native ADD COLUMN IF NOT EXISTS; loader tolerates duplicate error.
ALTER TABLE pm_positions ADD COLUMN base TEXT;
ALTER TABLE pm_positions ADD COLUMN strategy_type TEXT
  CHECK (strategy_type IN ('SPOT_PERP','PERP_PERP'));

CREATE TABLE IF NOT EXISTS pm_trades (
  trade_id        TEXT PRIMARY KEY,
  position_id     TEXT NOT NULL REFERENCES pm_positions(position_id),
  trade_type      TEXT NOT NULL CHECK (trade_type IN ('OPEN','CLOSE')),
  state           TEXT NOT NULL CHECK (state IN ('DRAFT','FINALIZED')),
  start_ts        INTEGER NOT NULL,
  end_ts          INTEGER NOT NULL,
  note            TEXT,

  long_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  long_size       REAL,
  long_notional   REAL,
  long_avg_px     REAL,
  long_fees       REAL,
  long_fill_count INTEGER,

  short_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  short_size       REAL,
  short_notional   REAL,
  short_avg_px     REAL,
  short_fees       REAL,
  short_fill_count INTEGER,

  spread_bps        REAL,
  realized_pnl_bps  REAL,

  created_at_ms     INTEGER NOT NULL,
  finalized_at_ms   INTEGER,
  computed_at_ms    INTEGER NOT NULL,

  UNIQUE (position_id, trade_type, start_ts, end_ts)
);

CREATE INDEX IF NOT EXISTS idx_pm_trades_position ON pm_trades(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_trades_window ON pm_trades(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_pm_trades_state ON pm_trades(state);

CREATE TABLE IF NOT EXISTS pm_trade_fills (
  trade_id  TEXT NOT NULL REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  fill_id   INTEGER NOT NULL REFERENCES pm_fills(fill_id),
  leg_side  TEXT NOT NULL CHECK (leg_side IN ('LONG','SHORT')),
  PRIMARY KEY (trade_id, fill_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_trade_fills_fill ON pm_trade_fills(fill_id);

CREATE TABLE IF NOT EXISTS pm_trade_reconcile_warnings (
  trade_id          TEXT PRIMARY KEY REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  unassigned_count  INTEGER NOT NULL,
  first_seen_ms     INTEGER NOT NULL,
  last_checked_ms   INTEGER NOT NULL
);
