# V3-053 — Risk engine (delta drift, liq buffer, stress tests)

## Status: todo

## Goal
Compute actionable risk metrics per managed position and generate recommended actions.

## Deliverables
- Module: `tracking/position_manager/risk.py`
- Metrics:
  - gross notional, net delta USD, drift %
  - per-leg and per-position buffer-to-liquidation (%)
  - stress tests (±5%, ±10%) approximate
  - reconciliation flags (registry vs venue truth)
- Rollup output (JSON) for UI + CLI

## Acceptance / How to verify
- Given mocked snapshots, risk engine outputs consistent drift/buffer
- Unit tests for drift sign + buffer computation
- Produces WARN/CRIT/EMERGENCY flags based on thresholds

## Docs
- docs/POSITION_MANAGER.md

## Notes
- Keep formulas explicit and tested; wrong sign here = disaster.
