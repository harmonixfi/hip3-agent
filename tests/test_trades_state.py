"""Integration tests for DRAFT creation, FINALIZE/REOPEN/DELETE, and validation.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
"""
from __future__ import annotations
import sqlite3
import time

import pytest

from tracking.pipeline.trades import (
    create_draft_trade,
    TradeCreateError,
)


_SCHEMA_SQL = """
CREATE TABLE pm_positions (
  position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT,
  status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
  closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT
);
CREATE TABLE pm_legs (
  leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL,
  inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL,
  entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
  status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER,
  raw_json TEXT, meta_json TEXT, account_id TEXT
);
CREATE TABLE pm_fills (
  fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT,
  inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT,
  ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL,
  position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT
);
CREATE TABLE pm_trades (
  trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL,
  state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT,
  long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL,
  long_fees REAL, long_fill_count INTEGER,
  short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL,
  short_fees REAL, short_fill_count INTEGER,
  spread_bps REAL, realized_pnl_bps REAL,
  created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL,
  UNIQUE (position_id, trade_type, start_ts, end_ts)
);
CREATE TABLE pm_trade_fills (
  trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL,
  PRIMARY KEY (trade_id, fill_id)
);
CREATE TABLE pm_trade_reconcile_warnings (
  trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL,
  first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL
);
"""


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(_SCHEMA_SQL)
    now = int(time.time() * 1000)
    c.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES ('pos_X', 'hyperliquid', 'OPEN', ?, ?, 'GOOGL', 'SPOT_PERP')",
        (now, now),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_SPOT', 'pos_X', 'hyperliquid', 'GOOGL', 'LONG', 0, 'OPEN', ?, '0xMAIN')",
        (now,),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_PERP', 'pos_X', 'hyperliquid', 'xyz:GOOGL', 'SHORT', 0, 'OPEN', ?, '0xMAIN')",
        (now,),
    )
    c.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",  100.0, 2.0, 0.05, 1100, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",  102.0, 3.0, 0.08, 1500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL","SELL", 101.0, 2.0, 0.04, 1200, "pos_X_PERP", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL","SELL", 103.0, 3.0, 0.06, 1700, "pos_X_PERP", "pos_X"),
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",   99.0, 1.0, 0.03, 5000, "pos_X_SPOT", "pos_X"),
        ],
    )
    c.commit()
    yield c
    c.close()


def test_create_draft_open_aggregates_in_window_fills(con):
    result = create_draft_trade(
        con,
        position_id="pos_X",
        trade_type="OPEN",
        start_ts=1000,
        end_ts=2000,
        note="initial",
    )
    # Spot long: 2+3 = 5 size; notional = 100*2 + 102*3 = 506; avg = 101.2
    assert result["long_size"] == pytest.approx(5.0)
    assert result["long_avg_px"] == pytest.approx(101.2)
    # Perp short: 2+3 = 5 size; notional = 101*2 + 103*3 = 511; avg = 102.2
    assert result["short_size"] == pytest.approx(5.0)
    assert result["short_avg_px"] == pytest.approx(102.2)
    # spread = (101.2 / 102.2 - 1) * 10000 ≈ -97.85 bps
    assert result["spread_bps"] == pytest.approx(-97.84735, abs=0.01)
    assert result["state"] == "DRAFT"
    assert result["realized_pnl_bps"] is None

    links = con.execute(
        "SELECT fill_id, leg_side FROM pm_trade_fills WHERE trade_id = ?",
        (result["trade_id"],),
    ).fetchall()
    assert len(links) == 4


def test_create_draft_excludes_out_of_window_fills(con):
    result = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    assert result["long_fill_count"] == 2


def test_create_draft_rejects_if_fill_already_linked(con):
    create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    with pytest.raises(TradeCreateError, match="already linked|no fills"):
        create_draft_trade(con, "pos_X", "OPEN", 1000, 2000, note="dup")


def test_create_draft_rejects_unknown_position(con):
    with pytest.raises(TradeCreateError, match="position"):
        create_draft_trade(con, "pos_MISSING", "OPEN", 1000, 2000)


def test_create_draft_rejects_invalid_window(con):
    with pytest.raises(TradeCreateError, match="window"):
        create_draft_trade(con, "pos_X", "OPEN", 2000, 1000)  # start > end


def test_create_draft_rejects_invalid_trade_type(con):
    with pytest.raises(TradeCreateError, match="trade_type"):
        create_draft_trade(con, "pos_X", "ADD", 1000, 2000)
