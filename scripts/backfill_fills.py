#!/usr/bin/env python3
"""Backfill trade fills for existing positions.

Pulls fill history from Hyperliquid and stores in pm_fills.
Supports backfilling all positions, specific positions, or since a date.

Usage:
    python scripts/backfill_fills.py --all
    python scripts/backfill_fills.py --position pos_xyz_GOLD
    python scripts/backfill_fills.py --since 2026-01-01
    python scripts/backfill_fills.py --all --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
# Ensure repo root is on sys.path so `import tracking...` works.
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill trade fills from Hyperliquid")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--all", action="store_true", help="Backfill all positions (OPEN + CLOSED)")
    ap.add_argument("--position", type=str, help="Backfill a specific position ID")
    ap.add_argument("--since", type=str, help="Start date (YYYY-MM-DD). Default: beginning of time")
    ap.add_argument("--dry-run", action="store_true", help="Show targets without ingesting")
    args = ap.parse_args()

    if not args.all and not args.position:
        ap.error("Specify --all or --position <id>")

    from tracking.pipeline.spot_meta import fetch_spot_index_map
    from tracking.pipeline.fill_ingester import (
        load_fill_targets,
        ingest_hyperliquid_fills,
    )

    con = connect(args.db)

    # Determine since_ms
    since_ms = 0
    if args.since:
        dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        since_ms = int(dt.timestamp() * 1000)

    # Determine position filter
    position_ids = None
    if args.position:
        position_ids = [args.position]

    # Show targets
    targets = load_fill_targets(
        con,
        include_closed=True,
        position_ids=position_ids,
    )

    print(f"Backfill targets: {len(targets)} legs")
    positions_seen = set()
    for t in targets:
        pid = t["position_id"]
        if pid not in positions_seen:
            positions_seen.add(pid)
            # Get position status
            row = con.execute(
                "SELECT status, strategy FROM pm_positions WHERE position_id = ?",
                (pid,),
            ).fetchone()
            status = row[0] if row else "?"
            strategy = row[1] if row else "?"
            print(f"  {pid} [{status}] ({strategy})")
        print(f"    - {t['leg_id']}: {t['inst_id']} ({t['side']}) account={t['account_id'][:8]}...")

    if args.dry_run:
        print("\nDRY RUN: no fills ingested")
        return 0

    # Fetch spot metadata
    print("\nFetching spotMeta...")
    spot_cache = fetch_spot_index_map()
    print(f"  loaded {len(spot_cache)} spot pairs")

    # Run ingestion
    print(f"\nIngesting fills (since_ms={since_ms})...")
    count = ingest_hyperliquid_fills(
        con,
        spot_cache,
        include_closed=True,
        since_ms=since_ms,
        position_ids=position_ids,
    )

    # Summary
    total = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
    print(f"\nBackfill complete: {count} new fills inserted, {total} total in DB")

    # Per-position fill counts
    cur = con.execute("""
        SELECT position_id, COUNT(*) as cnt
        FROM pm_fills
        WHERE position_id IS NOT NULL
        GROUP BY position_id
        ORDER BY cnt DESC
    """)
    print("\nFills per position:")
    for pid, cnt in cur.fetchall():
        print(f"  {pid}: {cnt} fills")

    # Unmapped fills
    unmapped = con.execute(
        "SELECT COUNT(*) FROM pm_fills WHERE position_id IS NULL"
    ).fetchone()[0]
    if unmapped > 0:
        print(f"\n  WARNING: {unmapped} fills could not be mapped to a position")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
