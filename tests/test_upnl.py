#!/usr/bin/env python3
"""Tests for Unrealized PnL computation (ADR-001 bid/ask pricing)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.upnl import compute_unrealized_pnl, compute_leg_upnl


def _create_test_db() -> sqlite3.Connection:
    """Create in-memory SQLite DB with all required tables."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript("""
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
            unrealized_pnl REAL,
            current_price REAL,
            FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE pm_entry_prices (
            leg_id TEXT PRIMARY KEY,
            avg_entry_price REAL NOT NULL,
            FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
        );
        CREATE TABLE instruments_v3 (
            venue TEXT NOT NULL,
            inst_id TEXT NOT NULL,
            symbol_key TEXT,
            symbol_base TEXT,
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
    """)
    return con


def _seed_base(con: sqlite3.Connection):
    """Insert base position and legs for pos_xyz_GOLD."""
    con.execute(
        "INSERT INTO pm_positions VALUES (?, ?, ?, ?, ?, ?)",
        ("pos_xyz_GOLD", "xyz", "funding_arb", "OPEN", 1700000000000, 1700000000000),
    )
    # LONG spot leg
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("gold_spot", "pos_xyz_GOLD", "xyz_spot", "XAUT0/USDC", "LONG", 0.6608, None, None),
    )
    # SHORT perp leg
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("gold_perp", "pos_xyz_GOLD", "xyz", "xyz:GOLD", "SHORT", 0.6608, None, None),
    )
    # Entry prices
    con.execute("INSERT INTO pm_entry_prices VALUES (?, ?)", ("gold_spot", 3050.0))
    con.execute("INSERT INTO pm_entry_prices VALUES (?, ?)", ("gold_perp", 3055.0))
    # Instruments
    con.execute(
        "INSERT INTO instruments_v3 VALUES (?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", "XAUT0/USDC", "XAUT0"),
    )
    con.execute(
        "INSERT INTO instruments_v3 VALUES (?, ?, ?, ?)",
        ("xyz", "xyz:GOLD", "xyz:GOLD", "GOLD"),
    )
    # Prices: spot bid=3060, ask=3062; perp bid=3058, ask=3061
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", 1700000001000, 3060.0, 3062.0, 3061.0, 3061.0),
    )
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz", "xyz:GOLD", 1700000001000, 3058.0, 3061.0, 3059.5, 3059.5),
    )
    con.commit()


def test_long_leg_uses_bid():
    """LONG leg uPnL should use bid price."""
    con = _create_test_db()
    _seed_base(con)

    results = compute_unrealized_pnl(con)
    leg_results = {r["leg_id"]: r for r in results if "leg_id" in r and not r.get("skipped")}

    spot = leg_results["gold_spot"]
    assert spot["price_type"] == "bid", f"Expected 'bid', got '{spot['price_type']}'"
    assert spot["price_used"] == 3060.0, f"Expected 3060.0, got {spot['price_used']}"

    expected_upnl = (3060.0 - 3050.0) * 0.6608
    assert abs(spot["unrealized_pnl"] - expected_upnl) < 1e-9, (
        f"Expected {expected_upnl}, got {spot['unrealized_pnl']}"
    )
    print("PASS test_long_leg_uses_bid")


def test_short_leg_uses_ask():
    """SHORT leg uPnL should use ask price."""
    con = _create_test_db()
    _seed_base(con)

    results = compute_unrealized_pnl(con)
    leg_results = {r["leg_id"]: r for r in results if "leg_id" in r and not r.get("skipped")}

    perp = leg_results["gold_perp"]
    assert perp["price_type"] == "ask", f"Expected 'ask', got '{perp['price_type']}'"
    assert perp["price_used"] == 3061.0, f"Expected 3061.0, got {perp['price_used']}"

    expected_upnl = -(3061.0 - 3055.0) * 0.6608
    assert abs(perp["unrealized_pnl"] - expected_upnl) < 1e-9, (
        f"Expected {expected_upnl}, got {perp['unrealized_pnl']}"
    )
    print("PASS test_short_leg_uses_ask")


def test_position_level_upnl():
    """Position uPnL = sum of all leg uPnLs."""
    con = _create_test_db()
    _seed_base(con)

    results = compute_unrealized_pnl(con)
    pos_results = {r["position_id"]: r for r in results if "position_upnl" in r}

    assert "pos_xyz_GOLD" in pos_results, "Missing position-level uPnL entry"

    spot_upnl = (3060.0 - 3050.0) * 0.6608        # LONG uses bid
    perp_upnl = -(3061.0 - 3055.0) * 0.6608       # SHORT uses ask
    expected_total = spot_upnl + perp_upnl

    actual = pos_results["pos_xyz_GOLD"]["position_upnl"]
    assert abs(actual - expected_total) < 1e-9, (
        f"Expected position uPnL {expected_total}, got {actual}"
    )
    print("PASS test_position_level_upnl")


def test_fallback_to_mid_when_bid_ask_missing():
    """When bid/ask are NULL, fall back to mid price."""
    con = _create_test_db()
    _seed_base(con)

    # Replace spot price with NULL bid/ask, only mid available
    con.execute("DELETE FROM prices_v3 WHERE venue = 'xyz_spot'")
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", 1700000002000, None, None, None, 3061.0),
    )
    con.commit()

    results = compute_unrealized_pnl(con)
    leg_results = {r["leg_id"]: r for r in results if "leg_id" in r and not r.get("skipped")}

    spot = leg_results["gold_spot"]
    assert spot["price_type"] == "mid", f"Expected 'mid' fallback, got '{spot['price_type']}'"
    assert spot["price_used"] == 3061.0, f"Expected 3061.0, got {spot['price_used']}"

    expected_upnl = (3061.0 - 3050.0) * 0.6608
    assert abs(spot["unrealized_pnl"] - expected_upnl) < 1e-9, (
        f"Expected {expected_upnl}, got {spot['unrealized_pnl']}"
    )
    print("PASS test_fallback_to_mid_when_bid_ask_missing")


def test_no_price_skipped():
    """Legs with no price row are skipped with skip_reason='no_price'."""
    con = _create_test_db()
    _seed_base(con)

    # Remove spot price entirely
    con.execute("DELETE FROM prices_v3 WHERE venue = 'xyz_spot'")
    con.commit()

    results = compute_unrealized_pnl(con)
    skipped = [r for r in results if r.get("skipped") and r.get("leg_id") == "gold_spot"]

    assert len(skipped) == 1, f"Expected 1 skipped entry for gold_spot, got {len(skipped)}"
    assert skipped[0]["skip_reason"] == "no_price", (
        f"Expected skip_reason='no_price', got '{skipped[0]['skip_reason']}'"
    )

    # Perp leg should still compute normally
    leg_results = {r["leg_id"]: r for r in results if "leg_id" in r and not r.get("skipped")}
    assert "gold_perp" in leg_results, "gold_perp should still compute when only spot is missing"
    print("PASS test_no_price_skipped")


def test_no_entry_price_skipped():
    """Legs with no entry price are excluded entirely (JOIN filters them out)."""
    con = _create_test_db()
    # Setup position and legs but NO entry prices
    con.execute(
        "INSERT INTO pm_positions VALUES (?, ?, ?, ?, ?, ?)",
        ("pos_no_entry", "xyz", "funding_arb", "OPEN", 1700000000000, 1700000000000),
    )
    con.execute(
        "INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("leg_no_entry", "pos_no_entry", "xyz_spot", "XAUT0/USDC", "LONG", 1.0, None, None),
    )
    con.execute(
        "INSERT INTO instruments_v3 VALUES (?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", "XAUT0/USDC", "XAUT0"),
    )
    con.execute(
        "INSERT INTO prices_v3 (venue, inst_id, ts, bid, ask, last, mid) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("xyz_spot", "XAUT0/USDC", 1700000001000, 3060.0, 3062.0, 3061.0, 3061.0),
    )
    con.commit()

    results = compute_unrealized_pnl(con)

    # No entry price means the INNER JOIN filters it out → empty results
    assert results == [], f"Expected empty results when no entry prices, got {results}"
    print("PASS test_no_entry_price_skipped")


def main():
    tests = [
        test_long_leg_uses_bid,
        test_short_leg_uses_ask,
        test_position_level_upnl,
        test_fallback_to_mid_when_bid_ask_missing,
        test_no_price_skipped,
        test_no_entry_price_skipped,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL {t.__name__}: {e}")
            failed += 1

    print(f"\n{passed}/{len(tests)} tests passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
