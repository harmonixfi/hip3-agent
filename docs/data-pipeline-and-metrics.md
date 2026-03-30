# Data Pipeline & Metrics: Monitoring Dashboard

## Overview

```
[Data Sources]          [Pull Scripts]           [Computation]         [API]              [Dashboard UI]
HL API: fills      -->  pull_positions_v3.py  -> pipeline_hourly.py -> GET /portfolio  -> Equity, APR
HL API: prices     -->  pull_position_prices  -> entry_price.py     -> GET /positions  -> uPnL, Spreads
HL API: positions  -->  pull_hyperliquid_v3   -> upnl.py            -> GET /closed     -> Realized P&L
HL API: funding    -->  pm_cashflows.py       -> spreads.py         -> GET /health     -> System status
HL API: spotMeta   -->  backfill_fills.py     -> portfolio.py
```

---

## 1. Data Pull Scripts

### `scripts/pull_positions_v3.py`
- **Schedule**: Every 5 minutes
- **Input**: HL API `clearinghouseState` (per dex: native, xyz, hyna) + `spotClearinghouseState` + `webData2`
- **Output tables**:
  - `pm_account_snapshots` — total equity per wallet (perp margins + spot token values)
  - `pm_leg_snapshots` — current size, price, uPnL per position leg
- **Used for**: Total Equity, Wallet Breakdown, position sizes

### `scripts/pull_position_prices.py`
- **Schedule**: Every 5 minutes (offset +2 min)
- **Input**: HL API `l2Book` (spot via @index, native perps) + `allMids` (builder dex perps)
- **Output table**: `prices_v3` — bid, ask, mid per instrument
- **Instruments fetched**: Only those with active position legs (~11)
  - Spot: `HYPE/USDC`, `XAUT0/USDC`, `LINK0/USDC`, `UFART/USDC` (via L2Book @index → bid/ask)
  - Builder dex: `xyz:GOLD`, `hyna:HYPE`, `hyna:FARTCOIN`, `hyna:LINK` (via allMids → mid only)
  - Native perp: `HYPE`, `FARTCOIN`, `LINK` (via L2Book → bid/ask)
- **Used for**: uPnL computation, Exit Spread computation

### `scripts/pull_hyperliquid_v3.py`
- **Schedule**: Hourly at :20
- **Input**: HL API `meta` + `allMids` + `metaAndAssetCtxs` + `spotMeta`
- **Output tables**:
  - `instruments_v3` — perp + spot instrument definitions
  - `prices_v3` — mid prices for all 50 native perps
  - `funding_v3` — hourly funding rates for all perps
- **Used for**: Market data backdrop, funding rate tracking

### `scripts/pm_cashflows.py`
- **Schedule**: Hourly (via existing cron, not in Docker crontab — runs separately)
- **Input**: HL API `userFillsByTime` funding events
- **Output table**: `pm_cashflows` — FUNDING, FEE, DEPOSIT, WITHDRAW events per position/leg
- **Used for**: Funding earned, Fees paid, Carry APR, Net P&L

### `scripts/backfill_fills.py`
- **Schedule**: Manual (one-time or on-demand)
- **Input**: HL API `userFillsByTime` for all managed wallets
- **Output table**: `pm_fills` — raw trade fills with leg mapping
- **Used for**: Historical entry prices, fill history display

---

## 2. Computation Pipeline (`scripts/pipeline_hourly.py`)

**Schedule**: Hourly at :30. Runs these steps in order:

### Step 1: `spot_meta.py` — Spot Symbol Resolution
- Fetches `spotMeta` from HL API
- Builds `@index → SYMBOL/USDC` map (e.g., `@107 → HYPE/USDC`)
- Used by fill ingester to resolve spot fill coins

### Step 2: `fill_ingester.py` — Fill Ingestion
- **Input**: HL API `userFillsByTime` per wallet per dex
- **Output**: `pm_fills` table (new fills only, dedup by venue+account+tid)
- Resolves spot @index coins, maps fills to position legs

### Step 3: `entry_price.py` — VWAP Entry Price
- **Input**: `pm_fills` (opening fills per leg)
- **Output**: `pm_entry_prices` table + updates `pm_legs.entry_price`
- **Formula**: `avg_entry = SUM(px × sz) / SUM(sz)` for opening fills only
  - LONG leg: opening fills = BUY side
  - SHORT leg: opening fills = SELL side

### Step 4: `upnl.py` — Unrealized PnL (ADR-001)
- **Input**: `pm_entry_prices` + `prices_v3` (latest bid/ask)
- **Output**: Updates `pm_legs.unrealized_pnl` and `pm_legs.current_price`
- **Formulas**:
  - LONG uPnL = `(current_bid − avg_entry) × size`
  - SHORT uPnL = `−(current_ask − avg_entry) × size`
  - Fallback: if bid/ask NULL → use mid → use last
- **Position uPnL** = sum of all leg uPnLs

### Step 5: `spreads.py` — Entry/Exit Spread (ADR-008)
- **Input**: `pm_entry_prices` + `prices_v3` (latest bid/ask)
- **Output**: `pm_spreads` table
- **Formulas**:
  - Entry Spread = `long_avg_entry / short_avg_entry − 1`
  - Exit Spread = `long_exit_bid / short_exit_ask − 1`
  - Spread P&L = `(exit_spread − entry_spread) × 10,000` (in bps)
- Split-leg positions (1 spot + N perps) generate N sub-pairs

### Step 6: `portfolio.py` — Portfolio Aggregation
- **Input**: `pm_account_snapshots`, `pm_cashflows`, `pm_legs`, `pm_portfolio_snapshots`
- **Output**: `pm_portfolio_snapshots` table (1 row per hour)
- **Metrics computed**:
  - Total equity (from latest account snapshots)
  - Total unrealized PnL (sum across open legs)
  - Funding today (FUNDING cashflows since UTC midnight)
  - Funding all-time (since tracking start date)
  - Fees all-time (FEE cashflows since tracking start)
  - Daily change = current equity − 24h-ago equity
  - Cashflow-adjusted change = daily change − net deposits
  - APR = `(cashflow_adjusted_change / prior_equity) × 365`

---

## 3. API Endpoints → Dashboard Mapping

### `GET /api/portfolio/overview` → Dashboard top cards
| API Field | DB Source | Dashboard Display |
|-----------|----------|-------------------|
| `total_equity_usd` | `pm_account_snapshots` (latest per account) | **TOTAL EQUITY** card |
| `equity_by_account` | `pm_account_snapshots` (latest per account) | **WALLET BREAKDOWN** table |
| `daily_change_usd` | `pm_portfolio_snapshots` (latest) | "$X.XX (X.XX%) 24h" |
| `cashflow_adjusted_apr` | `pm_portfolio_snapshots` (latest) | "X.X% APR cashflow-adjusted" |
| `funding_today_usd` | `pm_cashflows` (FUNDING, today) | **FUNDING SUMMARY** Funding Today |
| `funding_alltime_usd` | `pm_cashflows` (FUNDING, all-time) | **FUNDING SUMMARY** Funding All-Time |
| `fees_alltime_usd` | `pm_cashflows` (FEE, all-time) | **FUNDING SUMMARY** Fees All-Time |
| `net_pnl_alltime_usd` | funding + fees | **FUNDING SUMMARY** Net P&L |
| `total_unrealized_pnl` | `pm_legs` (sum unrealized_pnl) | "uPnL $X.XX" |
| `open_positions_count` | `pm_positions` (status != CLOSED) | "N open positions" |

### `GET /api/positions` → Open Positions table
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `base` | `pm_positions.meta_json` | **Base** |
| `status` | `pm_positions.status` | **Status** |
| `amount_usd` | `pm_positions.meta_json` | **Amount** |
| `unrealized_pnl` | `pm_legs.unrealized_pnl` (sum) | **uPnL** |
| `funding_earned` | `pm_cashflows` (FUNDING per position) | **Funding** |
| `carry_apr` | computed: `(net_carry / amount) / days × 365` | **Carry APR** |
| `sub_pairs[].exit_spread_bps` | `pm_spreads.exit_spread × 10000` | **Exit Spread** |
| `sub_pairs[].spread_pnl_bps` | `pm_spreads.spread_pnl_bps` | **Spread P&L** |

### `GET /api/positions/{id}` → Position Detail page
| API Field | DB Source | Dashboard Section |
|-----------|----------|-------------------|
| `legs[]` | `pm_legs` + `pm_entry_prices` | **Legs table** (inst_id, side, size, entry, current, uPnL) |
| `sub_pairs[]` | `pm_spreads` | **Spread Display** (entry/exit/pnl per sub-pair) |
| `fills_summary[]` | `pm_fills` (count, first/last per leg) | **Fills Summary** |
| `cashflows[]` | `pm_cashflows` (per position) | **Cashflow Table** |
| `daily_funding_series[]` | `pm_cashflows` (FUNDING grouped by date) | **Funding Chart** |

### `GET /api/positions/{id}/fills` → Fills tab
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `fills[].inst_id` | `pm_fills.inst_id` | **Instrument** |
| `fills[].side` | `pm_fills.side` | **Side** |
| `fills[].px` | `pm_fills.px` | **Price** |
| `fills[].sz` | `pm_fills.sz` | **Size** |
| `fills[].fee` | `pm_fills.fee` | **Fee** |
| `fills[].ts` | `pm_fills.ts` | **Time** |

### `GET /api/positions/closed` → Closed Positions page
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `duration_days` | `closed_at_ms − created_at_ms` | **Duration** |
| `total_funding_earned` | `pm_cashflows` (FUNDING) | **Funding** |
| `total_fees_paid` | `pm_cashflows` (FEE) | **Fees** |
| `realized_spread_pnl` | `pm_fills.closed_pnl` (sum) | **Spread P&L** |
| `net_pnl` | spread + funding + fees | **Net P&L** |
| `net_apr` | `(net_pnl / amount) / days × 365` | **APR** |

### `GET /api/health` → System status bar
| API Field | DB Source | Dashboard Display |
|-----------|----------|-------------------|
| `last_fill_ingestion` | `pm_fills` MAX(ts) | "Fills: Xh ago" |
| `last_price_pull` | `prices_v3` MAX(ts) | "Prices: Xh ago" |
| `last_position_pull` | `pm_leg_snapshots` MAX(ts) | "Positions: Xh ago" |
| `db_size_mb` | File size of arbit_v3.db | "DB: X.X MB" |
| `open_positions` | `pm_positions` count | "N open" |

---

## 4. Data Flow Diagram

```
Every 5 min:
  pull_positions_v3.py ──> pm_account_snapshots (equity)
                       ──> pm_leg_snapshots (position state)

  pull_position_prices.py ──> prices_v3 (bid/ask/mid for position legs)

Hourly at :20:
  pull_hyperliquid_v3.py ──> instruments_v3, prices_v3, funding_v3

Hourly at :30:
  pipeline_hourly.py:
    1. spot_meta         (fetch @index map)
    2. fill_ingester     ──> pm_fills
    3. entry_price       ──> pm_entry_prices + pm_legs.entry_price
    4. upnl              ──> pm_legs.unrealized_pnl, pm_legs.current_price
    5. spreads           ──> pm_spreads
    6. portfolio         ──> pm_portfolio_snapshots

Hourly (separate cron):
  pm_cashflows.py ──> pm_cashflows (FUNDING, FEE events)
```

---

## 5. DB Tables Summary

| Table | Written by | Read by API | Key fields |
|-------|-----------|-------------|------------|
| `pm_positions` | pm.py sync-registry | positions, portfolio | position_id, status, strategy |
| `pm_legs` | pm.py sync + upnl.py | positions | leg_id, inst_id, side, size, entry_price, unrealized_pnl |
| `pm_fills` | fill_ingester.py | positions/{id}/fills | inst_id, side, px, sz, fee, ts, position_id, leg_id |
| `pm_entry_prices` | entry_price.py | positions | leg_id, avg_entry_price, fill_count |
| `pm_spreads` | spreads.py | positions | entry_spread, exit_spread, spread_pnl_bps |
| `pm_portfolio_snapshots` | portfolio.py | portfolio/overview | total_equity, apr_daily, funding_today |
| `pm_account_snapshots` | pull_positions_v3.py | portfolio/overview | account_id, total_balance |
| `pm_cashflows` | pm_cashflows.py | positions, portfolio | cf_type, amount, position_id |
| `prices_v3` | pull_position_prices + pull_hyperliquid_v3 | (via upnl/spreads) | inst_id, bid, ask, mid |
| `instruments_v3` | pull_hyperliquid_v3 | — (FK target) | venue, inst_id |
