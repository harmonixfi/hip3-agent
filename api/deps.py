"""Dependency injection for FastAPI.

Provides SQLite connections as async generator dependencies.
Read-only connections for GET endpoints, writable for POST.
"""

from __future__ import annotations

import sqlite3
from typing import Generator

from api.config import get_settings


def _connect(readonly: bool = True) -> sqlite3.Connection:
    """Open a SQLite connection.

    Args:
        readonly: If True, open with uri mode ?mode=ro for safety.
    """
    settings = get_settings()
    db_path = str(settings.db_path)

    if readonly:
        # SQLite URI mode for read-only access
        uri = f"file:{db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(db_path)

    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row  # dict-like access
    return con


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Read-only DB connection for GET endpoints."""
    con = _connect(readonly=True)
    try:
        yield con
    finally:
        con.close()


def get_db_writable() -> Generator[sqlite3.Connection, None, None]:
    """Writable DB connection for POST endpoints (cashflow insert)."""
    con = _connect(readonly=False)
    try:
        yield con
    finally:
        con.close()
