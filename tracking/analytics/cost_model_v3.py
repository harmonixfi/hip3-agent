#!/usr/bin/env python3
"""Cost model v3 - Fee lookup and spread/slippage cost estimation

Supports:
- Fee lookup per venue + product type (from config/fees.json)
- Spread cost estimation (bid/ask when available, else proxy)
- Flags for proxy usage
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent.parent
FEE_CONFIG_PATH = ROOT / "config" / "fees.json"


@dataclass
class FeeSchedule:
    """Fee schedule for a venue + product type."""
    venue: str
    product_type: str  # "spot" or "perp"
    maker_bps: float
    taker_bps: float


@dataclass
class SpreadCost:
    """Estimated spread/slippage cost in basis points."""
    cost_bps: float
    is_proxy: bool  # True if using proxy instead of actual bid/ask


class CostModelV3:
    """Cost model for funding arbitrage calculations."""

    def __init__(self, config_path: Optional[Path] = None):
        """Load fee configuration from JSON file.

        Args:
            config_path: Path to fees.json (defaults to config/fees.json)
        """
        if config_path is None:
            config_path = FEE_CONFIG_PATH

        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)

        self._fee_cache = {}

    def get_fee(self, venue: str, product_type: str, is_maker: bool = False) -> FeeSchedule:
        """Get fee schedule for a venue and product type.

        Args:
            venue: Venue name (e.g., "okx", "paradex")
            product_type: Product type ("spot" or "perp")
            is_maker: True for maker fee, False for taker fee

        Returns:
            FeeSchedule with fee in basis points

        Raises:
            KeyError: If venue or product type not found
        """
        cache_key = (venue, product_type)

        if cache_key not in self._fee_cache:
            venue_config = self.config["venues"].get(venue)
            if not venue_config:
                raise KeyError(f"Venue {venue!r} not found in fee config")

            product_config = venue_config.get(product_type)
            if not product_config:
                raise KeyError(f"Product type {product_type!r} not found for venue {venue!r}")

            self._fee_cache[cache_key] = FeeSchedule(
                venue=venue,
                product_type=product_type,
                maker_bps=product_config["maker_bps"],
                taker_bps=product_config["taker_bps"],
            )

        schedule = self._fee_cache[cache_key]
        return schedule

    def get_fee_bps(self, venue: str, product_type: str, is_maker: bool = False) -> float:
        """Get fee in basis points for a specific scenario.

        Args:
            venue: Venue name
            product_type: Product type
            is_maker: True for maker fee, False for taker fee

        Returns:
            Fee in basis points
        """
        schedule = self.get_fee(venue, product_type)
        return schedule.maker_bps if is_maker else schedule.taker_bps

    def estimate_spread_cost(
        self,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
        proxy_bps: Optional[float] = None,
    ) -> SpreadCost:
        """Estimate spread/slippage cost in basis points.

        Args:
            bid: Bid price (optional)
            ask: Ask price (optional)
            proxy_bps: Proxy spread in basis points if bid/ask unavailable

        Returns:
            SpreadCost with cost in bps and is_proxy flag
        """
        # If we have bid/ask, calculate actual spread
        if bid is not None and ask is not None and bid > 0 and ask > 0:
            mid = (bid + ask) / 2
            if mid > 0:
                spread_bps = ((ask - bid) / mid) * 10000
                return SpreadCost(cost_bps=spread_bps, is_proxy=False)

        # Fall back to proxy
        if proxy_bps is None:
            proxy_bps = self.config.get("default_assumptions", {}).get("proxy_slippage_bps", 10)

        return SpreadCost(cost_bps=proxy_bps, is_proxy=True)

    def calculate_entry_exit_cost(
        self,
        venue_1: str,
        product_type_1: str,
        venue_2: str,
        product_type_2: str,
        bid_1: Optional[float] = None,
        ask_1: Optional[float] = None,
        bid_2: Optional[float] = None,
        ask_2: Optional[float] = None,
        proxy_spread_bps: Optional[float] = None,
    ) -> dict:
        """Calculate total entry+exit cost for a 2-venue arbitrage.

        Args:
            venue_1: First venue
            product_type_1: First product type
            venue_2: Second venue
            product_type_2: Second product type
            bid_1, ask_1: Orderbook for venue 1
            bid_2, ask_2: Orderbook for venue 2
            proxy_spread_bps: Proxy spread if orderbooks unavailable

        Returns:
            Dict with:
                - total_bps: Total cost in basis points
                - venue_1_bps: Cost at venue 1
                - venue_2_bps: Cost at venue 2
                - used_proxy: List of which venues used proxy spread
        """
        # Get fees (assume taker for entry/exit)
        fee_1_bps = self.get_fee_bps(venue_1, product_type_1, is_maker=False)
        fee_2_bps = self.get_fee_bps(venue_2, product_type_2, is_maker=False)

        # Get spread costs
        spread_1 = self.estimate_spread_cost(bid_1, ask_1, proxy_spread_bps)
        spread_2 = self.estimate_spread_cost(bid_2, ask_2, proxy_spread_bps)

        # Entry + exit = fee*2 + spread*2 (enter and exit each side)
        total_1_bps = (fee_1_bps + spread_1.cost_bps) * 2
        total_2_bps = (fee_2_bps + spread_2.cost_bps) * 2

        used_proxy = []
        if spread_1.is_proxy:
            used_proxy.append(venue_1)
        if spread_2.is_proxy:
            used_proxy.append(venue_2)

        return {
            "total_bps": total_1_bps + total_2_bps,
            "venue_1_bps": total_1_bps,
            "venue_2_bps": total_2_bps,
            "used_proxy": used_proxy,
        }


def main() -> int:
    """Test CLI: load config and run basic sanity checks."""
    model = CostModelV3()

    # Test fee lookups
    test_cases = [
        ("okx", "spot"),
        ("okx", "perp"),
        ("paradex", "perp"),
        ("hyperliquid", "perp"),
    ]

    print("Fee lookups (taker fees):")
    for venue, product in test_cases:
        fee = model.get_fee_bps(venue, product, is_maker=False)
        print(f"  {venue}/{product}: {fee} bps")

    # Test spread estimation
    print("\nSpread estimation:")
    spread_real = model.estimate_spread_cost(bid=50000, ask=50100)
    print(f"  Real bid/ask: {spread_real.cost_bps:.2f} bps (proxy={spread_real.is_proxy})")

    spread_proxy = model.estimate_spread_cost(bid=None, ask=None, proxy_bps=15)
    print(f"  Proxy: {spread_proxy.cost_bps:.2f} bps (proxy={spread_proxy.is_proxy})")

    # Test total cost calculation
    print("\nTotal entry+exit cost (OKX spot vs OKX perp):")
    cost = model.calculate_entry_exit_cost(
        venue_1="okx",
        product_type_1="spot",
        venue_2="okx",
        product_type_2="perp",
        bid_1=50000,
        ask_1=50100,
        bid_2=50000,
        ask_2=50100,
    )
    print(f"  Total: {cost['total_bps']:.2f} bps")
    print(f"  Venue 1: {cost['venue_1_bps']:.2f} bps")
    print(f"  Venue 2: {cost['venue_2_bps']:.2f} bps")
    print(f"  Used proxy: {cost['used_proxy']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
