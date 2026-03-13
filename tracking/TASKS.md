# Task List — Funding Arb System (Legacy v1/v2)

NOTE: Paused. See tracking/TASKS_v3.md for the new reset plan.

# Task List — Funding Arb System (Reprioritized)

## P0 — Data correctness (must fix)
**T-016** — DB redesign (v2) instrument-centric schema for spot↔perp history + correct joins — ✅
- Rationale: current `(venue, symbol, ts)` design collides SPOT vs PERP and loses quote.

**T-017** — Migrate + backfill into v2 tables + keep old tables read-only (compat) — 🟧 IN PROGRESS
**T-018** — OKX ingestion writes to DB v2 (spot+perp history) — NEXT
**T-019** — Switch analytics to read DB v2 — NEXT
**T-020** — Port other venue ingestions to DB v2 (HL/Paradex/Lighter/Ethereal) — NEXT

## P1 — Ingestion completeness
**T-001** — Inventory public endpoints per venue — ✅
**T-002** — SQLite schema (v1) — ✅ (superseded by v2)

**T-003** — OKX public connector (PERP) — ✅
**T-015** — OKX SPOT connector (public) — ✅ (but needs v2 storage)

**T-004** — Hyperliquid public connector — ✅
**T-005** — Paradex public connector — ✅ (funding+prices via WS; needs v2 storage)
**T-006** — Lighter public connector — ✅ (REST-limited; needs v2 storage)
**T-007** — Ethereal public connector — ✅ (REST-limited; needs v2 storage)

## P2 — Analytics (v2-backed)
**T-008** — Basis/spread engine (public) — ✅ (needs switch to v2)
**T-009** — Opportunity screener (public) — ✅ (needs switch to v2 + spot↔perp history)

## P3 — Automation
**T-010** — Cron jobs public pulls — ✅ (update commands if migration changes paths)

## P4 — Private (requires API key — later)
**T-011** — Portfolio/risk snapshots
**T-012** — Private connectors (OKX auth, then other venues)
**T-013** — PnL tracking + liquidation alerts
**T-014** — Full opportunity workflow

---
### Notes
- After v2 migration, all analytics should read from v2 tables. v1 tables remain for audit until we purge.

