# Data Structures And Contracts

## 1. Registry JSON

Primary files:

- `config/positions.json`
- `config/positions.example.json`

Loader:

- `tracking/position_manager/registry.py`

Each position object:

```json
{
  "position_id": "EXAMPLE_BTC_SPOT_PERP_HL_001",
  "strategy_type": "SPOT_PERP",
  "base": "BTC",
  "status": "OPEN",
  "amount_usd": 6500,
  "open_fees_usd": 2.93,
  "thresholds": {},
  "legs": []
}
```

Required position fields:

- `position_id`
- `strategy_type`
- `base`
- `status`
- `legs`

Optional but important position fields:

- `amount_usd`
  manual position-level gross notional/capital for report economics
- `open_fees_usd`
  manual open-cost override if known
- `thresholds`
  per-position risk/rebalance thresholds

Each leg object:

- `leg_id`
- `venue`
- `inst_id`
- `side`
- `qty`

Optional leg fields:

- `qty_type`
- `leverage`
- `margin_mode`
- `collateral`

Invariants:

- `qty` is in base units, not USD
- `qty > 0`
- `side in {LONG, SHORT}`
- `strategy_type in {SPOT_PERP, PERP_PERP}`
- `status in {OPEN, PAUSED, EXITING, CLOSED}`
- `leg_id` must be unique within a position

## 2. PM database schema

Schema file:

- `tracking/sql/schema_pm_v3.sql`

Core tables:

### `pm_positions`

One logical position per tracked trade.

Important columns:

- `position_id`
- `venue`
- `strategy`
- `status`
- `created_at_ms`
- `updated_at_ms`
- `closed_at_ms`
- `raw_json`
- `meta_json`

Important `meta_json` fields used by Harmonix:

- `strategy_type`
- `base`
- `amount_usd`
- `open_fees_usd`
- `thresholds`

### `pm_legs`

One row per live leg.

Important columns:

- `leg_id`
- `position_id`
- `venue`
- `inst_id`
- `side`
- `size`
- `entry_price`
- `current_price`
- `unrealized_pnl`
- `realized_pnl`
- `status`
- `opened_at_ms`
- `closed_at_ms`
- `meta_json`

Important `meta_json` fields:

- `qty_type`
- `leverage`
- `margin_mode`
- `collateral`

### `pm_cashflows`

Append-only realized events.

Important columns:

- `cashflow_id`
- `position_id`
- `leg_id`
- `venue`
- `account_id`
- `ts`
- `cf_type`
- `amount`
- `currency`
- `description`
- `raw_json`
- `meta_json`

Allowed `cf_type` values:

- `REALIZED_PNL`
- `FEE`
- `FUNDING`
- `TRANSFER`
- `DEPOSIT`
- `WITHDRAW`
- `OTHER`

Sign convention:

- positive `amount` = credit received
- negative `amount` = debit paid

This sign contract is critical for funding and fee rollups.

### `pm_leg_snapshots`

Append-only state history for each leg.

### `pm_account_snapshots`

Append-only account balance and margin history.

## 3. Public funding CSV

Primary file:

- `data/loris_funding_history.csv`

Columns:

- `timestamp_utc`
- `exchange`
- `symbol`
- `oi_rank`
- `funding_8h_scaled`
- `funding_8h_rate`

Semantics:

- `funding_8h_scaled`
  raw Loris scaled funding value
- `funding_8h_rate`
  scaled value divided by `10000`
- row granularity
  live pull appends one snapshot timestamp per run
  backfill can write resampled hourly rows

Deduplication contract:

- backfill treats `(timestamp_utc, exchange, symbol)` as the unique row key

## 4. Hyperliquid namespaced perp ids

Current project must support plain and namespaced Hyperliquid `inst_id` values:

- plain base dex: `BTC`
- builder-dex: `xyz:GOLD`, `flx:ABC`, `km:BTC`, `hyna:HYPE`

Two separate contracts matter:

### PM / connector contract

- keep `inst_id` namespaced in PM tables where that is how the venue distinguishes the perp

### Loris lookup contract

When resolving a Hyperliquid perp leg into Loris funding rows:

- `BTC` => `(hyperliquid, BTC)`
- `xyz:GOLD` => `(tradexyz, GOLD)`
- `flx:ABC` => `(felix, ABC)`
- `km:BTC` => `(kinetiq, BTC)`
- `hyna:HYPE` => `(hyena, HYPE)`

## 5. Report-level derived fields

Derived by `report_daily_funding_with_portfolio.py`:

- `start_time`
- `avg_15d_funding_usd_per_day`
- `funding_1d_usd`
- `funding_2d_usd`
- `funding_3d_usd`
- `open_fees_usd`
- `breakeven_days`
- `advisory`
- candidate APR windows and `stability_score`

These are derived fields, not persistent source-of-truth columns.

## 6. Source-of-truth order

Use this order when debugging mismatches:

1. Registry JSON for intent and manual capital metadata
2. PM DB tables for synced positions and realized cashflows
3. Loris CSV for public funding history and ranking inputs
4. Report script for derived economics and formatting
