# V3-056 — CLI (Position Manager)

## Status: todo

## Goal
Provide a simple CLI to query managed positions, risk, carry, and alerts.

## Deliverables
- Script: `scripts/pm.py` with subcommands:
  - `list`, `show <position_id>`, `alerts`, `export`
- JSON output mode for scripting
- Uses DB v3 + pm_* tables

## Acceptance / How to verify
- `python3 scripts/pm.py list` prints a positions rollup
- `python3 scripts/pm.py show <id>` prints leg breakdown + risk metrics

## Docs
- docs/RUNBOOK.md
- docs/POSITION_MANAGER.md
