# V3-003 — Verify suite for DB v3 invariants

## Status: done

## Goal
Add an invariant checker so we never silently break symbol keys / inst_id uniqueness.

## Deliverables
- `scripts/verify_db_v3.py`

## Acceptance / How to verify
- `python3 scripts/verify_db_v3.py` passes on a freshly initialized DB
- Invariants enforced:
  - symbol_key contains ':'
  - no inst_id collisions between OKX spot/perp when present

## QC / Real-world cases considered
- Runs with `PRAGMA foreign_keys=ON` to catch broken references.
- Fails fast on missing tables and malformed `symbol_key`.
- Collision check for OKX spot vs perp inst_id when those rows exist.

## Docs
- docs/CONVENTIONS.md
- docs/DESIGN_v3.md

CompletedAt: 2026-02-08
CompletionNote: verify_db_v3 implemented + passes on fresh DB
