"""Reconcile hook: DRAFT auto-picks late fills; FINALIZED raises warning.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_reconcile.py -v
"""
from __future__ import annotations
import sqlite3
import time

import pytest

from tracking.pipeline.trades import create_draft_trade, finalize_trade
from tracking.pipeline.trade_reconcile import run_reconcile


# Same schema fixture pattern as test_trades_state.py (kept independent on purpose)
_SCHEMA_SQL = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(_SCHEMA_SQL)
    now = int(time.time() * 1000)
    c.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES ('pos_X','hyperliquid','OPEN',?,?,'GOOGL','SPOT_PERP')",
        (now, now),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_SPOT','pos_X','hyperliquid','GOOGL','LONG',0,'OPEN',?, '0xMAIN')",
        (now,),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_PERP','pos_X','hyperliquid','xyz:GOOGL','SHORT',0,'OPEN',?, '0xMAIN')",
        (now,),
    )
    c.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL","BUY",100.0,2.0,0.05,1100,"pos_X_SPOT","pos_X"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0,2.0,0.04,1200,"pos_X_PERP","pos_X"),
        ],
    )
    c.commit()
    yield c
    c.close()


def test_reconcile_draft_picks_up_late_fill(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    assert t["long_size"] == pytest.approx(2.0)

    # Late fill arrives (within window, inserted after DRAFT creation)
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)

    long_size = con.execute("SELECT long_size FROM pm_trades WHERE trade_id=?", (tid,)).fetchone()[0]
    assert long_size == pytest.approx(5.0)


def test_reconcile_finalized_raises_warning_not_auto_merge(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    finalize_trade(con, tid)

    # Late fill arrives in the FINALIZED window
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)

    # Aggregates unchanged
    long_size = con.execute("SELECT long_size FROM pm_trades WHERE trade_id=?", (tid,)).fetchone()[0]
    assert long_size == pytest.approx(2.0)
    # Warning row written
    warn = con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone()
    assert warn is not None
    assert warn[0] == 1


def test_reconcile_finalized_old_trade_still_warned(con):
    """Age-of-finalization must not affect warning behavior."""
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    finalize_trade(con, tid)

    # Age the trade by patching finalized_at_ms far in the past
    con.execute("UPDATE pm_trades SET finalized_at_ms = 0 WHERE trade_id=?", (tid,))
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)
    warn = con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone()
    assert warn is not None


def test_reconcile_returns_summary(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    summary = run_reconcile(con)
    assert "drafts_recomputed" in summary
    assert "warnings_raised" in summary
    assert "warnings_cleared" in summary
    assert summary["drafts_recomputed"] == 1


def test_reconcile_clears_warning_when_fills_no_longer_orphan(con):
    """Once user rebinds late fills (e.g. by reopening + editing window), warning clears."""
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    finalize_trade(con, tid)

    # Orphan fill in FINALIZED window
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)
    assert con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone() is not None

    # Manually bind the orphan fill to the trade (simulating user reopen+edit+finalize)
    fill_id = con.execute(
        "SELECT fill_id FROM pm_fills WHERE ts=1500 AND leg_id='pos_X_SPOT'"
    ).fetchone()[0]
    con.execute(
        "INSERT INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?,?, 'LONG')",
        (tid, fill_id),
    )
    con.commit()

    run_reconcile(con)
    assert con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone() is None
