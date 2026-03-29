#!/usr/bin/env python3
"""Tests for Hyperliquid fill ingester."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db(db_path: Path) -> sqlite3.Connection:
    """Create a test DB with pm_positions, pm_legs, and pm_fills tables."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    # Minimal position/leg tables (matching schema_pm_v3.sql)
    con.executescript("""
        CREATE TABLE pm_positions(
          position_id TEXT PRIMARY KEY,
          venue TEXT NOT NULL,
          strategy TEXT,
          status TEXT NOT NULL,
          created_at_ms INTEGER NOT NULL,
          updated_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_legs(
          leg_id TEXT PRIMARY KEY,
          position_id TEXT NOT NULL,
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL,
          size REAL NOT NULL,
          entry_price REAL,
          current_price REAL,
          unrealized_pnl REAL,
          realized_pnl REAL,
          status TEXT NOT NULL,
          opened_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
    """)

    # pm_fills (matching schema_monitoring_v1.sql)
    con.executescript("""
        CREATE TABLE pm_fills (
          fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          tid TEXT,
          oid TEXT,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
          px REAL NOT NULL,
          sz REAL NOT NULL,
          fee REAL,
          fee_currency TEXT,
          ts INTEGER NOT NULL,
          closed_pnl REAL,
          dir TEXT,
          builder_fee REAL,
          position_id TEXT,
          leg_id TEXT,
          raw_json TEXT,
          meta_json TEXT,
          UNIQUE (venue, account_id, tid),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
        );
    """)
    return con


def _seed_positions(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed test positions matching the actual config structure."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_hyna_HYPE", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_xyz_GOOGL", "hyperliquid", "SPOT_PERP", "CLOSED", now_ms, now_ms, "{}"),
            ("pos_paused", "hyperliquid", "SPOT_PERP", "PAUSED", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # GOLD: spot + perp
            ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            # HYPE: spot + 2 perps
            ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE/USDC", "LONG", 200.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            ("hype_perp_hyna", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 100.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            ("hype_perp_native", "pos_hyna_HYPE", "hyperliquid", "HYPE", "SHORT", 100.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            # GOOGL: CLOSED
            ("googl_spot", "pos_xyz_GOOGL", "hyperliquid", "GOOGL/USDC", "LONG", 5.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            ("googl_perp", "pos_xyz_GOOGL", "hyperliquid", "xyz:GOOGL", "SHORT", 5.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            # PAUSED position
            ("paused_spot", "pos_paused", "hyperliquid", "TEST/USDC", "LONG", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("paused_perp", "pos_paused", "hyperliquid", "TEST", "SHORT", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


def test_load_fill_targets_excludes_closed():
    """CLOSED positions are excluded from fill targets."""
    from tracking.pipeline.fill_ingester import load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con)

        # OPEN positions are included
        assert any(t["leg_id"] == "gold_spot" for t in targets)
        assert any(t["leg_id"] == "gold_perp" for t in targets)
        # PAUSED positions are included
        assert any(t["leg_id"] == "paused_spot" for t in targets)
        # CLOSED positions are excluded
        assert not any(t["leg_id"] == "googl_spot" for t in targets)
        assert not any(t["leg_id"] == "googl_perp" for t in targets)

        con.close()


def test_load_fill_targets_for_backfill_includes_closed():
    """Backfill mode includes CLOSED positions."""
    from tracking.pipeline.fill_ingester import load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con, include_closed=True)

        assert any(t["leg_id"] == "googl_spot" for t in targets)
        assert any(t["leg_id"] == "googl_perp" for t in targets)

        con.close()


def test_map_fill_to_leg():
    """Fill is mapped to correct leg by inst_id + account_id."""
    from tracking.pipeline.fill_ingester import map_fill_to_leg, load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con)

        # Perp fill maps to perp leg
        result = map_fill_to_leg("xyz:GOLD", "0xabc", targets)
        assert result is not None
        assert result["leg_id"] == "gold_perp"

        # Spot fill maps to spot leg
        result = map_fill_to_leg("XAUT0/USDC", "0xabc", targets)
        assert result is not None
        assert result["leg_id"] == "gold_spot"

        # Split perp: hyna:HYPE maps to hype_perp_hyna
        result = map_fill_to_leg("hyna:HYPE", "0xdef", targets)
        assert result is not None
        assert result["leg_id"] == "hype_perp_hyna"

        # Native perp: HYPE maps to hype_perp_native
        result = map_fill_to_leg("HYPE", "0xdef", targets)
        assert result is not None
        assert result["leg_id"] == "hype_perp_native"

        # Unknown inst_id returns None
        result = map_fill_to_leg("UNKNOWN", "0xabc", targets)
        assert result is None

        con.close()


def test_insert_fills_dedup():
    """Duplicate fills (same venue+account+tid) are skipped."""
    from tracking.pipeline.fill_ingester import insert_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        fills = [
            {
                "venue": "hyperliquid",
                "account_id": "0xabc",
                "tid": "t001",
                "oid": "o001",
                "inst_id": "xyz:GOLD",
                "side": "SELL",
                "px": 3000.0,
                "sz": 1.0,
                "fee": 0.5,
                "fee_currency": "USDC",
                "ts": 1711900000000,
                "position_id": "pos_xyz_GOLD",
                "leg_id": "gold_perp",
                "raw_json": "{}",
            }
        ]

        # First insert: 1 new
        inserted = insert_fills(con, fills)
        assert inserted == 1

        # Second insert: 0 (dedup)
        inserted = insert_fills(con, fills)
        assert inserted == 0

        # Verify only 1 row in DB
        count = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
        assert count == 1

        con.close()


def test_synthetic_tid():
    """Venues without native tid get a synthetic hash-based tid."""
    from tracking.pipeline.fill_ingester import generate_synthetic_tid

    tid = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=150.0,
        sz=10.0,
        ts=1711900000000,
    )
    assert tid.startswith("syn_")
    assert len(tid) > 10

    # Same inputs produce same tid (deterministic)
    tid2 = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=150.0,
        sz=10.0,
        ts=1711900000000,
    )
    assert tid == tid2

    # Different inputs produce different tid
    tid3 = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=151.0,  # different price
        sz=10.0,
        ts=1711900000000,
    )
    assert tid != tid3


def test_parse_hl_fill_valid():
    """A well-formed HL fill response is parsed correctly."""
    from tracking.pipeline.fill_ingester import parse_hl_fill

    raw = {
        "time": 1711900000000,
        "coin": "HYPE",
        "side": "A",
        "px": "25.50",
        "sz": "100.0",
        "fee": "0.45",
        "oid": 12345,
        "tid": 67890,
        "dir": "Open Short",
        "closedPnl": "0.0",
    }
    spot_cache = {}
    targets = [
        {"leg_id": "hype_perp", "position_id": "pos_hype", "inst_id": "HYPE", "side": "SHORT", "account_id": "0xabc", "venue": "hyperliquid"},
    ]

    result = parse_hl_fill(raw, "0xabc", spot_cache, targets, dex="")
    assert result is not None
    assert result["inst_id"] == "HYPE"
    assert result["side"] == "SELL"
    assert result["px"] == 25.50
    assert result["sz"] == 100.0
    assert result["fee"] == 0.45
    assert result["leg_id"] == "hype_perp"
    assert result["position_id"] == "pos_hype"


def test_parse_hl_fill_malformed():
    """Malformed fill responses return None."""
    from tracking.pipeline.fill_ingester import parse_hl_fill

    # Missing time
    assert parse_hl_fill({}, "0xabc", {}, []) is None
    # Missing coin
    assert parse_hl_fill({"time": 123}, "0xabc", {}, []) is None
    # Zero price
    assert parse_hl_fill({"time": 123, "coin": "X", "side": "B", "px": "0", "sz": "1"}, "0xabc", {}, []) is None
    # Invalid side
    assert parse_hl_fill({"time": 123, "coin": "X", "side": "Z", "px": "1", "sz": "1"}, "0xabc", {}, []) is None


def main() -> int:
    test_load_fill_targets_excludes_closed()
    print("PASS: test_load_fill_targets_excludes_closed")
    test_load_fill_targets_for_backfill_includes_closed()
    print("PASS: test_load_fill_targets_for_backfill_includes_closed")
    test_map_fill_to_leg()
    print("PASS: test_map_fill_to_leg")
    test_insert_fills_dedup()
    print("PASS: test_insert_fills_dedup")
    test_synthetic_tid()
    print("PASS: test_synthetic_tid")
    test_parse_hl_fill_valid()
    print("PASS: test_parse_hl_fill_valid")
    test_parse_hl_fill_malformed()
    print("PASS: test_parse_hl_fill_malformed")
    print("\nAll fill_ingester tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
