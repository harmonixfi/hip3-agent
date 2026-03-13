# V3-054 — Cashflow ledger (realized funding/fees)

## Status: todo

## Goal
Track realized funding and fees so we can compare expected vs realized and compute true carry.

## Deliverables
- Table writes into `pm_cashflows`
- Parsers per venue for funding payments (and fees if available)
- Daily rollup report per position:
  - realized funding 24h / 7d
  - fees
  - net realized carry

## Acceptance / How to verify
- Can ingest at least 1 venue’s funding payment history
- Reconcile realized funding against position notional directionally (sanity checks)

## Docs
- docs/POSITION_MANAGER.md

## Notes
- Don’t overfit early; get funding ledger correct first.
