"""Test that pm.py sync-registry warns when wallet_label is unknown.

Run: .venv/bin/python -m pytest tests/test_pm_validate.py -v
"""

import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import scripts.pm as pm_mod

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
"""

_REGISTRY_KNOWN = [
    {
        "position_id": "pos_test_HYPE",
        "strategy_type": "SPOT_PERP",
        "base": "HYPE",
        "status": "OPEN",
        "amount_usd": 1000.0,
        "legs": [
            {"leg_id": "pos_test_HYPE_SPOT", "venue": "hyperliquid", "inst_id": "HYPE/USDC", "side": "LONG", "qty": 10.0, "wallet_label": "alt"},
            {"leg_id": "pos_test_HYPE_PERP", "venue": "hyperliquid", "inst_id": "HYPE", "side": "SHORT", "qty": 10.0, "wallet_label": "alt"},
        ],
    }
]

_REGISTRY_UNKNOWN = [
    {
        "position_id": "pos_test_HYPE",
        "strategy_type": "SPOT_PERP",
        "base": "HYPE",
        "status": "OPEN",
        "amount_usd": 1000.0,
        "legs": [
            {"leg_id": "pos_test_HYPE_SPOT", "venue": "hyperliquid", "inst_id": "HYPE/USDC", "side": "LONG", "qty": 10.0, "wallet_label": "unknown_wallet"},
            {"leg_id": "pos_test_HYPE_PERP", "venue": "hyperliquid", "inst_id": "HYPE", "side": "SHORT", "qty": 10.0, "wallet_label": "unknown_wallet"},
        ],
    }
]


def _run_sync(registry: list, env_accounts: dict) -> str:
    """Run sync_registry with given registry and mocked accounts env, return captured stdout."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(registry, f)
        registry_path = Path(f.name)

    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(_SCHEMA)

    env_json = json.dumps(env_accounts)
    captured = io.StringIO()

    with patch.dict(os.environ, {"HYPERLIQUID_ACCOUNTS_JSON": env_json}), \
         patch("sys.stdout", captured):
        pm_mod.sync_registry(con, registry_path)

    registry_path.unlink(missing_ok=True)
    return captured.getvalue()


def test_no_warning_when_wallet_label_known():
    """No WARNING lines when all wallet_labels exist in env accounts."""
    output = _run_sync(
        _REGISTRY_KNOWN,
        {"main": "0xMAIN", "alt": "0xALT"},
    )
    warnings = [line for line in output.splitlines() if "WARNING" in line]
    assert warnings == [], f"Unexpected warnings: {warnings}"


def test_warning_when_wallet_label_unknown():
    """A WARNING line is printed when wallet_label is not in HYPERLIQUID_ACCOUNTS_JSON."""
    output = _run_sync(
        _REGISTRY_UNKNOWN,
        {"main": "0xMAIN", "alt": "0xALT"},
    )
    warnings = [line for line in output.splitlines() if "WARNING" in line]
    assert len(warnings) > 0, f"Expected WARNING about 'unknown_wallet', got none.\nOutput:\n{output}"
    combined = " ".join(warnings)
    assert "unknown_wallet" in combined, f"WARNING should mention 'unknown_wallet': {combined}"
    assert "hyperliquid" in combined.lower(), f"WARNING should mention venue: {combined}"
