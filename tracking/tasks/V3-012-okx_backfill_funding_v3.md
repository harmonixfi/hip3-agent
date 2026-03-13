# V3-012 — OKX backfill funding history (minimal)

## Status: done


## Status: todo

## Goal
Backfill funding history for OKX perps into `funding_v3`.

## Deliverables
- `scripts/backfill_okx_funding_v3.py`
- Uses OKX history endpoint if possible; fallback to Loris if needed

## Acceptance / How to verify
- For a sample instrument, funding_v3 has multiple historical points
- 7D/14D averages can be computed from v3 DB

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
CompletedAt: 2026-02-08 05:57:21Z
CompletionNote: okx backfill from loris ok
