# TOOLS.md - Harmonix Local Notes

This file maps the local Harmonix tooling surface into the workflow. The runtime tree was cloned from Arbit, so use it as a baseline and call out any behavior that still reflects the old strategy.

## Workspace assumption

Harmonix now carries its own local runtime under:

`/Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral`

The current `scripts/`, `tracking/`, and `config/` trees were cloned from `workspace-arbit` on `2026-03-06`.
Do not invent new commands when an existing local script already covers the job. Also do not pretend a cloned Arbit script already matches Harmonix semantics if it still needs adaptation.

Routine command pattern:

```bash
cd /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral
source .arbit_env
.venv/bin/python <script> ...
```

---

## 1) Market / Funding Fetchers

### `scripts/pull_hyperliquid_v3.py`
- Purpose: pull current Hyperliquid market state into the v3 DB used by the position-manager stack.
- Inputs: environment + DB path defaults inside Arbit workspace.
- Output: refreshed market data in the tracking DB.
- Preconditions: environment sourced; DB writable.
- Failure mode: stale market context; position review becomes degraded.
- Safe for routine runs: **yes**

### `scripts/pull_loris_funding.py`
- Purpose: ingest normalized funding history for ranking and persistence logic.
- Inputs: Loris API.
- Output: `data/loris_funding_history.csv`.
- Preconditions: network access and sane system clock.
- Failure mode: candidate scoring becomes stale or misleading.
- Safe for routine runs: **yes**

---

## 2) Position / Portfolio Sync

### `scripts/pull_positions_v3.py --venues hyperliquid`
- Purpose: sync current managed positions and leg snapshots for the Hyperliquid side of the book.
- Inputs: private connector credentials.
- Output: updated `pm_legs`, `pm_leg_snapshots`, related DB state.
- Preconditions: managed positions already registered.
- Failure mode: position review may reference stale legs or missing hedges.
- Safe for routine runs: **yes**

### `scripts/equity_daily.py snapshot`
- Purpose: snapshot venue equity for portfolio context.
- Inputs: private connectors.
- Output: equity CSV.
- Preconditions: connector auth works.
- Failure mode: top-level equity context becomes stale.
- Safe for routine runs: **yes**

---

## 3) Ledger / Cashflow Maintenance

### `scripts/pm_cashflows.py ingest --venues hyperliquid`
- Purpose: ingest realized funding and fee cashflows into `pm_cashflows`.
- Inputs: private exchange history + managed leg index.
- Output: updated funding / fee ledger.
- Preconditions: managed positions map cleanly to venue legs.
- Failure mode: realized PnL headline becomes wrong or incomplete.
- Safe for routine runs: **yes**

### `scripts/pm_cashflows.py report`
- Purpose: roll up recent realized funding / fee data for inspection.
- Inputs: existing cashflow ledger.
- Output: CLI rollup.
- Preconditions: ingest has been running.
- Failure mode: none beyond stale rollup.
- Safe for routine runs: **yes**

---

## 4) Freshness / Health Checks

### `scripts/pm_healthcheck.py`
- Purpose: detect broken state, stale loops, or operational issues.
- Inputs: DB + environment.
- Output: health summary text when issues are found; cron-safe silent behavior when healthy.
- Preconditions: the rest of the PM stack has run at least once.
- Failure mode: hidden degradation if ignored; do not assume shell exit code alone is enough because the script is designed to stay cron-friendly.
- Safe for routine runs: **yes**

### `scripts/setup_crontab_pm.sh`
- Purpose: install the standard monitoring/reporting cron schedule.
- Inputs: host cron access.
- Output: live crontab changes.
- Preconditions: correct runtime machine and env paths.
- Failure mode: duplicate or wrong cron entries if installed carelessly.
- Safe for routine runs: **no, manual ops only**

---

## 5) Ranking / Reporting

### `scripts/report_daily_funding_with_portfolio.py --section ...`
- Purpose: single entrypoint for sectioned daily report output plus on-demand rotation-cost analysis.
- Inputs: DB, funding history, cashflow ledger, Felix equities cache, optional equity data.
- Output: one human-readable section body on `stdout` plus one JSON status line on `stderr`.
- Preconditions: pull + ingest steps already completed.
- Failure mode: hard-fail on missing required DB tables; degraded section output on stale/missing Loris or Felix classification.
- Rotation behavior: stale Felix cache still permits general/equities ranking with a degraded warning; candidate identity is `symbol + venue` in ranked/flagged rows.
- Safe for routine runs: **yes**

Daily section commands:

```bash
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

CLI notes:
- `--equities` is rejected
- no default no-`--section` daily mode remains
- `--section` is mutually exclusive with `--rotate-from/--rotate-to`
- `--rotate-from/--rotate-to` remains the on-demand `Rotation Cost Analysis` path

### `scripts/report_funding_opps.py`
- Purpose: broader opportunity screening.
- Inputs: funding history / DB context.
- Output: opportunity list.
- Preconditions: funding data available.
- Failure mode: useful for exploration, but not sufficient alone for final advice.
- Safe for routine runs: **yes**

### `scripts/opportunity_report_public.py`
- Purpose: public-facing opportunity formatting.
- Inputs: opportunity data.
- Output: summary text.
- Preconditions: upstream data already validated.
- Failure mode: can hide nuance if used as the only decision layer.
- Safe for routine runs: **yes, with review**

### `scripts/report_core_tier_portfolio_construction.py`
- Purpose: compare Strategy 3 vs Strategy 2 for Core-tier construction using current funding data.
- Inputs: `data/loris_funding_history.csv`, `data/felix_equities_cache.json`, `config/fees.json`
- Output: human-readable Core basket recommendation plus method/deployment verdicts.
- Preconditions: funding history exists; spot availability is modeled from current Felix cache plus any explicit Hyperliquid spot inputs wired into the runtime.
- Failure mode: degraded input state or unresolved spot mapping can leave the basket empty; this is advisory-only and must not be treated as an execution command.
- Safe for routine runs: **yes**

On-demand command:

```bash
.venv/bin/python scripts/report_core_tier_portfolio_construction.py --portfolio-capital 1000000 --core-capital 600000
```

---

## 6) Delivery

### `scripts/send_daily_funding_with_portfolio.sh`
- Purpose: deliver the final daily report message once the wrapper is aligned to Harmonix channel/schedule.
- Inputs: generated report text + configured channel env.
- Output: sent chat message.
- Preconditions: final content already reviewed and channel config is correct.
- Failure mode: wrong destination, wrong schedule, or bad formatting if the wrapper still reflects Arbit defaults.
- Safe for routine runs: **yes**

### Telegram target
- Default send time: `09:00` Asia/Ho_Chi_Minh
- Rule: never send raw dumps; always send the summarized report contract from `WORKFLOW.md`.
- Current reality: this workspace now has its own cloned wrapper, but the content still inherits Arbit defaults until Harmonix-specific channel/schedule settings are verified.

---

## 7) Debug / Recovery

### `scripts/hyperliquid_dump.py`
- Purpose: inspect Hyperliquid raw state for debugging connector/data mismatches.
- Inputs: connector access.
- Output: raw snapshots / debug output.
- Preconditions: use only when the normal report shows inconsistencies.
- Failure mode: none, but noisy.
- Safe for routine runs: **manual debug only**

### `scripts/test_hyperliquid_public.py`
- Purpose: quick sanity check for public Hyperliquid connectivity.
- Inputs: network access.
- Output: test result.
- Preconditions: none.
- Failure mode: none.
- Safe for routine runs: **manual debug only**

### `scripts/test_funding_sign_convention.py`
- Purpose: confirm funding sign assumptions haven't drifted.
- Inputs: local code/test fixtures.
- Output: pass/fail.
- Preconditions: Python environment ready.
- Failure mode: sign bugs can invert the thesis, so treat failures as blocking.
- Safe for routine runs: **yes**

---

## 8) Practical rules

- Pull -> freshness/integrity -> compute -> summarize -> send.
- Do not use a single script output as the final recommendation if freshness was not checked.
- Realized funding/fees are the PnL headline.
- Unrealized MTM is context, not permission to ignore broken carry.
- If a command changes host scheduling or sends messages, treat it as an operator action, not a background read.
