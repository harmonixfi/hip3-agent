#!/usr/bin/env python3
"""One-time migration: wipe hyperliquid FUNDING+FEE, then backfill via hl_reset_backfill (not pm_cashflows).

Does NOT import pm_cashflows.ingest_hyperliquid — cron continues to use scripts/pm_cashflows.py only.

Historical instruments (CLOSED legs): edit config/hl_cashflow_backfill_extra_targets.json

Examples:
  .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db --dry-run
  .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db --start 2026-03-01T00:00:00Z -v
"""

from __future__ import annotations

import argparse
import importlib.util
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_DEFAULT = ROOT / "tracking" / "db" / "arbit_v3.db"


def _load_hl_reset():
    path = ROOT / "scripts" / "hl_reset_backfill.py"
    spec = importlib.util.spec_from_file_location("hl_reset_backfill", path)
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
    hl = _load_hl_reset()
    since_default = hl.HYPERLIQUID_DEFAULT_SINCE_HOURS

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", type=Path, default=DB_DEFAULT, help=f"SQLite DB (default: {DB_DEFAULT})")
    ap.add_argument(
        "--since-hours",
        type=int,
        default=since_default,
        help=f"Backfill window ending at --end or now (default {since_default}h). Ignored if --start is set.",
    )
    ap.add_argument(
        "--start",
        type=str,
        default=None,
        help="UTC range start (ISO or epoch ms). If set, backfill [start, end].",
    )
    ap.add_argument(
        "--end",
        type=str,
        default=None,
        help="UTC range end (default: now). ISO or epoch ms.",
    )
    ap.add_argument(
        "--extra-targets-config",
        type=Path,
        default=None,
        help=f"JSON with include_closed_inst_ids (default: {hl.DEFAULT_CONFIG})",
    )
    ap.add_argument("--dry-run", action="store_true", help="Print counts only; no delete or API calls")
    ap.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose hl_reset_backfill logs (stderr)",
    )
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

        end_ms = hl.parse_ts_to_ms(args.end) if args.end else hl.now_ms()
        if args.start:
            start_ms = hl.parse_ts_to_ms(args.start)
            win_desc = f"[{start_ms} .. {end_ms}] (--start/--end)"
        else:
            start_ms = None
            win_desc = f"last {args.since_hours}h ending {end_ms}"

        if args.dry_run:
            print(f"DRY RUN: would delete {n} hyperliquid FUNDING+FEE row(s), then hl_reset_backfill: {win_desc}.")
            return 0

        if args.verbose:
            import os

            print(
                "=== reset_hyperliquid_cashflows (verbose) ===\n"
                "Ensure you ran:  source .arbit_env\n"
                f"HYPERLIQUID_ADDRESS set: {bool((os.environ.get('HYPERLIQUID_ADDRESS') or '').strip())}\n"
                "Detailed logs go to stderr; redirect:  2> /tmp/hl_reset.log\n"
                "---",
                file=sys.stderr,
            )

        deleted = _delete_hl_funding_fee(con)
        print(f"OK: deleted {deleted} hyperliquid FUNDING+FEE row(s).")

        cfg = Path(args.extra_targets_config) if args.extra_targets_config else None
        if args.start:
            inserted = hl.run_backfill(
                con,
                start_ms=start_ms,
                end_ms=end_ms,
                verbose=bool(args.verbose),
                config_path=cfg,
            )
        else:
            inserted = hl.run_backfill(
                con,
                since_hours=int(args.since_hours),
                end_ms=end_ms if args.end else None,
                verbose=bool(args.verbose),
                config_path=cfg,
            )
        print(f"OK: backfilled {inserted} new event(s) via hl_reset_backfill.")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
