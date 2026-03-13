# T-003 — OKX public market-data connector

## Goal
Pull OKX instruments, mark/index/last, orderbook top, funding rate for perps.

## Data to pull
- Instrument list (perp contracts with specs)
- Funding rate (current + next funding time)
- Mark price + Index price + Last price
- Orderbook top-of-book (bid/ask for basis/slippage)

## Deliverables
- `tracking/connectors/okx_public.py`
  - Functions: get_instruments(), get_funding(), get_mark_prices(), get_orderbook()
- `scripts/pull_okx_market.py` writes into DB

## Status
✅ **Completed** (2025-01-02)

## Extensions
✅ **SPOT connector added** (see `tracking/tasks/T-015_okx_spot_connector.md`)
- Functions: get_spot_instruments(), get_spot_tickers()
- Stores with `contract_type='SPOT'`
- Enables spot↔perp basis calculations

## Acceptance
- Running script stores latest funding + mark price + orderbook for a list of symbols
- No auth required (public endpoints only)

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

