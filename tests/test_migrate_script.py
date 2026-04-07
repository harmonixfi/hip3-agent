"""Tests for scripts/migrate_strategy_wallets.py.

Run: .venv/bin/python -m pytest tests/test_migrate_script.py -v
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


_VALID_STRATEGIES = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453"},
            ],
            "target_weight_pct": 95.0, "config": {},
        },
        {
            "strategy_id": "lending",
            "name": "Lending", "type": "LENDING", "status": "ACTIVE",
            "wallets": [],
            "target_weight_pct": 5.0, "config": {"lending_accounts": ["0x1"]},
        },
    ],
}

_DUPLICATE_LABEL_STRATEGIES = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "a", "name": "A", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x1111111111111111111111111111111111111111"}],
            "target_weight_pct": 50.0, "config": {},
        },
        {
            "strategy_id": "b", "name": "B", "type": "DEPEG", "status": "ACTIVE",
            "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x2222222222222222222222222222222222222222"}],
            "target_weight_pct": 50.0, "config": {},
        },
    ],
}


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """Create a temp repo structure with strategies.json and empty DB."""
    (tmp_path / "config").mkdir()
    (tmp_path / "tracking" / "db").mkdir(parents=True)

    strategies_path = tmp_path / "config" / "strategies.json"
    db_path = tmp_path / "tracking" / "db" / "arbit_v3.db"

    # Create minimal DB schema
    con = sqlite3.connect(str(db_path))
    con.executescript("""
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
      raw_json TEXT, meta_json TEXT, account_id TEXT
    );
    CREATE TABLE pm_account_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
      total_balance REAL, available_balance REAL, margin_balance REAL,
      unrealized_pnl REAL, position_value REAL, raw_json TEXT
    );
    """)
    con.commit()
    con.close()

    yield {"root": tmp_path, "strategies": strategies_path, "db": db_path}


def test_migrate_validates_strategies_structure(tmp_repo, monkeypatch, capsys):
    """Dry-run with valid strategies passes validation."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_VALID_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])
    monkeypatch.setattr(mig, "POSITIONS_PATH", tmp_repo["root"] / "nonexistent_positions.json")

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "VALIDATE" in captured or "validate" in captured.lower()


def test_migrate_rejects_duplicate_labels(tmp_repo, monkeypatch, capsys):
    """Migration fails fast when strategies.json has duplicate labels."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_DUPLICATE_LABEL_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])
    monkeypatch.setattr(mig, "POSITIONS_PATH", tmp_repo["root"] / "nonexistent_positions.json")

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 1
    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert "duplicate" in combined.lower() or "FAIL" in combined


def test_migrate_rejects_invalid_address_format(tmp_repo, monkeypatch, capsys):
    """Migration fails when address is not a valid 0x... hex string."""
    from tracking.position_manager import accounts as accounts_mod

    bad = {
        "vault_name": "Test",
        "strategies": [{
            "strategy_id": "dn", "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [{"label": "alt", "venue": "hyperliquid", "address": "not_an_address"}],
            "target_weight_pct": 100.0, "config": {},
        }],
    }
    tmp_repo["strategies"].write_text(json.dumps(bad))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])
    monkeypatch.setattr(mig, "POSITIONS_PATH", tmp_repo["root"] / "nonexistent_positions.json")

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 1


def test_migrate_dry_run_does_not_write_to_db(tmp_repo, monkeypatch):
    """Dry-run must not insert rows into pm_account_snapshots."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_VALID_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])
    monkeypatch.setattr(mig, "POSITIONS_PATH", tmp_repo["root"] / "nonexistent_positions.json")

    mig.main(dry_run=True, skip_recompute=True)

    con = sqlite3.connect(str(tmp_repo["db"]))
    count = con.execute("SELECT COUNT(*) FROM pm_account_snapshots").fetchone()[0]
    con.close()
    assert count == 0
