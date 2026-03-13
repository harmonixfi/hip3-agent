# T-005 — Basis/spread engine

## Goal
Compute:
- spot↔perp basis (where spot is available)
- perp↔perp cross-exchange spread for shared symbols

## Deliverables
- `tracking/analytics/basis.py`
- `scripts/compute_basis.py` writes to DB

## Acceptance
- For a chosen symbol, basis is computed and stored with timestamp.

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

