# V3-011 — OKX writer → v3 tables (append-only)

## Status: done


## Status: todo

## Goal
Write OKX normalized outputs into v3 DB append-only and idempotent.

## Deliverables
- `tracking/writers/okx_v3_writer.py` (or similar)
- Inserts idempotent by PK:
  - (venue, inst_id) instruments
  - (venue, inst_id, ts) prices/funding

## Acceptance / How to verify
- Running writer twice does not duplicate rows
- `verify_db_v3.py` passes after ingestion

## Docs
- docs/DESIGN_v3.md
- docs/CONVENTIONS.md
- docs/CONNECTORS.md
CompletedAt: 2026-02-08 04:45:33Z
CompletionNote: okx v3 ingestion+verify ok
