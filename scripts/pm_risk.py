#!/usr/bin/env python3
"""Position Manager Risk CLI

Computes and displays risk metrics for managed positions.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.position_manager.risk import compute_all_rollups, DEFAULT_WARN_DRIFT_USD, DEFAULT_CRIT_DRIFT_USD, DEFAULT_WARN_DRIFT_PCT, DEFAULT_CRIT_DRIFT_PCT


def main():
    parser = argparse.ArgumentParser(
        description="Compute and display risk metrics for managed positions"
    )
    parser.add_argument(
        "--db",
        type=str,
        default=str(ROOT / "tracking" / "db" / "arbit_v3.db"),
        help="Path to SQLite database (default: tracking/db/arbit_v3.db)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON instead of table"
    )
    parser.add_argument(
        "--warn-drift-usd",
        type=float,
        default=DEFAULT_WARN_DRIFT_USD,
        help=f"Warning threshold for drift in USD (default: ${DEFAULT_WARN_DRIFT_USD})"
    )
    parser.add_argument(
        "--crit-drift-usd",
        type=float,
        default=DEFAULT_CRIT_DRIFT_USD,
        help=f"Critical threshold for drift in USD (default: ${DEFAULT_CRIT_DRIFT_USD})"
    )
    parser.add_argument(
        "--warn-drift-pct",
        type=float,
        default=DEFAULT_WARN_DRIFT_PCT,
        help=f"Warning threshold for drift percentage (default: {DEFAULT_WARN_DRIFT_PCT*100:.0f} pct)"
    )
    parser.add_argument(
        "--crit-drift-pct",
        type=float,
        default=DEFAULT_CRIT_DRIFT_PCT,
        help=f"Critical threshold for drift percentage (default: {DEFAULT_CRIT_DRIFT_PCT*100:.0f} pct)"
    )

    args = parser.parse_args()

    # Connect to database
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    try:
        # Compute rollups
        rollups = compute_all_rollups(
            con,
            warn_drift_usd=args.warn_drift_usd,
            crit_drift_usd=args.crit_drift_usd,
            warn_drift_pct=args.warn_drift_pct,
            crit_drift_pct=args.crit_drift_pct
        )

        if args.json:
            # Output as JSON
            print(json.dumps(rollups, indent=2))
        else:
            # Output as table
            print_table(rollups)

    finally:
        con.close()


def print_table(rollups):
    """Print rollups as a formatted table."""
    if not rollups:
        print("No managed positions found.")
        return

    # Table header
    print("\n" + "=" * 140)
    print(f"{'Position ID':<20} {'Status':<10} {'Venue':<10} {'Legs':<5} {'Snapshots':<10} {'Gross Notional':<15} {'Net Delta':<12} {'Drift USD':<12} {'Drift %':<10} {'Risk':<10}")
    print("=" * 140)

    # Table rows
    for rollup in rollups:
        position_id = rollup["position_id"][:20]  # Truncate if too long
        status = rollup["status"]
        venue = rollup["venue"]
        leg_count = rollup["leg_count"]
        snapshots_status = rollup["snapshots_status"]
        gross_notional = f"${rollup['gross_notional_usd']:,.0f}" if rollup["gross_notional_usd"] is not None else "N/A"
        net_delta = f"${rollup['net_delta_usd']:,.2f}" if rollup.get("net_delta_usd") is not None else "N/A"
        drift_usd = f"${rollup['drift_usd']:,.2f}" if rollup.get("drift_usd") is not None else "N/A"
        drift_pct = f"{rollup['drift_pct']*100:.2f}%" if rollup['drift_pct'] is not None else "N/A"

        # Risk flags
        if rollup["crit"]:
            risk = "CRIT"
        elif rollup["warn"]:
            risk = "WARN"
        else:
            risk = "OK"

        print(f"{position_id:<20} {status:<10} {venue:<10} {leg_count:<5} {snapshots_status:<10} {gross_notional:<15} {net_delta:<12} {drift_usd:<12} {drift_pct:<10} {risk:<10}")

    print("=" * 140)

    # Summary
    total = len(rollups)
    ok = sum(1 for r in rollups if not r["warn"] and not r["crit"])
    warn = sum(1 for r in rollups if r["warn"] and not r["crit"])
    crit = sum(1 for r in rollups if r["crit"])
    stale_or_missing = sum(1 for r in rollups if r["snapshots_status"] in ("stale", "missing", "partial"))

    print(f"\nSummary: {total} positions | {ok} OK | {warn} WARN | {crit} CRIT | {stale_or_missing} stale/missing snapshots")
    print()


if __name__ == "__main__":
    main()
