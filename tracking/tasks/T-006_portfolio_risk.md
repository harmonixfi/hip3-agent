# T-006 — Portfolio + risk snapshots

## Goal
Pull (auth) balances/equity + positions/margin and compute:
- uPnL
- margin usage
- liquidation distance

## Deliverables
- `tracking/portfolio/` module
- `scripts/pull_accounts.py`
- `scripts/risk_report.py`

## Acceptance
- For at least 1 venue, script outputs: equity, positions, uPnL, liq price (or best available proxy) and flags low buffer.

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

