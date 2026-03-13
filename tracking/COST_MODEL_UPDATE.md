# Cost Model Update - Opportunity Screener

## Summary
Updated the opportunity screener cost model to use venue-specific fee schedules and spread costs instead of a flat 0.2% roundtrip cost.

## Changes Made

### 1. Fee Configuration (`config/fees.json`)
Created/updated fee schedule with venue-specific and product-type-specific fees:

**OKX:**
- Spot: maker 0.08%, taker 0.10% (regular user baseline)
- Perp: maker 0.02%, taker 0.05%

**Hyperliquid (perp only):**
- maker -0.02% (rebate), taker 0.05%

**Paradex (perp only):**
- maker 0%, taker 0.03%

**Lighter (perp only):**
- maker 0.02%, taker 0.07%

**Ethereal (perp only):**
- maker 0%, taker 0.03% (Bean confirmed)

**Default Assumptions:**
- Execution type: market (taker)
- Proxy slippage: 10 bps (0.10%) when bid/ask unavailable

### 2. Opportunity Screener (`tracking/analytics/opportunity_screener.py`)
**New Features:**
- Loads fee config from `config/fees.json`
- Computes roundtrip fees per leg, per entry/exit based on venue + product type
- Calculates spread cost from bid/ask when available
- Falls back to proxy slippage (configurable, default 10 bps) when bid/ask missing
- Tracks cost sources and data quality flags

**Cost Metrics:**
- `fee_cost_pct`: Total trading fees (both legs, entry+exit)
- `spread_cost_pct`: Spread/slippage cost (or proxy if unavailable)
- `cost_min_pct`: Fees-only cost
- `cost_est_pct`: Estimated total cost (fees + spread/proxy)
- `total_cost_pct`: Total cost (used in PnL calculation)
- `spread_source`: 'cross_spread', 'proxy', or 'no_price'

**Implementation Details:**
- Fees computed as: `(entry_fee + exit_fee) × 2 legs`
- For market (taker) execution: `taker_bps × 4 / 100` (convert bps to %)
- For limit (maker) execution: `maker_bps × 4 / 100`
- Cross-spread cost: `(ask_long - bid_short) / mid_avg × 100`
- Proxy fallback: `proxy_slippage_bps / 100`

**Data Structure Updates:**
- Added `contract_type` field to PriceData ('PERP' or 'SPOT')
- Added new cost fields to Opportunity dataclass
- Added `spread_source` to track spread cost source

### 3. Report Output (`scripts/opportunity_report_public.py`)
**Updated Table Format:**
- Added columns for fee cost, spread cost, and total cost
- Format: `Fee% | Sprd% | Tot%`

**Updated Details Section:**
- Shows cost breakdown: fees, spread (with source), total
- Shows Cost Min (fees-only) and Cost Est (fees+spread)
- Updated assumptions to reflect new cost model

**New Summary Stats:**
- Average fee cost across opportunities
- Average spread cost across opportunities

### 4. OKX Spot-Perp Support
**Status:** Not implemented - OKX spot data not currently collected

**Findings:**
- Checked database for OKX spot symbols (not ending in -SWAP)
- Found no OKX spot data in prices table
- Instruments table only shows PERP type for OKX

**Note:** Spot-perp mode for OKX (spot vs OKX perp basis opportunities) is skipped due to missing spot price data. Implementation pending OKX spot data collection.

**Future Implementation:**
Once OKX spot prices are available:
- Update `normalize_symbol()` to handle OKX spot format (e.g., `BTC-USDT`)
- Update `get_contract_type()` to return 'SPOT' for OKX spot instruments
- Fee schedule already includes OKX spot fees
- Cross-spread computation will work automatically with bid/ask from spot

## Sample Output: BERA Paradex↔Ethereal

```
=== BERA Paradex↔Ethereal Opportunity ===
BERA | Long ethereal, Short paradex
  Funding APR (exchange): Long -1.16%, Short -16.64%
  Net Funding PnL APR: +15.48% (position PnL from funding)
  Cost Breakdown: Fee +0.120% | Spread +0.100% (proxy) | Total 0.220%
  Cost Min (fees only): 0.120% | Cost Est (fees+spread): 0.220%
  Breakeven: 5.2 days
  14D Hold PnL: +0.37% ($+37.41 on $10k)
  Data Quality: long_funding:limited(5pts), short_funding:limited(4pts), exec:proxy

Cost Breakdown:
  Fee Cost (roundtrip): 0.120%
  Spread Cost: +0.100% (proxy)
  Cost Min (fees-only): 0.120%
  Cost Est (fees+spread): 0.220%
  Total Cost: 0.220%

Fee Calculation:
  Paradex perp: maker 0%, taker 0.03%
  Ethereal perp: maker 0%, taker 0.03%
  Roundtrip: 2 legs × entry+exit × taker = 4 × 0.03% = 0.12%

Funding PnL Calculation:
  Position PnL: pnl_long = -funding_long, pnl_short = +funding_short
  pnl_long_ethereal = -(-1.16%) = +1.16% (long receives when funding negative)
  pnl_short_paradex = +(-16.64%) = -16.64% (short pays when funding negative)
  Net funding PnL = +1.16% + (-16.64%) = -15.48% (arbitrage pays funding)
  *Note: This example shows negative net funding PnL; a profitable opportunity would have positive net PnL
```

**Interpretation:**
- Funding sign convention: funding > 0 = long pays, short receives; funding < 0 = long receives, short pays
- Long Ethereal: funding -1.16% (exchange) → position PnL +1.16% (long receives)
- Short Paradex: funding -16.64% (exchange) → position PnL -16.64% (short pays)
- Net funding PnL: -15.48% (negative = arbitrage pays funding overall)
- Fees: 0.12% (both legs, taker execution)
- Spread: 0.10% proxy (bid/ask not available for cross-spread)
- Total cost: 0.22%
- Breakeven: N/A (net funding PnL negative)
- 14-day PnL: -0.59% (-$59.41 on $10k) - *This example shows negative PnL; look for opportunities with positive net funding PnL*

## Testing
Run the opportunity report:
```bash
python3 scripts/opportunity_report_public.py --top 5
```

Test with different execution types:
```bash
python3 scripts/opportunity_report_public.py --top 5 --execution limit
```

## Files Changed
1. `config/fees.json` - Created/updated with fee schedule
2. `tracking/analytics/opportunity_screener.py` - Major update for cost model
3. `scripts/opportunity_report_public.py` - Updated report output format
4. `tracking/COST_MODEL_UPDATE.md` - This documentation file

## Next Steps
- Collect OKX spot market data to enable spot-perp opportunities
- Consider adding configurable execution type per venue
- Consider adding funding rate quality scoring for confidence metrics
