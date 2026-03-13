# V3-052 Private Connectors - Implementation Checklist

## Deliverables

### 1. ✅ Create `tracking/connectors/private_base.py`
- [x] Define small interface for private connectors
- [x] `fetch_account_snapshot()` method returns normalized dict
- [x] `fetch_open_positions()` method returns normalized dict (list)
- [x] Abstract base class using ABC

### 2. ✅ Add stub modules

#### `tracking/connectors/paradex_private.py`
- [x] Load credentials from env vars (`PARADEX_PRIVATE_KEY`, `PARADEX_ACCOUNT_ADDRESS`)
- [x] Document env vars in module docstring
- [x] Raise clear exception if credentials missing
- [x] Return empty results for scaffolding

#### `tracking/connectors/hyperliquid_private.py`
- [x] Load credentials from env vars (`HYPERLIQUID_PRIVATE_KEY`, `HYPERLIQUID_ACCOUNT_ADDRESS`)
- [x] Document env vars in module docstring
- [x] Raise clear exception if credentials missing
- [x] Return empty results for scaffolding

#### `tracking/connectors/ethereal_private.py`
- [x] Load credentials from env vars (`ETHEREAL_API_KEY`, `ETHEREAL_API_SECRET`)
- [x] Document env vars in module docstring
- [x] Raise clear exception if credentials missing
- [x] Return empty results for scaffolding

#### `tracking/connectors/lighter_private.py`
- [x] Load credentials from env vars (`LIGHTER_API_KEY`, `LIGHTER_API_SECRET`)
- [x] Document env vars in module docstring
- [x] Raise clear exception if credentials missing
- [x] Return empty results for scaffolding

### 3. ✅ Implement `tracking/position_manager/puller.py`
- [x] Load managed positions from DB (pm_positions/pm_legs)
- [x] Load managed positions from registry file
- [x] Call appropriate connector per venue
- [x] Write results to `pm_account_snapshots` (append-only)
- [x] Write results to `pm_leg_snapshots` (append-only)

### 4. ✅ Add script `scripts/pull_positions_v3.py`
- [x] Runs puller once
- [x] Supports `--db` option
- [x] Supports `--registry` option
- [x] Supports `--venues` filter (comma-separated list)
- [x] Safe to run without creds (no crash)
- [x] Prints which venues are skipped

## Constraints

- [x] Do not implement full auth flows (just scaffolding + normalization + DB writes)
- [x] Keep code minimal
- [x] No external dependencies

## Acceptance Criteria

- [x] Running `python3 scripts/pull_positions_v3.py --registry config/positions.example.json` completes successfully even with no env creds
- [x] Writes zero or more snapshots without throwing
- [x] Code structured so later we can fill real API calls per venue

## Files Created

```
tracking/connectors/private_base.py          - Base interface
tracking/connectors/paradex_private.py       - Paradex connector
tracking/connectors/hyperliquid_private.py   - Hyperliquid connector
tracking/connectors/ethereal_private.py      - Ethereal connector
tracking/connectors/lighter_private.py       - Lighter connector
tracking/position_manager/puller.py          - Position puller
scripts/pull_positions_v3.py                - CLI script
scripts/init_db.py                          - DB initialization (bonus)
scripts/test_private_connectors.py           - Test script (bonus)
tracking/tasks/V3-052-summary.md             - Implementation summary
tracking/tasks/V3-052-checklist.md           - This checklist
```

## Additional Notes

- Updated `config/positions.example.json` to use supported venues (paradex, hyperliquid, ethereal, lighter)
- Unsupported venues (e.g., bybit, okx) are skipped rather than failing
- Exit code 0 = success (even if all venues skipped)
- Exit code 1 = error (unexpected failures only)
- Normalized data structures make future API integration straightforward
