#!/usr/bin/env python3
"""One-shot migration: wipe hyperliquid FUNDING+FEE in pm_cashflows, then backfill from HL API.

Use once after the ingest fix that matches `delta.coin` namespace to each leg's dex (avoids
HYNA+NATIVE double-count). Ongoing updates use `pm_cashflows.py ingest` as usual.

Prerequisites: `source .arbit_env` (wallets), registry synced so `pm_legs` reflects open HL perps.

Examples:
  .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db --dry-run
  .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db
"""

from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load_pm_cashflows():
    path = ROOT / "scripts" / "pm_cashflows.py"
    spec = importlib.util.spec_from_file_location("pm_cashflows", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _delete_hl_funding_fee(con: sqlite3.Connection) -> int:
    cur = con.execute(
        """
        SELECT COUNT(*) FROM pm_cashflows
        WHERE venue = 'hyperliquid' AND cf_type IN ('FUNDING', 'FEE')
        """
    )
    n = int(cur.fetchone()[0] or 0)
    if n == 0:
        return 0
    con.execute(
        """
        DELETE FROM pm_cashflows
        WHERE venue = 'hyperliquid' AND cf_type IN ('FUNDING', 'FEE')
        """
    )
    con.commit()
    return n


def main() -> int:
    pm = _load_pm_cashflows()
    db_default = pm.DB_DEFAULT
    since_default = pm.HYPERLIQUID_DEFAULT_SINCE_HOURS

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=db_default, help=f"SQLite DB (default: {db_default})")
    ap.add_argument(
        "--since-hours",
        type=int,
        default=since_default,
        help=f"Backfill window for ingest_hyperliquid (default {since_default})",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print counts only; no delete or API calls")
    args = ap.parse_args()

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns

        ensure_multi_wallet_columns(con)

        cur = con.execute(
            """
            SELECT COUNT(*) FROM pm_cashflows
            WHERE venue = 'hyperliquid' AND cf_type IN ('FUNDING', 'FEE')
            """
        )
        n = int(cur.fetchone()[0] or 0)
        if args.dry_run:
            print(
                f"DRY RUN: would delete {n} hyperliquid FUNDING+FEE row(s), "
                f"then backfill ingest_hyperliquid (last {args.since_hours}h)."
            )
            return 0

        deleted = _delete_hl_funding_fee(con)
        print(f"OK: deleted {deleted} hyperliquid FUNDING+FEE row(s).")

        inserted = pm.ingest_hyperliquid(con, since_hours=int(args.since_hours))
        print(f"OK: backfilled {inserted} new event(s) via ingest_hyperliquid.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
