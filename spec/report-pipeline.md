# Report Pipeline Spec

This file describes the current behavior of:

- `scripts/report_daily_funding_with_portfolio.py`
- `scripts/report_daily_funding_sections.py`

It reflects the runtime as implemented now.

## Purpose

Produce deterministic section outputs for the upstream report assembler:

- `portfolio-summary`
- `rotation-general`
- `rotation-equities`

The same script also supports on-demand `Rotation Cost Analysis`.

## Inputs

Required:

- SQLite DB: `tracking/db/arbit_v3.db`
- Loris funding CSV: `data/loris_funding_history.csv`

Optional:

- equity CSV: `tracking/equity/equity_daily.csv`
- Felix cache: `data/felix_equities_cache.json` for trusted general/equities partitioning

Required DB tables:

- `pm_positions`
- `pm_legs`
- `pm_cashflows`

## Section mode contract

Invoke one section at a time:

```bash
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

Behavior:

- `stdout`: human-readable section body only
- `stderr`: exactly one JSON line with `section`, `state`, `snapshot_ts`, `warnings`, `hard_fail`
- exit `0`: section rendered truthfully in `NORMAL` or `DEGRADED`
- non-zero exit: hard failure, no truthful section body could be rendered

## Portfolio section

`portfolio-summary` renders:

- `## Portfolio Summary`
- position rows
- `### Flagged Positions`

Hard-fail conditions:

- missing required DB tables
- malformed required portfolio schema

Degraded conditions:

- carry inputs missing or incomplete
- fallback advisory/rendering required for one or more rows

## Rotation sections

`rotation-general` renders only symbols not in Felix equities.

`rotation-equities` renders only symbols in Felix equities.

Shared ranked-row fields:

- rank
- symbol
- venue
- `APR14`
- `APR7`
- `APR 1d / 2d / 3d`
- `stability score`
- note

Shared footer:

- `### Flagged Candidates`

Candidate ranking formula:

`0.55 * APR14 + 0.30 * APR7 + 0.15 * APR_latest`

Eligibility gate before ranking:

- `APR14 >= 20%`
- no stale symbol funding
- no `LOW_14D_SAMPLE`
- no `LOW_3D_SAMPLE`
- no `BROKEN_PERSISTENCE`
- no `SEVERE_STRUCTURE`

Held symbols are excluded from both ranked outputs.

## Degraded behavior

Missing or stale Loris input:

- render empty ranked block
- keep `### Flagged Candidates`
- set section state to `DEGRADED`

Stale or unavailable Felix classification:

- stale Felix cache still allows ranked general/equities lists using the cached symbol set
- stale Felix cache must render an explicit warning and set section state to `DEGRADED`
- unavailable Felix classification still suppresses ranked split output
- include only safely partitionable flagged names when possible
- set section state to `DEGRADED`

## On-demand rotation analysis

Invoke:

```bash
.venv/bin/python scripts/report_daily_funding_with_portfolio.py \
  --rotate-from <position_id|ticker> \
  --rotate-to <symbol>
```

This mode prints only `# Rotation Cost Analysis`.
