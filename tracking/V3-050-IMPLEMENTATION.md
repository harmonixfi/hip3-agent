# V3-050 Implementation Summary

## What Changed

### 1. New Schema File
**File:** `tracking/sql/schema_pm_v3.sql`

Created Position Manager schema with 5 tables:
- **pm_positions** - Main position tracking table
- **pm_legs** - Individual legs of positions
- **pm_leg_snapshots** - Append-only historical snapshots of leg state
- **pm_account_snapshots** - Append-only account state snapshots
- **pm_cashflows** - Financial event records (pnl, fees, funding, transfers)

All tables include:
- `raw_json TEXT` - Original API response JSON
- `meta_json TEXT` - Metadata (tags, notes, etc.)
- Helpful indexes on `position_id`, `ts`, `venue`, and other key fields

### 2. Updated Initialization Script
**File:** `scripts/db_v3_init.py`

Modified to apply BOTH schema files:
- Reads `schema_v3.sql` (core tables)
- Reads `schema_pm_v3.sql` (position manager tables)
- Combines and executes together in a single transaction

### 3. Updated Verification Script
**File:** `scripts/verify_db_v3.py`

Extended to assert all `pm_*` tables exist:
- `pm_positions`
- `pm_legs`
- `pm_leg_snapshots`
- `pm_account_snapshots`
- `pm_cashflows`

### 4. No Changes Needed
**File:** `scripts/db_v3_reset_backup.py`

Already calls `db_v3_init.py`, so automatically applies both schemas.

## How to Verify

Run the smoke tests:
```bash
python3 scripts/db_v3_reset_backup.py
python3 scripts/verify_db_v3.py
```

Expected output:
- `db_v3_reset_backup.py`: Backs up old DB and re-initializes with both schemas
- `verify_db_v3.py`: Prints `OK: verify_db_v3 passed`

## Database Structure

Created 19 indexes for optimal query performance:
- **pm_positions**: venue, status, created_at_ms
- **pm_legs**: position_id, venue+inst_id, status
- **pm_leg_snapshots**: leg_id, position_id, ts, venue
- **pm_account_snapshots**: venue, account_id, ts, venue+ts
- **pm_cashflows**: position_id, leg_id, venue, account_id, ts, venue+ts, cf_type

All snapshot tables are append-only with INTEGER PRIMARY KEY AUTOINCREMENT for insert efficiency.
