# V3-010 — OKX connector normalized outputs (v3)

## Status: done


## Status: todo

## Goal
Normalize OKX spot+perp instruments/prices/funding into v3-ready records.

## Deliverables
- Connector functions returning normalized structures for:
  - instruments (spot + perp)
  - prices (spot tickers + perp mark/last)
  - funding (perp)

## Acceptance / How to verify
- Unit tests for parsing:
  - BTC-USDT (SPOT) vs BTC-USDT-SWAP (PERP) map to distinct inst_id
  - base/quote and symbol_key are correct

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/okx.md
- docs/quote_aware_matching.md
CompletedAt: 2026-02-08 04:34:48Z
CompletionNote: okx normalization tests pass
