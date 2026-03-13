# V3-020 — Cost model v3

## Status: done


## Status: todo

## Goal
Cost model used by screeners: fees + cross-spread/slippage (with flags).

## Deliverables
- `tracking/analytics/cost_model_v3.py`
- `config/fees.json` (if not exists)

## Acceptance / How to verify
- Unit tests for:
  - fee lookup
  - spread cost uses bid/ask when present else proxy+flag

## Docs
- docs/CONVENTIONS.md
CompletedAt: 2026-02-08 06:32:37Z
CompletionNote: cost_model_v3 ok
