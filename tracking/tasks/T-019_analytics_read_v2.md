# T-019 — Switch analytics to read DB v2

## Status: todo

## Goal
Update basis + opportunity screener to read from v2 tables (inst_id + symbol_key) instead of v1.

## Acceptance
- `python3 scripts/compute_basis.py` works on v2
- `python3 scripts/opportunity_report_public.py` works on v2
- spot↔perp section uses DB history (no live mode).

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

