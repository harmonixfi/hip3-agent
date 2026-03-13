# V3-053 Risk Engine MVP

## Summary

Implemented MVP risk engine for computing delta drift and basic risk flags from managed positions + latest snapshots.

## Files Created

1. **`tracking/position_manager/risk.py`** - Core risk module
   - `load_managed_positions(con)` - Loads positions with legs from DB
   - `load_latest_leg_snapshots(con, position_ids)` - Gets latest snapshot per leg_id
   - `compute_position_rollup(position, leg_snapshots)` - Computes risk metrics for a single position
   - `compute_all_rollups(con, ...)` - Computes rollups for all positions

2. **`scripts/pm_risk.py`** - CLI script
   - `--db` - Path to database
   - `--json` - Output as JSON instead of table
   - `--warn-drift-usd` - Warning threshold for drift in USD (default: $50)
   - `--crit-drift-usd` - Critical threshold for drift in USD (default: $150)
   - `--warn-drift-pct` - Warning threshold for drift percentage (default: 2%)
   - `--crit-drift-pct` - Critical threshold for drift percentage (default: 4%)

## Risk Metrics

Each position rollup includes:
- `gross_notional_usd` - Sum of absolute leg notionals (if prices available)
- `net_delta_usd` - Sum of leg deltas (LONG positive, SHORT negative)
- `drift_usd` - Absolute deviation from delta-neutral
- `drift_pct` - Drift as percentage of gross notional (if available)
- `warn` / `crit` - Boolean flags based on thresholds
- `snapshots_status` - `ok`, `partial`, or `missing`
- Raw inputs included for debugging

## Usage

```bash
# Show table view
python3 scripts/pm_risk.py

# JSON output
python3 scripts/pm_risk.py --json

# Custom thresholds
python3 scripts/pm_risk.py --warn-drift-usd 100 --crit-drift-usd 300
```

## Testing

Tested with:
- ✅ Positions without snapshots (stale/missing status)
- ✅ Balanced positions with snapshots
- ✅ Positions with drift (WARN/CRIT flags)
- ✅ Partial snapshots (some legs missing)
- ✅ Custom threshold overrides

All acceptance criteria met. Implementation uses stdlib only (no external deps).
