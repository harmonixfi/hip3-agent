#!/usr/bin/env python3
"""CLI for monitoring carry metrics on managed positions.

Usage:
    python3 scripts/pm_carry.py           # Display table
    python3 scripts/pm_carry.py --json    # Output JSON
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.position_manager.risk import load_managed_positions
from tracking.position_manager.carry import compute_all_carries


# Paths
DB_PATH = Path(__file__).parent.parent / "tracking" / "db" / "arbit_v3.db"
LORIS_CSV_PATH = Path(__file__).parent.parent / "data" / "loris_funding_history.csv"


def format_apr(apr: float) -> str:
    """Format APR value with sign and percentage."""
    if apr is None:
        return "N/A"
    sign = "+" if apr >= 0 else ""
    return f"{sign}{apr:.2f}%"


def format_8h(rate: float) -> str:
    """Format 8h funding rate."""
    if rate is None:
        return "N/A"
    sign = "+" if rate >= 0 else ""
    return f"{sign}{rate*100:.3f}%"


def get_exit_signal(carry: dict) -> str:
    """Determine signal using smoothed+persistence rules.

    - BTC EXIT: require ~12h persistence (smooth_ok_12h + persist_nonpos_12h + apr_smooth_12h<=0)
    - Others EXIT: require ~24h persistence
    - WARN/REDUCE: require ~12h persistence below thresholds
    """

    sym = (carry.get("symbol_hint") or str(carry.get("position_id", "")).split("_", 1)[0] or "").upper()

    apr_s12 = carry.get("apr_smooth_12h")
    apr_s24 = carry.get("apr_smooth_24h")

    ok12 = bool(carry.get("smooth_ok_12h"))
    ok24 = bool(carry.get("smooth_ok_24h"))

    if sym == "BTC":
        if ok12 and carry.get("persist_nonpos_12h") and (apr_s12 is not None and float(apr_s12) <= 0.0):
            return "EXIT"
    else:
        if ok24 and carry.get("persist_nonpos_24h") and (apr_s24 is not None and float(apr_s24) <= 0.0):
            return "EXIT"

    if ok12 and (carry.get("persist_below_half_14d_12h") or carry.get("persist_below_10apr_12h")):
        return "WARN"

    return ""


def print_table(carries: list[dict]) -> None:
    """Print carry metrics as a table."""
    if not carries:
        print("No managed positions found.")
        return

    # Header
    print(f"{'Position ID':<25} {'Status':<8} {'APR S12':<10} {'APR Cur':<10} {'APR 14D':<10} {'EXIT_SIGNAL':<12}")
    print("-" * 92)

    # Rows
    for carry in carries:
        pos_id = carry['position_id'][:25]
        status = carry['status'][:8]
        apr_s12 = format_apr(carry.get('apr_smooth_12h'))
        apr_cur = format_apr(carry['apr_cur'])
        apr_14d = format_apr(carry.get('apr_14d'))
        signal = get_exit_signal(carry)

        # Keep deterministic/simple output for scripting
        # (no ANSI colors; emojis are ok but keep signal machine-readable)
        if signal == "EXIT":
            signal = "EXIT"
        elif signal == "WARN":
            signal = "WARN"

        # Highlight missing funding data
        if carry['missing_funding_data']:
            pos_id = f"{pos_id}*"

        print(f"{pos_id:<25} {status:<8} {apr_s12:<10} {apr_cur:<10} {apr_14d:<10} {signal:<8}")

    # Footer
    print()
    missing_count = sum(1 for c in carries if c['missing_funding_data'])
    if missing_count > 0:
        print(f"* {missing_count} position(s) have missing funding data (check leg details)")
    print()


def print_json(carries: list[dict]) -> None:
    """Print carry metrics as JSON."""
    output = {
        "@type": "pm_carry_report",
        "positions": carries,
    }
    print(json.dumps(output, indent=2))


def print_details(carries: list[dict]) -> None:
    """Print detailed leg-by-leg carry information."""
    for carry in carries:
        print(f"\n{'='*60}")
        print(f"Position: {carry['position_id']} ({carry['venue']}/{carry['strategy']})")
        print(f"Status: {carry['status']}")
        print(f"Net 8h: {format_8h(carry['net_8h_cur'])}")
        print(f"APR Cur: {format_apr(carry['apr_cur'])}")
        if carry.get('apr_7d'):
            print(f"APR 7D: {format_apr(carry['apr_7d'])}")
        if carry.get('apr_14d'):
            print(f"APR 14D: {format_apr(carry['apr_14d'])}")
        print(f"\nLegs:")
        print(f"  {'Leg ID':<20} {'Inst':<15} {'Side':<6} {'8h Cur':<10} {'Source':<15}")
        print("  " + "-"*65)
        for leg in carry['legs']:
            leg_id = leg['leg_id'][:20]
            inst = leg['inst_id'][:15]
            side = leg['side'][:6]
            funding = format_8h(leg['funding_8h_cur'])
            source = leg['data_source'][:15]
            if leg.get('missing_funding_data'):
                source = f"{source}*"
            print(f"  {leg_id:<20} {inst:<15} {side:<6} {funding:<10} {source:<15}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Monitor carry metrics for managed arbitrage positions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 scripts/pm_carry.py               # Show table
  python3 scripts/pm_carry.py --json        # Output JSON
  python3 scripts/pm_carry.py --details    # Show leg-by-leg details
        """
    )
    parser.add_argument(
        '--db',
        type=str,
        default=str(DB_PATH),
        help=f"Path to SQLite database (default: {DB_PATH})"
    )
    parser.add_argument(
        '--loris-csv',
        type=str,
        default=str(LORIS_CSV_PATH),
        help=f"Path to Loris funding history CSV (default: {LORIS_CSV_PATH})"
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help="Output as JSON"
    )
    parser.add_argument(
        '--details',
        action='store_true',
        help="Show detailed leg-by-leg information"
    )
    parser.add_argument(
        '--position',
        type=str,
        help="Filter to specific position ID"
    )

    args = parser.parse_args()

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(db_path))
    con.row_factory = sqlite3.Row

    loris_csv_path = Path(args.loris_csv)

    # Compute carries
    carries = compute_all_carries(con, loris_csv_path)

    # Filter by position if requested
    if args.position:
        carries = [c for c in carries if c['position_id'] == args.position]
        if not carries:
            print(f"Error: Position '{args.position}' not found", file=sys.stderr)
            return 1

    # Output
    if args.json:
        print_json(carries)
    elif args.details:
        print_details(carries)
    else:
        print_table(carries)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
