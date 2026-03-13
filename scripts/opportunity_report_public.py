#!/usr/bin/env python3
"""
Public opportunity report script.

Runs the opportunity screener and prints the top N opportunities in a clean format.
Supports two strategy types:
- SPOT↔PERP (carry): Long spot + Short perp to collect funding
- PERP↔PERP (extreme): Cross-venue funding arbitrage

Supports --top N flag and --quiet mode for automation.
"""

import argparse
import sys
from pathlib import Path

# Add tracking/analytics to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / 'tracking' / 'analytics'))

# Add parent directory to path for absolute imports
sys.path.insert(0, str(script_dir.parent))

from tracking.analytics.opportunity_screener import OpportunityScreener


def print_header(title: str):
    """Print a section header."""
    print(f"\n{'=' * 70}")
    print(f"  {title}")
    print(f"{'=' * 70}\n")


def print_opportunity_table(opportunities, quiet: bool = False, show_flags: bool = True):
    """
    Print opportunities in a clean table format.

    Args:
        opportunities: List of Opportunity objects
        quiet: Suppress verbose output
        show_flags: Show flags like requires_short_spot, extreme funding
    """
    if not opportunities:
        print("No opportunities found.")
        return

    # Print header
    if not quiet:
        print_header(f"Top {len(opportunities)} Funding Arbitrage Opportunities")

    # Table header - updated to include strategy type and flags
    header = f"{'#':<3} {'Symbol':<10} {'Strat':<10} {'Dir':<18} {'Net%':<6} {'Fee%':<7} {'Tot%':<7} {'Breakeven':<9} {'7D%':<7} {'7D$':<8} {'7D APR':<8} {'14D%':<7} {'14D$':<8} {'14D APR':<8}"
    separator = '-' * 114

    print(header)
    print(separator)

    # Print each opportunity
    for i, opp in enumerate(opportunities, 1):
        symbol = opp.symbol[:10]
        strategy = opp.strategy_type[:10]

        # Direction: abbreviated
        if len(opp.long_venue) + len(opp.short_venue) < 16:
            direction = f"L:{opp.long_venue}/S:{opp.short_venue}"
        else:
            direction = f"L:{opp.long_venue[:3]}/S:{opp.short_venue[:3]}"

        # Build flags
        flags = []
        if opp.requires_short_spot:
            flags.append("SHORT_SPOT")
        if show_flags and flags:
            symbol_with_flags = f"{symbol} ({','.join(flags)})"
            symbol_with_flags = symbol_with_flags[:10]
        else:
            symbol_with_flags = symbol

        net_apr = f"{opp.net_funding_pnl_apr:+.1f}%"
        fee_pct = f"{opp.fee_cost_pct:+.3f}%"
        total_pct = f"{opp.total_cost_pct:.3f}%"
        breakeven = f"{opp.breakeven_days:.1f}d" if opp.breakeven_days else "N/A"
        pnl_7d_pct = f"{opp.pnl_7d_pct:+.2f}%"
        pnl_7d_usd = f"${opp.pnl_7d_usd:+.2f}"
        apr_7d = f"{opp.apr_from_7d:+.0f}%"
        pnl_14d_pct = f"{opp.pnl_14d_pct:+.2f}%"
        pnl_14d_usd = f"${opp.pnl_14d_usd:+.2f}"
        apr_14d = f"{opp.apr_from_14d:+.0f}%"

        print(f"{i:<3} {symbol_with_flags:<10} {strategy:<10} {direction:<18} {net_apr:<6} {fee_pct:<7} {total_pct:<7} {breakeven:<9} {pnl_7d_pct:<7} {pnl_7d_usd:<8} {apr_7d:<8} {pnl_14d_pct:<7} {pnl_14d_usd:<8} {apr_14d:<8}")

    print(separator)

    # Print detailed notes
    if not quiet:
        print("\n--- Details for Top 5 ---\n")
        for i, opp in enumerate(opportunities[:5], 1):
            print(f"#{i} {opp.symbol} [{opp.strategy_type.upper()}]")
            print(f"  {opp.direction}")
            print(f"  Funding APR (exchange rate): Long {opp.long_funding_apr:+.2f}% | Short {opp.short_funding_apr:+.2f}%")
            print(f"  Net Funding PnL APR: {opp.net_funding_pnl_apr:+.2f}% (position PnL from funding)")
            print(f"  Cost Breakdown:")
            print(f"    Fees: {opp.fee_cost_pct:.3f}%")
            print(f"    Spread: {opp.spread_cost_pct:+.3f}% ({opp.spread_source})")
            print(f"    Total: {opp.total_cost_pct:.3f}%")
            print(f"  Cost Min (fees only): {opp.cost_min_pct:.3f}%")
            print(f"  Cost Est (fees+spread): {opp.cost_est_pct:.3f}%")
            if opp.breakeven_days:
                print(f"  Min-Hold Breakeven: {opp.breakeven_days:.1f} days")
            else:
                print(f"  Min-Hold Breakeven: N/A (net funding PnL negative)")
            print(f"  7-Day Hold PnL: {opp.pnl_7d_pct:+.2f}% (${opp.pnl_7d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_7d:+.1f}%")
            print(f"  14-Day Hold PnL: {opp.pnl_14d_pct:+.2f}% (${opp.pnl_14d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_14d:+.1f}%")
            # Print funding quality for spot-perp
            if opp.strategy_type == 'spot_perp' and opp.funding_quality:
                print(f"  Funding Stability: {opp.funding_quality}")
            # Print data quality notes
            if opp.data_quality and opp.data_quality != 'good':
                print(f"  Data Quality Notes: {opp.data_quality}")
            # Print flags
            flags = []
            if opp.requires_short_spot:
                flags.append("⚠ Requires shorting spot")
            if flags:
                print(f"  Flags: {' | '.join(flags)}")
            print()

        # Print assumptions
        print("--- Assumptions ---")
        print("  Notional: $10,000")
        print("  Execution: market (taker) by default")
        print("  Fees: loaded from config/fees.json per venue and product type")
        print("  Spread: cross-spread (bid for sell, ask for buy), fallback to proxy (10 bps)")
        print("  Funding: prefer 14D average; fallback to latest if unavailable")
        print("  Funding sign convention: funding > 0 = long pays, short receives")
        print("  Cost: roundtrip fees+spread applied once at position entry")
        print("  7D PnL = net_funding_pnl_apr * (7/365) - cost_est_pct")
        print("  14D PnL = net_funding_pnl_apr * (14/365) - cost_est_pct")
        print("  APR from 7D = pnl_7d_pct * (365/7)")
        print("  APR from 14D = pnl_14d_pct * (365/14)")
        print("  Breakeven = cost_est_pct / (net_funding_pnl_apr / 365)")


def print_summary(opportunities, quiet: bool = False):
    """
    Print a summary of opportunities.

    Args:
        opportunities: List of Opportunity objects
        quiet: Suppress verbose output
    """
    if not opportunities:
        if not quiet:
            print("No opportunities found.")
        return

    positive_pnl = [o for o in opportunities if o.pnl_14d_pct > 0]
    avg_breakeven = sum(o.breakeven_days for o in opportunities if o.breakeven_days) / len([o for o in opportunities if o.breakeven_days]) if opportunities else 0
    avg_fee_cost = sum(o.fee_cost_pct for o in opportunities) / len(opportunities) if opportunities else 0
    avg_spread_cost = sum(o.spread_cost_pct for o in opportunities) / len(opportunities) if opportunities else 0

    # Count by strategy type
    spot_perp_count = sum(1 for o in opportunities if o.strategy_type == 'spot_perp')
    perp_perp_count = sum(1 for o in opportunities if o.strategy_type == 'perp_perp')

    if not quiet:
        print(f"\n--- Summary ---")
        print(f"  Total opportunities: {len(opportunities)}")
        print(f"  SPOT↔PERP: {spot_perp_count} | PERP↔PERP: {perp_perp_count}")
        print(f"  Positive 14D PnL: {len(positive_pnl)}")
        if positive_pnl:
            print(f"  Avg breakeven: {avg_breakeven:.1f} days")
        print(f"  Avg fee cost: {avg_fee_cost:.3f}%")
        print(f"  Avg spread cost: {avg_spread_cost:+.3f}%")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate public opportunity report for funding arbitrage'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of top opportunities to show (default: 10)'
    )
    parser.add_argument(
        '--min-apr',
        type=float,
        default=0.1,
        help='Minimum net funding APR percentage (default: 0.1)'
    )
    parser.add_argument(
        '--notional',
        type=float,
        default=10000.0,
        help='Notional amount in USD (default: 10000)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Quiet mode (suppress headers and details)'
    )
    parser.add_argument(
        '--positive-only',
        action='store_true',
        help='Only show opportunities with positive 14D PnL'
    )
    parser.add_argument(
        '--db',
        type=str,
        default='/mnt/data/agents/arbit/tracking/db/arbit.db',
        help='Path to SQLite database (default: /mnt/data/agents/arbit/tracking/db/arbit.db)'
    )
    parser.add_argument(
        '--execution',
        type=str,
        default='market',
        choices=['market', 'limit'],
        help='Execution type: market (taker) or limit (maker) (default: market)'
    )
    parser.add_argument(
        '--spot-perp-venue',
        type=str,
        default='okx',
        help='Venue for spot-perp opportunities (default: okx)'
    )
    parser.add_argument(
        '--strategy',
        type=str,
        default='all',
        choices=['all', 'spot_perp', 'perp_perp'],
        help='Strategy type: all, spot_perp, or perp_perp (default: all)'
    )
    parser.add_argument(
        '--live-spot-perp',
        action='store_true',
        help='Use live OKX API for spot-perp opportunities (default: False, uses DB)'
    )

    args = parser.parse_args()

    # Run screener
    try:
        with OpportunityScreener(args.db) as screener:
            # Find all opportunities split by strategy type
            spot_perp_opps, perp_perp_opps = screener.find_all_opportunities(
                min_notional=args.notional,
                min_net_funding_apr=args.min_apr,
                max_opportunities=args.top,
                execution_type=args.execution,
                include_spot_perp=(args.strategy in ['all', 'spot_perp']),
                spot_perp_venue=args.spot_perp_venue,
                use_live_spot_perp=args.live_spot_perp
            )

            # Filter to positive 14D PnL if requested
            if args.positive_only:
                spot_perp_opps = [o for o in spot_perp_opps if o.pnl_14d_pct > 0]
                perp_perp_opps = [o for o in perp_perp_opps if o.pnl_14d_pct > 0]

            # Determine which strategies to show
            show_spot_perp = args.strategy in ['all', 'spot_perp'] and spot_perp_opps
            show_perp_perp = args.strategy in ['all', 'perp_perp'] and perp_perp_opps

            # Print spot-perp section
            if show_spot_perp:
                print_header(f"SPOT↔PERP (Carry) - Top {len(spot_perp_opps)}")
                print_opportunity_table(spot_perp_opps, quiet=args.quiet)
                print_summary(spot_perp_opps, quiet=args.quiet)

            # Print perp-perp section
            if show_perp_perp:
                if show_spot_perp and not args.quiet:
                    print()  # Add spacing
                print_header(f"PERP↔PERP (Extreme Funding) - Top {len(perp_perp_opps)}")
                print_opportunity_table(perp_perp_opps, quiet=args.quiet)
                print_summary(perp_perp_opps, quiet=args.quiet)

            # Print detailed notes for top 5 from each strategy
            if not args.quiet:
                if show_spot_perp and spot_perp_opps:
                    print("\n--- Top 5 SPOT↔PERP Details ---\n")
                    for i, opp in enumerate(spot_perp_opps[:5], 1):
                        print(f"#{i} {opp.symbol} [{opp.strategy_type.upper()}]")
                        print(f"  {opp.direction}")
                        print(f"  Funding APR (exchange rate): Long {opp.long_funding_apr:+.2f}% | Short {opp.short_funding_apr:+.2f}%")
                        print(f"  Net Funding PnL APR: {opp.net_funding_pnl_apr:+.2f}% (position PnL from funding)")
                        print(f"  Cost Breakdown:")
                        print(f"    Fees: {opp.fee_cost_pct:.3f}%")
                        print(f"    Spread: {opp.spread_cost_pct:+.3f}% ({opp.spread_source})")
                        print(f"    Total: {opp.total_cost_pct:.3f}%")
                        print(f"  Cost Min (fees only): {opp.cost_min_pct:.3f}%")
                        print(f"  Cost Est (fees+spread): {opp.cost_est_pct:.3f}%")
                        if opp.breakeven_days:
                            print(f"  Min-Hold Breakeven: {opp.breakeven_days:.1f} days")
                        else:
                            print(f"  Min-Hold Breakeven: N/A (net funding PnL negative)")
                        print(f"  7-Day Hold PnL: {opp.pnl_7d_pct:+.2f}% (${opp.pnl_7d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_7d:+.1f}%")
                        print(f"  14-Day Hold PnL: {opp.pnl_14d_pct:+.2f}% (${opp.pnl_14d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_14d:+.1f}%")
                        # Print funding quality for spot-perp
                        if opp.strategy_type == 'spot_perp' and opp.funding_quality:
                            print(f"  Funding Stability: {opp.funding_quality}")
                        # Print data quality notes
                        if opp.data_quality and opp.data_quality != 'good':
                            print(f"  Data Quality Notes: {opp.data_quality}")
                        # Print flags
                        flags = []
                        if opp.requires_short_spot:
                            flags.append("⚠ Requires shorting spot")
                        if flags:
                            print(f"  Flags: {' | '.join(flags)}")
                        print()

                if show_perp_perp and perp_perp_opps:
                    print("\n--- Top 5 PERP↔PERP Details ---\n")
                    for i, opp in enumerate(perp_perp_opps[:5], 1):
                        print(f"#{i} {opp.symbol} [{opp.strategy_type.upper()}]")
                        print(f"  {opp.direction}")
                        print(f"  Funding APR (exchange rate): Long {opp.long_funding_apr:+.2f}% | Short {opp.short_funding_apr:+.2f}%")
                        print(f"  Net Funding PnL APR: {opp.net_funding_pnl_apr:+.2f}% (position PnL from funding)")
                        print(f"  Cost Breakdown:")
                        print(f"    Fees: {opp.fee_cost_pct:.3f}%")
                        print(f"    Spread: {opp.spread_cost_pct:+.3f}% ({opp.spread_source})")
                        print(f"    Total: {opp.total_cost_pct:.3f}%")
                        print(f"  Cost Min (fees only): {opp.cost_min_pct:.3f}%")
                        print(f"  Cost Est (fees+spread): {opp.cost_est_pct:.3f}%")
                        if opp.breakeven_days:
                            print(f"  Min-Hold Breakeven: {opp.breakeven_days:.1f} days")
                        else:
                            print(f"  Min-Hold Breakeven: N/A (net funding PnL negative)")
                        print(f"  7-Day Hold PnL: {opp.pnl_7d_pct:+.2f}% (${opp.pnl_7d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_7d:+.1f}%")
                        print(f"  14-Day Hold PnL: {opp.pnl_14d_pct:+.2f}% (${opp.pnl_14d_usd:+.2f} on $10k notional) | APR: {opp.apr_from_14d:+.1f}%")
                        # Print data quality notes
                        if opp.data_quality and opp.data_quality != 'good':
                            print(f"  Data Quality Notes: {opp.data_quality}")
                        print()

            # Print assumptions
            if not args.quiet:
                print("--- Assumptions ---")
                print("  Notional: $10,000")
                print("  Execution: market (taker) by default")
                print("  Fees: loaded from config/fees.json per venue and product type")
                print("  Spread: cross-spread (bid for sell, ask for buy), fallback to proxy (10 bps)")
                print("  Funding: prefer 14D average; fallback to latest if unavailable")
                print("  Funding sign convention: funding > 0 = long pays, short receives")
                print("  Cost: roundtrip fees+spread applied once at position entry")
                print("  7D PnL = net_funding_pnl_apr * (7/365) - cost_est_pct")
                print("  14D PnL = net_funding_pnl_apr * (14/365) - cost_est_pct")
                print("  APR from 7D = pnl_7d_pct * (365/7)")
                print("  APR from 14D = pnl_14d_pct * (365/14)")
                print("  Breakeven = cost_est_pct / (net_funding_pnl_apr / 365)")
                print("\n  Strategy Types:")
                print("    SPOT↔PERP (Carry): Long spot + Short perp to collect funding. Uses spot for hedge.")
                print("    PERP↔PERP (Extreme): Cross-venue funding arbitrage between perp contracts.")

            # Exit with error if no opportunities found
            total_opps = len(spot_perp_opps) + len(perp_perp_opps)
            if not total_opps and not args.quiet:
                sys.exit(1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if not args.quiet:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
