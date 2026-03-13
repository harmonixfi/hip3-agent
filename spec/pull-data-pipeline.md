# Pull Data Pipeline Spec

## Goal

The pipeline populates the data required by the daily portfolio report:

- public funding history
- private realized cashflows
- managed positions and leg state
- optional equity snapshot

The pipeline is split into public pull, historical backfill, private ingest, and DB sync.

## Canonical daily run order

```bash
cd /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral
source .arbit_env

.venv/bin/python scripts/pull_hyperliquid_v3.py
.venv/bin/python scripts/pull_loris_funding.py
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid
.venv/bin/python scripts/equity_daily.py snapshot
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --top 5
```

If only candidate funding is needed, the minimum path is:

- `pull_loris_funding.py`
- `report_daily_funding_with_portfolio.py`

## Public pull scripts

### `scripts/pull_loris_funding.py`

Purpose:

- fetch live funding snapshot from `https://api.loris.tools/funding`
- append normalized rows into `data/loris_funding_history.csv`

Input config:

- `config/strategy.json.target_exchanges`
- `config/strategy.json.oi_rank_max`

Normalization rules:

- exchange aliases are normalized before filtering and writing
- supported aliases currently include:
  - `hl -> hyperliquid`
  - `xyz -> tradexyz`
  - `tradexyz_perp -> tradexyz`
  - `felix -> felix`
  - `kinetiq -> kinetiq`
  - `hyena -> hyena`

Output row contract:

- `timestamp_utc`
- `exchange`
- `symbol`
- `oi_rank`
- `funding_8h_scaled`
- `funding_8h_rate`

OI-rank behavior:

- keep rows with missing OI rank
- drop rows whose known OI rank exceeds `oi_rank_max`

### `scripts/pull_loris_backfill_history.py`

Purpose:

- backfill historical funding into the same CSV used by the live puller

Sources:

- `https://api.loris.tools/funding`
- `https://loris.tools/api/funding/historical`

Defaults:

- `--days 30`
- `--resolution hourly`
- jitter sleep between symbols: `0.2s` to `0.5s`

Important behaviors:

- historical timestamps ending with `Z` must parse as UTC
- dedupe key is `(timestamp_utc, exchange, symbol)`
- raw Loris exchange names are normalized with the same alias map as live pull
- symbol universe defaults to live symbols filtered by OI rank or missing-rank allowance

Supported target exchanges in current config:

- `hyperliquid`
- `tradexyz`
- `felix`
- `kinetiq`
- `hyena`

## Private ingest scripts

### `scripts/pull_positions_v3.py`

Purpose:

- refresh open managed legs and account state into PM tables

Current Harmonix use:

- `--venues hyperliquid`

Output tables:

- `pm_positions`
- `pm_legs`
- `pm_leg_snapshots`
- `pm_account_snapshots`

### `scripts/pm_cashflows.py ingest`

Purpose:

- write realized economic events into `pm_cashflows`

Current important venues:

- Hyperliquid
- other connectors still exist from Arbit baseline, but Harmonix daily workflow is currently Hyperliquid-first

Hyperliquid behavior:

- fetches `userFunding` in time windows
- fetches `userFillsByTime` in time windows
- ingests only managed perp legs
- for `SPOT_PERP`, that means the `SHORT` perp leg only

Important sign rules:

- `FUNDING`
  positive means funding received by the tracked account
- `FEE`
  negative means fee paid

Important Hyperliquid namespace behavior:

- managed `inst_id` can be plain `BTC`
- or namespaced builder-dex form such as `xyz:GOLD`
- funding ingest keeps the namespace in PM metadata, but Loris carry lookup resolves it to:
  - `xyz -> tradexyz`
  - `flx -> felix`
  - `km -> kinetiq`
  - `hyna -> hyena`

### `scripts/equity_daily.py snapshot`

Purpose:

- append daily equity snapshots to `tracking/equity/equity_daily.csv`

This section is optional in the report.
If equity data is absent, the report should still render.

## Registration and DB sync

### `scripts/pm.py sync-registry`

Purpose:

- load `config/positions.json`
- validate with `tracking.position_manager.registry`
- upsert to `pm_positions` and `pm_legs`

This is mandatory before portfolio reporting has anything meaningful to review.

## Failure modes

Expected degraded conditions:

- Loris CSV missing or stale
- PM tables missing
- position registry empty
- private connector env missing
- cashflow ingest succeeds partially but not for all legs

Degraded behavior:

- do not silently fabricate portfolio economics
- keep candidate/report output explicit about stale or missing sources
- preserve append-only history where possible instead of rewriting old data
