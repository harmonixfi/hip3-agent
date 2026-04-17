# WORKFLOW.md - Harmonix Daily Delta-Neutral Workflow

Last updated: 2026-04-17
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

### Step 0 — Position registry → DB (`pm.py sync-registry`)

**Source of truth:** `config/positions.json` → **`pm_positions` / `pm_legs`** in SQLite.

| Run `sync-registry` | Skip it |
|----------------------|--------|
| After any registry edit: new position, leg/qty, `wallet_label`, `status` (OPEN / PAUSED / CLOSED), rebalance | Ordinary “refresh market data” days with **no** JSON changes |

```bash
source .arbit_env
.venv/bin/python scripts/pm.py sync-registry
.venv/bin/python scripts/pm.py list
```

**Order:** Run **before** `pull_positions_v3` and the rest of the pull/compute chain so pulls and metrics target the right legs. It is **not** a substitute for `pipeline_hourly` or `pull_positions_v3`.

Playbook: `docs/playbook-position-management.md`.

### Step A - Pull market and funding inputs

Use the local Harmonix runtime, cloned from the Arbit baseline, as the workflow skeleton:

1. `scripts/pull_hyperliquid_v3.py`
2. `scripts/pull_loris_funding.py`
3. `scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid`
4. `scripts/pull_position_prices.py` — bid/ask (and mids where applicable) for every open leg’s `inst_id`; feeds price rows used by uPnL and spread math
5. `scripts/pm_cashflows.py ingest --venues hyperliquid`
6. `scripts/equity_daily.py snapshot`
7. `scripts/pipeline_hourly.py` — ingest fills (HL), VWAP entry prices, unrealized PnL, entry/exit spreads, and `pm_portfolio_snapshots` (dashboard / APR context). Not the same as `pull_position_prices.py`; run both when doing a full manual pass

Intent:
- market state from Hyperliquid runtime
- funding history for persistence, carry resolution, and candidate scoring
- latest managed position and account snapshots (`pull_positions_v3`)
- fresh leg marks for MTM (`pull_position_prices`; production often runs this on a separate ~5m cron — see `docker/crontab`)
- realized funding/fee ledger updates
- latest tracked equity context
- recomputed portfolio metrics in SQLite (`pipeline_hourly`)

Bootstrap note:
- `config/positions.json` is intentionally reset to an empty registry in this workspace.
- Register Harmonix positions explicitly before treating any report as portfolio-aware.
- Generated alert/cashflow/equity/report state was also reset after cloning so the first run starts clean.

### Step A+ - Account equity mechanics (read this before touching equity)

`pull_positions_v3.py` writes one row per tracked wallet into `pm_account_snapshots`. How `total_balance` is computed depends on the Hyperliquid **account abstraction mode**, auto-detected per pull via `POST /info {"type":"userAbstraction","user":<addr>}` and stored in `raw_json.account_mode`:

| Mode | Equity formula |
|---|---|
| `unifiedAccount` / `portfolioMargin` | `spot_equity + Σ(unrealizedPnl across dexes)` — collateral is a single shared pool, so summing `accountValue` across builder dexes **double-counts** |
| `disabled` / `default` / `dexAbstraction` | `perp_native + Σ(accountValue per builder dex) + spot_equity` — each dex is a separate isolated pool |

Current wallet modes (DN strategy):
- `0xd4737…` (commodity) → `unifiedAccount`
- `0x3c2c…` (alt), `0x4Fde…` (main), `0x0BdF…` (depeg) → `disabled`

**Excluded spot tokens** — `config/equity_config.json::exclude_spot_tokens` lists tokens per-account to skip from `spot_equity`. They stay in `raw_json.spot_tokens` for audit but don't count toward `total_balance`. **Do NOT** add tokens that can be spot legs of a DN position (e.g., `HYPE`, `LINK0`, `UFART`) — tokens only belong here if they are unrelated noise (e.g., airdrops, protocol rewards).

**Felix equity** — pulled separately (different auth flow, see `docs/felix-auth.md`). When Felix is drained and the Felix puller is not running, insert a manual zero snapshot:
```sql
INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance, available_balance, margin_balance, unrealized_pnl, position_value)
VALUES ('felix', '0xB89E…', strftime('%s','now')*1000, 0, 0, 0, 0, 0);
```

Reference: `tracking/connectors/hyperliquid_private.py::fetch_account_snapshot`.

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

### Step B+ - Cashflow reconciliation (APR correctness)

External capital movements (user deposits/withdrawals, transfers of non-strategy assets out) MUST be recorded in two tables so APR formulas don't misclassify them as trading PnL:

| Table | Level | Consumed by | APR field affected |
|---|---|---|---|
| `pm_cashflows` | Per-wallet (`account_id`) | `tracking/pipeline/portfolio.py::compute_portfolio_snapshot` | `pm_portfolio_snapshots.apr_daily` (via `cashflow_adjusted_change = daily_change - net_deposits_24h`) |
| `vault_cashflows` | Per-strategy (`strategy_id`) | `tracking/vault/recalc.py` | `vault_strategy_snapshots.apr_7d` / `apr_30d` |

`cf_type` semantics:
- `DEPOSIT` (+amount), `WITHDRAW` (−amount) — affect equity, subtracted from APR numerator
- `OTHER` — audit-only; does NOT affect APR (use for transferring out `exclude_spot_tokens` assets)
- `FUNDING`, `FEE`, `REALIZED_PNL` — ingested automatically by `pm_cashflows.py`; don't insert manually

When inserting DEPOSIT/WITHDRAW for a DN wallet, mirror the event into `vault_cashflows` with `strategy_id='delta_neutral'` (or matching strategy) so strategy-level APR also adjusts.

After backfilling cashflows, recompute historical APR fields in-place:
```bash
.venv/bin/python scripts/recompute_portfolio_apr.py --since 2026-04-02
```
This iterates `pm_portfolio_snapshots` and rewrites `daily_change_usd`, `cashflow_adjusted_change`, `apr_daily` using current `pm_cashflows`. Equity values stay untouched.

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

Daily manual run shape (adjust `cd` to your clone):

```bash
cd /home/node/.openclaw/workspace-harmonix-delta-neutral
source .arbit_env

# 0) Only if you changed config/positions.json since last sync:
# .venv/bin/python scripts/pm.py sync-registry && .venv/bin/python scripts/pm.py list

# 1) pull market/funding inputs
.venv/bin/python scripts/pull_hyperliquid_v3.py
.venv/bin/python scripts/pull_loris_funding.py

# 2) sync positions + realized cashflows + equity snapshot
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid
.venv/bin/python scripts/equity_daily.py snapshot

# 3) leg bid/ask prices (open legs only — required for sensible uPnL/spreads; omitted from older runbooks)
.venv/bin/python scripts/pull_position_prices.py

# 4) hourly compute: fills → entry VWAP → uPnL → spreads → portfolio snapshot
.venv/bin/python scripts/pipeline_hourly.py
# Recompute metrics only (no new fill ingest): .venv/bin/python scripts/pipeline_hourly.py --skip-ingest

# 5) generate operator-grade sections
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
.venv/bin/python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

Send behavior after run:
- if freshness or integrity checks fail, say so in the global header and inside the degraded section
- if `config/positions.json` is still empty, keep `Portfolio Summary` explicit that no open positions are tracked
- if one section hard-fails, still send the remaining sections and name the failed section in the header
- if Bean asks about a specific rotation, rerun with `--rotate-from ... --rotate-to ...` and include the populated `Rotation Cost Analysis`

### Equity reconciliation helpers

When reported equity doesn't match exchange UI ground truth:

1. **Verify account mode** (unified vs standard):
   ```bash
   source .arbit_env && .venv/bin/python -c "
   from tracking.connectors.hyperliquid_private import post_info
   for a in ['0x3c2c…','0xd4737…']:
       print(a, post_info({'type':'userAbstraction','user':a}))"
   ```

2. **Inspect snapshot breakdown**:
   ```sql
   SELECT datetime(ts/1000,'unixepoch'), round(total_balance,2),
          json_extract(raw_json,'$.account_mode') AS mode,
          json_extract(raw_json,'$.spot_equity') AS spot,
          json_extract(raw_json,'$.perp_native') AS native,
          json_extract(raw_json,'$.unified_upnl_sum') AS unified_upnl
   FROM pm_account_snapshots WHERE account_id='0x…' ORDER BY ts DESC LIMIT 1;
   ```

3. **Reset derived snapshots + re-pull** (after fixing connector / backfilling cashflows):
   ```sql
   DELETE FROM pm_account_snapshots WHERE ts >= strftime('%s','YYYY-MM-DD')*1000
     AND account_id IN ('0x…', '0x…');
   DELETE FROM pm_portfolio_snapshots WHERE ts >= strftime('%s','YYYY-MM-DD')*1000;
   ```
   Then re-run `pull_positions_v3.py` + `pipeline_hourly.py`. APR will be NULL on the first post-reset snapshot (no prior 24h to compare) — normal.

### Common gotchas

- **CRLF in `.arbit_env`** (Windows/WSL clone): Python scripts may fail with `ValueError: unconverted data remains` on env-sourced dates. Fix: `sed -i 's/\r$//' .arbit_env`. `tracking/pipeline/portfolio.py::DEFAULT_TRACKING_START` already strips defensively.
- **Delta Neutral provider**: `tracking/vault/providers/delta_neutral.py::get_equity` initializes `counted_lower: set` before the wallet loop. If vault_snapshot fails with `NameError: name 'counted_lower' is not defined`, confirm this line exists (refactor residue bug).
- **Builder dex fallback duplicate**: In `disabled` mode, HL's API may return master `accountValue` when querying a builder dex the wallet isn't using — `perp_native == perp_xyz` exactly is a tell. Current logic trusts the API; if HL changes this behavior, filter by `bool(bst.get("assetPositions"))` before summing.
- **Cashflow Apr 7 TRANSFER**: an older `TRANSFER` event on 2026-04-07 (`allocate fund to open stocks`) was an internal strategy reallocation. User-provided Apr 2-10 deposit/withdraw backfill supersedes it — don't re-add.

### Local backend + frontend (dashboard)

Run from the **repo root** with `.venv` and `source .arbit_env` (same as other Python commands).

**Backend (BE)** — FastAPI + uvicorn on port **8000**:

```bash
source .arbit_env
.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

**Frontend (FE)** — Next.js (default **3000**), in a **second** terminal:

```bash
cd frontend
# One-time: copy env and point at local API (API_KEY must match HARMONIX_API_KEY in .arbit_env)
# cp .env.local.example .env.local  → set API_BASE_URL=http://127.0.0.1:8000 and API_KEY=…
npm install
npm run dev
```

`package.json` declares **Yarn** as the package manager; `yarn install` / `yarn dev` is equivalent if you use Yarn.

The app proxies browser calls via `frontend/app/api/harmonix/...` using **`API_BASE_URL`** and **`API_KEY`** (see `frontend/.env.local.example`). No `NEXT_PUBLIC_*` keys are required for that path.

**Production-style FE** (after `npm run build`): `npm run start` (same `API_BASE_URL` / `API_KEY` rules).

---

## 6) Out of scope

- Auto execution
- Cross-exchange pair routing
- Multi-leg basket logic
- Using unrealized MTM as the headline return number
