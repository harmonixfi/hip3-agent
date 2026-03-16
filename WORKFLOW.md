# WORKFLOW.md - Harmonix Daily Delta-Neutral Workflow

Last updated: 2026-03-11
Owner: Harmonix

---

## 1) Strategy contract

- Portfolio/runtime venue family understood by the workspace: **`hyperliquid`, `tradexyz`, `felix`, `kinetiq`, `hyena`**
- Daily top-candidate ranking scope today: **`hyperliquid` rows only from Loris CSV unless code is intentionally widened**
- Pair model: **spot + perp same asset**
- Agent mode: **advisory only**
- Candidate floor: **`APR14 >= 20%`**
- Headline PnL: **realized funding - trading fees**
- Diagnostic PnL: **unrealized MTM shown separately**
- Default report time: **09:00 Asia/Ho_Chi_Minh**

---

## 2) Canonical data flow

### Step A - Pull market and funding inputs

Use the local Harmonix runtime, cloned from the Arbit baseline, as the workflow skeleton:

1. `scripts/pull_hyperliquid_v3.py`
2. `scripts/pull_loris_funding.py`
3. `scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid`
4. `scripts/pm_cashflows.py ingest --venues hyperliquid`
5. `scripts/equity_daily.py snapshot`

Intent:
- market state from Hyperliquid runtime
- funding history for persistence, carry resolution, and candidate scoring
- latest managed position state
- realized funding/fee ledger updates
- latest tracked equity context

Bootstrap note:
- `config/positions.json` is intentionally reset to an empty registry in this workspace.
- Register Harmonix positions explicitly before treating any report as portfolio-aware.
- Generated alert/cashflow/equity/report state was also reset after cloning so the first run starts clean.

### Step B - Freshness and integrity gate

Before any recommendation:

1. Verify the latest funding snapshot is fresh.
2. Verify latest managed positions were pulled successfully.
3. Verify ledger ingest did not fail.
4. Verify each open position still has both expected legs.

If any of these fail:
- report status becomes `DEGRADED`
- recommendations may downgrade to `MONITOR` or `INVESTIGATE`
- the warning must appear near the top of the report

### Step C - Compute candidate ranking

Rank only symbols that pass the minimum strategy filters from `res-delta-neutral-rules.md`.
For daily send-report behavior, use the current runtime scope from:
- `./spec/report-pipeline.md`
- today the shared candidate pool is loaded from supported report exchanges in `data/loris_funding_history.csv`

Core fields:
- `APR_latest`
- `APR7`
- `APR14`
- `stability_score`
- `confidence`
- `stale_hours`
- `flags`

Stability score formula:

`0.55 * APR14 + 0.30 * APR7 + 0.15 * APR_latest`

Do not recommend a candidate from raw score alone.
Use score + freshness + persistence + market quality together.

### Step D - Review existing positions

For each open position, compute:
- start date
- current token size
- funding earned
- fees paid
- net realized
- unrealized MTM
- current carry regime
- recommendation

Allowed position actions:
- `HOLD`
- `MONITOR`
- `EXIT`
- `INCREASE SIZE`

Every action needs a short reason.

### Step E - Generate daily report

The report must be human-readable and Telegram-ready.
Never send raw CSV, raw JSON, or debug dumps.

Required human-facing template:
1. global header from section metadata
2. `Portfolio Summary`
3. `Top 10 Rotation Candidates - General`
4. `Top 10 Rotation Candidates - Equities`

Delivery rules:
- The daily report is assembled from three separate section commands.
- The final report sent to chat must follow the template above.
- Script section output is an input artifact, not the final delivery contract.
- Warnings, freshness state, and degraded-state notes belong in the global header and the relevant section body.
- If one required section hard-fails, still send a partial report with the remaining sections and clearly name the failed section in the header.
- Do not improvise legacy sections such as `Quick take`, `High APR but unstable`, `Action list`, or a daily `Rotation Cost Analysis` block unless Bean explicitly asks for them.

### On-demand Core Candidate Export
Use `scripts/export_core_candidates.py` to export all scored candidates as CSV.
Scores are informational — flags (DECAYING_REGIME, STALE_DATA, etc.) are surfaced but do not gate scores.
Human picks pairs from the exported data.

### Step F - Deliver

Send the final report to Telegram at `09:00` Asia/Ho_Chi_Minh.
The local scripts in this workspace were cloned from Arbit and may still need Harmonix-specific schedule/channel adjustments before production rollout.

If the run is degraded:
- still send the report
- label it clearly
- do not pretend the recommendations are normal quality

---

## 3) Decision logic

### Candidate qualification

A candidate belongs in a ranked rotation section only if:
- `APR14 >= 20%`
- latest data is fresh enough for same-day use
- persistence is not obviously broken
- no severe liquidity or structure flags

Daily ranked candidates must then be split into:
- `Top 10 Rotation Candidates - General`
  symbols not in Felix equities
- `Top 10 Rotation Candidates - Equities`
  symbols in Felix equities

Weak, stale, or structurally broken names must appear under `Flagged Candidates` in the relevant rotation section instead of being silently skipped.

### Confidence / stability reading

Use the same mental model as the existing funding workflow:
- freshness first
- then sample quality / persistence
- then trend alignment across `APR_latest`, `APR7`, `APR14`

### Existing position advisory

Default sequencing:
- healthy but slightly weaker -> `MONITOR`
- broken persistence or net realized economics deteriorating -> `EXIT`
- stable and improving with healthy risk -> `INCREASE SIZE`
- stable and acceptable -> `HOLD`

Do not jump straight from minor weakness to `EXIT` unless risk or data integrity is bad.

---

## 4) Report contract

### Header

- snapshot timestamp
- report timezone
- workflow state: `NORMAL` or `DEGRADED`
- warning line near the top when freshness, integrity, or input coverage is degraded

### Portfolio Summary

Each row must include:
- ticker
- amount ($)
- start time
- avg 15d funding ($)
- funding 1d / 2d / 3d ($)
- open fees ($)
- breakeven time
- advisory

Notes:
- `amount ($)` is position-level report notional from `amount_usd`
- `avg 15d funding ($)` means average daily funding earned over the last 15 days
- `breakeven time` means `open fees / avg daily funding`
- advisory must stay concise and action-oriented

### Top 10 Rotation Candidates - General

Each ranked row must include:
- rank
- symbol
- venue
- `APR14`
- `APR7`
- `APR 1d / 2d / 3d`
- `stability_score`
- note

Section rules:
- include only symbols not in Felix equities
- exclude symbols already held in the portfolio
- stale Felix cache may still be used for split/ranking, but the section must be marked `DEGRADED`
- append `### Flagged Candidates` for relevant excluded names

### Top 10 Rotation Candidates - Equities

Each ranked row must include:
- rank
- symbol
- venue
- `APR14`
- `APR7`
- `APR 1d / 2d / 3d`
- `stability_score`
- note

Section rules:
- include only symbols in Felix equities
- exclude symbols already held in the portfolio
- stale Felix cache may still be used for split/ranking, but the section must be marked `DEGRADED`
- append `### Flagged Candidates` for relevant excluded names

### Rotation Cost Analysis

This block is on-demand only.

Use it when Bean asks about a specific rotation with `--rotate-from ... --rotate-to ...`.

When populated, it must show:
- close fees ($)
- open fees ($)
- total switch cost ($)
- expected daily funding ($)
- breakeven time

### Source Of Truth

- Human-facing report template source of truth:
  `./spec/feat-delta-neutral-agent.md`
- Runtime/current implementation references:
  `./spec/README.md`
  `./spec/report-pipeline.md`
  `./spec/pull-data-pipeline.md`
  `./spec/data-contracts.md`

If script output and chat template differ, the agent must treat the feature spec template as the delivery contract and reformat accordingly before sending.

---

## 5) Runbook

Daily manual run shape:

```bash
cd /home/node/.openclaw/workspace-harmonix-delta-neutral
source .arbit_env

# 1) pull market/funding inputs
.venv/bin/python scripts/pull_hyperliquid_v3.py
.venv/bin/python scripts/pull_loris_funding.py

# 2) sync positions + realized cashflows
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid
.venv/bin/python scripts/equity_daily.py snapshot

# 3) generate operator-grade sections
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

Send behavior after run:
- if freshness or integrity checks fail, say so in the global header and inside the degraded section
- if `config/positions.json` is still empty, keep `Portfolio Summary` explicit that no open positions are tracked
- if one section hard-fails, still send the remaining sections and name the failed section in the header
- if Bean asks about a specific rotation, rerun with `--rotate-from ... --rotate-to ...` and include the populated `Rotation Cost Analysis`

---

## 6) Out of scope

- Auto execution
- Cross-exchange pair routing
- Multi-leg basket logic
- Using unrealized MTM as the headline return number
