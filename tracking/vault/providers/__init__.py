"""Equity provider registry."""

from .base import EquityProvider, StrategyEquity
from .delta_neutral import DeltaNeutralProvider
from .depeg import DepegProvider
from .lending import LendingProvider

PROVIDER_REGISTRY: dict[str, type[EquityProvider]] = {
    "DELTA_NEUTRAL": DeltaNeutralProvider,
    "LENDING": LendingProvider,
    "DEPEG": DepegProvider,
}

__all__ = [
    "EquityProvider",
    "StrategyEquity",
    "PROVIDER_REGISTRY",
    "DeltaNeutralProvider",
    "LendingProvider",
    "DepegProvider",
]
