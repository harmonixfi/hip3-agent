"""Tests for VWAP entry price computation.

Run: .venv/bin/python tests/test_entry_price.py
"""

import sqlite3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tracking.pipeline.entry_price import compute_entry_prices


_SCHEMA = """
    CREATE TABLE pm_positions (
      position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT,
      status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
      closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT
    );
    CREATE TABLE pm_legs (
      leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL,
      inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL,
      entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
      status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER,
      raw_json TEXT, meta_json TEXT, account_id TEXT,
      FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
    );
    CREATE TABLE pm_fills (
      fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
      venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT,
      inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
      px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT,
      ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL,
      position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT,
      UNIQUE (venue, account_id, tid),
      FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
      FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
    );
    CREATE TABLE pm_entry_prices (
      leg_id TEXT NOT NULL PRIMARY KEY, position_id TEXT NOT NULL,
      avg_entry_price REAL NOT NULL, total_filled_qty REAL NOT NULL,
      total_cost REAL NOT NULL, fill_count INTEGER NOT NULL,
      first_fill_ts INTEGER, last_fill_ts INTEGER, computed_at_ms INTEGER NOT NULL,
      method TEXT NOT NULL DEFAULT 'VWAP', meta_json TEXT,
      FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
      FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
    );
"""


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(_SCHEMA)
    return con


def _insert_position(con, position_id, status="OPEN"):
    con.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms) VALUES (?, 'HL', ?, 1000, 1000)",
        (position_id, status),
    )


def _insert_leg(con, leg_id, position_id, side, size=1.0):
    con.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms) VALUES (?, ?, 'HL', 'BTC', ?, ?, 'OPEN', 1000)",
        (leg_id, position_id, side, size),
    )


def _insert_fill(con, leg_id, position_id, side, px, sz, ts=1000):
    con.execute(
        "INSERT INTO pm_fills (venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("HL", "main", f"tid-{leg_id}-{px}-{ts}", "BTC", side, px, sz, ts, position_id, leg_id),
    )


def test_vwap_single_fill():
    con = _make_db()
    _insert_position(con, "pos1")
    _insert_leg(con, "leg1", "pos1", "LONG")
    _insert_fill(con, "leg1", "pos1", "BUY", px=100.0, sz=1.0)

    results = compute_entry_prices(con)
    assert len(results) == 1
    r = results[0]
    assert r["leg_id"] == "leg1"
    assert r["avg_entry_price"] == 100.0
    assert r["total_filled_qty"] == 1.0
    assert r["fill_count"] == 1

    row = con.execute("SELECT avg_entry_price FROM pm_entry_prices WHERE leg_id = 'leg1'").fetchone()
    assert row is not None and row[0] == 100.0

    leg_row = con.execute("SELECT entry_price FROM pm_legs WHERE leg_id = 'leg1'").fetchone()
    assert leg_row[0] == 100.0


def test_vwap_multiple_fills():
    con = _make_db()
    _insert_position(con, "pos1")
    _insert_leg(con, "leg1", "pos1", "LONG")
    # Fill 1: px=100, sz=2  → cost=200
    # Fill 2: px=110, sz=3  → cost=330
    # VWAP = 530 / 5 = 106.0
    _insert_fill(con, "leg1", "pos1", "BUY", px=100.0, sz=2.0, ts=1000)
    _insert_fill(con, "leg1", "pos1", "BUY", px=110.0, sz=3.0, ts=2000)

    results = compute_entry_prices(con)
    assert len(results) == 1
    r = results[0]
    assert abs(r["avg_entry_price"] - 106.0) < 1e-9
    assert r["total_filled_qty"] == 5.0
    assert r["total_cost"] == 530.0
    assert r["fill_count"] == 2


def test_vwap_short_leg_uses_sell_fills():
    con = _make_db()
    _insert_position(con, "pos1")
    _insert_leg(con, "leg1", "pos1", "SHORT")
    # Opening fill for SHORT = SELL
    _insert_fill(con, "leg1", "pos1", "SELL", px=200.0, sz=1.0, ts=1000)
    # Closing fill (BUY) should be ignored
    _insert_fill(con, "leg1", "pos1", "BUY", px=180.0, sz=1.0, ts=2000)

    results = compute_entry_prices(con)
    assert len(results) == 1
    r = results[0]
    assert r["avg_entry_price"] == 200.0
    assert r["fill_count"] == 1
    assert r["total_filled_qty"] == 1.0


def test_no_fills_skipped():
    con = _make_db()
    _insert_position(con, "pos1")
    _insert_leg(con, "leg1", "pos1", "LONG")
    # No fills inserted

    results = compute_entry_prices(con)
    assert results == []

    row = con.execute("SELECT * FROM pm_entry_prices WHERE leg_id = 'leg1'").fetchone()
    assert row is None


def test_includes_closed_positions():
    con = _make_db()
    _insert_position(con, "pos1", status="CLOSED")
    _insert_leg(con, "leg1", "pos1", "LONG")
    _insert_fill(con, "leg1", "pos1", "BUY", px=95.0, sz=2.0)

    results = compute_entry_prices(con)
    assert len(results) == 1
    assert results[0]["avg_entry_price"] == 95.0


def test_recompute_overwrites():
    con = _make_db()
    _insert_position(con, "pos1")
    _insert_leg(con, "leg1", "pos1", "LONG")
    _insert_fill(con, "leg1", "pos1", "BUY", px=100.0, sz=1.0, ts=1000)

    # First compute
    compute_entry_prices(con)

    # Add another fill and recompute
    _insert_fill(con, "leg1", "pos1", "BUY", px=120.0, sz=1.0, ts=2000)
    results = compute_entry_prices(con)

    # Should be overwritten, not duplicated
    count = con.execute("SELECT COUNT(*) FROM pm_entry_prices WHERE leg_id = 'leg1'").fetchone()[0]
    assert count == 1

    assert len(results) == 1
    r = results[0]
    # VWAP of (100*1 + 120*1) / 2 = 110
    assert abs(r["avg_entry_price"] - 110.0) < 1e-9
    assert r["fill_count"] == 2


def main() -> int:
    test_vwap_single_fill()
    print("PASS: test_vwap_single_fill")

    test_vwap_multiple_fills()
    print("PASS: test_vwap_multiple_fills")

    test_vwap_short_leg_uses_sell_fills()
    print("PASS: test_vwap_short_leg_uses_sell_fills")

    test_no_fills_skipped()
    print("PASS: test_no_fills_skipped")

    test_includes_closed_positions()
    print("PASS: test_includes_closed_positions")

    test_recompute_overwrites()
    print("PASS: test_recompute_overwrites")

    print("\nAll entry_price tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
