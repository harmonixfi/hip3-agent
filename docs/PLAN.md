# Delta-Neutral Funding Arbitrage: Monitoring & Reporting System

## 1. Overview & Goals

OpenClaw/Harmonix is a delta-neutral funding arbitrage system operating on the Hyperliquid ecosystem. It holds paired positions (spot long + perp short) to collect funding payments while remaining market-neutral.

**Current state**: The system tracks positions, funding cashflows, equity snapshots, and live carry metrics in a SQLite database. Cron jobs pull data every 5 minutes (positions) and hourly (market data, cashflows). A CLI-based workflow manages everything.

**Key gap**: No trade/fill tracking. Without fills, we cannot compute average entry prices, unrealized P&L, entry/exit spreads, or closed-position performance. The system also lacks a web UI and API layer, making it dependent on SSH + CLI access.

**What we are building**:

1. **Fill ingestion pipeline** -- pull and store all trade fills from Hyperliquid (native perps, builder dex perps, spot) and Felix equities.
2. **Computation layer** -- average entry price per leg, unrealized P&L, entry/exit basis spread, cashflow-adjusted APR.
3. **REST API** (FastAPI) -- expose portfolio overview, position detail, fill history, closed-position analysis, and manual cashflow input.
4. **Web dashboard** (Next.js on Vercel) -- visual overview of the portfolio for quick daily monitoring without SSH.
5. **Secret vault** -- eliminate plaintext secrets from environment files.
6. **PERP_PERP readiness** -- schema designed now, implementation in Phase 2.

**Success criteria**: A single dashboard page shows total equity, daily/all-time APR, per-position uPnL, basis spread, and funding earned. Closed positions show realized net P&L. All data refreshes hourly via cron. The system operates unattended with encrypted secrets.

---

## 2. System Architecture

```
                         INTERNET
                            |
              +-------------+-------------+
              |                           |
        [Vercel CDN]              [Cloudflare Tunnel]
        Next.js Frontend           HTTPS termination
        (static + SSR)                    |
              |                    +------+------+
              +-------- HTTPS ---->|  VPS (Linux) |
                                   |              |
                                   | FastAPI app  |
                                   | (uvicorn)    |
                                   |              |
                                   | Cron jobs    |
                                   | (systemd     |
                                   |  timers)     |
                                   |              |
                                   | Secret Vault |
                                   | (age/sops)   |
                                   |              |
                                   | SQLite DB    |
                                   | arbit_v3.db  |
                                   +--------------+
                                         |
                      +------------------+------------------+
                      |                  |                  |
               [Hyperliquid API]  [Felix Proxy API]  [Other venues]
               - clearinghouseState  - Turnkey JWT auth   (Paradex, etc.)
               - userFillsByTime     - /v1/portfolio
               - spotMeta            - /v1/trading/orders
               - allMids
```

### Component responsibilities

| Component | Runtime | Role |
|-----------|---------|------|
| **FastAPI backend** | VPS, uvicorn behind Cloudflare Tunnel | Serves REST API, reads SQLite |
| **Cron scheduler** | VPS, systemd timers (or crontab) | Hourly data pulls, fill ingestion, metric computation |
| **Felix JWT refresher** | VPS, separate timer (~14 min) | Maintains valid Turnkey JWT for Felix API |
| **Next.js frontend** | Vercel (free tier) | Dashboard, position detail, closed analysis |
| **Secret vault** | VPS, `age` + `sops` | Encrypts wallet keys, JWTs at rest |
| **SQLite DB** | VPS, single file | All state; backed up daily |

### Network flow

- Frontend (Vercel) calls backend via Cloudflare Tunnel URL (HTTPS, no exposed ports on VPS).
- Backend reads SQLite directly (no ORM, raw SQL via `sqlite3` module -- consistent with existing codebase).
- Cron jobs write to SQLite; FastAPI reads. No concurrent write contention because cron runs are short-lived and sequential.
- Claude agent calls the same API endpoints for manual ops (deposit/withdraw input).

---

## 3. Database Schema Changes

### 3.1 New table: `pm_fills`

Stores raw trade fills from all venues. One row per fill (execution). This is the source-of-truth for entry price computation.

```sql
-- Enable WAL mode for concurrent read/write (cron writes, API reads)
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS pm_fills (
  fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  -- Identifiers
  venue TEXT NOT NULL,                -- 'hyperliquid', 'felix', etc.
  account_id TEXT NOT NULL,           -- wallet address
  -- Fill data
  tid TEXT,                           -- venue trade ID (HL: tid field)
  oid TEXT,                           -- venue order ID (HL: oid field)
  inst_id TEXT NOT NULL,              -- instrument: 'HYPE', 'xyz:GOLD', 'HYPE/USDC', etc.
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  px REAL NOT NULL,                   -- execution price
  sz REAL NOT NULL,                   -- execution size (always positive)
  fee REAL,                           -- fee amount (positive = paid, negative = rebate)
  fee_currency TEXT,                  -- e.g. 'USDC'
  ts INTEGER NOT NULL,               -- epoch ms UTC (fill timestamp)
  -- HL-specific fields (nullable for other venues)
  closed_pnl REAL,                   -- HL closedPnl field
  dir TEXT,                           -- HL dir field: 'Open Long', 'Close Short', etc.
  builder_fee REAL,                  -- builder dex fee if applicable
  -- Position mapping (set during ingestion if deterministic, or via backfill)
  position_id TEXT,                  -- FK to pm_positions
  leg_id TEXT,                       -- FK to pm_legs
  -- Raw data
  raw_json TEXT,                     -- full venue response for this fill
  meta_json TEXT,                    -- computed metadata (e.g., spot symbol resolved from @index)
  -- Dedup
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
```

**Design notes**:
- `tid` is the venue-assigned trade ID. For HL, this is globally unique. UNIQUE constraint on `(venue, account_id, tid)` prevents duplicate ingestion.
- `inst_id` uses the same namespace as `pm_legs`: plain `HYPE` for native perp, `xyz:GOLD` for builder dex perp, `HYPE/USDC` for spot.
- `position_id` and `leg_id` are set during ingestion by matching `inst_id` + `account_id` against active legs in `pm_legs`. For ambiguous cases (e.g., a coin with multiple legs across positions), the mapping is resolved by time-window heuristics or left NULL for manual assignment.

**Spot `inst_id` canonicalization**:

The canonical format for spot instruments is `SYMBOL/QUOTE` (e.g., `HYPE/USDC`, `LINK0/USDC`). Some legacy `pm_legs` rows use plain symbols (e.g., `GOOGL`, `MSFT`) from Felix equities — these predate the naming convention.

Phase 1a includes a migration step:
1. Query all `pm_legs` rows where `inst_id` does not contain `/` and the parent position's strategy is `SPOT_PERP` and leg side is `LONG`.
2. Append `/USDC` to these inst_ids (e.g., `GOOGL` → `GOOGL/USDC`).
3. The fill ingester always produces `SYMBOL/USDC` format (via `spotMeta` resolution or Felix API normalization).

This ensures fills always match legs by `inst_id`.

**Felix fill dedup**: Felix fills may not provide a `tid`. For venues without a native trade ID, the ingester generates a synthetic `tid` from a hash of `(venue, account_id, inst_id, side, px, sz, ts)`. This ensures the UNIQUE constraint on `(venue, account_id, tid)` works for all sources.

### 3.2 New table: `pm_entry_prices`

Materialized computation of average entry price per leg. Recomputed from `pm_fills` on every ingestion cycle. This is a derived table, not a source of truth.

```sql
CREATE TABLE IF NOT EXISTS pm_entry_prices (
  leg_id TEXT NOT NULL,
  position_id TEXT NOT NULL,
  -- Computed values
  avg_entry_price REAL NOT NULL,      -- VWAP of all opening fills
  total_filled_qty REAL NOT NULL,     -- sum of sz for opening fills
  total_cost REAL NOT NULL,           -- sum of (px * sz) for opening fills
  fill_count INTEGER NOT NULL,        -- number of fills used
  first_fill_ts INTEGER,              -- earliest fill timestamp
  last_fill_ts INTEGER,               -- latest fill timestamp
  -- Metadata
  computed_at_ms INTEGER NOT NULL,    -- when this was last recomputed
  method TEXT NOT NULL DEFAULT 'VWAP', -- computation method
  meta_json TEXT,                     -- e.g., excluded fill IDs, notes
  PRIMARY KEY (leg_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_entry_prices_position ON pm_entry_prices(position_id);
```

**Computation logic** (VWAP for opening fills):
```
avg_entry_price = SUM(px * sz) / SUM(sz)
  WHERE fill is an "opening" fill:
    - LONG leg: side = 'BUY'
    - SHORT leg: side = 'SELL'
```

For legs that have been partially closed and re-opened, we use FIFO cost basis: closing fills reduce the position; remaining fills define the current avg entry. This matters for rebalanced positions.

### 3.3 New table: `pm_spreads`

Tracks entry and exit basis spread per sub-pair (spot leg + perp leg). A position like HYPE with 1 spot + 2 perp legs produces 2 sub-pairs.

```sql
CREATE TABLE IF NOT EXISTS pm_spreads (
  spread_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  position_id TEXT NOT NULL,
  long_leg_id TEXT NOT NULL,           -- long leg (spot for SPOT_PERP, long perp for PERP_PERP)
  short_leg_id TEXT NOT NULL,          -- short leg (perp for SPOT_PERP, short perp for PERP_PERP)
  -- Entry spread (from fills)
  entry_spread REAL,                   -- long_avg_entry / short_avg_entry - 1
  long_avg_entry REAL,
  short_avg_entry REAL,
  -- Exit spread (from live prices)
  exit_spread REAL,                    -- spot_bid / perp_ask - 1
  long_exit_price REAL,                -- current best bid for spot
  short_exit_price REAL,               -- current best ask for perp
  -- Spread P&L
  spread_pnl_bps REAL,                -- (exit_spread - entry_spread) * 10000
  -- Metadata
  computed_at_ms INTEGER NOT NULL,
  meta_json TEXT,
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
  FOREIGN KEY (long_leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (short_leg_id) REFERENCES pm_legs(leg_id),
  UNIQUE (position_id, long_leg_id, short_leg_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_spreads_position ON pm_spreads(position_id);
```

### 3.4 New table: `pm_portfolio_snapshots`

Hourly snapshots of portfolio-level metrics for historical tracking and daily-change computation.

```sql
CREATE TABLE IF NOT EXISTS pm_portfolio_snapshots (
  snapshot_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,                 -- epoch ms UTC
  -- Equity
  total_equity_usd REAL NOT NULL,      -- sum across all wallets/venues
  equity_by_account_json TEXT,         -- {"main": 12345.67, "alt": 8901.23}
  -- P&L
  total_unrealized_pnl REAL,
  total_funding_today REAL,            -- funding earned in current UTC day
  total_funding_alltime REAL,          -- funding earned since tracking_start_date
  total_fees_alltime REAL,             -- fees paid since tracking_start_date
  -- APR
  daily_change_usd REAL,               -- equity delta from 24h ago
  cashflow_adjusted_change REAL,       -- daily_change - net_deposits
  apr_daily REAL,                       -- annualized from cashflow-adjusted daily change
  -- Config
  tracking_start_date TEXT,            -- ISO date, configurable
  meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_ts ON pm_portfolio_snapshots(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_hourly
  ON pm_portfolio_snapshots(CAST(ts / 3600000 AS INTEGER));
```

### 3.5 Alterations to existing tables

**`pm_legs`** -- no schema change needed. The existing `entry_price`, `current_price`, `unrealized_pnl` columns will now be populated from the computation layer rather than left NULL.

**Status asymmetry note**: `pm_positions.status` supports `OPEN|PAUSED|EXITING|CLOSED`, but `pm_legs.status` only supports `OPEN|CLOSED`. When a position is PAUSED or EXITING, its legs remain `OPEN`. The fill ingester and computation layer must filter by **position** status (not leg status) to determine active positions.

**`pm_cashflows`** -- add `MANUAL_DEPOSIT` and `MANUAL_WITHDRAW` to the cf_type CHECK constraint to distinguish agent-submitted cashflows:

```sql
-- Migration: expand cf_type enum
-- SQLite doesn't support ALTER CHECK, so we recreate or use a permissive approach.
-- Practical approach: the existing CHECK already includes 'DEPOSIT' and 'WITHDRAW'.
-- We will use those existing types with a meta_json flag {"source": "manual"}.
-- No schema migration needed.
```

### 3.6 PERP_PERP readiness

The schema above already supports PERP_PERP positions:
- `pm_fills` stores fills for any `inst_id` (both spot and perp).
- `pm_entry_prices` is per-leg, agnostic to instrument type.
- `pm_spreads` has `long_leg_id` / `short_leg_id` columns -- already named generically so they work for both SPOT_PERP and PERP_PERP without any renaming. We use `meta_json` to indicate leg type if needed.

**PERP_PERP uPnL formulas** (Phase 2):
- Long perp exit: `(current_bid - avg_entry) * size`
- Short perp exit: `-(current_ask - avg_entry) * size`
- Both legs accrue funding -- net funding = `long_funding + short_funding` (short funding is typically positive, long funding negative).

---

## 4. Backend API Design

### 4.1 Project structure

```
api/
  __init__.py
  main.py                  # FastAPI app, CORS, lifespan
  config.py                # Settings (DB path, vault key path, etc.)
  deps.py                  # Dependency injection (DB connection, vault)
  routers/
    portfolio.py           # /api/portfolio/*
    positions.py           # /api/positions/*
    cashflows.py           # /api/cashflows/*
    health.py              # /api/health
  services/
    upnl.py                # Unrealized P&L calculator
    spreads.py             # Entry/exit spread calculator
    apr.py                 # APR calculator
    entry_price.py         # Avg entry price from fills (VWAP/FIFO)
    portfolio.py           # Portfolio aggregation
  models/
    schemas.py             # Pydantic response models
```

### 4.1.1 Authentication

Single-user system with shared secret authentication:
- API key stored in the vault (`vault/secrets.enc.json` → `api_key`).
- FastAPI middleware checks `X-API-Key` header on all `/api/*` routes.
- Returns `401 Unauthorized` if header is missing or invalid.
- On Vercel, the API key is stored as a **server-side** environment variable (NOT `NEXT_PUBLIC_*`) to prevent client-side exposure. All API calls are made from Server Components.

### 4.2 Endpoint specifications

#### `GET /api/portfolio/overview`

Returns aggregate portfolio metrics.

**Response**:
```json
{
  "total_equity_usd": 25000.50,
  "equity_by_account": {
    "main": {"address": "0xabc...", "equity_usd": 10000.00, "venue": "hyperliquid"},
    "alt": {"address": "0xdef...", "equity_usd": 15000.50, "venue": "hyperliquid"}
  },
  "daily_change_usd": 42.30,
  "daily_change_pct": 0.17,
  "cashflow_adjusted_apr": 18.5,
  "funding_today_usd": 12.40,
  "funding_alltime_usd": 850.00,
  "fees_alltime_usd": -120.00,
  "net_pnl_alltime_usd": 730.00,
  "tracking_start_date": "2026-01-15",
  "open_positions_count": 4,
  "total_unrealized_pnl": -15.20,
  "as_of": "2026-03-29T10:00:00Z"
}
```

**Query params**: `?tracking_start=2026-01-15` (optional, overrides default).

**Computation**:
```
daily_change = current_equity - equity_24h_ago
net_deposits_24h = SUM(DEPOSIT amounts) - SUM(WITHDRAW amounts) in last 24h
cashflow_adjusted_change = daily_change - net_deposits_24h
apr_daily = (cashflow_adjusted_change / equity_24h_ago) * 365
```

#### `GET /api/positions`

Returns all positions with computed metrics.

**Query params**: `?status=OPEN` (default OPEN), `?status=ALL`.

**Response** (array):
```json
[
  {
    "position_id": "pos_hyna_HYPE",
    "base": "HYPE",
    "strategy": "SPOT_PERP",
    "status": "OPEN",
    "amount_usd": 5071.13,
    "unrealized_pnl": -8.50,
    "unrealized_pnl_pct": -0.17,
    "funding_earned": 45.20,
    "fees_paid": -12.30,
    "net_carry": 32.90,
    "carry_apr": 24.5,
    "sub_pairs": [
      {
        "spot_leg_id": "pos_hyna_HYPE_SPOT",
        "perp_leg_id": "pos_hyna_HYPE_PERP_HYNA",
        "entry_spread_bps": 15.2,
        "exit_spread_bps": 12.8,
        "spread_pnl_bps": -2.4
      },
      {
        "spot_leg_id": "pos_hyna_HYPE_SPOT",
        "perp_leg_id": "pos_hyna_HYPE_PERP_NATIVE",
        "entry_spread_bps": 18.0,
        "exit_spread_bps": 14.5,
        "spread_pnl_bps": -3.5
      }
    ],
    "legs": [
      {
        "leg_id": "pos_hyna_HYPE_SPOT",
        "venue": "hyperliquid",
        "inst_id": "HYPE/USDC",
        "side": "LONG",
        "size": 126.98,
        "avg_entry_price": 19.85,
        "current_price": 19.80,
        "unrealized_pnl": -6.35
      }
    ],
    "opened_at": "2026-03-10T14:00:00Z"
  }
]
```

#### `GET /api/positions/{position_id}`

Returns detailed position with full leg breakdown and fill history summary.

**Response**: Same as list item but with additional fields:
- `fills_summary`: count, first/last fill date per leg.
- `cashflows`: array of all cashflow events for this position.
- `daily_funding_series`: last 7 days of daily funding amounts (for sparkline).

#### `GET /api/positions/{position_id}/fills`

Returns trade fills for a position.

**Query params**: `?leg_id=...` (optional filter), `?limit=100`, `?offset=0`.

**Response**:
```json
{
  "position_id": "pos_hyna_HYPE",
  "fills": [
    {
      "fill_id": 123,
      "leg_id": "pos_hyna_HYPE_SPOT",
      "inst_id": "HYPE/USDC",
      "side": "BUY",
      "px": 19.85,
      "sz": 50.0,
      "fee": 0.25,
      "ts": 1741622400000,
      "dir": "Open Long",
      "tid": "0x..."
    }
  ],
  "total": 5,
  "limit": 100,
  "offset": 0
}
```

#### `GET /api/positions/closed`

Returns closed position analysis with realized P&L breakdown.

**Response**:
```json
[
  {
    "position_id": "pos_xyz_GOOGL",
    "base": "GOOGL",
    "status": "CLOSED",
    "opened_at": "2026-02-01T10:00:00Z",
    "closed_at": "2026-03-01T15:00:00Z",
    "duration_days": 28,
    "amount_usd": 1862.00,
    "realized_spread_pnl": -5.20,
    "total_funding_earned": 42.80,
    "total_fees_paid": -8.50,
    "net_pnl": 29.10,
    "net_apr": 20.4,
    "entry_spread_bps": 12.0,
    "exit_spread_bps": 9.2
  }
]
```

**Closed position P&L formulas**:
```
realized_spread_pnl = SUM(closing_fill_proceeds) - SUM(opening_fill_cost)
                    = (spot_sell_value - spot_buy_value) + (perp_close_value - perp_open_value)
total_funding_earned = SUM(FUNDING cashflows for this position)
total_fees_paid = SUM(FEE cashflows for this position)  # negative
net_pnl = realized_spread_pnl + total_funding_earned + total_fees_paid
net_apr = (net_pnl / amount_usd) / duration_days * 365
```

#### `POST /api/cashflows/manual`

Allows the Claude agent (or human) to record deposits and withdrawals.

**Request**:
```json
{
  "account_id": "0xabc...",
  "venue": "hyperliquid",
  "cf_type": "DEPOSIT",
  "amount": 5000.00,
  "currency": "USDC",
  "ts": 1741622400000,
  "description": "Deposit from Arbitrum bridge"
}
```

**Response**: `201 Created` with the `cashflow_id`.

**Validation**:
- `cf_type` must be `DEPOSIT` or `WITHDRAW`.
- `amount` must be positive (sign is determined by `cf_type`: DEPOSIT = +, WITHDRAW = -).
- `ts` defaults to now if omitted.

#### `GET /api/health`

**Response**:
```json
{
  "status": "ok",
  "db_size_mb": 45.2,
  "last_fill_ingestion": "2026-03-29T09:00:00Z",
  "last_price_pull": "2026-03-29T09:20:00Z",
  "last_position_pull": "2026-03-29T09:05:00Z",
  "felix_jwt_expires_at": "2026-03-29T09:14:00Z",
  "open_positions": 4,
  "uptime_seconds": 86400
}
```

### 4.3 Computation layer detail

#### uPnL calculator (`services/upnl.py`)

Per-leg unrealized P&L, using exit-side pricing:

```python
def compute_leg_upnl(side: str, avg_entry: float, exit_price: float, size: float) -> float:
    """
    side: 'LONG' or 'SHORT'
    exit_price: bid for LONG exit, ask for SHORT exit
    """
    if side == 'LONG':
        return (exit_price - avg_entry) * size      # spot long: sell at bid
    else:
        return -(exit_price - avg_entry) * size      # perp short: buy at ask
```

**Price selection**:
- LONG leg (spot): use `bid` from `prices_v3` for the spot inst_id.
- SHORT leg (perp): use `ask` from `prices_v3` for the perp inst_id.
- If bid/ask unavailable, fall back to `mid` or `last` with a quality flag.

Position-level uPnL = `SUM(leg_upnl for all legs)`.

#### Spread calculator (`services/spreads.py`)

For each sub-pair (spot_leg, perp_leg):

```python
def entry_spread(spot_avg_entry: float, perp_avg_entry: float) -> float:
    """Entry basis spread (positive = spot premium)."""
    return spot_avg_entry / perp_avg_entry - 1.0

def exit_spread(spot_bid: float, perp_ask: float) -> float:
    """Exit basis spread (what you'd realize if you closed now)."""
    return spot_bid / perp_ask - 1.0

def spread_pnl_bps(entry: float, exit: float) -> float:
    """
    Spread P&L in basis points.
    Positive = spread moved in your favor (you entered wide, can exit narrow).
    For spot-long/perp-short: you WANT exit_spread > entry_spread if you
    entered at a discount, but typically you entered at a premium and want
    the premium to persist or shrink less than funding earned.
    """
    return (exit - entry) * 10000
```

**Sub-pair assignment for split-leg positions** (e.g., HYPE = 1 spot + 2 perp legs):

Each perp leg forms a sub-pair with the spot leg. The spot leg's avg entry price is shared, but the perp leg's avg entry price is computed independently. Spread is calculated per sub-pair. The position-level spread P&L is the size-weighted average of sub-pair spread P&Ls.

#### APR calculator (`services/apr.py`)

```python
def cashflow_adjusted_apr(
    current_equity: float,
    prior_equity: float,
    net_deposits: float,         # deposits - withdrawals in period
    period_days: float
) -> float:
    """
    Cashflow-adjusted annualized return.
    Removes deposit/withdraw impact from equity change.
    """
    if prior_equity <= 0 or period_days <= 0:
        return 0.0
    organic_change = (current_equity - prior_equity) - net_deposits
    period_return = organic_change / prior_equity
    avg_daily_return = period_return / period_days
    return avg_daily_return * 365
```

For per-position carry APR, the existing `tracking/position_manager/carry.py` logic is reused but enhanced with fill-derived entry prices.

---

## 5. Data Pipeline (Cron Jobs)

### 5.1 Hourly pipeline: `cron_data_pipeline.py`

Runs every hour at minute :00. Orchestrates the full data refresh cycle.

```
:00  [1] Pull fills      -- userFillsByTime for each account
     [2] Pull prices     -- allMids + orderbook top for active instruments
     [3] Pull equity     -- clearinghouseState for each account
     [4] Compute metrics -- avg entry, uPnL, spreads, portfolio snapshot
```

**Step 1: Pull fills** (`pipeline/fill_ingester.py`)

For each wallet (main, alt):
1. Load last ingested fill timestamp from `pm_fills` for this account.
2. Call HL `userFillsByTime` with `startTime = last_ts + 1` (or 0 for initial backfill).
3. For each fill:
   - Resolve `coin` to `inst_id`:
     - `@107` format: call `spotMeta`, lookup `universe[107].tokens` to get symbol, form `SYMBOL/USDC`.
     - `xyz:GOLD` format: use as-is.
     - Plain `HYPE` format: use as-is (native perp).
   - Map to `position_id` / `leg_id` by matching `(inst_id, account_id)` against `pm_legs` WHERE position status != 'CLOSED' (i.e., includes OPEN, PAUSED, and EXITING positions). A paused or exiting position still holds live fills that must be recorded.
   - Insert into `pm_fills` with UNIQUE constraint handling (skip duplicates).
4. Log: `{N} new fills ingested for account {account_id}`.

**Spot symbol resolution cache**: Call `spotMeta` once per pipeline run, build a dict `{index: symbol}`. Cache in memory for the run duration.

```python
def resolve_spot_coin(coin: str, spot_meta_cache: dict) -> str:
    """
    '@107' -> 'HYPE/USDC' (via spotMeta lookup)
    'xyz:GOLD' -> 'xyz:GOLD' (builder dex perp, pass through)
    'HYPE' -> 'HYPE' (native perp, pass through)
    """
    if coin.startswith('@'):
        index = int(coin[1:])
        token_name = spot_meta_cache.get(index)
        if token_name:
            return f"{token_name}/USDC"
        raise ValueError(f"Unknown spot index: {coin}")
    return coin
```

**Step 2: Pull prices** -- already implemented in `pull_hyperliquid_market.py`. No change needed; existing cron job handles this.

**Step 3: Pull equity** -- already implemented in `pull_positions_v3.py` (every 5 min). The hourly pipeline reads the latest snapshot from `pm_account_snapshots`.

**Step 4: Compute metrics** (`pipeline/metric_computer.py`)

1. For each OPEN leg with new fills since last computation:
   - Recompute `pm_entry_prices` from all fills for that leg.
   - Update `pm_legs.entry_price` and `pm_legs.unrealized_pnl`.
2. For each OPEN position:
   - Compute sub-pair spreads, upsert into `pm_spreads`.
3. Insert a `pm_portfolio_snapshots` row with aggregate metrics.

### 5.2 Felix JWT auto-refresh: `cron_felix_jwt.py`

Runs every 14 minutes via a separate systemd timer.

```
Flow:
1. Load encrypted wallet private key from vault.
2. Derive secp256k1 signing key.
3. Call stamp_login on Felix proxy to get initial JWT (if no valid session).
4. If existing session: use P-256 session keypair to refresh JWT.
5. Store new JWT + expiry in vault (encrypted).
6. Log: "Felix JWT refreshed, expires at {expiry}".
```

**Session state file** (encrypted): `vault/felix_session.age`
```json
{
  "jwt": "eyJ...",
  "expires_at": 1741623300,
  "session_key_p256_pem": "-----BEGIN EC PRIVATE KEY-----\n...",
  "refresh_token": "..."
}
```

### 5.3 Backfill job: `scripts/backfill_fills.py`

One-time script to backfill fills for the 7 already-closed positions and all open positions.

```
Usage:
  python scripts/backfill_fills.py --all          # backfill all positions
  python scripts/backfill_fills.py --position pos_xyz_GOOGL  # specific position
  python scripts/backfill_fills.py --since 2026-01-01        # from date
```

Uses the same fill ingestion logic but with `startTime = 0` (or a specified date). After ingestion, triggers metric recomputation for affected positions.

### 5.4 Updated crontab

```cron
# --- Existing jobs (unchanged) ---
*/5 * * * *  ... pull_positions_v3.py ...
20 * * * *   ... pull_hyperliquid_v3.py ...
1-56/5 * * * * ... pm_alerts.py ...
2-57/5 * * * * ... send_pm_alerts.sh ...
4-59/15 * * * * ... send_pm_health.sh ...
37 * * * * ... pm_cashflows.py ingest ...
45 0 * * * ... pm_cashflows.py report ...
5 9 * * *  ... report_daily_funding_with_portfolio.py ...
10 9 * * * ... equity_daily.py snapshot ...
50 2 * * * ... db_v3_backup.py ...

# --- New jobs ---
# Hourly fill ingestion + metric computation (:05, after position pull settles)
5 * * * *  cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py >> logs/pipeline_hourly.log 2>&1

# Felix JWT refresh (every 14 minutes)
*/14 * * * * cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1
```

---

## 6. Frontend (Next.js)

### 6.1 Tech stack

- **Framework**: Next.js 14+ (App Router)
- **Hosting**: Vercel (free tier, auto-deploy from GitHub)
- **Styling**: Tailwind CSS (utility-first, fast to build)
- **Data fetching**: Server components + `fetch()` to backend API (no client-side state library needed initially)
- **Auth**: Simple shared secret in header (`X-API-Key`) -- sufficient for single-user system

### 6.2 Pages

#### Dashboard (`/`)

The primary page. Shows at-a-glance portfolio health.

| Section | Data source | Display |
|---------|-------------|---------|
| **Equity card** | `GET /api/portfolio/overview` | Total equity, 24h change (USD + %), APR |
| **Wallet breakdown** | same | Table: wallet label, address (truncated), equity |
| **Funding summary** | same | Today's funding, all-time funding, all-time fees, net P&L |
| **Open positions table** | `GET /api/positions?status=OPEN` | Table: base, amount, uPnL, funding earned, carry APR, exit spread, signal |
| **System status** | `GET /api/health` | Last data pull times, Felix JWT status, DB size |

#### Position Detail (`/positions/[id]`)

Drill-down for a single position.

| Section | Data |
|---------|------|
| **Header** | Position ID, base, strategy, status, opened date, amount |
| **Legs table** | Per-leg: venue, inst_id, side, size, avg entry, current price, uPnL |
| **Sub-pair spreads** | Per sub-pair: entry spread, exit spread, spread P&L (bps) |
| **Funding chart** | Last 14 days daily funding (simple bar chart, can use `<table>` bars initially) |
| **Cashflows** | Table of all cashflow events (funding, fees) |
| **Fills** | Table of all trade fills |

#### Closed Positions (`/closed`)

Analysis of completed trades.

| Column | Description |
|--------|-------------|
| Base | Token symbol |
| Duration | Days open |
| Amount | USD notional |
| Spread P&L | Entry vs exit spread realized |
| Funding | Total funding earned |
| Fees | Total fees paid |
| Net P&L | spread + funding + fees |
| Net APR | Annualized net return |

#### Settings (`/settings`)

- Tracking start date configuration
- Manual deposit/withdraw form (calls `POST /api/cashflows/manual`)
- System info (DB path, vault status, cron status)

### 6.3 Component structure

```
app/
  layout.tsx              # Shell: nav sidebar, header
  page.tsx                # Dashboard
  positions/
    page.tsx              # Positions list (redirect from / if preferred)
    [id]/
      page.tsx            # Position detail
  closed/
    page.tsx              # Closed position analysis
  settings/
    page.tsx              # Settings
components/
  EquityCard.tsx
  PositionsTable.tsx
  LegDetail.tsx
  SpreadDisplay.tsx
  CashflowTable.tsx
  FillsTable.tsx
  HealthStatus.tsx
  ManualCashflowForm.tsx
lib/
  api.ts                  # Backend API client (typed fetch wrapper)
  types.ts                # TypeScript interfaces matching API response shapes
  format.ts               # Number formatting (USD, %, bps)
```

### 6.4 Design principles

- **Data density over aesthetics**: This is a monitoring tool. Tables with good alignment and color-coding (green/red for P&L) matter more than animations.
- **No fancy charts in v1**: Use colored text and simple `<div>` bar charts. Real charting (recharts/d3) can come later.
- **Server-side rendering**: All pages are server components fetching from the API. No client-side polling in v1 (manual refresh or page reload).
- **Mobile-responsive**: Tailwind responsive classes. Dashboard should be readable on phone (stacked cards).

---

## 7. Secret Vault

### 7.1 Recommended approach: `age` + `sops`

**Why `age` over Fernet/KMS**:
- Single static binary, no Python dependency, works on any Linux VPS.
- `sops` integrates with `age` for structured secret files (JSON/YAML).
- Simple key management: one `age` identity file, protected by filesystem permissions.
- No cloud dependency (unlike AWS KMS or GCP KMS).

### 7.2 What gets encrypted

| Secret | Current storage | Vault path |
|--------|----------------|------------|
| HL wallet private key (main) | `.arbit_env` env var | `vault/secrets.enc.json` → `hl_main_private_key` |
| HL wallet private key (alt) | `.arbit_env` env var | `vault/secrets.enc.json` → `hl_alt_private_key` |
| Felix Turnkey API key | `.arbit_env` env var | `vault/secrets.enc.json` → `felix_turnkey_api_key` |
| Felix session JWT + P-256 key | N/A (new) | `vault/felix_session.enc.json` |
| Discord webhook URL | `.arbit_env` env var | `vault/secrets.enc.json` → `discord_webhook_url` |
| API key (frontend auth) | N/A (new) | `vault/secrets.enc.json` → `api_key` |

### 7.3 Integration

```
vault/
  age-identity.txt         # age private key (chmod 600, NOT in git)
  secrets.enc.json         # sops-encrypted secrets file (in git)
  felix_session.enc.json   # sops-encrypted Felix session (in git)
  .gitignore               # ignores age-identity.txt
```

**Python integration** (`api/vault.py`):

```python
import subprocess
import json

def decrypt_secrets(vault_path: str = "vault/secrets.enc.json") -> dict:
    """Decrypt secrets file using sops + age."""
    result = subprocess.run(
        ["sops", "--decrypt", vault_path],
        capture_output=True, text=True, check=True
    )
    return json.loads(result.stdout)

def get_secret(key: str) -> str:
    """Get a single secret by key."""
    secrets = decrypt_secrets()
    return secrets[key]
```

**Migration from `.arbit_env`**:
1. Create `age` identity: `age-keygen -o vault/age-identity.txt`
2. Create `.sops.yaml` config pointing to the age public key.
3. Populate `vault/secrets.enc.json` with current env var values.
4. Encrypt: `sops --encrypt --in-place vault/secrets.enc.json`
5. Update Python code to call `get_secret()` instead of `os.environ[]`.
6. Keep `.arbit_env` as a fallback during migration (vault takes precedence).

---

## 8. Phase Breakdown

### Phase 1a: Backend foundation (DB schema, fill ingestion, vault)

**Estimated effort**: 3-4 days

**Deliverables**:
1. SQL migration script: create `pm_fills`, `pm_entry_prices`, `pm_spreads`, `pm_portfolio_snapshots` tables.
2. Fill ingester module (`tracking/pipeline/fill_ingester.py`):
   - HL `userFillsByTime` integration with `spotMeta` resolution.
   - Dedup logic (UNIQUE on venue+account+tid).
   - Position/leg mapping.
3. Backfill script for all existing positions.
4. Vault setup (`age` + `sops` installation, secret migration).
5. Unit tests for fill ingestion and spot symbol resolution.

**Verification**:
- Run backfill, verify fills appear in DB with correct inst_id and position mapping.
- Verify dedup: running backfill twice produces no duplicates.
- Verify vault: secrets decrypt correctly, env var fallback works.

### Phase 1b: Computation layer (avg entry, uPnL, spreads)

**Estimated effort**: 2-3 days

**Deliverables**:
1. Entry price computer (`tracking/pipeline/entry_price.py`) -- VWAP from opening fills.
2. uPnL calculator (`tracking/pipeline/upnl.py`) -- per-leg, uses bid/ask from prices_v3.
3. Spread calculator (`tracking/pipeline/spreads.py`) -- entry/exit per sub-pair.
4. Portfolio aggregator (`tracking/pipeline/portfolio.py`) -- equity, APR, funding totals.
5. Metric computation orchestrator (called by hourly cron).
6. Update `pm_legs.entry_price`, `pm_legs.unrealized_pnl` on each computation.

**Verification**:
- Manual check: compute avg entry for pos_xyz_GOLD by hand from fills, compare to system output.
- Verify uPnL sign: spot long with price below entry should show negative uPnL.
- Verify spread: entry spread for a position where spot was bought at premium should be positive.

### Phase 1c: API endpoints

**Estimated effort**: 2-3 days

**Deliverables**:
1. FastAPI app skeleton with CORS, API key auth middleware.
2. All endpoints from Section 4.2 implemented.
3. Pydantic response models.
4. Manual cashflow endpoint with validation.
5. Health endpoint reading cron timestamps from DB.

**Verification**:
- `curl` all endpoints, verify response shapes match spec.
- Post a manual deposit, verify it appears in cashflows.
- Verify API key auth rejects unauthorized requests.

### Phase 1d: Frontend basic

**Estimated effort**: 3-4 days

**Deliverables**:
1. Next.js project scaffold (App Router, Tailwind).
2. Dashboard page with equity card, positions table, funding summary.
3. Position detail page with legs, spreads, cashflows, fills.
4. Closed positions page with P&L breakdown.
5. Settings page with manual cashflow form.
6. Deploy to Vercel, configure environment variable for API URL.

**Verification**:
- Dashboard loads and shows correct equity, positions.
- Click into a position, verify leg details and fills display.
- Submit manual deposit via settings, verify it appears in portfolio overview.

### Phase 1e: Cron + Cloudflare Tunnel deployment

**Estimated effort**: 1-2 days

**Deliverables**:
1. Cloudflare Tunnel setup (`cloudflared`) on VPS, pointing to uvicorn.
2. Systemd service for FastAPI (`harmonix-api.service`).
3. Systemd timer for hourly pipeline (`harmonix-pipeline.timer`).
4. Update existing crontab with new jobs.
5. Vercel environment variable pointing to tunnel URL.
6. End-to-end test: Vercel frontend loads data from VPS backend via tunnel.

**Verification**:
- Frontend on Vercel loads portfolio data via HTTPS tunnel.
- Hourly cron fires, fills appear in DB, metrics update.
- `GET /api/health` shows all systems green.

### Phase 2: PERP_PERP support

**Estimated effort**: 2-3 days

**Deliverables**:
1. Fill ingestion handles PERP_PERP legs (both legs have funding; both have fills).
2. uPnL for PERP_PERP: long perp uses bid for exit, short perp uses ask.
3. Spread calculator for PERP_PERP: `long_perp_bid / short_perp_ask - 1`.
4. Frontend handles PERP_PERP display (both legs show funding).
5. Add sample PERP_PERP position to positions.json and verify end-to-end.

### Phase 3: Felix equities headless auth

**Estimated effort**: 3-4 days

**Deliverables**:
1. Turnkey `stamp_login` implementation:
   - Load wallet private key (secp256k1) from vault.
   - Sign stamp_login challenge.
   - Exchange for JWT (ES256, 900s TTL).
2. P-256 session keypair generation and JWT refresh logic.
3. Felix fill ingestion from `/v1/trading/orders`.
4. Felix equity from `/v1/portfolio/{address}`.
5. 14-minute refresh cron job.
6. Integration tests against Felix proxy.

---

## 9. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| **HL `userFillsByTime` rate limits** | Fill ingestion blocked | Medium | Implement exponential backoff. Cache `startTime` watermark so we only request new fills. Batch requests per 24h windows for backfill. |
| **Spot `@index` mapping changes** | Wrong symbol in `pm_fills` | Low | Call `spotMeta` fresh on every pipeline run (not cached across runs). Store raw `coin` field in `raw_json` for forensic recovery. |
| **SQLite write contention** | Cron job and API conflict | Low | Cron jobs are short (<30s). Enable WAL mode (`PRAGMA journal_mode=WAL`) for concurrent read/write. FastAPI is read-only except for manual cashflow endpoint. |
| **Felix JWT auth complexity** | Headless auth fails silently | Medium | Phase 3 (deferred). Build with graceful degradation: system works without Felix data, logs warning. Implement JWT expiry monitoring in health endpoint. |
| **Split-leg position fill mapping** | Fills assigned to wrong leg | Medium | For HYPE (1 spot + 2 perp legs on different builder dexes), the `inst_id` namespace (`hyna:HYPE` vs `HYPE`) is sufficient to disambiguate. For same-venue split legs (unlikely), use fill timestamp proximity to leg creation date. |
| **Backfill: HL fill history limits** | Can't retrieve old fills | Medium | HL `userFillsByTime` returns all fills for an address (no hard limit documented). Start with `startTime = 0`. If API returns partial data, paginate using `endTime` windows. Worst case: manually enter entry prices for old closed positions via `pm_entry_prices` with `method = 'MANUAL'`. |
| **Cloudflare Tunnel downtime** | Frontend can't reach backend | Low | Tunnel auto-reconnects. Systemd restart policy on `cloudflared` service. Frontend shows "backend unavailable" gracefully with last-known data. |
| **Secret vault key loss** | Can't decrypt secrets | High impact, Low likelihood | Backup `age-identity.txt` to a separate secure location (e.g., encrypted USB or password manager). Document recovery procedure. |
| **VPS disk full (SQLite growth)** | DB writes fail | Low | Daily backup job already prunes old backups. Add monitoring: health endpoint reports DB size. `pm_fills` growth is bounded (~50 fills/day max at current trading volume). |
| **PERP_PERP dual funding accounting** | Incorrect carry calculation | Medium | Design schema now (Phase 2). Both legs produce `FUNDING` cashflows. Net carry = `SUM(all funding cashflows for position)`. Existing `pm_cashflows` schema already handles this since `leg_id` distinguishes which leg generated the funding. |
