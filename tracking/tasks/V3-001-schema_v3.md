# V3-001 — Finalize schema_v3.sql (instrument-centric)

## Status: done

## Goal
Create an instrument-centric, quote-aware schema v3 so spot↔perp history and cross-venue joins are correct.

## Deliverables
- `tracking/sql/schema_v3.sql`
- v3 tables: `instruments_v3`, `prices_v3`, `funding_v3` (+ optional `orderbook_top_v3`)

## Acceptance / How to verify
- `python3 scripts/db_v3_init.py` succeeds
- PK constraints:
  - instruments: (venue, inst_id)
  - time series: (venue, inst_id, ts)

## QC / Real-world cases considered
- SQLite foreign key enforcement is **per-connection** → init/verify scripts explicitly enable `PRAGMA foreign_keys=ON`.
- Append-only time series with strict PK `(venue, inst_id, ts)` to prevent duplicates in cron runs.
- Quote-aware joins via `symbol_key = BASE:QUOTE` and cross-venue joins via `symbol_base = BASE`.

## Docs
- tracking/PROJECT_STRUCTURE.md
- docs/DESIGN_v3.md
- docs/CONVENTIONS.md
- docs/CONNECTORS.md
- docs/RUNBOOK.md

CompletedAt: 2026-02-08
CompletionNote: schema_v3.sql created + db_v3_init verified
