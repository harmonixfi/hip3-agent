"""Position Manager package.

This package provides position registry, validation, and database synchronization
for tracking arbitrage positions across multiple venues.
"""

from .registry import load_registry, PositionConfig, LegConfig
from .risk import (
    load_managed_positions,
    load_latest_leg_snapshots,
    compute_position_rollup,
    compute_all_rollups,
    DEFAULT_WARN_DRIFT_USD,
    DEFAULT_CRIT_DRIFT_USD,
    DEFAULT_WARN_DRIFT_PCT,
    DEFAULT_CRIT_DRIFT_PCT,
)
from .alerts import (
    Alert,
    generate_alerts,
    filter_alerts_by_cooldown,
    format_alerts_for_discord,
)
from .carry import (
    compute_all_carries,
    compute_position_carry,
    compute_leg_carry,
)

__all__ = [
    "load_registry",
    "PositionConfig",
    "LegConfig",
    "load_managed_positions",
    "load_latest_leg_snapshots",
    "compute_position_rollup",
    "compute_all_rollups",
    "DEFAULT_WARN_DRIFT_USD",
    "DEFAULT_CRIT_DRIFT_USD",
    "DEFAULT_WARN_DRIFT_PCT",
    "DEFAULT_CRIT_DRIFT_PCT",
    "Alert",
    "generate_alerts",
    "filter_alerts_by_cooldown",
    "format_alerts_for_discord",
    "compute_all_carries",
    "compute_position_carry",
    "compute_leg_carry",
]
