#!/usr/bin/env python3
"""Initialize the tracking database with the position manager schema."""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "tracking.db"
SCHEMA_PATH = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"


def init_db():
    """Initialize database with position manager schema."""
    if not SCHEMA_PATH.exists():
        print(f"ERROR: Schema file not found: {SCHEMA_PATH}")
        return

    print(f"Initializing database at: {DB_PATH}")
    print(f"Schema file: {SCHEMA_PATH}")

    # Read schema
    schema_sql = SCHEMA_PATH.read_text()

    # Connect and create tables
    con = sqlite3.connect(str(DB_PATH))
    con.execute("PRAGMA foreign_keys = ON")

    con.executescript(schema_sql)
    con.commit()

    # Verify
    tables = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()

    print(f"\nCreated {len(tables)} tables:")
    for table in tables:
        print(f"  - {table[0]}")

    con.close()
    print("\n✓ Database initialized successfully")


if __name__ == "__main__":
    init_db()
