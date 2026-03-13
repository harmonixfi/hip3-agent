# T-004 — Hyperliquid public market-data connector

## Goal
Pull Hyperliquid perps mark price + funding (and next funding info if available).

## Data to pull
- Instrument list (perp contracts)
- Funding rate (current + next funding time)
- Mark price + Index price + Last price
- Orderbook (bid/ask mid for basis)

## Deliverables
- `tracking/connectors/hyperliquid_public.py`
  - Functions: get_instruments(), get_funding(), get_mark_prices(), get_orderbook()
- `scripts/pull_hyperliquid_market.py`

## Acceptance
- Script stores latest funding + mark price + orderbook for a list of symbols
- No auth required (public endpoints only)

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

