# Funding Sign Convention Fix - Summary

## Bug Fixed
The opportunity screener was incorrectly treating funding rates as position PnL, leading to incorrect net funding calculations.

## Correct Convention
- **funding > 0**: long pays, short receives
- **funding < 0**: long receives, short pays

## Position PnL from Funding
- `pnl_long_apr = -funding_apr` (if funding > 0, long pays → negative PnL)
- `pnl_short_apr = +funding_apr` (if funding > 0, short receives → positive PnL)

## Net Funding PnL for Arbitrage
For an opportunity with Long venue A, Short venue B:
- `net_funding_pnl_apr = pnl_long_apr + pnl_short_apr = funding_apr_B - funding_apr_A`

## Files Changed

### 1. `tracking/analytics/opportunity_screener.py`
**Changes:**
- Updated `Opportunity` dataclass:
  - Renamed `net_funding_apr` → `net_funding_pnl_apr`
  - Updated field descriptions (removed "long receives funding" etc.)
  - Clarified: `long_funding_apr` and `short_funding_apr` are exchange funding rates (same sign as funding_rate)

- Updated `find_opportunities()`:
  - Added position PnL calculation: `pnl_long_apr = -long_funding`, `pnl_short_apr = +short_funding`
  - Changed `net_funding_apr = long_funding - short_funding` → `net_funding_pnl_apr = pnl_long_apr + pnl_short_apr`
  - Updated all references to use `net_funding_pnl_apr`

- Updated `format_opportunity()`:
  - Changed display to show "Funding APR (exchange)" vs "Net Funding PnL APR (position PnL)"
  - Removed ambiguous "receive/pay" language

### 2. `scripts/opportunity_report_public.py`
**Changes:**
- Updated table header: "Net APR%" → "Net PnL%"
- Updated table row to use `net_funding_pnl_apr`
- Updated details section:
  - Changed "Long Funding APR" → "Funding APR (exchange rate): Long X%, Short Y%"
  - Changed "Net Funding APR" → "Net Funding PnL APR (position PnL from funding)"
  - Updated assumptions to include funding sign convention
  - Updated formulas to use `net_funding_pnl_apr`

### 3. `tracking/tasks/T-009_opportunity_screener_public.md`
**Changes:**
- Updated formulas section to clarify funding sign convention
- Changed formulas to use `net_funding_pnl_apr`
- Added position PnL calculation formulas

### 4. `tracking/COST_MODEL_UPDATE.md`
**Changes:**
- Updated sample output interpretation to use correct funding sign convention
- Added explicit funding PnL calculation breakdown
- Clarified that negative funding = long receives, short pays

### 5. `COST_MODEL_SUMMARY.md`
**Changes:**
- Updated sample output to show correct field names and calculations
- Added funding PnL calculation breakdown

## Verification Results

### BERA Paradex↔Ethereal Example

**Current Data:**
- Paradex BERA funding: -13.29% (exchange rate)
- Ethereal BERA funding: -1.47% (exchange rate)

**Long Paradex, Short Ethereal:**
- Position PnL Long Paradex: -(-13.29%) = +13.29% (long receives)
- Position PnL Short Ethereal: +(-1.47%) = -1.47% (short pays)
- Net Funding PnL APR: +11.82%

**Long Ethereal, Short Paradex:**
- Position PnL Long Ethereal: -(-1.47%) = +1.47% (long receives)
- Position PnL Short Paradex: +(-13.29%) = -13.29% (short pays)
- Net Funding PnL APR: -11.82%

**Validation:**
- ✅ If Paradex funding is very negative, SHORT Paradex has negative PnL component (pays)
- ✅ If Paradex funding is very negative, LONG Paradex has positive PnL component (receives)
- ✅ Screener correctly identifies Long Paradex opportunities as profitable
- ✅ Short Paradex opportunities have negative net funding PnL (correctly filtered out)

## Sample Output (BERA Paradex↔Ethereal)

```
#3 BERA
  Long paradex, Short ethereal
  Funding APR (exchange rate): Long -13.29% | Short -1.47%
  Net Funding PnL APR: +11.82% (position PnL from funding)
  Cost Breakdown:
    Fees: 0.120%
    Spread: +0.100% (proxy)
    Total: 0.220%
  Cost Min (fees only): 0.120%
  Cost Est (fees+spread): 0.220%
  Min-Hold Breakeven: 6.8 days
  14-Day Hold PnL: +0.23% ($+23.32 on $10k notional)
  Data Quality Notes: long_funding:limited(7pts), short_funding:limited(8pts), exec:proxy
```

## Impact
- Correctly identifies profitable funding arbitrage opportunities
- Accurate position PnL calculation from funding rates
- Clear distinction between exchange funding rates and position PnL
- All documentation now uses correct funding sign convention
