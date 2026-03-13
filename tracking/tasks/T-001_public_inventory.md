# T-001 — Inventory public endpoints per venue

## Goal
List all public endpoints needed for each venue (OKX, Hyperliquid, Paradex, Lighter, Ethereal):
- Instruments (perps list, tick size, contract specs)
- Funding rate (current + next funding time if available)
- Mark price / Index price / Last price
- Orderbook (top of book for basis/slippage estimation)

## Deliverables
- `tracking/docs/api-inventory-public.md` with:
  - For each venue: base URL, auth required (public = none), rate limits
  - Endpoints: instruments, funding, mark/index/last, orderbook
  - Notes: data format, quirks (e.g., symbol format, tick size)

## Acceptance
- Document includes all 5 venues (OKX / Hyperliquid / Paradex / Lighter / Ethereal)

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

