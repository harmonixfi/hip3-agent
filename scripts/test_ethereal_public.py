#!/usr/bin/env python3
"""Test script for Ethereal public connector."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))

from ethereal_public import get_instruments, get_funding, get_mark_prices, get_orderbook


def test_get_instruments():
    """Test get_instruments function."""
    print("=" * 60)
    print("Test 1: get_instruments()")
    print("=" * 60)

    instruments = get_instruments()
    print(f"\nTotal instruments: {len(instruments)}")

    if instruments:
        print("\nFirst 5 instruments:")
        for inst in instruments[:5]:
            print(f"  - {inst['symbol']}: {inst['displayTicker']}")
            print(f"    inst_id: {inst['inst_id']}")
            print(f"    base: {inst['base']}, quote: {inst['quote']}")
            print(f"    tickSize: {inst['tickSize']}, contractSize: {inst['contractSize']}")
        print("\n✓ PASSED: get_instruments() returned data")
    else:
        print("\n✗ FAILED: get_instruments() returned empty list")
        return False

    return True


def test_get_funding():
    """Test get_funding function."""
    print("\n" + "=" * 60)
    print("Test 2: get_funding()")
    print("=" * 60)

    funding = get_funding()
    print(f"\nTotal funding entries: {len(funding)}")

    if funding:
        print("\nFirst 5 funding rates:")
        for symbol, info in list(funding.items())[:5]:
            print(f"  - {symbol}: {info['fundingRate']:.8f} (1h)")
        print("\n✓ PASSED: get_funding() returned data")
    else:
        print("\n✗ FAILED: get_funding() returned empty dict")
        return False

    return True


def test_get_mark_prices():
    """Test get_mark_prices function."""
    print("\n" + "=" * 60)
    print("Test 3: get_mark_prices()")
    print("=" * 60)

    prices = get_mark_prices(limit=5)
    print(f"\nTotal price entries: {len(prices)}")

    if prices:
        print("\nFirst 5 mark prices:")
        for symbol, info in prices.items():
            print(f"  - {symbol}:")
            print(f"    markPrice: ${info['markPrice']:.2f}")
            print(f"    indexPrice: ${info['indexPrice']:.2f}")
            print(f"    lastPrice: ${info['lastPrice']:.2f}")
        print("\n✓ PASSED: get_mark_prices() returned data")
    else:
        print("\n✗ FAILED: get_mark_prices() returned empty dict")
        return False

    return True


def test_get_orderbook():
    """Test get_orderbook function."""
    print("\n" + "=" * 60)
    print("Test 4: get_orderbook()")
    print("=" * 60)

    # Test with a few common symbols
    test_symbols = ["BTCUSD", "ETHUSD", "SOLUSD"]

    for symbol in test_symbols:
        print(f"\nTesting {symbol}...")
        ob = get_orderbook(symbol, limit=20)

        if ob:
            print(f"  bid: ${ob['bid']:.2f}")
            print(f"  ask: ${ob['ask']:.2f}")
            print(f"  mid: ${ob['mid']:.2f}")

            if ob['mid'] > 0:
                print(f"  ✓ Valid orderbook for {symbol}")
            else:
                print(f"  ✗ Invalid orderbook for {symbol} (mid = 0)")
        else:
            print(f"  ✗ Failed to get orderbook for {symbol}")

    print("\n✓ PASSED: get_orderbook() completed")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Ethereal Public Connector Test Suite")
    print("=" * 60)

    tests = [
        test_get_instruments,
        test_get_funding,
        test_get_mark_prices,
        test_get_orderbook,
    ]

    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"\n✗ EXCEPTION in {test_func.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ ALL TESTS PASSED")
        return 0
    else:
        print(f"\n✗ {total - passed} TEST(S) FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
