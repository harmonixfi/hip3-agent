#!/usr/bin/env python3
"""Initialize arbit.db SQLite database and run schema.sql."""

import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit.db"
SCHEMA_PATH = ROOT / "tracking" / "sql" / "schema.sql"


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Creating database at: {DB_PATH}")

    if DB_PATH.exists():
        print("Database already exists. Recreating...")
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Read and execute schema
    schema_sql = SCHEMA_PATH.read_text()
    cursor.executescript(schema_sql)

    # Enable WAL for better concurrency
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")

    # Verify tables
    tables = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"Tables created: {[t[0] for t in tables]}")

    conn.commit()
    conn.close()

    print("Database initialization complete.")


if __name__ == "__main__":
    main()
