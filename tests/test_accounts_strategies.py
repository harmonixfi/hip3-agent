"""Tests for tracking/position_manager/accounts.py reading from strategies.json.

Run: .venv/bin/python -m pytest tests/test_accounts_strategies.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.position_manager import accounts as accounts_mod


_STRATEGIES_FIXTURE = {
    "vault_name": "Test Vault",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "Delta Neutral",
            "type": "DELTA_NEUTRAL",
            "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0xALT"},
                {"label": "main", "venue": "hyperliquid", "address": "0xMAIN"},
            ],
            "target_weight_pct": 45.0,
            "config": {},
        },
        {
            "strategy_id": "depeg",
            "name": "Depeg",
            "type": "DEPEG",
            "status": "ACTIVE",
            "wallets": [
                {"label": "depeg", "venue": "hyperliquid", "address": "0xDEPEG"},
            ],
            "target_weight_pct": 5.0,
            "config": {},
        },
        {
            "strategy_id": "lending",
            "name": "Lending",
            "type": "LENDING",
            "status": "ACTIVE",
            "wallets": [],
            "target_weight_pct": 50.0,
            "config": {"lending_accounts": ["0xLENDING"]},
        },
    ],
}


@pytest.fixture
def tmp_strategies(monkeypatch):
    """Write strategies fixture to a temp file and point accounts module at it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_STRATEGIES_FIXTURE, f)
        path = Path(f.name)
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", path)
    accounts_mod._CACHE.clear()
    yield path
    path.unlink(missing_ok=True)
    accounts_mod._CACHE.clear()


def test_resolve_venue_accounts_reads_from_strategies_json(tmp_strategies, monkeypatch):
    monkeypatch.delenv("HYPERLIQUID_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("HYPERLIQUID_ADDRESS", raising=False)

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert result == {"alt": "0xALT", "main": "0xMAIN", "depeg": "0xDEPEG"}


def test_resolve_venue_accounts_ignores_hyperliquid_accounts_json_env(tmp_strategies, monkeypatch):
    """HYPERLIQUID_ACCOUNTS_JSON env var MUST be ignored — strategies.json wins."""
    monkeypatch.setenv("HYPERLIQUID_ACCOUNTS_JSON", json.dumps({"phantom": "0xPHANTOM"}))

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert "phantom" not in result
    assert "alt" in result


def test_resolve_venue_accounts_falls_back_to_legacy_address(monkeypatch, tmp_path):
    """When strategies.json has no wallets for a venue, fall back to HYPERLIQUID_ADDRESS."""
    empty_strategies = {
        "vault_name": "Empty",
        "strategies": [
            {
                "strategy_id": "delta_neutral",
                "name": "DN",
                "type": "DELTA_NEUTRAL",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 100.0,
                "config": {},
            }
        ],
    }
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps(empty_strategies))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", p)
    accounts_mod._CACHE.clear()

    monkeypatch.delenv("HYPERLIQUID_ACCOUNTS_JSON", raising=False)
    monkeypatch.setenv("HYPERLIQUID_ADDRESS", "0xFALLBACK")

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert result == {"main": "0xFALLBACK"}


def test_get_strategy_wallets_returns_only_own_wallets(tmp_strategies):
    result = accounts_mod.get_strategy_wallets("delta_neutral")

    assert len(result) == 2
    labels = {w["label"] for w in result}
    assert labels == {"alt", "main"}
    addresses = {w["address"] for w in result}
    assert addresses == {"0xALT", "0xMAIN"}


def test_get_strategy_wallets_returns_empty_for_lending(tmp_strategies):
    """Lending strategy has wallets=[] (reads from external NAV DB)."""
    result = accounts_mod.get_strategy_wallets("lending")
    assert result == []


def test_get_strategy_wallets_raises_keyerror_for_unknown(tmp_strategies):
    with pytest.raises(KeyError):
        accounts_mod.get_strategy_wallets("nonexistent")


def test_duplicate_labels_across_strategies_rejected(tmp_path, monkeypatch):
    """Labels must be globally unique across all strategies."""
    dup_strategies = {
        "vault_name": "Dup",
        "strategies": [
            {
                "strategy_id": "a",
                "name": "A", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
                "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x1"}],
                "target_weight_pct": 50.0, "config": {},
            },
            {
                "strategy_id": "b",
                "name": "B", "type": "DEPEG", "status": "ACTIVE",
                "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x2"}],
                "target_weight_pct": 50.0, "config": {},
            },
        ],
    }
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps(dup_strategies))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", p)
    accounts_mod._CACHE.clear()

    with pytest.raises(ValueError, match="duplicate.*label.*main"):
        accounts_mod.resolve_venue_accounts("hyperliquid")


def test_get_strategy_wallets_filters_malformed_entries(tmp_path, monkeypatch):
    """Wallets missing label or address must be filtered out (not returned as empty strings)."""
    malformed = {
        "vault_name": "Malformed",
        "strategies": [
            {
                "strategy_id": "delta_neutral",
                "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
                "wallets": [
                    {"label": "good", "venue": "hyperliquid", "address": "0xGOOD"},
                    {"label": "no_addr", "venue": "hyperliquid"},
                    {"venue": "hyperliquid", "address": "0xNOLABEL"},
                    {"label": "", "venue": "hyperliquid", "address": "0xEMPTY"},
                ],
                "target_weight_pct": 100.0, "config": {},
            }
        ],
    }
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps(malformed))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", p)
    accounts_mod._CACHE.clear()

    result = accounts_mod.get_strategy_wallets("delta_neutral")

    assert len(result) == 1
    assert result[0]["label"] == "good"
    assert result[0]["address"] == "0xGOOD"


def test_get_felix_wallet_address_from_env_normalizes(tmp_strategies, monkeypatch):
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xAbC")
    assert accounts_mod.get_felix_wallet_address_from_env() == "0xabc"
    monkeypatch.delenv("FELIX_WALLET_ADDRESS", raising=False)
    assert accounts_mod.get_felix_wallet_address_from_env() is None


def test_get_delta_neutral_equity_account_ids_merges_felix(tmp_strategies, monkeypatch):
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xFELIX")
    ids = accounts_mod.get_delta_neutral_equity_account_ids()
    assert "0xALT" in ids
    assert "0xMAIN" in ids
    assert "0xfelix" in ids


def test_get_delta_neutral_equity_account_ids_dedupes_felix_with_strategy_wallet(
    tmp_strategies, monkeypatch,
):
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xALT")
    ids = accounts_mod.get_delta_neutral_equity_account_ids()
    assert ids == ["0xALT", "0xMAIN"]
