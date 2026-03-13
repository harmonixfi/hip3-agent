# Architecture

## Components

### 1) Ingestion (per-exchange connectors)
For each venue we need to pull:
- Instruments metadata (contract specs, funding interval, multiplier)
- Funding rate (current + upcoming, if available)
- Mark price / index price / last price
- Orderbook top-of-book / mid (optional depth)
- Account endpoints (balances, positions, margin) — authenticated

### 2) Normalization
Normalize into common schemas:
- `instrument` (symbol, venue_symbol, type spot/perp, contract_size, quote, base)
- `funding` (ts, exchange, symbol, funding_rate, interval, next_funding_ts)
- `price` (ts, exchange, symbol, mark, index, last, bid, ask)
- `basis` (ts, symbol, leg_a, leg_b, spread, annualized, fees_est)
- `account_snapshot` (ts, exchange, equity, free_margin, margin_used)
- `position` (ts, exchange, symbol, side, size, entry, mark, uPnL, liq_price)

#### Symbol Normalization Standard

**Canonical Symbol Format:**
- Base asset ticker only (uppercase, 2-6 characters)
- Examples: BTC, ETH, SOL, BERA, DOGE, 1INCH
- No suffixes, no special characters

**Venue-Specific Parsing:**
- **OKX**: `BTC-USDT-SWAP` → `BTC`
- **Paradex**: `BTC-USD-PERP` → `BTC`
- **Ethereal**: `BTCUSD` → `BTC`
- **Lighter**: `BTC` → `BTC` (already canonical)
- **Hyperliquid**: `BTC` → `BTC` (already canonical)

**Database Schema:**
- `symbol` column: Canonical symbol (e.g., `BTC`)
- `inst_id` column: Venue-specific identifier (e.g., `BTC-USDT-SWAP` for OKX)

**Implementation:**
- Module: `tracking/symbols.py` provides `normalize_symbol(venue, raw_symbol)` function
- All pull scripts use this function when inserting into `symbol` columns
- The `basis.py` analytics module uses the shared normalization utility
- Migration script: `scripts/normalize_symbols_db.py` backfills existing data

### 3) Storage
Phase 1: SQLite (simple, queryable) + CSV exports.
- `tracking/db/arbit.db`
- Daily partitions optional later.

### 4) Analytics engine
- Funding carry: receive - pay (APR)
- Basis:
  - spot↔perp: (perp_mark - spot_mid) / spot_mid
  - perp↔perp: (perpA_mark - perpB_mark) / reference
- Net EV: funding carry ± expected basis mean reversion - fees - slippage
- Stability: rolling windows (3D/7D/14D), percent-positive, vol, drawdowns

### 5) Risk engine
- Per-exchange leverage target 2–3x
- Margin buffer tracking (30–50% excess margin)
- Liquidation-distance alerts (e.g., liq < X% away)

### 6) Reporting/alerts
- CLI report + optional cron to post top 3 opportunities
- Alert on: funding flip, basis blowout, margin stress
