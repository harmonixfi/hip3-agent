#!/usr/bin/env python3
"""Apply monitoring v1 schema migration to arbit_v3.db.

Creates new tables: pm_fills, pm_entry_prices, pm_spreads, pm_portfolio_snapshots.
Also fixes legacy spot inst_ids in pm_legs (e.g., GOOGL -> GOOGL/USDC).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_MONITORING = ROOT / "tracking" / "sql" / "schema_monitoring_v1.sql"
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def apply_schema(con: sqlite3.Connection) -> None:
    """Apply the monitoring v1 schema."""
    sql = SCHEMA_MONITORING.read_text(encoding="utf-8")
    con.executescript(sql)
    print("OK: monitoring v1 schema applied")


def fix_legacy_spot_inst_ids(con: sqlite3.Connection) -> int:
    """Append /USDC to legacy spot inst_ids that lack a slash.

    Targets: LONG legs in SPOT_PERP positions where inst_id has no '/'.
    Example: GOOGL -> GOOGL/USDC
    """
    cur = con.execute(
        """
        SELECT l.leg_id, l.inst_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.strategy = 'SPOT_PERP'
          AND l.side = 'LONG'
          AND l.inst_id NOT LIKE '%/%'
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("OK: no legacy spot inst_ids to fix")
        return 0

    for leg_id, old_inst_id in rows:
        new_inst_id = f"{old_inst_id}/USDC"
        con.execute(
            "UPDATE pm_legs SET inst_id = ? WHERE leg_id = ?",
            (new_inst_id, leg_id),
        )
        print(f"  fixed: {leg_id}: {old_inst_id} -> {new_inst_id}")

    con.commit()
    print(f"OK: fixed {len(rows)} legacy spot inst_ids")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply monitoring v1 migration")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without applying")
    args = ap.parse_args()

    if not SCHEMA_MONITORING.exists():
        raise SystemExit(f"missing schema: {SCHEMA_MONITORING}")
    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}. Run db_v3_init.py first.")

    con = sqlite3.connect(str(args.db))
    try:
        con.execute("PRAGMA foreign_keys = ON")

        if args.dry_run:
            # Show legacy inst_ids that would be fixed
            cur = con.execute(
                """
                SELECT l.leg_id, l.inst_id
                FROM pm_legs l
                JOIN pm_positions p ON p.position_id = l.position_id
                WHERE p.strategy = 'SPOT_PERP'
                  AND l.side = 'LONG'
                  AND l.inst_id NOT LIKE '%/%'
                """
            )
            rows = cur.fetchall()
            print(f"DRY RUN: would fix {len(rows)} inst_ids:")
            for leg_id, inst_id in rows:
                print(f"  {leg_id}: {inst_id} -> {inst_id}/USDC")
            return 0

        apply_schema(con)
        fix_legacy_spot_inst_ids(con)

    finally:
        con.close()

    print(f"\nMigration complete: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
