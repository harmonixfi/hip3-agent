#!/usr/bin/env python3
"""Make pm_cashflows.venue nullable (SQLite cannot ALTER COLUMN DROP NOT NULL).

Run once on existing DBs after pulling schema_pm_v3.sql change:
  source .arbit_env && .venv/bin/python scripts/migrate_pm_cashflows_venue_nullable.py

Safe to re-run: no-op if venue is already nullable.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent


def _venue_is_not_null(con: sqlite3.Connection) -> bool:
    for row in con.execute("PRAGMA table_info(pm_cashflows)").fetchall():
        if row[1] == "venue":
            return bool(row[3])
    return False


def migrate(con: sqlite3.Connection) -> bool:
    if not _venue_is_not_null(con):
        return False

    con.executescript(
        """
        PRAGMA foreign_keys = OFF;
        BEGIN;

        CREATE TABLE pm_cashflows_new (
          cashflow_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          position_id TEXT,
          leg_id TEXT,
          venue TEXT,
          account_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          cf_type TEXT NOT NULL CHECK (cf_type IN (
            'REALIZED_PNL', 'FEE', 'FUNDING', 'TRANSFER', 'DEPOSIT', 'WITHDRAW', 'OTHER'
          )),
          amount REAL NOT NULL,
          currency TEXT NOT NULL,
          description TEXT,
          raw_json TEXT,
          meta_json TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
        );

        INSERT INTO pm_cashflows_new (
          cashflow_id, position_id, leg_id, venue, account_id, ts, cf_type,
          amount, currency, description, raw_json, meta_json
        )
        SELECT
          cashflow_id, position_id, leg_id, venue, account_id, ts, cf_type,
          amount, currency, description, raw_json, meta_json
        FROM pm_cashflows;

        DROP TABLE pm_cashflows;
        ALTER TABLE pm_cashflows_new RENAME TO pm_cashflows;

        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_position_id ON pm_cashflows(position_id);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_leg_id ON pm_cashflows(leg_id);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_venue ON pm_cashflows(venue);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_account_id ON pm_cashflows(account_id);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_ts ON pm_cashflows(ts);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_venue_ts ON pm_cashflows(venue, ts);
        CREATE INDEX IF NOT EXISTS idx_pm_cashflows_type ON pm_cashflows(cf_type);

        COMMIT;
        PRAGMA foreign_keys = ON;
        """
    )
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--db",
        type=Path,
        default=ROOT / "tracking" / "db" / "arbit_v3.db",
        help="SQLite path",
    )
    args = ap.parse_args()

    if not args.db.exists():
        print(f"ERROR: DB not found: {args.db}")
        return 1

    con = sqlite3.connect(str(args.db))
    try:
        con.execute("PRAGMA foreign_keys = ON")
        if migrate(con):
            con.commit()
            print(f"OK: migrated pm_cashflows.venue nullable at {args.db}")
        else:
            print(f"OK: no migration needed (venue already nullable): {args.db}")
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
