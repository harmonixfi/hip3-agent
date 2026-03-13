# V3-002 — DB init + reset/backup tooling

## Status: done

## Goal
Provide safe tools to initialize and reset the v3 sqlite DB.

## Deliverables
- `scripts/db_v3_init.py`
- `scripts/db_v3_reset_backup.py`
- default db: `tracking/db/arbit_v3.db`

## Acceptance / How to verify
- `python3 scripts/db_v3_init.py` creates tables from `tracking/sql/schema_v3.sql`
- `python3 scripts/db_v3_reset_backup.py` backs up existing db and recreates a fresh v3 db

## QC / Real-world cases considered
- Reset tool preserves the `--db` path (no accidental reset of wrong file).
- Backup uses timestamped suffix to avoid overwriting previous backups.
- Safe to run repeatedly (idempotent).

## Docs
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

CompletedAt: 2026-02-08
CompletionNote: init + reset/backup scripts verified
