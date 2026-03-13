#!/usr/bin/env python3
"""Verify DB v3 invariants.

This is a lightweight invariant checker to prevent silent key-collisions.

Checks:
- table existence
- for OKX: if BTC-USDT spot and BTC-USDT-SWAP perp are present, inst_id must differ
- symbol_key must be quote-aware (contains ':')

Exit code non-zero on failure.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def q1(con, sql, params=()):
    cur = con.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    if not args.db.exists():
        raise SystemExit(f"missing db: {args.db} (run scripts/db_v3_init.py)")

    con = sqlite3.connect(str(args.db))
    try:
        con.execute("PRAGMA foreign_keys = ON")
        # core v3 tables
        for t in ("instruments_v3", "prices_v3", "funding_v3"):
            n = q1(con, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (t,))
            if not n:
                raise SystemExit(f"missing table: {t}")

        # position manager tables
        pm_tables = ("pm_positions", "pm_legs", "pm_leg_snapshots", "pm_account_snapshots", "pm_cashflows")
        for t in pm_tables:
            n = q1(con, "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (t,))
            if not n:
                raise SystemExit(f"missing table: {t}")

        # symbol_key sanity
        bad = q1(con, "SELECT count(*) FROM instruments_v3 WHERE symbol_key NOT LIKE '%:%'")
        if bad and bad > 0:
            raise SystemExit(f"bad symbol_key rows (missing ':'): {bad}")

        # OKX specific collision check if present
        okx_spot = q1(con, "SELECT inst_id FROM instruments_v3 WHERE venue='okx' AND raw_symbol='BTC-USDT' AND contract_type='SPOT' LIMIT 1")
        okx_perp = q1(con, "SELECT inst_id FROM instruments_v3 WHERE venue='okx' AND raw_symbol='BTC-USDT-SWAP' AND contract_type='PERP' LIMIT 1")
        if okx_spot and okx_perp and okx_spot == okx_perp:
            raise SystemExit("collision: OKX BTC-USDT spot and BTC-USDT-SWAP perp share inst_id")

    finally:
        con.close()

    print("OK: verify_db_v3 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
