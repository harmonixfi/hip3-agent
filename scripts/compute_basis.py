#!/usr/bin/env python3
"""
Compute basis/spread for shared symbols across venues and store to database.

Usage:
    python3 compute_basis.py [--horizon-days DAYS] [--min-price PRICE]
"""

import sys
import argparse
from datetime import datetime
import os

# Add tracking directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tracking'))

from analytics.basis import BasisEngine


def print_top_opportunities(basis_records, top_n=10):
    """
    Print top N basis opportunities.

    Args:
        basis_records: List of basis records
        top_n: Number of top opportunities to print
    """
    if not basis_records:
        print("No basis records found.")
        return

    # Sort by absolute basis_pct
    sorted_by_abs = sorted(
        basis_records,
        key=lambda r: abs(r['basis_pct']),
        reverse=True
    )

    # Sort by absolute annualized_basis_pct
    sorted_by_annual = sorted(
        basis_records,
        key=lambda r: abs(r['annualized_basis_pct']),
        reverse=True
    )

    print("\n" + "="*80)
    print(f"TOP {top_n} BASIS OPPORTUNITIES (BY ABSOLUTE SPREAD %)")
    print("="*80)
    print(f"{'Symbol':<12} {'Venue A → B':<20} {'Spread %':<12} {'Price A':<12} {'Price B':<12}")
    print("-"*80)

    for i, r in enumerate(sorted_by_abs[:top_n], 1):
        print(f"{i:2d}. {r['symbol']:<10} "
              f"{r['leg_a_venue']:>5} → {r['leg_b_venue']:<5} "
              f"{r['basis_pct']:>10.4f}% "
              f"${r['leg_a_price']:>10.4f} "
              f"${r['leg_b_price']:>10.4f}")

    print("\n" + "="*80)
    print(f"TOP {top_n} ANNUALIZED BASIS OPPORTUNITIES")
    print("="*80)
    print(f"{'Symbol':<12} {'Venue A → B':<20} {'Annual %':<12} {'Spread %':<12}")
    print("-"*80)

    for i, r in enumerate(sorted_by_annual[:top_n], 1):
        print(f"{i:2d}. {r['symbol']:<10} "
              f"{r['leg_a_venue']:>5} → {r['leg_b_venue']:<5} "
              f"{r['annualized_basis_pct']:>10.4f}% "
              f"{r['basis_pct']:>10.4f}%")


def print_summary(basis_records):
    """
    Print summary statistics for basis records.

    Args:
        basis_records: List of basis records
    """
    if not basis_records:
        print("No basis records found.")
        return

    # Statistics
    basis_pcts = [r['basis_pct'] for r in basis_records]
    annual_pcts = [r['annualized_basis_pct'] for r in basis_records]

    print("\n" + "="*80)
    print("SUMMARY STATISTICS")
    print("="*80)
    print(f"Total pairs computed: {len(basis_records)}")

    # Basis spread statistics
    print(f"\nBasis Spread %:")
    print(f"  Mean:    {sum(basis_pcts) / len(basis_pcts):.4f}%")
    print(f"  Max:     {max(basis_pcts):.4f}%")
    print(f"  Min:     {min(basis_pcts):.4f}%")
    print(f"  Std Dev: {__import__('statistics').stdev(basis_pcts) if len(basis_pcts) > 1 else 0:.4f}%")

    # Annualized basis statistics
    print(f"\nAnnualized Basis %:")
    print(f"  Mean:    {sum(annual_pcts) / len(annual_pcts):.4f}%")
    print(f"  Max:     {max(annual_pcts):.4f}%")
    print(f"  Min:     {min(annual_pcts):.4f}%")

    # Unique symbols and venue pairs
    unique_symbols = len(set(r['symbol'] for r in basis_records))
    unique_venue_pairs = len(set((r['leg_a_venue'], r['leg_b_venue']) for r in basis_records))

    print(f"\nUnique symbols: {unique_symbols}")
    print(f"Unique venue pairs: {unique_venue_pairs}")

    # Count by venue pair
    print(f"\nRecords by venue pair:")
    from collections import Counter
    venue_pairs = Counter(
        (r['leg_a_venue'], r['leg_b_venue'])
        for r in basis_records
    )
    for pair, count in venue_pairs.most_common():
        print(f"  {pair[0]} ↔ {pair[1]}: {count} pairs")


def main():
    parser = argparse.ArgumentParser(
        description='Compute basis/spread for shared symbols across venues'
    )
    parser.add_argument(
        '--db-path',
        default='/mnt/data/agents/arbit/tracking/db/arbit.db',
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--horizon-days',
        type=float,
        default=1.0,
        help='Mean reversion horizon in days (default: 1.0)'
    )
    parser.add_argument(
        '--min-price',
        type=float,
        default=0.0,
        help='Minimum price threshold (default: 0.0)'
    )
    parser.add_argument(
        '--top',
        type=int,
        default=10,
        help='Number of top opportunities to display (default: 10)'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress output (useful for cron jobs)'
    )

    args = parser.parse_args()

    if not args.quiet:
        print("="*80)
        print("BASIS/SPREAD COMPUTATION ENGINE")
        print("="*80)
        print(f"Database: {args.db_path}")
        print(f"Horizon: {args.horizon_days} days")
        print(f"Min price: ${args.min_price}")
        print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

    try:
        with BasisEngine(args.db_path) as engine:
            basis_records = engine.run(
                horizon_days=args.horizon_days,
                min_price=args.min_price
            )

            if not args.quiet:
                print(f"\n✓ Computed {len(basis_records)} basis pairs")

                if basis_records:
                    print_summary(basis_records)
                    print_top_opportunities(basis_records, top_n=args.top)

                print()
                print("="*80)
                print(f"Completed at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print("="*80)

            return 0

    except Exception as e:
        print(f"\n✗ ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
