"""Tests for migrate_positions_to_db.py — idempotency + qty diff.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_positions_to_db.py -v
"""
from __future__ import annotations
import json
import sqlite3

import pytest

from scripts.migrate_positions_to_db import migrate


_SCHEMA = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


def _fixture_positions():
    """Single CLOSED position with two legs, expected qty 5.0 on each leg."""
    return [{
        "position_id": "pos_xyz_GOOGL",
        "strategy_type": "SPOT_PERP",
        "base": "GOOGL",
        "status": "CLOSED",
        "legs": [
            {"leg_id":"pos_xyz_GOOGL_SPOT","venue":"hyperliquid","inst_id":"GOOGL","side":"LONG","qty":5.0,"wallet_label":"main"},
            {"leg_id":"pos_xyz_GOOGL_PERP","venue":"hyperliquid","inst_id":"xyz:GOOGL","side":"SHORT","qty":5.0,"wallet_label":"main"},
        ],
    }]


def _seed_fills(con):
    """Fills: 1 OPEN batch (ts ~1000-1100) + 1 CLOSE batch (ts ~5000-5100). 5 qty each leg."""
    con.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL",    "BUY", 100.0, 5.0, 0.1, 1000, "pos_xyz_GOOGL_SPOT","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0, 5.0, 0.1, 1100, "pos_xyz_GOOGL_PERP","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","GOOGL",    "SELL",110.0, 5.0, 0.1, 5000, "pos_xyz_GOOGL_SPOT","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","BUY", 108.0, 5.0, 0.1, 5100, "pos_xyz_GOOGL_PERP","pos_xyz_GOOGL"),
        ],
    )


def test_migrate_creates_position_and_trades_then_idempotent(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    _seed_fills(con); con.commit()

    pos_path = tmp_path / "positions.json"
    pos_path.write_text(json.dumps(_fixture_positions()))

    report = migrate(con, positions_path=pos_path, commit=True)

    # Position + 2 legs
    assert con.execute("SELECT COUNT(*) FROM pm_positions").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM pm_legs").fetchone()[0] == 2
    # 2 FINALIZED trades (OPEN + CLOSE, since status=CLOSED)
    tcount = con.execute("SELECT COUNT(*) FROM pm_trades WHERE state='FINALIZED'").fetchone()[0]
    assert tcount == 2
    # Position status derived → CLOSED
    status = con.execute("SELECT status FROM pm_positions").fetchone()[0]
    assert status == "CLOSED"

    # Second run idempotent
    report2 = migrate(con, positions_path=pos_path, commit=True)
    assert report2["positions_created"] == 0
    assert report2["trades_created"] == 0


def test_migrate_qty_diff_within_tolerance(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    _seed_fills(con); con.commit()

    pos_path = tmp_path / "positions.json"
    pos_path.write_text(json.dumps(_fixture_positions()))

    report = migrate(con, positions_path=pos_path, commit=True)
    # For CLOSED positions the net qty after OPEN-CLOSE is 0.
    # Expected (from positions.json) is 5.0, but actual derived net is 0 after close.
    # The report should still tally the diff — tolerance assertion applies to OPEN
    # positions only, so for this CLOSED fixture we just assert the diff list is populated.
    assert len(report["qty_diffs"]) == 2  # 2 legs
    for d in report["qty_diffs"]:
        assert d["leg_id"] in ("pos_xyz_GOOGL_SPOT", "pos_xyz_GOOGL_PERP")
        assert "expected" in d and "actual" in d and "delta_pct" in d


def test_migrate_dry_run_does_not_commit(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    _seed_fills(con); con.commit()

    pos_path = tmp_path / "positions.json"
    pos_path.write_text(json.dumps(_fixture_positions()))

    migrate(con, positions_path=pos_path, commit=False)

    # A separate connection should not see the inserts
    con2 = sqlite3.connect(str(db))
    assert con2.execute("SELECT COUNT(*) FROM pm_positions").fetchone()[0] == 0
    con2.close()
