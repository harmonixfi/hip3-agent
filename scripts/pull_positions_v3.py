#!/usr/bin/env python3
"""CLI script to pull position snapshots from venue APIs.

Usage:
    python3 scripts/pull_positions_v3.py --registry config/positions.example.json
    python3 scripts/pull_positions_v3.py --db tracking.db --venues paradex,hyperliquid
    python3 scripts/pull_positions_v3.py --registry config/positions.json --venues hyperliquid
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Project env convention: source /mnt/data/agents/arbit/.arbit_env (optional)
# This file is NOT auto-loaded here; keep explicit sourcing in shell/cron.

from tracking.position_manager.puller import run_pull


def main():
    parser = argparse.ArgumentParser(
        description="Pull position snapshots from venue private APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --registry config/positions.example.json
  %(prog)s --db tracking.db
  %(prog)s --registry config/positions.json --venues paradex,hyperliquid
  %(prog)s --db tracking.db --venues hyperliquid --quiet
        """,
    )

    # Data source options (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument(
        "--registry",
        type=Path,
        help="Path to position registry JSON file",
    )
    source_group.add_argument(
        "--db",
        type=Path,
        help="Path to database file (loads positions from pm_positions/pm_legs)",
    )

    # Filter options
    parser.add_argument(
        "--venues",
        type=str,
        help="Comma-separated list of venues to pull from (e.g., paradex,hyperliquid)",
    )

    # Output options
    parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Parse venues filter
    venues_filter = None
    if args.venues:
        venues_filter = [v.strip().lower() for v in args.venues.split(",") if v.strip()]

    # Determine database path
    default_db = ROOT / "tracking" / "db" / "arbit_v3.db"
    if args.registry:
        # Use default v3 DB when registry specified
        db_path = default_db
    else:
        db_path = args.db

    # Run puller
    try:
        summary = run_pull(
            db_path=db_path,
            registry_path=args.registry,
            venues_filter=venues_filter,
            verbose=not args.quiet,
        )

        # Exit with error code if any venues failed
        if summary["venues_failed"]:
            sys.exit(1)

        sys.exit(0)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
