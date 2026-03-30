#!/usr/bin/env python3
"""Tests for Felix fill ingestion pipeline."""

from __future__ import annotations

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


def _seed_felix_positions(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed Felix equity positions for testing."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("pos_felix_AAPL", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_felix_GOOGL", "hyperliquid", "SPOT_PERP", "CLOSED", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("aapl_spot", "pos_felix_AAPL", "felix", "AAPL/USDC", "LONG", 10.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("aapl_perp", "pos_felix_AAPL", "hyperliquid", "xyz:AAPL", "SHORT", 10.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("googl_spot", "pos_felix_GOOGL", "felix", "GOOGL/USDC", "LONG", 3.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            ("googl_perp", "pos_felix_GOOGL", "hyperliquid", "xyz:GOOGL", "SHORT", 3.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


def test_ingest_felix_fills_maps_to_legs():
    """Felix fills are mapped to correct position legs."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_001",
                "oid": "ord_001",
                "inst_id": "AAPL/USDC",
                "side": "BUY",
                "px": 175.30,
                "sz": 10.0,
                "fee": 0.88,
                "fee_currency": "USDC",
                "ts": 1711900000000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        inserted = ingest_felix_fills(con, raw_fills)
        assert inserted == 1

        # Verify fill was mapped to correct leg
        row = con.execute(
            "SELECT position_id, leg_id FROM pm_fills WHERE tid = 'felix_ord_001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "pos_felix_AAPL"
        assert row[1] == "aapl_spot"

        con.close()


def test_ingest_felix_fills_dedup():
    """Duplicate Felix fills are rejected."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_002",
                "oid": "ord_002",
                "inst_id": "AAPL/USDC",
                "side": "BUY",
                "px": 176.00,
                "sz": 5.0,
                "fee": 0.44,
                "fee_currency": "USDC",
                "ts": 1711900100000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        assert ingest_felix_fills(con, raw_fills) == 1
        assert ingest_felix_fills(con, raw_fills) == 0  # dedup

        count = con.execute("SELECT COUNT(*) FROM pm_fills WHERE venue = 'felix'").fetchone()[0]
        assert count == 1

        con.close()


def test_ingest_felix_fills_unmapped():
    """Fills for unknown inst_id are inserted with NULL position/leg."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_999",
                "oid": "ord_999",
                "inst_id": "UNKNOWN/USDC",
                "side": "BUY",
                "px": 50.0,
                "sz": 1.0,
                "fee": 0.05,
                "fee_currency": "USDC",
                "ts": 1711900200000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        inserted = ingest_felix_fills(con, raw_fills)
        assert inserted == 1

        row = con.execute(
            "SELECT position_id, leg_id FROM pm_fills WHERE tid = 'felix_ord_999'"
        ).fetchone()
        assert row[0] is None
        assert row[1] is None

        con.close()


def main() -> int:
    test_ingest_felix_fills_maps_to_legs()
    print("PASS: test_ingest_felix_fills_maps_to_legs")
    test_ingest_felix_fills_dedup()
    print("PASS: test_ingest_felix_fills_dedup")
    test_ingest_felix_fills_unmapped()
    print("PASS: test_ingest_felix_fills_unmapped")
    print("\nAll felix_fill_ingester tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
