# T-017 — Migrate + backfill into v2 tables + keep v1 read-only

## Status: done ✅

## Goal
Harden v2 migration/backfill so v2 tables are consistent and complete enough for analytics.

## Acceptance
- `python3 scripts/migrate_db_v2.py` exits 0
- `python3 scripts/verify_db_v2.py` exits 0
- v2 tables populated and growing with ingestion writes (no collisions).

## Notes
- v1 tables remain for audit; new ingestion should write v2.

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

