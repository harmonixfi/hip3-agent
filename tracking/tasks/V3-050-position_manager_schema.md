# V3-050 — Position Manager schema (DB tables)

## Status: todo

## Goal
Add position-centric tables to DB v3 so we can store managed positions, legs, snapshots, and cashflows.

## Deliverables
- New schema file (preferred): `tracking/sql/schema_pm_v3.sql` (or extend `schema_v3.sql` if we want single-file)
- Tables:
  - `pm_positions`
  - `pm_legs`
  - `pm_leg_snapshots`
  - `pm_account_snapshots`
  - `pm_cashflows`
- Update `scripts/db_v3_init.py` to initialize both schemas (v3 + pm)

## Acceptance / How to verify
- `python3 scripts/db_v3_reset_backup.py` creates DB with new tables
- `sqlite3 tracking/db/arbit_v3.db ".tables"` shows the new pm_* tables
- Foreign keys work for `(venue, inst_id)` references where applicable

## Docs
- docs/POSITION_MANAGER.md
- docs/DESIGN_v3.md

## Notes
- Keep snapshots append-only.
- Store raw_json/meta_json columns for debugging when venues differ.
