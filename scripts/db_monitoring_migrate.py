#!/usr/bin/env python3
"""Apply monitoring schema migrations to arbit_v3.db.

v1: Creates new tables: pm_fills, pm_entry_prices, pm_spreads, pm_portfolio_snapshots.
v2: Adds trade aggregation layer: pm_trades, pm_trade_fills, pm_trade_reconcile_warnings.
    Also extends pm_positions with base and strategy_type columns.
Also fixes legacy spot inst_ids in pm_legs (e.g., GOOGL -> GOOGL/USDC).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_MONITORING_V1 = ROOT / "tracking" / "sql" / "schema_monitoring_v1.sql"
SCHEMA_MONITORING_V2 = ROOT / "tracking" / "sql" / "schema_monitoring_v2.sql"
# Keep backward-compatible alias
SCHEMA_MONITORING = SCHEMA_MONITORING_V1
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def _apply_sql_file(con: sqlite3.Connection, path: Path, tolerate_duplicate_column: bool = False) -> None:
    """Apply a SQL file statement by statement.

    When tolerate_duplicate_column=True, silently skip ALTER TABLE statements
    that fail with 'duplicate column name' (idempotent re-runs).

    Inline-comment limitation:
        The comment-stripping pass below filters whole-line ``--`` comments only
        (lines whose first non-whitespace characters are ``--``).  Inline trailing
        comments such as ``CREATE TABLE x(...);  -- note`` are NOT stripped.
        SQLite treats the trailing ``-- note`` text as a no-op empty statement,
        which is harmless in practice, but future developers who see unexpected
        no-op executions in tracing should be aware of this.

    split(";") fragility:
        Splitting on ``";"`` is only safe for schema files that contain:
          - No ``CREATE TRIGGER ... BEGIN ... END`` blocks (each ``END;``
            introduces an embedded semicolon that would be split incorrectly).
          - No string literals with embedded semicolons.
        If either of those constructs is ever added to a schema file, replace
        this helper with ``con.executescript()`` (which handles semicolons
        inside trigger bodies correctly), or upgrade this parser.
    """
    raw = path.read_text(encoding="utf-8")
    # Strip single-line comments before splitting on ";" to avoid false splits
    # inside comment text (e.g. "-- foo; bar" would yield a bogus "bar" statement).
    lines = [ln for ln in raw.splitlines() if not ln.lstrip().startswith("--")]
    sql = "\n".join(lines)
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:
            if tolerate_duplicate_column and "duplicate column name" in str(e):
                continue
            raise
    con.commit()


def apply_schema(con: sqlite3.Connection) -> None:
    """Apply monitoring v1 and v2 schemas."""
    # v1: use executescript (no per-statement errors expected; tables are IF NOT EXISTS)
    sql_v1 = SCHEMA_MONITORING_V1.read_text(encoding="utf-8")
    con.executescript(sql_v1)
    print("OK: monitoring v1 schema applied")

    # v2: apply statement-by-statement to tolerate duplicate column errors on re-runs
    _apply_sql_file(con, SCHEMA_MONITORING_V2, tolerate_duplicate_column=True)
    print("OK: monitoring v2 schema applied")


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
    ap = argparse.ArgumentParser(description="Apply monitoring schema migrations (v1 + v2)")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without applying")
    args = ap.parse_args()

    if not SCHEMA_MONITORING_V1.exists():
        raise SystemExit(f"missing schema: {SCHEMA_MONITORING_V1}")
    if not SCHEMA_MONITORING_V2.exists():
        raise SystemExit(f"missing schema: {SCHEMA_MONITORING_V2}")
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
