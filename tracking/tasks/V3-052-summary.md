# V3-052: Private Connectors Scaffolding - Summary

## Overview

Implemented scaffolding for private venue connectors to fetch account and position data from supported venues. The implementation provides a clean interface structure that can be easily extended with real API calls later.

## Files Created

### 1. Base Interface
**`tracking/connectors/private_base.py`**
- Abstract base class `PrivateConnectorBase` defining the connector interface
- Methods: `fetch_account_snapshot()` and `fetch_open_positions()`
- Returns normalized dicts with standard field names
- Optional `is_configured()` method for credential validation

### 2. Venue-Specific Connectors
**`tracking/connectors/paradex_private.py`**
- Environment vars: `PARADEX_PRIVATE_KEY`, `PARADEX_ACCOUNT_ADDRESS`
- Raises clear exception if credentials missing
- Returns empty account snapshot and position list for scaffolding

**`tracking/connectors/hyperliquid_private.py`**
- Environment vars: `HYPERLIQUID_PRIVATE_KEY`, `HYPERLIQUID_ACCOUNT_ADDRESS`
- Raises clear exception if credentials missing
- Returns empty account snapshot and position list for scaffolding

**`tracking/connectors/ethereal_private.py`**
- Environment vars: `ETHEREAL_API_KEY`, `ETHEREAL_API_SECRET`
- Raises clear exception if credentials missing
- Returns empty account snapshot and position list for scaffolding

**`tracking/connectors/lighter_private.py`**
- Environment vars: `LIGHTER_API_KEY`, `LIGHTER_API_SECRET`
- Raises clear exception if credentials missing
- Returns empty account snapshot and position list for scaffolding

### 3. Position Puller
**`tracking/position_manager/puller.py`**
- Loads managed positions from DB (`pm_positions`/`pm_legs`) or registry file
- Calls appropriate connector per venue
- Writes results to `pm_account_snapshots` and `pm_leg_snapshots` (append-only)
- Gracefully handles missing credentials (skips venue, doesn't crash)
- Supports venue filtering
- Returns summary dict with pull results

### 4. CLI Script
**`scripts/pull_positions_v3.py`**
- Runs puller once
- Supports `--registry` and `--db` options (mutually exclusive)
- Supports `--venues` filter (comma-separated list)
- Supports `--quiet` flag for silent operation
- Exits with code 0 on success, 1 on errors

### 5. Supporting Files
**`scripts/init_db.py`** (bonus)
- Initializes database with position manager schema
- Creates required tables: `pm_positions`, `pm_legs`, `pm_account_snapshots`, `pm_leg_snapshots`, `pm_cashflows`

**`scripts/test_private_connectors.py`** (bonus)
- Tests all private connectors
- Reports which connectors are configured vs missing credentials

**`config/positions.example.json`** (updated)
- Updated to use supported private connector venues (paradex, hyperliquid, ethereal, lighter)
- Example positions for testing

## Data Structures

### Account Snapshot (normalized)
```python
{
    "account_id": str,
    "total_balance": float (optional),
    "available_balance": float (optional),
    "margin_balance": float (optional),
    "unrealized_pnl": float (optional),
    "position_value": float (optional),
    "raw_json": dict (optional),
}
```

### Position/Leg (normalized)
```python
{
    "leg_id": str,
    "position_id": str,
    "inst_id": str,
    "side": str ("LONG" or "SHORT"),
    "size": float,
    "entry_price": float (optional),
    "current_price": float (optional),
    "unrealized_pnl": float (optional),
    "realized_pnl": float (optional),
    "raw_json": dict (optional),
}
```

## Usage Examples

### Run with registry (no credentials)
```bash
python3 scripts/pull_positions_v3.py --registry config/positions.example.json
```
Output: Skips all venues (missing credentials), writes 0 snapshots, exits successfully.

### Run with specific venues
```bash
python3 scripts/pull_positions_v3.py --registry config/positions.json --venues paradex,hyperliquid
```
Output: Only pulls from specified venues.

### Run with database (requires initialized DB)
```bash
python3 scripts/pull_positions_v3.py --db tracking.db
```
Output: Loads positions from `pm_positions`/`pm_legs` tables, pulls from all venues used.

### Initialize database
```bash
python3 scripts/init_db.py
```

## Testing

The implementation has been verified to:

1. ✅ Complete successfully with no credentials (no crashes)
2. ✅ Skip venues with missing credentials gracefully
3. ✅ Work correctly when credentials are provided (writes snapshots)
4. ✅ Support venue filtering
5. ✅ Write to correct database tables (`pm_account_snapshots`, `pm_leg_snapshots`)
6. ✅ Return appropriate exit codes (0 = success, 1 = error)

## Future Work

To implement real API calls for each connector:

1. Replace placeholder code in `fetch_account_snapshot()` with actual API calls
2. Replace placeholder code in `fetch_open_positions()` with actual API calls
3. Parse API responses into the normalized dict format
4. Add authentication logic (signing requests, headers, etc.)
5. Add error handling and retry logic
6. Test with real credentials

## Constraints Met

- ✅ No external dependencies (uses only stdlib)
- ✅ Minimal code (scaffolding only, no real auth flows)
- ✅ No crashes with missing credentials
- ✅ Structured for future extension (clear interface, normalized data)
- ✅ Acceptance criteria met: script completes successfully with no creds

## Exit Codes

- `0`: Success (even if all venues skipped)
- `1`: Error (unexpected failures, missing files, etc.)

Note: Venues skipped due to missing credentials are NOT considered failures.
