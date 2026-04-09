"""Test that _get_total_equity() only includes Delta Neutral strategy wallets.

Run: .venv/bin/python -m pytest tests/test_portfolio_dn_filter.py -v
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.pipeline import portfolio as portfolio_mod
from tracking.position_manager import accounts as accounts_mod

_SCHEMA = """
CREATE TABLE pm_account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
  total_balance REAL, available_balance REAL, margin_balance REAL,
  unrealized_pnl REAL, position_value REAL, raw_json TEXT
);
"""

_STRATEGIES_FIXTURE = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0xALT"},
                {"label": "main", "venue": "hyperliquid", "address": "0xMAIN"},
            ],
            "target_weight_pct": 45.0, "config": {},
        },
        {
            "strategy_id": "depeg",
            "name": "Depeg", "type": "DEPEG", "status": "ACTIVE",
            "wallets": [{"label": "depeg", "venue": "hyperliquid", "address": "0xDEPEG"}],
            "target_weight_pct": 5.0, "config": {},
        },
    ],
}


@pytest.fixture
def tmp_strategies(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_STRATEGIES_FIXTURE, f)
        path = Path(f.name)
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", path)
    accounts_mod._CACHE.clear()
    yield path
    path.unlink(missing_ok=True)
    accounts_mod._CACHE.clear()


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(_SCHEMA)
    return con


def test_get_total_equity_only_dn_wallets(tmp_strategies):
    """pm_account_snapshots has alt, main, AND depeg. _get_total_equity returns only alt+main."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT",   1000, 50000.0),
            ("hyperliquid", "0xMAIN",  1000,   500.0),
            ("hyperliquid", "0xDEPEG", 1000,  5000.0),  # must NOT be included
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 50500.0  # alt + main only
    assert "0xALT" in result["equity_by_account"]
    assert "0xMAIN" in result["equity_by_account"]
    assert "0xDEPEG" not in result["equity_by_account"]


def test_get_total_equity_picks_latest_ts(tmp_strategies):
    """When multiple snapshots exist for same account, use latest."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT", 1000, 40000.0),  # old
            ("hyperliquid", "0xALT", 2000, 55000.0),  # latest
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 55000.0


def test_get_total_equity_returns_zero_when_no_dn_wallets_in_db(tmp_strategies):
    """When no DN wallet snapshots exist yet, return 0 (not an error)."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [("hyperliquid", "0xDEPEG", 1000, 5000.0)],  # only depeg
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 0.0
    assert result["equity_by_account"] == {}


def test_get_total_equity_excludes_felix_even_when_env_set(tmp_strategies, monkeypatch):
    """FELIX_WALLET_ADDRESS in env must NOT be included in DN equity totals."""
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xFELIX")
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT", 1000, 50000.0),
            ("hyperliquid", "0xMAIN", 1000, 500.0),
            ("felix", "0xfelix", 1000, 999.0),  # must NOT be included
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 50500.0  # alt + main only, no felix
    assert "0xfelix" not in result["equity_by_account"]
    assert "0xFELIX" not in result["equity_by_account"]
