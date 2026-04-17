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
    recompute_trade,
    finalize_trade,
    reopen_trade,
    delete_trade,
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


def test_create_draft_rejects_closed_position(con):
    con.execute("UPDATE pm_positions SET status='CLOSED' WHERE position_id='pos_X'")
    con.commit()
    with pytest.raises(TradeCreateError, match="CLOSED"):
        create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)


def test_create_draft_rejects_missing_base(con):
    con.execute("UPDATE pm_positions SET base=NULL WHERE position_id='pos_X'")
    con.commit()
    with pytest.raises(TradeCreateError, match="base"):
        create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)


def test_create_draft_rejects_missing_leg(con):
    # Insert a position with only a LONG leg
    now = int(time.time() * 1000)
    con.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES ('pos_Y','hyperliquid','OPEN',?,?,'GOOG','SPOT_PERP')",
        (now, now),
    )
    con.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_Y_SPOT','pos_Y','hyperliquid','GOOG','LONG',0,'OPEN',?, '0xMAIN')",
        (now,),
    )
    con.commit()
    with pytest.raises(TradeCreateError, match="LONG or SHORT"):
        create_draft_trade(con, "pos_Y", "OPEN", 1000, 2000)


def test_create_draft_rejects_one_sided_fills(con):
    # Delete all short fills so long has fills but short is empty
    con.execute("DELETE FROM pm_fills WHERE leg_id='pos_X_PERP'")
    con.commit()
    with pytest.raises(TradeCreateError, match="no fills"):
        create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)


# ---------------------------------------------------------------------------
# A5: recompute, finalize, reopen, delete
# ---------------------------------------------------------------------------


def test_recompute_draft_picks_up_new_fill(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]

    # Insert a late fill at t=1800 (within window)
    con.execute(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,1.0,0.02,1800,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    result = recompute_trade(con, tid)
    # new long size = 5 + 1 = 6
    assert result["long_size"] == pytest.approx(6.0)


def test_finalize_sets_state_and_timestamp(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalized = finalize_trade(con, t["trade_id"])
    assert finalized["state"] == "FINALIZED"
    assert finalized["finalized_at_ms"] is not None


def test_finalize_updates_leg_qty_and_position_status(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t["trade_id"])
    long_size = con.execute("SELECT size FROM pm_legs WHERE leg_id = 'pos_X_SPOT'").fetchone()[0]
    short_size = con.execute("SELECT size FROM pm_legs WHERE leg_id = 'pos_X_PERP'").fetchone()[0]
    assert long_size == pytest.approx(5.0)
    assert short_size == pytest.approx(5.0)
    status = con.execute("SELECT status FROM pm_positions WHERE position_id = 'pos_X'").fetchone()[0]
    assert status == "OPEN"


def test_finalize_rejects_overlap_with_existing_finalized(con):
    t1 = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t1["trade_id"])

    # Need more fills for t2 (fills in 1000-2000 are consumed)
    con.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",     "BUY",  100.0, 1.0, 0.01, 1500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL", "SELL", 101.0, 1.0, 0.01, 1500, "pos_X_PERP", "pos_X"),
        ],
    )
    con.commit()
    t2 = create_draft_trade(con, "pos_X", "OPEN", 1000, 1800)  # overlaps with 1000-2000
    with pytest.raises(TradeCreateError, match="overlap"):
        finalize_trade(con, t2["trade_id"])


def test_reopen_finalized_goes_back_to_draft(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t["trade_id"])
    reopened = reopen_trade(con, t["trade_id"])
    assert reopened["state"] == "DRAFT"
    assert reopened["finalized_at_ms"] is None


def test_delete_draft_releases_fills(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]

    delete_trade(con, tid)

    assert con.execute("SELECT COUNT(*) FROM pm_trades WHERE trade_id = ?", (tid,)).fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM pm_trade_fills WHERE trade_id = ?", (tid,)).fetchone()[0] == 0
    # And fills remain in pm_fills
    assert con.execute("SELECT COUNT(*) FROM pm_fills WHERE leg_id = 'pos_X_SPOT'").fetchone()[0] >= 2


def test_close_realized_pnl_after_open_finalized(con):
    t_open = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t_open["trade_id"])

    # Seed CLOSE fills (spot SELL + perp BUY) at 3000..4000
    con.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",     "SELL", 110.0, 5.0, 0.10, 3500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL", "BUY",  108.0, 5.0, 0.10, 3500, "pos_X_PERP", "pos_X"),
        ],
    )
    con.commit()

    t_close = create_draft_trade(con, "pos_X", "CLOSE", 3000, 4000)
    # open spread ≈ -97.85 bps; close spread = (110/108 - 1) * 10000 ≈ 185.19 bps
    # realized = open - close = -97.85 - 185.19 ≈ -283.04 bps
    assert t_close["realized_pnl_bps"] == pytest.approx(-283.0, abs=0.5)
