"""Tests for retroactive snapshot recalculation."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMA_PM = Path(__file__).parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = Path(__file__).parent.parent / "tracking" / "sql" / "schema_vault.sql"


def _setup_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())
    return con


def test_recalc_updates_apr_not_equity():
    from tracking.vault.recalc import recalc_snapshots

    con = _setup_db()
    now_ms = int(time.time() * 1000)
    day_ms = 86400000

    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        ("test", "Test", "DELTA_NEUTRAL", "ACTIVE", "[]", 100.0, now_ms, now_ms),
    )

    ts_day1 = now_ms - 2 * day_ms
    ts_day2 = now_ms - day_ms
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("test", ts_day1, 10000.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("test", ts_day2, 10100.0, 5.0, 5.0, 5.0),
    )

    con.execute(
        "INSERT INTO vault_snapshots(ts, total_equity_usd, total_apr, apr_30d, apr_7d) VALUES (?,?,?,?,?)",
        (ts_day1, 10000.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        "INSERT INTO vault_snapshots(ts, total_equity_usd, total_apr, apr_30d, apr_7d) VALUES (?,?,?,?,?)",
        (ts_day2, 10100.0, 5.0, 5.0, 5.0),
    )
    con.commit()

    con.execute(
        """
        INSERT INTO vault_cashflows(ts, cf_type, amount, strategy_id, created_at_ms)
        VALUES (?,?,?,?,?)
        """,
        (ts_day1 + 1000, "DEPOSIT", 50.0, "test", now_ms),
    )
    con.commit()

    count = recalc_snapshots(con, ts_day1)
    assert count == 2

    row = con.execute(
        "SELECT equity_usd FROM vault_strategy_snapshots WHERE ts = ?", (ts_day2,)
    ).fetchone()
    assert row[0] == 10100.0

    row = con.execute(
        "SELECT apr_since_inception FROM vault_strategy_snapshots WHERE ts = ?", (ts_day2,)
    ).fetchone()
    assert row[0] != 5.0
