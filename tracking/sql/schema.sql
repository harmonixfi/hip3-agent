-- arbit.db schema for public market data
-- SQLite, WITHOUT ROWID optimization
-- Timestamps: INTEGER (epoch milliseconds UTC)

-- Instruments table (perps + spot pairs)
CREATE TABLE IF NOT EXISTS instruments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,              -- okx, hyperliquid, paradex, lighter, ethereal
    symbol TEXT NOT NULL,             -- normalized symbol (e.g., BTC, ETH)
    inst_id TEXT,                       -- venue-specific instrument ID
    contract_type TEXT,                  -- PERP or SPOT
    tick_size REAL,                     -- minimum price movement
    contract_size REAL,                  -- contract size (e.g., 0.01 BTC)
    quote_currency TEXT,                  -- USDT, USDC, USD, etc.
    base_currency TEXT,
    funding_interval_hours INTEGER,         -- funding interval in hours (1h, 4h, 8h)
    created_at INTEGER NOT NULL           -- creation timestamp (epoch ms UTC)
);

-- Funding rates time-series
CREATE TABLE IF NOT EXISTS funding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    symbol TEXT NOT NULL,
    funding_rate REAL NOT NULL,            -- 8h-equivalent rate (decimal, e.g., 0.0001)
    funding_interval_hours INTEGER,            -- from instruments table
    next_funding_ts INTEGER,               -- epoch ms of next funding event
    ts INTEGER NOT NULL,                  -- epoch ms UTC
    UNIQUE(venue, symbol, ts)
);

-- Mark price / Index price / Last price / Orderbook mid
CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venue TEXT NOT NULL,
    symbol TEXT NOT NULL,
    mark_price REAL NOT NULL,             -- perp mark price
    index_price REAL,                      -- index price (for perps)
    last_price REAL,                       -- last trade price (for reference)
    bid REAL,                               -- top bid
    ask REAL,                               -- top ask
    mid REAL,                               -- (bid + ask) / 2
    ts INTEGER NOT NULL,
    UNIQUE(venue, symbol, ts)
);

-- Basis/spread between venues
CREATE TABLE IF NOT EXISTS basis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    leg_a_venue TEXT NOT NULL,              -- venue with higher price (short leg)
    leg_b_venue TEXT NOT NULL,              -- venue with lower price (long leg)
    leg_a_price REAL NOT NULL,            -- mark price on leg_a
    leg_b_price REAL NOT NULL,            -- mark price on leg_b
    basis_spread REAL NOT NULL,           -- absolute: leg_a_price - leg_b_price
    basis_pct REAL,                         -- (leg_a_price - leg_b_price) / leg_b_price * 100
    annualized_basis_pct REAL,           -- adjusted for funding interval
    ts INTEGER NOT NULL,
    UNIQUE(symbol, leg_a_venue, leg_b_venue, ts)
);

-- Indexes for query optimization
CREATE INDEX IF NOT EXISTS idx_funding_venue_symbol ON funding(venue, symbol, ts);
CREATE INDEX IF NOT EXISTS idx_funding_ts ON funding(ts);
CREATE INDEX IF NOT EXISTS idx_prices_venue_symbol ON prices(venue, symbol, ts);
CREATE INDEX IF NOT EXISTS idx_prices_ts ON prices(ts);
CREATE INDEX IF NOT EXISTS idx_basis_symbol ON basis(symbol, ts);
CREATE INDEX IF NOT EXISTS idx_basis_venues ON basis(leg_a_venue, leg_b_venue);
