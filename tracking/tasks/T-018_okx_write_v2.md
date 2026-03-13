# T-018 — OKX ingestion writes to DB v2 (spot+perp history)

## Status: todo

## Goal
Write OKX spot+perp instruments/prices/funding into v2 tables keyed by `(venue, inst_id, ts)`.

## Acceptance
- Running OKX pull populates:
  - `instruments_v2` with both `BTC-USDT` (SPOT) and `BTC-USDT-SWAP` (PERP)
  - `prices_v2` rows for both inst_ids with same ts range
  - `funding_v2` rows for perp inst_ids
- Verify script demonstrates spot↔perp history exists for BTC/ETH/SOL.

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

