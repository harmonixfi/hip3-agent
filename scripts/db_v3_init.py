#!/usr/bin/env python3
"""Initialize DB v3 (SQLite) using tracking/sql/schema_v3.sql.

Creates (or updates) the v3 tables in a target sqlite file.
Default path: tracking/db/arbit_v3.db
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_V3 = ROOT / "tracking" / "sql" / "schema_v3.sql"
SCHEMA_PM = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    for schema_path, schema_name in [(SCHEMA_V3, "schema_v3.sql"), (SCHEMA_PM, "schema_pm_v3.sql")]:
        if not schema_path.exists():
            raise SystemExit(f"missing schema: {schema_path}")

    args.db.parent.mkdir(parents=True, exist_ok=True)

    # Load both schemas
    sql_v3 = SCHEMA_V3.read_text(encoding="utf-8")
    sql_pm = SCHEMA_PM.read_text(encoding="utf-8")
    combined_sql = sql_v3 + "\n\n" + sql_pm

    con = sqlite3.connect(str(args.db))
    try:
        # IMPORTANT: foreign key enforcement is per-connection in SQLite.
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(combined_sql)
        con.commit()
    finally:
        con.close()

    print(f"OK: initialized v3 db at {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
