# Symbol Normalization Implementation Notes

## Date: 2025-01-20

## Overview
Implemented system-wide symbol normalization across all venues to enable cross-venue joins for arbitrage analysis.

## Canonical Standard
- **Format**: Base asset ticker only (uppercase, 2-6 characters)
- **Examples**: BTC, ETH, SOL, BERA, DOGE, 1INCH
- **Rule**: Strip quote currency suffixes (USDT, USD, USDC) and contract type suffixes (SWAP, PERP, FUTURES)

## Venue-Specific Mappings

| Venue     | Raw Format       | Canonical | Example Transformation     |
|-----------|------------------|-----------|----------------------------|
| OKX       | `BTC-USDT-SWAP`  | BTC       | Split on `-`, take first    |
| Paradex   | `BTC-USD-PERP`   | BTC       | Split on `-`, take first    |
| Ethereal  | `BTCUSD`         | BTC       | Strip `USD` suffix          |
| Lighter   | `BTC`            | BTC       | Already canonical          |
| Hyperliquid | `BTC`          | BTC       | Already canonical          |

## Files Created

### 1. `tracking/symbols.py`
Core normalization module providing:
- `normalize_symbol(venue, raw_symbol)` → canonical symbol
- `normalize_instrument_id(venue, raw_symbol)` → venue-specific ID
- `parse_base_quote(venue, raw_symbol)` → (base, quote) tuple
- Manual override mapping for edge cases
- CLI for testing: `python tracking/symbols.py <venue> <raw_symbol>`

### 2. `scripts/normalize_symbols_db.py`
Migration script for backfilling existing data:
- Updates `symbol` column in `instruments`, `funding`, and `prices` tables
- Preserves `inst_id` column with venue-specific identifiers
- Safe execution with transaction support and backup creation
- Dry-run mode: `python scripts/normalize_symbols_db.py --dry-run`
- Full migration: `python scripts/normalize_symbols_db.py`

## Files Modified

### Pull Scripts (all 5 venues)
Updated to use canonical symbols in the `symbol` column:
- `scripts/pull_okx_market.py`
- `scripts/pull_paradex_market.py`
- `scripts/pull_ethereal_market.py`
- `scripts/pull_lighter_market.py`
- `scripts/pull_hyperliquid_market.py`

**Changes in each script:**
1. Import `normalize_symbol` and `normalize_instrument_id` from `tracking.symbols`
2. Update `insert_instruments()` to use canonical symbol in `symbol` column
3. Update `insert_funding()` to use canonical symbol in `symbol` column
4. Update `insert_prices()` to use canonical symbol in `symbol` column
5. Keep `inst_id` column with the raw venue-specific identifier

### Analytics Module
- `tracking/analytics/basis.py`
  - Removed local `normalize_symbol()` method
  - Now delegates to shared `symbols.normalize_symbol()` utility

### Documentation
- `tracking/01-ARCHITECTURE.md`
  - Added "Symbol Normalization Standard" section with mapping rules and implementation details

## Database Schema

### Before Migration
- `symbol` column contained venue-specific identifiers
- Example: `instruments` table had `BTC-USDT-SWAP` for OKX, `BTC-USD-PERP` for Paradex
- Cross-venue joins failed due to mismatched symbols

### After Migration
- `symbol` column contains canonical base asset (e.g., `BTC`)
- `inst_id` column preserves venue-specific identifier
- Example:
  ```
  | venue    | symbol | inst_id              | ... |
  |----------|--------|----------------------|-----|
  | okx      | BTC    | BTC-USDT-SWAP        | ... |
  | paradex  | BTC    | BTC-USD-PERP         | ... |
  | ethereal | BTC    | abc-123-def (UUID)   | ... |
  | lighter  | BTC    | 12345 (market_id)    | ... |
  ```
- Cross-venue joins now work on `symbol` column

## Running the Migration

### Step 1: Test with Dry Run
```bash
cd /mnt/data/agents/arbit
python scripts/normalize_symbols_db.py --dry-run
```
This will show what would be changed without modifying the database.

### Step 2: Run the Migration
```bash
python scripts/normalize_symbols_db.py
```
This will:
1. Create a backup of the database with timestamp
2. Update symbols in all three tables
3. Report statistics on changes made

### Step 3: Verify
```python
import sqlite3

conn = sqlite3.connect('tracking/db/arbit.db')
cursor = conn.cursor()

# Check BERA across venues
cursor.execute("""
    SELECT venue, symbol, inst_id
    FROM instruments
    WHERE symbol = 'BERA'
    ORDER BY venue
""")
print(cursor.fetchall())

conn.close()
```

## Testing the Normalization

### Test Individual Symbols
```bash
python tracking/symbols.py okx BTC-USDT-SWAP
python tracking/symbols.py paradex BTC-USD-PERP
python tracking/symbols.py ethereal BTCUSD
python tracking/symbols.py lighter BTC
python tracking/symbols.py hyperliquid BTC
```

### Test All Pull Scripts
After running the migration, new data pulls will use canonical symbols:
```bash
python scripts/pull_okx_market.py
python scripts/pull_paradex_market.py
python scripts/pull_ethereal_market.py
python scripts/pull_lighter_market.py
python scripts/pull_hyperliquid_market.py
```

## Benefits

1. **Cross-Venue Joins**: Shared symbols enable joining data across venues for arbitrage analysis
2. **Consistent Analytics**: Basis computation and opportunity screening now work correctly
3. **Venue Preservation**: Original identifiers preserved in `inst_id` for API calls and debugging
4. **Maintainable**: Single source of truth for symbol normalization rules
5. **Extensible**: Easy to add new venues with custom parsing rules

## Edge Cases and Overrides

The `SYMBOL_OVERRIDES` dict in `symbols.py` can be used for special cases:
```python
SYMBOL_OVERRIDES: Dict[Tuple[str, str], str] = {
    ("okx", "1INCH-USDT-SWAP"): "1INCH",
    # Add more as needed
}
```

Use `add_override()` function to add overrides at runtime:
```python
from symbols import add_override
add_override("okx", "1INCH-USDT-SWAP", "1INCH")
```

## Rollback

If issues occur after migration, restore from the backup:
```bash
# Find the backup file
ls tracking/db/arbit_backup_*.db

# Restore
cp tracking/db/arbit_backup_YYYYMMDD_HHMMSS.db tracking/db/arbit.db
```
