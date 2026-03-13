# V3-062 Implementation Summary

## Completed Changes

### 1. tracking/position_manager/risk.py ✅
- **Added** `_enrich_leg_price_from_db(con, venue, inst_id)` function:
  - Queries DB v3 `prices_v3` table for latest price
  - Prefers: mid > mark > last (first non-null)
  - Returns None if no data found

- **Modified** `compute_position_rollup()`:
  - Added `con` parameter for database connection
  - Enriches missing leg prices from DB before computing delta
  - Tracks `legs_missing_price` count
  - New status `partial_price` when any leg's price is still missing after enrichment
  - Sets `warn=True, warn_reason="missing_price"` instead of CRIT
  - Skips drift_pct computation in partial_price state

- **Modified** `compute_all_rollups()`:
  - Passes `con=con` to `compute_position_rollup()` for price enrichment

### 2. tracking/connectors/lighter_private.py ✅
- **Modified** `_last_trade_price(market_id)`:
  - Prefers `last_trade_price` from API
  - Fallback to mid of `highest_bid` and `lowest_ask`
  - Final fallback to bid or ask if only one available
  - Returns None if all sources unavailable

### 3. tracking/connectors/paradex_private.py ✅
- **Modified** `fetch_open_positions()`:
  - Imports `paradex_public` module dynamically (lazy import)
  - Calls `paradex_public.get_orderbook(market, timeout_s=3)` for each position
  - Uses `mid` price from orderbook as `current_price`
  - Wrapped in try/except for best-effort handling
  - Continues without price if orderbook fetch fails

### 4. tracking/position_manager/V3-062-NOTES.md ✅
- Created regression test documentation
- Includes quick test commands
- Includes Python verification code
- Documents expected behavior

## Verification

All changes:
- ✅ Compile without syntax errors
- ✅ Import correctly
- ✅ Use stdlib only (no new dependencies)
- ✅ Handle failures gracefully (try/except, best-effort)
- ✅ Minimal changes (focused fixes only)

## Expected Behavior

**Before:** Missing `current_price` on one leg → drift_pct = 100% → False CRIT alert

**After:**
1. Connector tries to fetch price (Paradex: orderbook mid, Lighter: bid/ask mid)
2. If still missing, risk.py enriches from DB v3 `prices_v3`
3. If still missing, status = "partial_price", warn_reason = "missing_price" (not CRIT)
4. No drift_pct computed in partial_price state
5. Prevents false CRIT alerts

## Testing

Run regression test per V3-062-NOTES.md:
```bash
python -m scripts.pull_positions_v3
python -m tracking.position_manager.risk
```

Expected: drift_pct should be reasonable (< 10% for delta-neutral positions) when both legs priced.
