"""Tests for vault strategy registry loader and validator."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.vault.registry import load_registry

VALID_STRATEGIES = {
    "vault_name": "Test Vault",
    "strategies": [
        {
            "strategy_id": "lending",
            "name": "Lending",
            "type": "LENDING",
            "status": "ACTIVE",
            "wallets": [{"wallet_label": "lending", "venue": "hyperliquid"}],
            "target_weight_pct": 50.0,
            "config": {},
        },
        {
            "strategy_id": "delta_neutral",
            "name": "Delta Neutral",
            "type": "DELTA_NEUTRAL",
            "status": "ACTIVE",
            "wallets": [{"wallet_label": "alt", "venue": "hyperliquid"}],
            "target_weight_pct": 45.0,
            "config": {},
        },
    ],
}


def _write_json(data) -> Path:
    f = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


def test_load_valid_registry():
    path = _write_json(VALID_STRATEGIES)
    vault_name, strategies = load_registry(path)
    assert vault_name == "Test Vault"
    assert len(strategies) == 2
    assert strategies[0].strategy_id == "lending"
    assert strategies[0].type == "LENDING"
    assert strategies[1].strategy_id == "delta_neutral"
    assert strategies[1].wallets[0]["wallet_label"] == "alt"


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        load_registry(Path("/nonexistent/file.json"))


def test_load_invalid_json():
    f = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.write("{bad json")
    f.close()
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_registry(Path(f.name))


def test_validate_missing_strategy_id():
    data = {
        "vault_name": "Test",
        "strategies": [
            {
                "name": "X",
                "type": "LENDING",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 50.0,
                "config": {},
            },
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="strategy_id is required"):
        load_registry(path)


def test_validate_invalid_status():
    data = {
        "vault_name": "Test",
        "strategies": [
            {
                "strategy_id": "x",
                "name": "X",
                "type": "LENDING",
                "status": "INVALID",
                "wallets": [],
                "target_weight_pct": 50.0,
                "config": {},
            },
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="status must be one of"):
        load_registry(path)


def test_validate_duplicate_strategy_ids():
    data = {
        "vault_name": "Test",
        "strategies": [
            {
                "strategy_id": "dup",
                "name": "A",
                "type": "LENDING",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 50.0,
                "config": {},
            },
            {
                "strategy_id": "dup",
                "name": "B",
                "type": "DEPEG",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 50.0,
                "config": {},
            },
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="duplicate strategy_id"):
        load_registry(path)


def test_validate_weights_exceed_100():
    data = {
        "vault_name": "Test",
        "strategies": [
            {
                "strategy_id": "a",
                "name": "A",
                "type": "LENDING",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 60.0,
                "config": {},
            },
            {
                "strategy_id": "b",
                "name": "B",
                "type": "DEPEG",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 50.0,
                "config": {},
            },
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="target weights sum to"):
        load_registry(path)
