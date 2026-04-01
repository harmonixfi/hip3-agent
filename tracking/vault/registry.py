"""Vault Strategy Registry Loader and Validator.

Loads and validates strategy configurations from strategies.json.
Pattern follows tracking/position_manager/registry.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

VALID_STATUSES = {"ACTIVE", "PAUSED", "CLOSED"}


@dataclass
class StrategyConfig:
    """Configuration for a single strategy."""

    strategy_id: str
    name: str
    type: str
    status: str
    wallets: List[Dict[str, str]]
    target_weight_pct: float
    config: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate strategy configuration. Returns list of error messages."""
        errors = []
        if not self.strategy_id:
            errors.append("strategy_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.type:
            errors.append("type is required")
        if not self.status:
            errors.append("status is required")
        elif self.status not in VALID_STATUSES:
            errors.append(f"status must be one of {VALID_STATUSES}, got '{self.status}'")
        if self.target_weight_pct is not None and self.target_weight_pct < 0:
            errors.append(f"target_weight_pct must be non-negative, got {self.target_weight_pct}")
        return errors


def load_registry(path: Path) -> Tuple[str, List[StrategyConfig]]:
    """Load strategy registry from JSON file.

    Args:
        path: Path to strategies.json

    Returns:
        Tuple of (vault_name, list of StrategyConfig)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid or validation fails
    """
    if not path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}") from e

    if not isinstance(data, dict):
        raise ValueError("Registry must be a JSON object with 'vault_name' and 'strategies'")

    vault_name = data.get("vault_name", "Vault")
    raw_strategies = data.get("strategies", [])

    if not isinstance(raw_strategies, list):
        raise ValueError("'strategies' must be a list")

    strategies = []
    all_errors = []

    for i, s in enumerate(raw_strategies):
        try:
            cfg = StrategyConfig(
                strategy_id=s.get("strategy_id", ""),
                name=s.get("name", ""),
                type=s.get("type", ""),
                status=s.get("status", ""),
                wallets=s.get("wallets", []),
                target_weight_pct=s.get("target_weight_pct", 0.0),
                config=s.get("config", {}),
            )
            errors = cfg.validate()
            if errors:
                all_errors.extend([f"strategy {i} ({cfg.strategy_id}): {e}" for e in errors])
            strategies.append(cfg)
        except Exception as e:
            all_errors.append(f"strategy {i}: {e}")

    ids = [s.strategy_id for s in strategies if s.strategy_id]
    if len(ids) != len(set(ids)):
        dupes = [sid for sid in ids if ids.count(sid) > 1]
        all_errors.append(f"duplicate strategy_id(s): {set(dupes)}")

    active_weights = sum(s.target_weight_pct for s in strategies if s.status == "ACTIVE")
    if active_weights > 100.01:
        all_errors.append(f"target weights sum to {active_weights:.1f}% (exceeds 100%)")

    if all_errors:
        raise ValueError("Validation failed:\n" + "\n".join(all_errors))

    return vault_name, strategies
