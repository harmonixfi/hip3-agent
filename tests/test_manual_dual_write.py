"""Unit tests for tracking.vault.manual_dual_write (strategy manual dual-write)."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

SCHEMA_PM = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = ROOT / "tracking" / "sql" / "schema_vault.sql"

from tracking.vault.manual_dual_write import (  # noqa: E402
    ManualDualWriteError,
    insert_manual_deposit_withdraw_dual,
    require_active_strategy,
)


def _memory_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())
    return con


def _seed_strategies(con: sqlite3.Connection, now_ms: int) -> None:
    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            config_json, created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "s_active",
            "Active Strat",
            "DELTA_NEUTRAL",
            "ACTIVE",
            None,
            100.0,
            None,
            now_ms,
            now_ms,
        ),
    )
    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            config_json, created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "s_paused",
            "Paused Strat",
            "LENDING",
            "PAUSED",
            None,
            0.0,
            None,
            now_ms,
            now_ms,
        ),
    )


def test_require_active_strategy_unknown_raises():
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    with pytest.raises(ManualDualWriteError, match="Unknown strategy_id"):
        require_active_strategy(con, "missing_id")


def test_require_active_strategy_paused_raises():
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    with pytest.raises(ManualDualWriteError, match="not ACTIVE"):
        require_active_strategy(con, "s_paused")


def test_require_active_strategy_ok():
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    require_active_strategy(con, "s_active")  # no exception


def test_insert_dual_deposit_signed_amounts_and_meta():
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    ts = now_ms - 60_000

    require_active_strategy(con, "s_active")
    v_id, p_id = insert_manual_deposit_withdraw_dual(
        con,
        strategy_id="s_active",
        account_id="0xabc",
        cf_type="DEPOSIT",
        amount=100.0,
        currency="USDC",
        ts=ts,
        description="unit",
        now_ms=now_ms,
    )
    con.commit()

    assert v_id > 0 and p_id > 0

    vr = con.execute(
        "SELECT amount, cf_type, strategy_id, ts FROM vault_cashflows WHERE cashflow_id = ?",
        (v_id,),
    ).fetchone()
    assert float(vr["amount"]) == 100.0
    assert vr["cf_type"] == "DEPOSIT"
    assert vr["strategy_id"] == "s_active"
    assert vr["ts"] == ts

    pr = con.execute(
        """
        SELECT amount, cf_type, venue, meta_json, ts FROM pm_cashflows
        WHERE cashflow_id = ?
        """,
        (p_id,),
    ).fetchone()
    assert float(pr["amount"]) == 100.0
    assert pr["cf_type"] == "DEPOSIT"
    assert pr["venue"] is None
    assert pr["ts"] == ts
    meta = json.loads(pr["meta_json"])
    assert meta["source"] == "manual"
    assert meta["strategy_id"] == "s_active"


def test_insert_dual_withdraw_negative_signed():
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    ts = now_ms

    v_id, p_id = insert_manual_deposit_withdraw_dual(
        con,
        strategy_id="s_active",
        account_id="0xabc",
        cf_type="WITHDRAW",
        amount=50.0,
        currency="USDC",
        ts=ts,
        description=None,
        now_ms=now_ms,
    )
    con.commit()

    v_amt = con.execute(
        "SELECT amount FROM vault_cashflows WHERE cashflow_id = ?",
        (v_id,),
    ).fetchone()[0]
    p_amt = con.execute(
        "SELECT amount FROM pm_cashflows WHERE cashflow_id = ?",
        (p_id,),
    ).fetchone()[0]
    assert float(v_amt) == -50.0
    assert float(p_amt) == -50.0


def test_insert_dual_both_rows_rolled_back_without_commit():
    """Explicit ROLLBACK after dual insert leaves both tables empty."""
    con = _memory_db()
    now_ms = int(time.time() * 1000)
    _seed_strategies(con, now_ms)
    con.commit()

    con.execute("BEGIN")
    require_active_strategy(con, "s_active")
    insert_manual_deposit_withdraw_dual(
        con,
        strategy_id="s_active",
        account_id="0xabc",
        cf_type="DEPOSIT",
        amount=1.0,
        currency="USDC",
        ts=now_ms,
        description=None,
        now_ms=now_ms,
    )
    con.rollback()

    n_vault = con.execute("SELECT COUNT(*) FROM vault_cashflows").fetchone()[0]
    n_pm = con.execute("SELECT COUNT(*) FROM pm_cashflows").fetchone()[0]
    assert n_vault == 0
    assert n_pm == 0
