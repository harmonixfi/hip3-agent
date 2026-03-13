-- arbit.db schema v2 - instrument identity redesign
-- SQLite, WITHOUT ROWID optimization
-- Timestamps: INTEGER (epoch milliseconds UTC)
-- 
-- Key change: (venue, inst_id) uniquely identifies an instrument
-- This allows OKX to have both BTC-USDT (SPOT) and BTC-USDT-SWAP (PERP) as distinct rows

-- Instruments table (perps + spot pairs)
-- Each row is uniquely identified by (venue, inst_id)
CREATE TABLE IF NOT EXISTS instruments_v2 (
    venue TEXT NOT NULL,              -- okx, hyperliquid, paradex, lighter, ethereal
    inst_id TEXT NOT NULL,            -- venue-specific instrument ID (e.g., BTC-USDT, BTC-USDT-SWAP)
    base TEXT NOT NULL,               -- base asset (e.g., BTC, ETH)
    quote TEXT,                       -- quote asset (e.g., USDT, USDC, USD) - NULL for USD-margined perps
    contract_type TEXT,               -- PERP or SPOT
    symbol_base TEXT NOT NULL,        -- normalized base symbol (e.g., BTC, ETH)
    symbol_key TEXT,                  -- composite key for joins (e.g., "BTC:USDT" or "BTC:PERP")
    tick_size REAL,                   -- minimum price movement
    contract_size REAL,               -- contract size (e.g., 0.01 BTC)
    funding_interval_hours INTEGER,   -- funding interval in hours (1h, 4h, 8h)
    created_at INTEGER NOT NULL,      -- creation timestamp (epoch ms UTC)
    PRIMARY KEY (venue, inst_id)
);

-- Prices time-series
CREATE TABLE IF NOT EXISTS prices_v2 (
    venue TEXT NOT NULL,
    inst_id TEXT NOT NULL,            -- joins to instruments_v2(venue, inst_id)
    bid REAL,                         -- top bid
    ask REAL,                         -- top ask
    mid REAL,                         -- (bid + ask) / 2
    mark_price REAL,                  -- perp mark price
    index_price REAL,                 -- index price (for perps)
    last_price REAL,                  -- last trade price
    ts INTEGER NOT NULL,              -- epoch ms UTC
    PRIMARY KEY (venue, inst_id, ts)
);

-- Funding rates time-series
CREATE TABLE IF NOT EXISTS funding_v2 (
    venue TEXT NOT NULL,
    inst_id TEXT NOT NULL,            -- joins to instruments_v2(venue, inst_id)
    funding_rate REAL NOT NULL,       -- 8h-equivalent rate (decimal, e.g., 0.0001)
    funding_interval_hours INTEGER,   -- from instruments_v2 table
    next_funding_ts INTEGER,          -- epoch ms of next funding event
    ts INTEGER NOT NULL,              -- epoch ms UTC
    PRIMARY KEY (venue, inst_id, ts)
);

-- Indexes for query optimization
-- Prices
CREATE INDEX IF NOT EXISTS idx_prices_v2_venue_inst_ts ON prices_v2(venue, inst_id, ts);
CREATE INDEX IF NOT EXISTS idx_prices_v2_ts ON prices_v2(ts);

-- Funding
CREATE INDEX IF NOT EXISTS idx_funding_v2_venue_inst_ts ON funding_v2(venue, inst_id, ts);
CREATE INDEX IF NOT EXISTS idx_funding_v2_ts ON funding_v2(ts);

-- Instruments
CREATE INDEX IF NOT EXISTS idx_instruments_v2_symbol_key ON instruments_v2(symbol_key);
CREATE INDEX IF NOT EXISTS idx_instruments_v2_base_quote ON instruments_v2(base, quote);
CREATE INDEX IF NOT EXISTS idx_instruments_v2_venue_base ON instruments_v2(venue, base);
