# T-016: Database v2 Schema & Migration

## Overview

Implemented v2 database schema to properly handle instrument identity, allowing venues like OKX to have both SPOT and PERP instruments with the same base/quote pair (e.g., BTC-USDT and BTC-USDT-SWAP).

## Key Changes

### Schema Design (`tracking/sql/schema_v2.sql`)

**instruments_v2**
- Primary key: `(venue, inst_id)` - uniquely identifies each instrument
- Added columns:
  - `base`: Base asset (e.g., BTC, ETH)
  - `quote`: Quote asset (e.g., USDT, USDC) - NULL for USD-margined perps
  - `symbol_base`: Normalized base symbol for lookups
  - `symbol_key`: Composite key for joins (e.g., "BTC:USDT" or "BTC:PERP")

**prices_v2**
- Primary key: `(venue, inst_id, ts)` - joins to instruments_v2 via inst_id
- Same columns as v1, but uses inst_id instead of symbol

**funding_v2**
- Primary key: `(venue, inst_id, ts)` - joins to instruments_v2 via inst_id
- Same columns as v1, but uses inst_id instead of symbol

### Migration Script (`scripts/migrate_db_v2.py`)

**Features:**
- Creates v2 tables if they don't exist
- Deduplicates v1 instruments (same venue/inst_id with latest created_at)
- Parses OKX inst_id to extract base/quote:
  - SPOT: `BTC-USDT` → base=BTC, quote=USDT
  - PERP: `BTC-USDT-SWAP` → base=BTC, quote=USDT
  - USD-margined: `BTC-USD-SWAP` → base=BTC, quote=NULL, symbol_key=BTC:PERP
- Backfills prices_v2 and funding_v2 using symbol_base mapping
- Reports ambiguous mappings (same symbol for multiple instruments)

**Migration Results:**
- Instruments: 17,419 → 1,454 (deduplicated)
- Prices: 9,266 → 7,744
- Funding: 6,705 → 6,183

### Verification Script (`scripts/verify_db_v2.py`)

**Verifies:**
1. OKX has both BTC-USDT (SPOT) and BTC-USDT-SWAP (PERP) as distinct rows ✓
2. Latest prices_v2 rows exist for each instrument
3. symbol_key is correctly populated for lookups
4. Statistics and coverage metrics

## Key Insight

**OKX SPOT vs PERP Distinction:**
```
inst_id: BTC-USDT         type: SPOT  base: BTC  quote: USDT  symbol_key: BTC:USDT
inst_id: BTC-USDT-SWAP    type: PERP  base: BTC  quote: USDT  symbol_key: BTC:USDT
```

Both have the same `symbol_key` (BTC:USDT) but are distinguished by:
- Different `inst_id`
- Different `contract_type`
- UNIQUE constraint on `(venue, inst_id)`

This allows arbitrage analysis between SPOT and PERP on the same venue!

## Usage

```bash
# Run migration
python3 scripts/migrate_db_v2.py

# Verify migration
python3 scripts/verify_db_v2.py
```

## Next Steps

- Refactor ingestion scripts to populate v2 tables
- Update analytics queries to use inst_id joins
- Add basis/spread analysis for SPOT vs PERP on same venue
- Consider migration strategy for production data

## Notes

- v1 tables remain untouched (no DROP statements)
- Migration is idempotent (safe to re-run)
- Duplicate v1 instruments are consolidated by taking latest created_at
- Some prices/funding rows may be unmigrated if symbol_base mapping fails
