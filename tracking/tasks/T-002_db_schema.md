# T-002 — SQLite schema for public data

## Goal
Create SQLite DB with normalized tables for public market data (funding, prices, basis).

## Tables
- `instruments`: venue, symbol, contract_size, tick_size, funding_interval, created_at
- `funding`: ts, venue, symbol, funding_rate, interval, next_funding_ts
- `prices`: ts, venue, symbol, mark_price, index_price, last_price, bid, ask, mid
- `basis`: ts, symbol, leg_a_venue, leg_b_venue, basis_spread, annualized_basis_pct

## Deliverables
- `tracking/db/arbit.db` (created)
- `tracking/sql/schema.sql`
- `scripts/db_init.py` to initialize DB

## Acceptance
- Can insert + query 1 funding row + 1 price row + 1 basis row

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

