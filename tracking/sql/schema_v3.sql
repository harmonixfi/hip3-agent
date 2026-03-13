-- schema_v3.sql (instrument-centric, quote-aware)
-- PKs are (venue, inst_id) for instruments and (venue, inst_id, ts) for time series.

PRAGMA foreign_keys = ON;

-- Instruments: one row per tradeable instrument on a venue
CREATE TABLE IF NOT EXISTS instruments_v3 (
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  base TEXT NOT NULL,
  quote TEXT NOT NULL,
  contract_type TEXT NOT NULL CHECK (contract_type IN ('SPOT','PERP')),
  symbol_key TEXT NOT NULL,     -- BASE:QUOTE (quote-aware join spot↔perp)
  symbol_base TEXT NOT NULL,    -- BASE (cross-venue perp↔perp join)
  raw_symbol TEXT,              -- venue native symbol if useful
  specs_json TEXT,              -- JSON string for tick size, lot size, etc.
  status TEXT,                  -- active/paused/etc.
  created_at_ms INTEGER,
  updated_at_ms INTEGER,
  PRIMARY KEY (venue, inst_id)
);

CREATE INDEX IF NOT EXISTS idx_instruments_v3_symbol_key ON instruments_v3(venue, symbol_key);
CREATE INDEX IF NOT EXISTS idx_instruments_v3_symbol_base ON instruments_v3(symbol_base);

-- Prices: append-only snapshots
CREATE TABLE IF NOT EXISTS prices_v3 (
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  ts INTEGER NOT NULL,          -- epoch ms UTC
  bid REAL,
  ask REAL,
  last REAL,
  mid REAL,
  mark REAL,
  index_price REAL,
  source TEXT,
  quality_flags TEXT,           -- JSON string
  PRIMARY KEY (venue, inst_id, ts),
  FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
);

CREATE INDEX IF NOT EXISTS idx_prices_v3_ts ON prices_v3(ts);
CREATE INDEX IF NOT EXISTS idx_prices_v3_inst_ts ON prices_v3(venue, inst_id, ts);

-- Funding: append-only per funding event/interval
CREATE TABLE IF NOT EXISTS funding_v3 (
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  ts INTEGER NOT NULL,                -- epoch ms UTC (event time or snapshot time)
  funding_rate REAL NOT NULL,         -- decimal per interval (NOT APR)
  interval_hours REAL,                -- e.g. 8, 1
  next_funding_ts INTEGER,            -- epoch ms UTC
  source TEXT,
  quality_flags TEXT,                 -- JSON string
  PRIMARY KEY (venue, inst_id, ts),
  FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
);

CREATE INDEX IF NOT EXISTS idx_funding_v3_ts ON funding_v3(ts);
CREATE INDEX IF NOT EXISTS idx_funding_v3_inst_ts ON funding_v3(venue, inst_id, ts);

-- Optional: top-of-book snapshots
CREATE TABLE IF NOT EXISTS orderbook_top_v3 (
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  bid REAL,
  ask REAL,
  bid_size REAL,
  ask_size REAL,
  source TEXT,
  quality_flags TEXT,
  PRIMARY KEY (venue, inst_id, ts),
  FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
);

CREATE INDEX IF NOT EXISTS idx_orderbook_top_v3_ts ON orderbook_top_v3(ts);
