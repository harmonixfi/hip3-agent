#!/usr/bin/env python3
"""Test script for Lighter public connector."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))

from lighter_public import get_instruments, get_mark_prices, get_orderbook, get_funding


def main():
    print("=" * 60)
    print("Lighter Public Connector Test")
    print("=" * 60)

    # Test 1: Get instruments
    print("\n[1] Testing get_instruments()...")
    instruments = get_instruments()
    print(f"✓ Retrieved {len(instruments)} active perp instruments")
    print(f"  Sample instruments:")
    for inst in instruments[:5]:
        print(f"    - {inst['symbol']} (market_id: {inst['inst_id']}, tick: {inst['tickSize']})")

    # Test 2: Get mark prices
    print("\n[2] Testing get_mark_prices(limit=10)...")
    prices = get_mark_prices(limit=10)
    print(f"✓ Retrieved prices for {len(prices)} instruments")
    print(f"  Sample prices:")
    for symbol, price_info in list(prices.items())[:5]:
        print(f"    - {symbol}: ${price_info['lastPrice']:,.2f}")

    # Test 3: Get orderbook for ETH
    print("\n[3] Testing get_orderbook('ETH')...")
    ob = get_orderbook("ETH")
    print(f"✓ Retrieved orderbook for ETH")
    print(f"    Bid: ${ob['bid']:,.2f}")
    print(f"    Ask: ${ob['ask']:,.2f}")
    print(f"    Mid: ${ob['mid']:,.2f}")
    print(f"    Spread: ${(ob['ask'] - ob['bid']):,.2f} ({((ob['ask'] - ob['bid']) / ob['mid'] * 100):.4f}%)")

    # Test 4: Get orderbook for BTC
    print("\n[4] Testing get_orderbook('BTC')...")
    ob = get_orderbook("BTC")
    print(f"✓ Retrieved orderbook for BTC")
    print(f"    Bid: ${ob['bid']:,.2f}")
    print(f"    Ask: ${ob['ask']:,.2f}")
    print(f"    Mid: ${ob['mid']:,.2f}")
    print(f"    Spread: ${(ob['ask'] - ob['bid']):,.2f} ({((ob['ask'] - ob['bid']) / ob['mid'] * 100):.4f}%)")

    # Test 5: Check funding (expected to be empty via REST)
    print("\n[5] Testing get_funding()...")
    funding = get_funding()
    print(f"⚠ Funding entries via REST API: {len(funding)}")
    print(f"    Note: Funding rates require WebSocket channel")

    print("\n" + "=" * 60)
    print("✓ All tests completed successfully!")
    print("=" * 60)
    print("\nTo pull data into the database:")
    print("  python3 scripts/pull_lighter_market.py")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
