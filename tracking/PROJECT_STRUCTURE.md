# Project Structure (Funding Arb System)

This repository is a **funding arbitrage terminal**. The codebase is organized to keep:
- connectors (venue adapters)
- normalization (symbols + instruments)
- storage (DB schema + writers)
- analytics (basis + screeners)
- ops (cron + logging + health checks)

The goal is: **instrument-centric, quote-aware, append-only time series**.

---

## Top-level

```
/mnt/data/agents/arbit/
  config/                 # runtime configs (fees, strategy thresholds)
  docs/                   # human docs (design, conventions, runbooks)
  scripts/                # executable entrypoints (pull, backfill, reports, tests)
  tracking/               # task board + architecture + sql schemas + ops logs
  tracking/connectors/    # venue connectors (public/private)
  tracking/analytics/     # analytics engines (basis, screener)
  tracking/db/            # sqlite db files (dev)
  trades/                 # trade logs (entries/exits/pnl/lessons)
  memory/                 # daily notes
```

---

## Canonical domain objects

### Instruments
- **Primary key**: `(venue, inst_id)`
- Fields:
  - `base`, `quote`
  - `contract_type`: SPOT | PERP
  - `symbol_key`: `BASE:QUOTE` (spot↔perp joins)
  - `symbol_base`: `BASE` (perp↔perp joins)

### Prices (time-series)
- **Primary key**: `(venue, inst_id, ts)`
- Store: bid/ask/mid/last/mark/index + quality flags.

### Funding (time-series)
- **Primary key**: `(venue, inst_id, ts)`
- Store: raw per-interval funding rate + interval hours.

---

## Directories (detailed)

### `tracking/connectors/`
**Purpose:** pure adapters to each venue.

Rules:
- Only I/O + parsing (HTTP/WS).
- No DB writes here.
- Return normalized snapshots.

Suggested files:
- `okx_public.py`, `okx_private.py`
- `paradex_public.py`, ...

### `tracking/`
#### `tracking/symbols.py`
Single source of truth for:
- symbol parsing
- quote-aware key creation
- venue-specific edge mappings

#### `tracking/sql/`
- `schema_v3.sql` (current)
- older schemas kept for audit

#### `tracking/db/`
- `arbit.db` (dev) or `arbit_v3.db`

#### `tracking/cron_*.{md,json}`
- `cron_progress.md` / `cron_state.json` etc.

### `scripts/`
**Purpose:** runnable commands.

Conventions:
- `pull_<venue>_<scope>.py` — ingestion runners
- `backfill_<venue>_<scope>.py` — history loaders
- `report_<topic>.py` — human output
- `test_<topic>.py` — smoke tests

### `tracking/analytics/`
- `basis.py`
- `opportunity_screener.py`
- `cost_model.py` (recommended)

---

## Testing requirements (must-follow)

### Funding sign convention (global)
- funding > 0: long pays, short receives
- funding < 0: long receives, short pays

Position PnL:
- `pnl_long = -funding_apr`
- `pnl_short = +funding_apr`

### Cost model
- Fees from `config/fees.json`
- Spread cost: cross-spread if bid/ask exist, else proxy + flag

### Loris cross-check
For any connector changes affecting funding:
- Compare a few symbols (e.g., BERA) against Loris snapshots.
- Log deltas and explain unit conversions.

---

## Documentation rule
Any time we:
- add a new venue
- change a formula / convention
- change schema

We must update:
- `docs/` design note (or create one)
- relevant task file in `tracking/tasks/`

---

## Suggested docs list
- `docs/DESIGN_v3.md` — end-to-end design
- `docs/CONNECTORS.md` — per-venue endpoints + caveats
- `docs/CONVENTIONS.md` — funding/cost/PnL formulas
- `docs/RUNBOOK.md` — how to run pulls/reports + cron

