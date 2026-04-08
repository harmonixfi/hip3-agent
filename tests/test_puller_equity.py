"""Test that equity snapshots are written for all env-configured wallets,
regardless of whether managed legs exist for that wallet.

Run: .venv/bin/python -m pytest tests/test_puller_equity.py -v
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.position_manager.puller import write_account_snapshot, run_pull

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
CREATE TABLE pm_account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
  total_balance REAL, available_balance REAL, margin_balance REAL,
  unrealized_pnl REAL, position_value REAL, raw_json TEXT, meta_json TEXT
);
CREATE TABLE pm_leg_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  leg_id TEXT NOT NULL, position_id TEXT, venue TEXT NOT NULL,
  inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL,
  entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
  ts INTEGER NOT NULL, account_id TEXT, raw_json TEXT
);
"""


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(_SCHEMA)
    return con


def _fake_snapshot(address: str) -> dict:
    return {
        "account_id": address,
        "dex": "",
        "total_balance": 12345.67,
        "available_balance": 10000.0,
        "margin_balance": 12345.67,
        "unrealized_pnl": None,
        "position_value": None,
        "raw_json": {},
    }


def test_equity_written_for_wallet_with_no_managed_legs():
    """Equity snapshot must be written for every wallet in env, even if no
    managed legs exist for that wallet in the DB."""
    con = _make_db()
    assert con.execute("SELECT COUNT(*) FROM pm_positions").fetchone()[0] == 0

    fake_accounts = {
        "main": "0xMAINADDRESS",
        "alt":  "0xALTADDRESS",
    }

    with patch("tracking.position_manager.puller.resolve_venue_accounts", return_value=fake_accounts), \
         patch("tracking.position_manager.puller.pull_venue_positions") as mock_pull, \
         patch("tracking.position_manager.puller.load_positions_from_db", return_value=[]), \
         patch("tracking.position_manager.puller.ensure_multi_wallet_columns"):

        def side_effect(venue, **kwargs):
            addr = kwargs.get("address", "")
            snap = _fake_snapshot(addr)
            return {"success": True, "account_snapshot": snap, "positions": [], "error": None}

        mock_pull.side_effect = side_effect

        run_pull(
            db_path=Path(":memory:"),
            registry_path=None,
            venues_filter={"hyperliquid"},
            verbose=False,
            _con_override=con,
        )

    rows = con.execute("SELECT account_id, total_balance FROM pm_account_snapshots ORDER BY account_id").fetchall()
    account_ids = [r[0] for r in rows]

    assert "0xMAINADDRESS" in account_ids, f"main wallet equity not written — got {account_ids}"
    assert "0xALTADDRESS" in account_ids, f"alt wallet equity not written — got {account_ids}"
    for account_id, balance in rows:
        assert balance == 12345.67, f"Wrong balance for {account_id}: {balance}"


def test_felix_snapshot_written_when_env_configured(monkeypatch):
    """Felix venue pull uses FELIX_* env (not strategies.json) and writes pm_account_snapshots."""
    con = _make_db()
    monkeypatch.setenv("FELIX_EQUITIES_JWT", "test-jwt")
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xFelixAddr")

    with patch("tracking.position_manager.puller.resolve_venue_accounts", return_value={}), \
         patch("tracking.position_manager.puller.pull_venue_positions") as mock_pull, \
         patch("tracking.position_manager.puller.load_positions_from_db", return_value=[]), \
         patch("tracking.position_manager.puller.ensure_multi_wallet_columns"):

        def side_effect(venue, **kwargs):
            if venue == "felix":
                return {
                    "success": True,
                    "account_snapshot": {
                        "account_id": "0xfelixaddr",
                        "total_balance": 42.0,
                        "available_balance": 40.0,
                        "margin_balance": 42.0,
                        "unrealized_pnl": None,
                        "position_value": None,
                        "raw_json": {},
                    },
                    "positions": [],
                    "error": None,
                }
            return {
                "success": True,
                "account_snapshot": _fake_snapshot(kwargs.get("address", "")),
                "positions": [],
                "error": None,
            }

        mock_pull.side_effect = side_effect

        run_pull(
            db_path=Path(":memory:"),
            registry_path=None,
            venues_filter=None,
            verbose=False,
            _con_override=con,
        )

    rows = con.execute(
        "SELECT venue, account_id, total_balance FROM pm_account_snapshots"
    ).fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "felix"
    assert rows[0][1] == "0xfelixaddr"
    assert rows[0][2] == 42.0
