# Funding Arb System — Overview

## Goal
Build a **first-party** data + risk system (no Loris dependency) that:
1) Pulls funding/price/orderbook/mark/index data directly from exchanges
2) Computes **basis/spread** (spot↔perp, perp↔perp cross-exchange) + expected net carry
3) Tracks portfolio (balances/positions/margin) + estimates liquidation buffers
4) Produces actionable **trade plans** + alerts (ping Bean)

## Scope (current venues)
- OKX
- Hyperliquid (HyENA)
- Paradex
- Lighter
- Ethereal

## Non-goals (for now)
- Auto-execution (phase 2)

## Key outputs
- Normalized time-series store (funding, prices, basis)
- Portfolio snapshots + PnL report
- Risk dashboard (margin usage, liquidation distance)
- Opportunity ranking with stability metrics
