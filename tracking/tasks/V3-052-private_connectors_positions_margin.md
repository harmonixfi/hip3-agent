# V3-052 — Private connectors (positions/balances/margin)

## Status: todo

## Goal
Implement authenticated pulls to fetch account snapshots: balances, open positions, margin/liquidation fields.

## Deliverables
- Per-venue private connector modules:
  - `tracking/connectors/okx_private.py`
  - `tracking/connectors/hyperliquid_private.py`
  - `tracking/connectors/paradex_private.py`
  - `tracking/connectors/lighter_private.py`
  - `tracking/connectors/ethereal_private.py`
- Normalized outputs:
  - account snapshot
  - positions list (inst_id, side, qty, entry, mark, uPnL, liq price if available)
- Config support for API keys (no hardcoding)

## Acceptance / How to verify
- For at least 1 venue: can pull and print open positions + margin metrics
- Store snapshots into `pm_account_snapshots` / `pm_leg_snapshots`
- Handles API failures gracefully + logs errors

## Docs
- docs/CONNECTORS.md
- docs/POSITION_MANAGER.md

## Notes
- Priority order (Bean): **Paradex → Hyperliquid → Ethereal → Lighter**.
- We’ll build a shared interface + stubs first, then fill auth details venue-by-venue.
