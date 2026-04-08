"""Tests for vault daily snapshot pipeline."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

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


def _insert_strategy(con, strategy_id="test_strat", stype="DELTA_NEUTRAL", status="ACTIVE"):
    now_ms = int(time.time() * 1000)
    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (strategy_id, "Test", stype, status, "[]", 100.0, now_ms, now_ms),
    )
    con.commit()


def test_run_snapshot_empty_strategies():
    from tracking.vault.snapshot import run_daily_snapshot

    con = _setup_db()
    result = run_daily_snapshot(con)
    assert result["strategies_processed"] == 0
    assert result["vault_equity"] == 0.0


def test_run_snapshot_writes_strategy_snapshot():
    from tracking.vault.snapshot import run_daily_snapshot
    from tracking.vault.providers.base import StrategyEquity

    con = _setup_db()
    _insert_strategy(con, "dn", "DELTA_NEUTRAL")

    mock_equity = StrategyEquity(
        equity_usd=10000.0,
        breakdown={"alt": {"equity_usd": 10000.0}},
        timestamp_ms=int(time.time() * 1000),
    )

    with patch(
        "tracking.vault.providers.delta_neutral.DeltaNeutralProvider.get_equity",
        return_value=mock_equity,
    ):
        result = run_daily_snapshot(con)

    assert result["strategies_processed"] == 1
    assert result["vault_equity"] == 10000.0

    row = con.execute(
        "SELECT equity_usd FROM vault_strategy_snapshots WHERE strategy_id = 'dn'"
    ).fetchone()
    assert row is not None
    assert row[0] == 10000.0

    row = con.execute(
        "SELECT total_equity_usd FROM vault_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == 10000.0


def test_refresh_vault_snapshots_after_cashflow_event_on_error():
    from tracking.vault.snapshot import refresh_vault_snapshots_after_cashflow_event

    con = _setup_db()
    with patch(
        "tracking.vault.snapshot.run_daily_snapshot",
        side_effect=RuntimeError("boom"),
    ):
        ok, err = refresh_vault_snapshots_after_cashflow_event(con)
    assert ok is False
    assert err is not None
    assert "boom" in err
