# Execution Plan (phased)

## Phase A — Foundations (1–2 days)
A1. Confirm venue APIs + auth method per exchange (public vs private).
A2. Define normalized schemas + create SQLite tables.
A3. Implement minimal logging + config system.

## Phase B — Market data (2–5 days)
B1. Implement public connector for each exchange:
- instruments list
- mark/index/last
- funding rate
B2. Start continuous sampling (cron every 60m; optionally 5–15m for price/basis).

## Phase C — Basis/spread engine (2–4 days)
C1. Spot↔perp basis on OKX (and any other venue with spot + perp).
C2. Perp↔perp cross-exchange basis for shared symbols.
C3. EV model: net carry after fees + basis component.

## Phase D — Portfolio + risk (3–7 days)
D1. Authenticated account snapshot per exchange (balances/equity).
D2. Position tracking + uPnL.
D3. Liquidation price + buffer estimation.
D4. Risk alerts (margin usage, liq distance).

## Phase E — Opportunity workflow (ongoing)
E1. Ranking with stability filters + OI rank filter (1–200).
E2. Generate “trade ticket” template: legs, sizing, entry/exit, min hold time.
E3. Ping Bean with top candidates.

## Acceptance criteria (phase 1 complete)
- For at least 2 venues (OKX + Hyperliquid):
  - funding + mark prices stored in DB
  - basis computed and queryable
  - account equity + positions pulled (auth)
  - report prints top opportunities + risk status
