"""Position Registry Loader and Validator.

Handles loading and validating position configurations from JSON files.
Validates schema, enums, and ensures leg_id uniqueness within positions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass


# Valid enums
VALID_STRATEGY_TYPES = {"SPOT_PERP", "PERP_PERP"}
VALID_SIDES = {"LONG", "SHORT"}
VALID_STATUSES = {"OPEN", "PAUSED", "EXITING", "CLOSED"}


@dataclass
class LegConfig:
    """Configuration for a single position leg."""
    leg_id: str
    venue: str
    inst_id: str
    side: str
    qty: float
    qty_type: Optional[str] = None
    leverage: Optional[float] = None
    margin_mode: Optional[str] = None
    collateral: Optional[float] = None
    wallet_label: Optional[str] = None

    def validate(self) -> List[str]:
        """Validate leg configuration. Returns list of error messages (empty if valid)."""
        errors = []

        if not self.leg_id:
            errors.append("leg_id is required")
        if not self.venue:
            errors.append("venue is required")
        if not self.inst_id:
            errors.append("inst_id is required")
        if not self.side:
            errors.append("side is required")
        elif self.side not in VALID_SIDES:
            errors.append(f"side must be one of {VALID_SIDES}, got '{self.side}'")

        if self.qty is None:
            errors.append("qty is required")
        elif self.qty <= 0:
            errors.append(f"qty must be positive, got {self.qty}")

        # Optional fields
        if self.leverage is not None and self.leverage <= 0:
            errors.append(f"leverage must be positive, got {self.leverage}")

        return errors


@dataclass
class PositionConfig:
    """Configuration for a position (one or more legs)."""
    position_id: str
    strategy_type: str
    base: str
    status: str
    legs: List[LegConfig]
    amount_usd: Optional[float] = None
    open_fees_usd: Optional[float] = None
    thresholds: Optional[Dict[str, Any]] = None

    def validate(self) -> List[str]:
        """Validate position configuration. Returns list of error messages (empty if valid)."""
        errors = []

        if not self.position_id:
            errors.append("position_id is required")
        if not self.strategy_type:
            errors.append("strategy_type is required")
        elif self.strategy_type not in VALID_STRATEGY_TYPES:
            errors.append(f"strategy_type must be one of {VALID_STRATEGY_TYPES}, got '{self.strategy_type}'")
        if not self.base:
            errors.append("base is required")
        if not self.status:
            errors.append("status is required")
        elif self.status not in VALID_STATUSES:
            errors.append(f"status must be one of {VALID_STATUSES}, got '{self.status}'")

        if self.amount_usd is not None and self.amount_usd <= 0:
            errors.append(f"amount_usd must be positive, got {self.amount_usd}")

        if self.open_fees_usd is not None and self.open_fees_usd < 0:
            errors.append(f"open_fees_usd must be non-negative, got {self.open_fees_usd}")

        if not self.legs:
            errors.append("at least one leg is required")

        # Validate each leg
        for i, leg in enumerate(self.legs):
            leg_errors = leg.validate()
            for err in leg_errors:
                errors.append(f"leg[{i}]: {err}")

        # Check leg_id uniqueness within position
        leg_ids = [leg.leg_id for leg in self.legs if leg.leg_id]
        if len(leg_ids) != len(set(leg_ids)):
            errors.append("leg_id must be unique within position")

        return errors


def load_registry(path: Path) -> List[PositionConfig]:
    """
    Load position registry from JSON file.

    Args:
        path: Path to the registry JSON file

    Returns:
        List of PositionConfig objects

    Raises:
        FileNotFoundError: If the registry file doesn't exist
        ValueError: If the JSON is invalid or validation fails
    """
    if not path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    if not isinstance(data, list):
        raise ValueError(f"Registry must be a list of positions, got {type(data).__name__}")

    positions = []
    all_errors = []

    for i, pos_data in enumerate(data):
        try:
            pos = parse_position(pos_data)
            errors = pos.validate()
            if errors:
                all_errors.extend([f"position {i} ({pos.position_id}): {err}" for err in errors])
            positions.append(pos)
        except Exception as e:
            all_errors.append(f"position {i}: {e}")

    if all_errors:
        raise ValueError(f"Validation failed:\n" + "\n".join(all_errors))

    return positions


def parse_position(data: Dict[str, Any]) -> PositionConfig:
    """
    Parse a single position configuration from dict.

    Args:
        data: Position configuration dictionary

    Returns:
        PositionConfig object

    Raises:
        KeyError: If required fields are missing
    """
    legs = []
    for leg_data in data.get("legs", []):
        leg = LegConfig(
            leg_id=leg_data["leg_id"],
            venue=leg_data["venue"],
            inst_id=leg_data["inst_id"],
            side=leg_data["side"],
            qty=leg_data["qty"],
            qty_type=leg_data.get("qty_type"),
            leverage=leg_data.get("leverage"),
            margin_mode=leg_data.get("margin_mode"),
            collateral=leg_data.get("collateral"),
            wallet_label=leg_data.get("wallet_label"),
        )
        legs.append(leg)

    return PositionConfig(
        position_id=data["position_id"],
        strategy_type=data["strategy_type"],
        base=data["base"],
        status=data["status"],
        legs=legs,
        amount_usd=data.get("amount_usd"),
        open_fees_usd=data.get("open_fees_usd"),
        thresholds=data.get("thresholds"),
    )
