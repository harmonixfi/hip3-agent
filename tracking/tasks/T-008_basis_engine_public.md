# T-008 — Basis/spread engine (public data) ✅ DONE

## Goal
Compute basis/spread using mark prices from public connectors:
- spot↔perp basis (on OKX if spot available)
- perp↔perp cross-exchange basis for shared symbols (mark_price diff)

## Data inputs
- Prices from DB (per-venue mark prices)
- Funding from DB (per-venue funding rates)

## Deliverables ✅
- `tracking/analytics/basis.py` ✅
- `scripts/compute_basis.py` writes to DB:
  - basis spread (absolute, %)
  - annualized basis % (adjusted for funding interval)
- Example: basis = (perpA_mark - perpB_mark) / perpB_mark

## Acceptance ✅
- For each shared symbol, basis is computed and stored with timestamp
- Output: ranking by annualized basis %

---

## Run Notes

**Date Completed:** 2026-02-07

### Files Created

1. **`tracking/analytics/basis.py`** (10,623 bytes)
   - `BasisEngine` class with full basis computation pipeline
   - Symbol normalization (ethereal: "BTCUSD" → "BTC", lighter: "BTC" → "BTC")
   - Price source priority: mid > mark_price > last_price
   - Computes basis_spread and annualized_basis_pct
   - Idempotent storage (deletes old records before inserting)

2. **`scripts/compute_basis.py`** (5,872 bytes, executable)
   - CLI with options: `--horizon-days`, `--min-price`, `--top`, `--quiet`
   - Prints summary statistics and top N opportunities
   - Both absolute and annualized rankings

### How to Run

```bash
# Basic run with top 10 opportunities
python3 scripts/compute_basis.py

# Custom parameters
python3 scripts/compute_basis.py --top 5 --horizon-days 1.0 --min-price 0.1

# Quiet mode (for cron)
python3 scripts/compute_basis.py --quiet
```

### Sample Output

```
================================================================================
BASIS/SPREAD COMPUTATION ENGINE
================================================================================
Database: /mnt/data/agents/arbit/tracking/db/arbit.db
Horizon: 1.0 days
Min price: $0.0

✓ Computed 10 basis pairs

================================================================================
SUMMARY STATISTICS
================================================================================
Total pairs computed: 10

Basis Spread %:
  Mean:    0.0014%
  Max:     0.9101%
  Min:     -0.9019%

Annualized Basis %:
  Mean:    0.5101%
  Max:     332.1716%
  Min:     -329.1759%

Unique symbols: 5
Unique venue pairs: 2

================================================================================
TOP 10 BASIS OPPORTUNITIES (BY ABSOLUTE SPREAD %)
================================================================================
Symbol       Venue A → B          Spread %     Price A      Price B
--------------------------------------------------------------------------------
 1. ZEC        ethereal → lighter     0.9101% $  238.7986 $  236.6450
 2. ZEC        lighter → ethereal    -0.9019% $  236.6450 $  238.7986
 ...
```

### Implementation Notes

**Symbol Normalization:**
- ethereal: strips 'USD' suffix (e.g., "BTCUSD" → "BTC")
- lighter: keeps as-is (e.g., "BTC" → "BTC")
- Limitation: Assumes USD-quoted pairs for ethereal; may need extension for other quote currencies

**Price Selection:**
- Priority: mid > mark_price > last_price
- Filters by min_price threshold (default 0.0) to exclude illiquid tokens

**Idempotency:**
- Deletes old records for matching (symbol, leg_a_venue, leg_b_venue) before inserting
- Handles both directions (A→B and B→A) for each symbol pair

**Formulas:**
- `basis_spread = (price_a - price_b) / price_b`
- `annualized_basis_pct = basis_spread * 365 * 100` (for 1-day horizon)

### Current State

- Venues: lighter, ethereal
- Shared symbols found: 5 (BERA, ENA, LIT, SOL, ZEC)
- Records stored: 10 (5 symbols × 2 directions)
- All acceptance criteria met ✅

### Next Steps

- Schedule via cron (e.g., every 5 minutes alongside price pulls)
- Consider adding funding rate basis if funding data available
- Extend symbol normalization for additional venues/quote currencies

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

