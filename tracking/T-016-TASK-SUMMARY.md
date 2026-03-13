# T-016 Task Summary: DB Redesign (v2) + Initial Migration Scaffolding

## ✅ Completed

### 1. Schema v2 (`tracking/sql/schema_v2.sql`)
Created new schema with tables:
- **instruments_v2**: PRIMARY KEY (venue, inst_id)
  - Columns: venue, inst_id, base, quote, contract_type, symbol_base, symbol_key, tick_size, contract_size, funding_interval_hours, created_at
  - UNIQUE constraint on (venue, inst_id) ensures no duplicates
  - Indexes on symbol_key, (base, quote), (venue, base)

- **prices_v2**: PRIMARY KEY (venue, inst_id, ts)
  - Columns: venue, inst_id, bid, ask, mid, mark_price, index_price, last_price, ts
  - Indexes on (venue, inst_id, ts) and ts

- **funding_v2**: PRIMARY KEY (venue, inst_id, ts)
  - Columns: venue, inst_id, funding_rate, funding_interval_hours, next_funding_ts, ts
  - Indexes on (venue, inst_id, ts) and ts

### 2. Migration Script (`scripts/migrate_db_v2.py`)
Features:
- Creates v2 tables if not exist
- Deduplicates v1 instruments (17,419 → 1,454 unique)
- Parses OKX inst_id to extract base/quote:
  - SPOT: `BTC-USDT` → base=BTC, quote=USDT
  - PERP: `BTC-USDT-SWAP` → base=BTC, quote=USDT
  - USD-margined: `BTC-USD-SWAP` → base=BTC, quote=NULL, symbol_key=BTC:PERP
- Backfills prices_v2 (9,266 → 7,744) and funding_v2 (6,705 → 6,183)
- Prints counts and warnings for ambiguous mappings

### 3. Verification Script (`scripts/verify_db_v2.py`)
Verifies:
- ✓ OKX has BOTH BTC-USDT SPOT and BTC-USDT-SWAP PERP as distinct rows
- ✓ Latest prices_v2 rows exist for each instrument
- ✓ symbol_key is correctly populated
- ✓ Shows statistics: 1,454 instruments, 7,744 prices, 6,183 funding rows
- ✓ Price coverage: 727/1,454 instruments (50%)

## Key Achievement

**SPOT vs PERP Distinction Working:**
```
inst_id: BTC-USDT         type: SPOT  base: BTC  quote: USDT  symbol_key: BTC:USDT
inst_id: BTC-USDT-SWAP    type: PERP  base: BTC  quote: USDT  symbol_key: BTC:USDT
```

- Different `inst_id` values ensure uniqueness
- Same `symbol_key` enables cross-product analysis
- Different `contract_type` enables SPOT vs PERP arbitrage

## Files Created

1. `/mnt/data/agents/arbit/tracking/sql/schema_v2.sql` (3.1 KB)
2. `/mnt/data/agents/arbit/scripts/migrate_db_v2.py` (12.6 KB)
3. `/mnt/data/agents/arbit/scripts/verify_db_v2.py` (6.6 KB)
4. `/mnt/data/agents/arbit/tracking/T-016-V2-MIGRATION.md` (documentation)

## Test Results

```bash
$ python3 scripts/migrate_db_v2.py
Instruments: 17,419 → 1,454 (skipped 0)
Prices:      9,266 → 7,744 (skipped 1,522)
Funding:     6,705 → 6,183 (skipped 522)

$ python3 scripts/verify_db_v2.py
✓ OKX has BOTH BTC-USDT SPOT and BTC-USDT-SWAP PERP as distinct rows!
✓ UNIQUE constraint working correctly (no duplicates)
```

## What Was NOT Done

As per task requirements:
- Did not refactor all ingestion/analytics scripts (future work)
- v1 tables remain untouched (no DROP statements)
- Migration is standalone and idempotent

## Next Steps (Future Work)

- Refactor ingestion scripts (pull_okx_market.py, etc.) to populate v2 tables
- Update analytics queries to use inst_id joins
- Add SPOT vs PERP basis analysis for same venue
- Plan production data migration strategy
