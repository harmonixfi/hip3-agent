# Data Contracts

This file defines the current contracts used across the Harmonix workspace.

## Strategy config

Path:

- `config/strategy.json`

Current important fields:

- `oi_rank_max`
- `target_exchanges`
- `spot_perp.min_funding_apr`
- `spot_perp.allow_short_spot`
- `spot_perp.quotes`
- `perp_perp.enabled`

Current meaning:

- `target_exchanges` controls Loris ingest scope
- it does not by itself widen daily candidate ranking scope
- `oi_rank_max` is used by Loris collectors, not by the current daily candidate loader

## Registry contract

Primary input file:

- `config/positions.json`

Example:

- `config/positions.example.json`

Top-level shape:

```json
[
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
]
```

### Position fields

- `position_id`: unique string
- `strategy_type`: `SPOT_PERP` or `PERP_PERP`
- `base`: report ticker/base symbol
- `status`: `OPEN`, `PAUSED`, `EXITING`, `CLOSED`
- `amount_usd`: optional but expected for economics/reporting
- `open_fees_usd`: optional explicit entry-fee override
- `thresholds`: optional operational metadata
- `legs`: required array

### Leg fields

- `leg_id`: unique within the position
- `venue`
- `inst_id`
- `side`: `LONG` or `SHORT`
- `qty`: positive base units
- `qty_type`: optional, usually `base`
- `leverage`: optional
- `margin_mode`: optional
- `collateral`: optional

Important invariant:

- `qty` is token/base size, not USD notional
- `amount_usd` is the position-level gross notional input used by report economics

## DB contracts

DB path:

- `tracking/db/arbit_v3.db`

Created by:

- `scripts/db_v3_init.py`

### Public market tables

`instruments_v3`
- one row per venue instrument
- primary key: `(venue, inst_id)`

`prices_v3`
- append-only price snapshots
- primary key: `(venue, inst_id, ts)`

`funding_v3`
- append-only funding observations
- `funding_rate` is per interval, not APR
- `interval_hours` is required for correct normalization to 8h-equivalent

### Position-manager tables

`pm_positions`
- runtime source of truth for tracked positions
- `meta_json` currently carries `base`, `amount_usd`, `open_fees_usd`, and optional thresholds

`pm_legs`
- current leg state for each tracked position
- `size` stores the synced `qty`

`pm_leg_snapshots`
- append-only leg history

`pm_account_snapshots`
- append-only account snapshots

`pm_cashflows`
- realized financial events
- current sign convention:
  - positive = credit
  - negative = debit

Supported `cf_type` values:

- `REALIZED_PNL`
- `FEE`
- `FUNDING`
- `TRANSFER`
- `DEPOSIT`
- `WITHDRAW`
- `OTHER`

Important invariant:

- report headline economics use realized funding and fees from `pm_cashflows`
- unrealized MTM is diagnostic only

## CSV contracts

### `data/loris_funding_history.csv`

Columns:

- `timestamp_utc`
- `exchange`
- `symbol`
- `oi_rank`
- `funding_8h_scaled`
- `funding_8h_rate`

Current meaning:

- `funding_8h_rate` is a decimal 8h-equivalent rate
- `exchange` is canonicalized by Loris collectors
- CSV is append-only and deduped by `(timestamp_utc, exchange, symbol)` in backfill

Current consumers:

- daily candidate ranking
- carry monitoring
- historical funding windows for managed positions

### `tracking/equity/equity_daily.csv`

Columns:

- `date_local`
- `ts_utc`
- `venue`
- `equity_usd`
- `note`

Current meaning:

- one row per venue per local day
- partial failure is represented via `note`, not by dropping the row entirely

## Carry resolution contract

Implemented in:

- `tracking/position_manager/carry.py`

Current behavior:

- Loris market resolution maps venue and `inst_id` into `(exchange, symbol)`
- Hyperliquid builder-dex instruments like `xyz:GOLD` map to Loris exchanges such as `tradexyz`
- spot-perp positions use the short leg as the funding leg when strategy is `SPOT_PERP`

Important invariant:

- carry logic already understands more exchanges than the daily candidate loader
- this asymmetry is real and should be documented when debugging differences between position carry and candidate ranking

## What to test after fixes

- registry validation rejects bad enums, non-positive `qty`, and duplicate `leg_id`
- sync preserves `amount_usd` and `open_fees_usd` into `pm_positions.meta_json`
- `pm_cashflows` rows use correct sign convention for funding and fees
- Loris CSV rows are canonicalized consistently for live pull and backfill
- carry resolution for namespaced Hyperliquid builder-dex instruments finds the expected Loris market
