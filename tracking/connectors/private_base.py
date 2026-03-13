"""Base interface for private connectors.

Defines the contract for venue-specific private API connectors that fetch
account and position data.
"""

from __future__ import annotations

from typing import Dict, List, Optional
from abc import ABC, abstractmethod


class PrivateConnectorBase(ABC):
    """Base class for private connectors."""

    def __init__(self, venue: str):
        """
        Initialize the connector.

        Args:
            venue: Venue identifier (e.g., 'paradex', 'hyperliquid')
        """
        self.venue = venue

    @abstractmethod
    def fetch_account_snapshot(self) -> Dict:
        """
        Fetch current account snapshot from the venue.

        Returns:
            Normalized account dict with keys:
            - account_id: str (account identifier)
            - total_balance: float (optional, total account balance)
            - available_balance: float (optional, available for trading)
            - margin_balance: float (optional, margin balance)
            - unrealized_pnl: float (optional, unrealized PnL across all positions)
            - position_value: float (optional, total value of open positions)
            - raw_json: dict (optional, raw API response for debugging)

        Raises:
            Exception: If credentials are missing or API call fails
        """
        pass

    @abstractmethod
    def fetch_open_positions(self) -> List[Dict]:
        """
        Fetch all open positions from the venue.

        Returns:
            List of normalized position dicts, each with keys:
            - leg_id: str (unique identifier for this position leg)
            - position_id: str (parent position ID, if applicable)
            - inst_id: str (instrument identifier, e.g., 'ETH-USD-PERP')
            - side: str ('LONG' or 'SHORT')
            - size: float (position size, positive number)
            - entry_price: float (optional, average entry price)
            - current_price: float (optional, current mark price)
            - unrealized_pnl: float (optional, unrealized PnL)
            - realized_pnl: float (optional, realized PnL)
            - raw_json: dict (optional, raw API response for debugging)

        Raises:
            Exception: If credentials are missing or API call fails
        """
        pass

    def is_configured(self) -> bool:
        """
        Check if the connector has valid credentials configured.

        Returns:
            True if credentials are present and valid, False otherwise
        """
        return True
