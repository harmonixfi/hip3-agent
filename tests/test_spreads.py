#!/usr/bin/env python3
"""Tests for Entry/Exit Spread Calculator (ADR-008, Phase 1b).

Run: .venv/bin/python tests/test_spreads.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.spreads import compute_spreads, entry_spread, exit_spread, spread_pnl_bps


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
    CREATE TABLE pm_positions (
        position_id TEXT PRIMARY KEY,
        venue TEXT NOT NULL,
        strategy TEXT,
        status TEXT NOT NULL,
        created_at_ms INTEGER NOT NULL,
        updated_at_ms INTEGER NOT NULL
    );
    CREATE TABLE pm_legs (
        leg_id TEXT PRIMARY KEY,
        position_id TEXT NOT NULL,
        venue TEXT NOT NULL,
        inst_id TEXT NOT NULL,
        side TEXT NOT NULL,
        size REAL NOT NULL,
        FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
    );
    CREATE TABLE pm_entry_prices (
        leg_id TEXT PRIMARY KEY,
        position_id TEXT NOT NULL,
        avg_entry_price REAL NOT NULL,
        total_filled_qty REAL NOT NULL DEFAULT 1,
        total_cost REAL NOT NULL DEFAULT 1,
        fill_count INTEGER NOT NULL DEFAULT 1,
        computed_at_ms INTEGER NOT NULL DEFAULT 0,
        method TEXT NOT NULL DEFAULT 'VWAP',
        FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
    );
    CREATE TABLE instruments_v3 (
        venue TEXT NOT NULL,
        inst_id TEXT NOT NULL,
        base TEXT NOT NULL DEFAULT '',
        quote TEXT NOT NULL DEFAULT '',
        contract_type TEXT NOT NULL DEFAULT 'SPOT',
        symbol_key TEXT NOT NULL DEFAULT '',
        symbol_base TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (venue, inst_id)
    );
    CREATE TABLE prices_v3 (
        venue TEXT NOT NULL,
        inst_id TEXT NOT NULL,
        ts INTEGER NOT NULL,
        bid REAL,
        ask REAL,
        last REAL,
        mid REAL,
        mark REAL,
        index_price REAL,
        source TEXT,
        quality_flags TEXT,
        PRIMARY KEY (venue, inst_id, ts),
        FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
    );
    CREATE TABLE pm_spreads (
        spread_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        position_id TEXT NOT NULL,
        long_leg_id TEXT NOT NULL,
        short_leg_id TEXT NOT NULL,
        entry_spread REAL,
        long_avg_entry REAL,
        short_avg_entry REAL,
        exit_spread REAL,
        long_exit_price REAL,
        short_exit_price REAL,
        spread_pnl_bps REAL,
        computed_at_ms INTEGER NOT NULL,
        meta_json TEXT,
        UNIQUE (position_id, long_leg_id, short_leg_id)
    );
"""


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(_SCHEMA)
    return con


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------

def _seed_gold(con: sqlite3.Connection):
    """pos_xyz_GOLD: 1 LONG spot + 1 SHORT perp."""
    con.execute(
        "INSERT INTO pm_positions VALUES (?, ?, ?, ?, ?, ?)",
        ("pos_xyz_GOLD", "xyz", "funding_arb", "OPEN", 1000, 1000),
    )
    # Legs
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?)",
        ("gold_spot", "pos_xyz_GOLD", "xyz_spot", "XAUT0/USDC", "LONG", 0.6608),
    )
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?)",
        ("gold_perp", "pos_xyz_GOLD", "xyz", "xyz:GOLD", "SHORT", 0.6608),
    )
    # Entry prices: spot=3050, perp=3055
    con.execute(
        "INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price) VALUES (?, ?, ?)",
        ("gold_spot", "pos_xyz_GOLD", 3050.0),
    )
    con.execute(
        "INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price) VALUES (?, ?, ?)",
        ("gold_perp", "pos_xyz_GOLD", 3055.0),
    )
    # Instruments
    con.execute(
        "INSERT INTO instruments_v3 (venue, inst_id) VALUES (?, ?)",
        ("xyz_spot", "XAUT0/USDC"),
    )
    con.execute(
        "INSERT INTO instruments_v3 (venue, inst_id) VALUES (?, ?)",
        ("xyz", "xyz:GOLD"),
    )
    # Prices: spot bid=3060, ask=3062; perp bid=3058, ask=3061
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", 1000, 3060.0, 3062.0, 3061.0, 3061.0),
    )
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz", "xyz:GOLD", 1000, 3058.0, 3061.0, 3059.5, 3059.5),
    )
    con.commit()


def _seed_hype(con: sqlite3.Connection):
    """pos_hyna_HYPE: 1 LONG spot + 2 SHORT perps (split-leg)."""
    con.execute(
        "INSERT INTO pm_positions VALUES (?, ?, ?, ?, ?, ?)",
        ("pos_hyna_HYPE", "hyna", "funding_arb", "OPEN", 1000, 1000),
    )
    # Legs
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?)",
        ("hype_spot", "pos_hyna_HYPE", "xyz_spot", "HYPE/USDC", "LONG", 126.98),
    )
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?)",
        ("hype_perp_hyna", "pos_hyna_HYPE", "hyna", "hyna:HYPE", "SHORT", 63.0),
    )
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?)",
        ("hype_perp_native", "pos_hyna_HYPE", "hl", "HYPE", "SHORT", 63.98),
    )
    # Entry prices: spot=20.00, hyna=20.05, native=20.03
    con.execute(
        "INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price) VALUES (?, ?, ?)",
        ("hype_spot", "pos_hyna_HYPE", 20.00),
    )
    con.execute(
        "INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price) VALUES (?, ?, ?)",
        ("hype_perp_hyna", "pos_hyna_HYPE", 20.05),
    )
    con.execute(
        "INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price) VALUES (?, ?, ?)",
        ("hype_perp_native", "pos_hyna_HYPE", 20.03),
    )
    # Instruments
    con.execute(
        "INSERT INTO instruments_v3 (venue, inst_id) VALUES (?, ?)",
        ("xyz_spot", "HYPE/USDC"),
    )
    con.execute(
        "INSERT INTO instruments_v3 (venue, inst_id) VALUES (?, ?)",
        ("hyna", "hyna:HYPE"),
    )
    con.execute(
        "INSERT INTO instruments_v3 (venue, inst_id) VALUES (?, ?)",
        ("hl", "HYPE"),
    )
    # Prices: spot bid=19.90; hyna ask=19.93; native ask=19.92
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "HYPE/USDC", 1000, 19.90, 19.95, 19.925, 19.925),
    )
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("hyna", "hyna:HYPE", 1000, 19.90, 19.93, 19.915, 19.915),
    )
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("hl", "HYPE", 1000, 19.89, 19.92, 19.905, 19.905),
    )
    con.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_simple_spread():
    """1 spot LONG + 1 perp SHORT: entry/exit spreads computed correctly."""
    con = _make_db()
    _seed_gold(con)

    results = compute_spreads(con)

    assert len(results) == 1, f"Expected 1 sub-pair, got {len(results)}"
    r = results[0]

    assert r["position_id"] == "pos_xyz_GOLD"
    assert r["long_leg_id"] == "gold_spot"
    assert r["short_leg_id"] == "gold_perp"

    # entry_spread = 3050 / 3055 - 1
    expected_entry = entry_spread(3050.0, 3055.0)
    assert abs(r["entry_spread"] - expected_entry) < 1e-9, (
        f"entry_spread mismatch: expected {expected_entry}, got {r['entry_spread']}"
    )

    # exit_spread = long_bid(3060) / short_ask(3061) - 1
    expected_exit = exit_spread(3060.0, 3061.0)
    assert abs(r["exit_spread"] - expected_exit) < 1e-9, (
        f"exit_spread mismatch: expected {expected_exit}, got {r['exit_spread']}"
    )

    # spread_pnl_bps
    expected_pnl_bps = spread_pnl_bps(expected_entry, expected_exit)
    assert abs(r["spread_pnl_bps"] - expected_pnl_bps) < 1e-6, (
        f"spread_pnl_bps mismatch: expected {expected_pnl_bps}, got {r['spread_pnl_bps']}"
    )

    # Verify DB write
    row = con.execute(
        "SELECT entry_spread, exit_spread, spread_pnl_bps FROM pm_spreads"
        " WHERE position_id = 'pos_xyz_GOLD'"
    ).fetchone()
    assert row is not None, "pm_spreads row not written"
    assert abs(row[0] - expected_entry) < 1e-9
    assert abs(row[1] - expected_exit) < 1e-9
    assert abs(row[2] - expected_pnl_bps) < 1e-6

    print("PASS test_simple_spread")


def test_split_leg_generates_two_sub_pairs():
    """1 LONG spot + 2 SHORT perps = 2 independent sub-pairs."""
    con = _make_db()
    _seed_hype(con)

    results = compute_spreads(con)

    assert len(results) == 2, f"Expected 2 sub-pairs, got {len(results)}"

    short_ids = {r["short_leg_id"] for r in results}
    assert short_ids == {"hype_perp_hyna", "hype_perp_native"}, (
        f"Unexpected short leg IDs: {short_ids}"
    )

    for r in results:
        assert r["long_leg_id"] == "hype_spot"
        assert r["position_id"] == "pos_hyna_HYPE"
        assert r["entry_spread"] is not None
        assert r["exit_spread"] is not None

    # Check hyna sub-pair
    hyna = next(r for r in results if r["short_leg_id"] == "hype_perp_hyna")
    expected_entry_hyna = entry_spread(20.00, 20.05)
    expected_exit_hyna = exit_spread(19.90, 19.93)
    assert abs(hyna["entry_spread"] - expected_entry_hyna) < 1e-9
    assert abs(hyna["exit_spread"] - expected_exit_hyna) < 1e-9

    # Check native sub-pair
    native = next(r for r in results if r["short_leg_id"] == "hype_perp_native")
    expected_entry_native = entry_spread(20.00, 20.03)
    expected_exit_native = exit_spread(19.90, 19.92)
    assert abs(native["entry_spread"] - expected_entry_native) < 1e-9
    assert abs(native["exit_spread"] - expected_exit_native) < 1e-9

    # Both rows should be in DB
    count = con.execute("SELECT COUNT(*) FROM pm_spreads WHERE position_id = 'pos_hyna_HYPE'").fetchone()[0]
    assert count == 2, f"Expected 2 rows in pm_spreads, got {count}"

    print("PASS test_split_leg_generates_two_sub_pairs")


def test_missing_entry_price_skips():
    """Sub-pair with missing entry price (leg not in pm_entry_prices) is skipped."""
    con = _make_db()
    _seed_gold(con)

    # Remove entry price for the short leg
    con.execute("DELETE FROM pm_entry_prices WHERE leg_id = 'gold_perp'")
    con.commit()

    results = compute_spreads(con)

    # No LONG×SHORT pair can be formed (short has no entry price)
    assert len(results) == 0, f"Expected 0 results when short entry missing, got {len(results)}"

    count = con.execute("SELECT COUNT(*) FROM pm_spreads").fetchone()[0]
    assert count == 0, f"Expected 0 pm_spreads rows, got {count}"

    print("PASS test_missing_entry_price_skips")


def test_missing_exit_price_partial():
    """Missing exit price: entry_spread computed, exit_spread and spread_pnl_bps are NULL."""
    con = _make_db()
    _seed_gold(con)

    # Remove prices for the perp (short) leg
    con.execute("DELETE FROM prices_v3 WHERE venue = 'xyz' AND inst_id = 'xyz:GOLD'")
    con.commit()

    results = compute_spreads(con)

    assert len(results) == 1, f"Expected 1 result, got {len(results)}"
    r = results[0]

    # Entry spread should still be computed
    expected_entry = entry_spread(3050.0, 3055.0)
    assert r["entry_spread"] is not None
    assert abs(r["entry_spread"] - expected_entry) < 1e-9

    # Exit spread and pnl_bps should be None
    assert r["exit_spread"] is None, f"Expected exit_spread=None, got {r['exit_spread']}"
    assert r["spread_pnl_bps"] is None, f"Expected spread_pnl_bps=None, got {r['spread_pnl_bps']}"

    # Verify DB
    row = con.execute(
        "SELECT entry_spread, exit_spread, spread_pnl_bps FROM pm_spreads"
        " WHERE position_id = 'pos_xyz_GOLD'"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - expected_entry) < 1e-9
    assert row[1] is None
    assert row[2] is None

    print("PASS test_missing_exit_price_partial")


def test_recompute_overwrites():
    """Running compute_spreads twice does not duplicate rows; values are updated."""
    con = _make_db()
    _seed_gold(con)

    # First run
    results1 = compute_spreads(con)
    assert len(results1) == 1

    count_after_first = con.execute("SELECT COUNT(*) FROM pm_spreads").fetchone()[0]
    assert count_after_first == 1, f"Expected 1 row after first run, got {count_after_first}"

    # Update price to simulate a market move; bid moves from 3060 to 3070
    con.execute("DELETE FROM prices_v3 WHERE venue = 'xyz_spot' AND inst_id = 'XAUT0/USDC'")
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", 2000, 3070.0, 3072.0, 3071.0, 3071.0),
    )
    con.commit()

    # Second run
    results2 = compute_spreads(con)
    assert len(results2) == 1

    count_after_second = con.execute("SELECT COUNT(*) FROM pm_spreads").fetchone()[0]
    assert count_after_second == 1, f"Expected 1 row after second run (no duplicates), got {count_after_second}"

    r2 = results2[0]

    # Exit spread should reflect new price (bid=3070, ask=3061)
    expected_exit_new = exit_spread(3070.0, 3061.0)
    assert abs(r2["exit_spread"] - expected_exit_new) < 1e-9, (
        f"Expected updated exit_spread {expected_exit_new}, got {r2['exit_spread']}"
    )

    # Entry spread unchanged
    expected_entry = entry_spread(3050.0, 3055.0)
    assert abs(r2["entry_spread"] - expected_entry) < 1e-9

    print("PASS test_recompute_overwrites")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_simple_spread,
        test_split_leg_generates_two_sub_pairs,
        test_missing_entry_price_skips,
        test_missing_exit_price_partial,
        test_recompute_overwrites,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            import traceback
            print(f"FAIL {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    if failed:
        return 1
    print("All spread tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
