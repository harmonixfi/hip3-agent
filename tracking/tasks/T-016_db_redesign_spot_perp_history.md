# T-016 — DB Redesign (v2) for Spot↔Perp History + Correct Joins

## Why
Current schema keys `prices` and `funding` by `(venue, symbol, ts)` where `symbol` is canonical base-only (BTC/ETH…). This breaks:
- spot↔perp history (spot and perp overwrite each other)
- multi-quote markets (BTC-USDT vs BTC-USD vs BTC-AUD)
- correct pairing for spot↔perp carry

## Goal
Introduce an instrument-centric schema so we can store history per **venue instrument** (including base/quote + contract_type) and join reliably.

## Deliverables
- New schema file: `tracking/sql/schema_v2.sql`
- Migration script: `scripts/migrate_db_v2.py`
  - Creates new tables
  - Backfills from existing tables where possible
  - Adds indexes
- Update ingestion scripts to write to v2 tables
- Update analytics (basis + screener) to read v2

## Proposed Schema (v2)
### instruments_v2
- venue
- inst_id (venue-specific, unique per venue)
- base
- quote
- contract_type (SPOT/PERP)
- symbol_base (canonical base-only, for perp↔perp joins)
- symbol_key (base-quote, for spot↔perp joins)
- funding_interval_hours
- created_at

Unique: (venue, inst_id)

### prices_v2
- ts
- venue
- inst_id
- bid/ask/mid/last/mark/index

Unique: (venue, inst_id, ts)

### funding_v2
- ts
- venue
- inst_id
- funding_rate
- funding_interval_hours
- next_funding_ts

Unique: (venue, inst_id, ts)

## Acceptance Criteria

Status: DONE ✅ (schema_v2.sql + migrate + verify implemented)
- ✅ OKX stores both BTC-USDT (SPOT) and BTC-USDT-SWAP (PERP) histories without collisions.
- ✅ Spot↔perp screener can compute 7D/14D funding stability using DB history.
- ✅ Perp↔perp screener continues to work.

---

## Completion
Status: done ✅

All deliverables completed:
- Schema v2 created (`tracking/sql/schema_v2.sql`)
- Migration script created (`scripts/migrate_db_v2.py`)
- Verification script created (`scripts/verify_db_v2.py`)
- Tests passing: 1,454 instruments, 7,744 prices, 6,183 funding rows
- SPOT vs PERP distinction working correctly

Next: T-017 (migrate+backfill into v2 tables + keep old tables read-only)

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

