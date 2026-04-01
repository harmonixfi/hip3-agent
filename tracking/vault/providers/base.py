"""Base class for strategy equity providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StrategyEquity:
    """Result of an equity query for a strategy."""

    equity_usd: float
    breakdown: dict
    timestamp_ms: int
    meta: dict = field(default_factory=dict)


class EquityProvider(ABC):
    """Abstract base for fetching equity of a strategy."""

    @abstractmethod
    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        """Fetch current equity for this strategy.

        Args:
            strategy: Row from vault_strategies (dict with strategy_id, wallets_json, etc.)
            db: SQLite connection (for reading pm_* tables or vault_* tables)

        Returns:
            StrategyEquity with current equity data
        """
        raise NotImplementedError
