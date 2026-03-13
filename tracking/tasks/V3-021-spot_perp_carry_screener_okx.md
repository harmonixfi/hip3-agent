# V3-021 — SPOT↔PERP Carry screener (OKX)

## Status: done


## Status: todo

## Goal
v3-backed carry screener: long spot + short perp (default), join by symbol_key.

## Deliverables
- `tracking/analytics/spot_perp_carry_v3.py`
- report script (TBD)

## Acceptance / How to verify
- Produces: breakeven, 7D/14D PnL + APR for top N
- Rejects/flags bad joins (quote mismatch)

## Docs
- docs/DESIGN_v3.md
- docs/CONVENTIONS.md
- docs/quote_aware_matching.md
CompletedAt: 2026-02-08 07:06:18Z
CompletionNote: spot_perp_screener_v3 ok
