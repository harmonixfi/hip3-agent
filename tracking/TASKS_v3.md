# Task Board (v3 Reset Plan)

## Goal
Rebuild the system around an **instrument-centric DB v3** (venue+inst_id+ts) so SPOT↔PERP history and cross-venue joins are correct, scalable, and testable.

## P0 — DB v3 Foundations (must)
**V3-001** — Finalize schema_v3.sql (instrument-centric)
- instruments_v3 (venue, inst_id PK; base, quote, contract_type; symbol_key, symbol_base; specs)
- prices_v3 (venue, inst_id, ts PK)
- funding_v3 (venue, inst_id, ts PK)
- optional: orderbook_top_v3

**V3-002** — DB init + migrations tooling
- scripts/db_v3_init.py
- scripts/db_v3_reset_backup.py (backup old DB, create fresh v3)

**V3-003** — Verify suite for DB invariants
- scripts/verify_db_v3.py
- invariants:
  - OKX BTC-USDT spot and BTC-USDT-SWAP perp distinct inst_id
  - no collisions between spot/perp
  - quote-aware keys exist

## P1 — Ingestion (OKX first)
**V3-010** — OKX connector normalized outputs
- instruments: spot+perp
- prices: spot tickers + perp mark/tickers
- funding: perp funding

**V3-011** — OKX writer → v3 tables (append-only)
- idempotent insert by (venue, inst_id, ts)
- cron-friendly

**V3-012** — OKX backfill (minimal)
- backfill funding history (via OKX endpoints if possible, else Loris fallback)
- store as funding_v3

## P2 — Analytics (v3-backed)
**V3-020** — Cost model v3
- fee schedule + cross-spread; proxy only when missing; flags

**V3-021** — SPOT↔PERP Carry screener (OKX) ✅
- pair by symbol_key
- default: long spot + short perp
- stability: 7D/14D avg + consistency
- outputs: breakeven, 7D/14D PnL + APR
- Script: tracking/analytics/spot_perp_screener_v3.py

**V3-022** — PERP↔PERP Extreme screener (cross-venue) ✅
- pair by symbol_base (+ quote compat)
- outputs: funding pnl + flags
- Script: tracking/analytics/perp_perp_screener_v3.py

## P3 — Expand Venues (Ingestion via Linux Crontab)
**✅ Implemented via Linux crontab (hourly):**
- Paradex: `scripts/pull_paradex_v3.py` → reports to Discord #funding-arbit
- Ethereal: `scripts/pull_ethereal_v3.py` → reports to Discord #funding-arbit
- Hyperliquid: `scripts/pull_hyperliquid_v3.py` → reports to Discord #funding-arbit
- Lighter: `scripts/pull_lighter_v3.py` → reports to Discord #funding-arbit

## P4 — Automation (All via Linux Crontab) ✅

### Data Pulls (hourly)
**All venues via Linux crontab:**
- `:00` — Loris funding pull → `logs/pull_loris_funding.log`
- `:05` — OKX pull → `logs/pull_okx_v3.log`
- `:10` — Paradex pull → `logs/pull_paradex_v3.log`
- `:15` — Ethereal pull → `logs/pull_ethereal_v3.log`
- `:20` — Hyperliquid pull → `logs/pull_hyperliquid_v3.log`
- `:25` — Lighter pull → `logs/pull_lighter_v3.log`

### Screeners (hourly)
**V3-040** — Screener pipeline (v3) ✅
- runs analytics → report opportunities
- hourly execution via Linux crontab (:30)
- alerts: opportunities found + failures only

**Implementation:**
- Script: `scripts/run_screeners_v3.py` (runs both screeners)
- Setup: Run `bash scripts/setup_crontab.sh`
- Output: tracking/reports/ + logs/run_screeners_v3.log

## P5 — Position Management (delta-neutral monitoring) [NEW]
**Goal:** move from “signal discovery” → “open position monitoring + actions”.

**V3-050** — Position Manager schema (DB tables)
- add position-centric tables: positions, legs, snapshots, cashflows
- keep append-only snapshots

**V3-051** — Position Registry + CRUD
- manage "what positions we track" (manual config + DB)
- link multi-leg strategies across venues

**V3-052** — Private connectors (positions/balances/margin)
- implement per-venue authenticated pulls (start with OKX or Hyperliquid)

**V3-053** — Risk engine (delta drift, liq buffer, stress tests)
- compute metrics per position
- produce recommended actions

**V3-054** — Cashflow ledger (realized funding/fees)
- store realized funding payments + fees
- reconcile expected vs realized

**V3-055** — Alert engine + routing policy
- severity levels + templates
- anti-spam + quiet hours

**V3-056** — CLI (query positions + export)
- `pm list / pm show / pm alerts / pm export`

**V3-057** — UI MVP (dashboard)
- Streamlit-first dashboard (positions table + detail view)

## Testing / Validation (always-on)
- Funding sign convention tests
- Fee/spread cost sanity
- Loris cross-check for a few symbols (BERA etc.)
- Position reconciliation: internal registry vs venue truth

---
Status: active

## New Tasks (2026-02-21)

**TASK-058** — Lighter readonly token integration ✅ DONE
- Check Lighter SDK/docs for readonly token usage ✅
- Update `lighter_private.py` to use readonly token instead of auth token ✅
- Token stored in env: `LIGHTER_READONLY_TOKEN` ✅
- Test funding history API works ✅

**TASK-059** — Fix SUI Hyena funding sign
- Investigate: Hyena shows +$8.16 earned, DB shows -$8.16 (paid)
- Root cause: sign convention in cumFunding field
- For SHORT positions: negative cumFunding = we're earning (short receives funding)
- Update connector or cashflow recording to fix sign
- Verify with actual API data

Docs:
- tracking/PROJECT_STRUCTURE.md
- docs/DESIGN_v3.md
- docs/POSITION_MANAGER.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
