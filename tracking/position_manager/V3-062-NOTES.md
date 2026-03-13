# V3-062: Price Enrichment for False CRIT Drift Fixes

**Problem:** False CRIT drift alerts triggered when one leg had missing `current_price` (e.g., Paradex positions had `current_price=None`). This caused drift_pct to be 100% due to zero gross_notional_usd.

**Fixes applied:**

1. **tracking/position_manager/risk.py**:
   - Added `_enrich_leg_price_from_db()` to query DB v3 `prices_v3` for latest price (prefers: mid > mark > last)
   - Updated `compute_position_rollup()` to enrich missing prices from DB before computing delta
   - New status `partial_price` when any leg's price is still missing after enrichment
   - Set `warn=True, warn_reason="missing_price"` instead of CRIT when partial_price
   - Do NOT compute drift_pct in partial_price state

2. **tracking/connectors/lighter_private.py**:
   - Updated `_last_trade_price()` to fallback to mid of best bid/ask when `last_trade_price` is missing

3. **tracking/connectors/paradex_private.py**:
   - Updated `fetch_open_positions()` to fetch current_price from public orderbook via `paradex_public.get_orderbook(market)` (3s timeout, best-effort)

## Regression Test

Quick test to verify drift_pct is not 100% for managed positions when both legs are priced:

```bash
# 1. Pull latest positions (enriches prices from connectors)
cd /mnt/data/agents/arbit
python -m scripts.pull_positions_v3

# 2. Run risk rollup (enriches missing prices from DB, computes drift)
python -m tracking.position_manager.risk

# Expected: drift_pct should be reasonable (< 10% for delta-neutral positions)
# If drift_pct is 100%, check that:
# - Both legs have current_price populated
# - Check snapshots_status is NOT "partial_price"
# - Check warn_reason is NOT "missing_price"
```

Verify via Python:
```python
import sqlite3
from tracking.position_manager.risk import compute_all_rollups

con = sqlite3.connect("tracking/db/arbit_v3.db")
rollups = compute_all_rollups(con)

for r in rollups:
    if r["status"] == "OPEN" and r["leg_count"] >= 2:
        print(f"Position: {r['position_id']}")
        print(f"  snapshots_status: {r['snapshots_status']}")
        print(f"  drift_pct: {r.get('drift_pct')}")
        print(f"  warn: {r['warn']}, crit: {r['crit']}")
        print(f"  warn_reason: {r.get('warn_reason')}")
        print(f"  Legs:")
        for leg in r["legs"]:
            print(f"    {leg['inst_id']}: price={leg.get('snapshot_current_price')}, enriched={leg.get('enriched_from_db')}")
```

## Status

- ✅ Code changes complete
- ⏳ Pending regression test verification
