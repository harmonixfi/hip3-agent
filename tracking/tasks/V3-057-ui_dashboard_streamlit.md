# V3-057 — UI MVP (Streamlit dashboard)

## Status: todo

## Goal
Ship a minimal UI to view open positions, risk, and carry at a glance.

## Deliverables
- Streamlit app (suggested path): `ui/streamlit_app.py`
- Views:
  - Positions table (rollup)
  - Position detail (legs + buffer/carry history)
  - Recent alerts
- Runs locally against SQLite

## Acceptance / How to verify
- `streamlit run ui/streamlit_app.py` opens dashboard
- Shows latest pm snapshots + derived metrics

## Docs
- docs/POSITION_MANAGER.md
- docs/RUNBOOK.md

## Notes
- Start simple; correctness > pretty.
