# T-009 — Opportunity screener (public data only)

## Status: ✅ DONE

## Implementation Summary
Implemented a public opportunity screener for cross-venue funding arbitrage with PnL estimation.

## Update 2026-02-09: Added Strategy Mode Support
Extended the opportunity screener to support two distinct strategy modes:

1. **SPOT↔PERP (Carry)**: Delta-neutral strategy using Long spot + Short perp
   - Captures persistent perp funding rates
   - Uses spot leg for hedge
   - Enforces LONG spot, SHORT perp as default
   - Flags opportunities that would require shorting spot

2. **PERP↔PERP (Extreme Funding)**: Cross-venue funding arbitrage
   - Captures extreme funding differentials between venues
   - Uses leverage to maximize carry
   - Labeled as 'perp_perp' strategy type

### Key Changes:
- Added `strategy_type` field to Opportunity: 'spot_perp' or 'perp_perp'
- Added `funding_quality` field with stability metrics (7D/14D avg, consistency)
- Added `requires_short_spot` flag for opportunities needing spot shorting
- New `find_spot_perp_opportunities()` method for OKX spot-perp matching
- New `find_all_opportunities()` wrapper returning (spot_perp, perp_perp)
- Updated `scripts/opportunity_report_public.py` to display two sections
- Added `config/strategy.json` for strategy-specific thresholds
- Added `scripts/test_spot_perp_screener.py` for sanity checks

### New Config: `config/strategy.json`
```json
{
  "spot_perp": {
    "min_funding_apr": 1.0,
    "allow_short_spot": false
  },
  "perp_perp": {
    "extreme_funding_threshold": 20.0
  }
}
```

### Usage Examples:
```bash
# Show both strategies
python3 scripts/opportunity_report_public.py --top 10

# Show only spot-perp carry
python3 scripts/opportunity_report_public.py --top 10 --strategy spot_perp

# Show only perp-perp extreme
python3 scripts/opportunity_report_public.py --top 10 --strategy perp_perp

# Run test
python3 scripts/test_spot_perp_screener.py
```

## Requirements (from Bean)
- Output must include:
  1) Min-hold breakeven time (based on total roundtrip cost 0.2% for both legs combined)
  2) Simulated PnL as % over a 7-day and 14-day hold (also show $ PnL for $10k notional)
  3) Annualized return (APR) derived from 7D and 14D PnL
- Notional: $10,000
- Execution: cross spread (use bid for sell, ask for buy); fallback to mid if bid/ask missing
- Funding: use average to gauge stability (prefer 14D avg funding APR when available). If only shorter history exists, compute what we can and clearly note.
- Include all venues (OKX, Hyperliquid, Paradex, Lighter, Ethereal). If data missing, explicitly note limitations per opportunity.

## Deliverables
1. ✅ `tracking/analytics/opportunity_screener.py` - Main screener module
   - Symbol normalization across venues
   - Net funding carry computation (receive - pay)
   - Execution slippage proxy using bid/ask (cross spread)
   - Min-hold breakeven calculation
   - 7D and 14D hold PnL% and $ PnL on $10k notional
   - APR derived from 7D and 14D PnL

2. ✅ `scripts/opportunity_report_public.py` - Report script
   - Runs screener, prints top 10-20 opps
   - For each opp: symbol, venues, direction (long/short where), net funding APR, estimated min-hold days, 7D and 14D PnL% and $ on $10k, APR from both horizons, data quality notes

3. ✅ Script supports --quiet flag for automation

## Key Formulas & Assumptions (documented in code)
- Total roundtrip cost (both legs combined): 0.2% of notional
- Cost: roundtrip fees+spread applied once at position entry
- Use 14D avg funding APR when possible; if funding table lacks 14D history, compute rolling average over available window and report window length
- Funding sign convention: funding > 0 = long pays, short receives; funding < 0 = long receives, short pays
- Position PnL from funding: pnl_long_apr = -funding_apr, pnl_short_apr = +funding_apr
- Net funding PnL APR = pnl_long_apr + pnl_short_apr = funding_apr_B - funding_apr_A (for Long A, Short B)
- 7D hold PnL% = net_funding_pnl_apr * (7/365) - cost_est_pct
- 14D hold PnL% = net_funding_pnl_apr * (14/365) - cost_est_pct
- APR from 7D = pnl_7d_pct * (365/7)
- APR from 14D = pnl_14d_pct * (365/14)
- Breakeven days = cost_est_pct / (net_funding_pnl_apr/365) (if net_funding_pnl_apr positive), else N/A
- Execution price: use bid/ask to compute implied entry basis and cross cost; if missing, use mid and flag
- Price sanity check: filter out venues with prices differing by >10% (likely different contract types)

## Data Quality Handling
- When bid/ask unavailable: fallback to mid price, flag in output
- When 14D funding history unavailable: use available window average, flag as "limited(Npts)"
- When price mismatch detected (>10%): flag as "price_mismatch"
- Extreme execution costs (>5%): filtered out, flag as "extreme_cost_filtered"

## Run Instructions
```bash
# Basic usage (shows top 10)
python3 scripts/opportunity_report_public.py --top 10

# Custom thresholds
python3 scripts/opportunity_report_public.py --top 20 --min-apr 0.5

# Quiet mode for automation
python3 scripts/opportunity_report_public.py --top 10 --quiet

# Only show profitable 14D opportunities
python3 scripts/opportunity_report_public.py --top 10 --positive-only
```

## Current Results (as of 2026-02-09)
With current data:
- Found 10 opportunities with min APR 0.1%
- Some opportunities have positive 14D PnL (e.g., BERA L:paradex/S:okx: +0.33% on 14D, +0.08% on 7D)
- APR derived from PnL shows realistic annualized returns (e.g., +8.5% from 14D PnL for top opportunity)
- Best opportunity: BERA L:paradex/S:okx with +12.7% net APR, 4.6-day breakeven, +0.08% 7D PnL, +0.33% 14D PnL
- Data quality notes show limited funding history (5-8 points only)

## Notes
- Current database has very limited funding history (only 2-3 data points per symbol), so 14D averages are not available
- All opportunities show negative short-term PnL (14 days) due to low funding carry vs trading costs
- Screener correctly identifies these as opportunities with longer-term potential (positive funding carry) but notes the breakeven horizon
- To show profitable opportunities, either:
  1. Wait for higher funding rates
  2. Reduce roundtrip cost assumption
  3. Increase hold period beyond 14 days
  4. Use --positive-only flag (currently returns 0 opportunities)

## Verification
```bash
python3 scripts/opportunity_report_public.py --top 10
```
✅ Script runs without errors
✅ Shows detailed opportunity breakdown with all required metrics (7D, 14D, APR)
✅ Handles missing data gracefully with quality flags
✅ Doesn't crash when venues missing data
✅ APR calculations correctly derived from PnL percentages

## Docs
- docs/CONNECTORS.md
- docs/CONVENTIONS.md
- docs/RUNBOOK.md
- docs/DESIGN_v3.md

