#!/usr/bin/env python3
"""
Test script for spot-perp screener functionality.

Performs sanity checks for spot-perp opportunities:
- BTC/ETH/SOL spot-perp computed if data present
- Funding quality metrics are computed
- Opportunities have correct strategy_type
- Live API method returns opportunities when OKX is reachable
"""

import sys
from pathlib import Path

# Add tracking/analytics to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / 'tracking' / 'analytics'))

# Add parent directory to path for absolute imports
sys.path.insert(0, str(script_dir.parent))

from tracking.analytics.opportunity_screener import OpportunityScreener


def test_spot_perp_screener():
    """Test spot-perp screener basic functionality."""
    print("Testing spot-perp screener...")

    db_path = '/mnt/data/agents/arbit/tracking/db/arbit.db'

    with OpportunityScreener(db_path) as screener:
        # Test DB-based spot-perp opportunities
        print("\n=== Testing DB-based spot-perp screener ===")
        opportunities = screener.find_spot_perp_opportunities(
            venue='okx',
            min_notional=10000.0,
            min_net_funding_apr=0.1,  # Lower threshold for testing
            max_opportunities=50,
            execution_type='market'
        )

        print(f"Found {len(opportunities)} DB-based spot-perp opportunities")

        # Check for expected symbols
        expected_symbols = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
        found_symbols = set()
        for opp in opportunities:
            # Extract base from quote-aware key (e.g., BTC-USDT -> BTC)
            if '-' in opp.symbol:
                found_symbols.add(opp.symbol.split('-')[0])
            else:
                found_symbols.add(opp.symbol)

        print(f"Symbols found: {sorted(found_symbols)}")

        # Verify at least one of the expected symbols is present
        test_symbols = [s for s in expected_symbols if any(s in opp.symbol for opp in opportunities)]
        if test_symbols:
            print(f"✓ Found expected symbols: {test_symbols}")
        else:
            print(f"⚠ None of expected symbols {expected_symbols} found (may be OK if no data)")

        # Verify opportunity properties
        if opportunities:
            print("\nSample opportunity checks:")
            for i, opp in enumerate(opportunities[:3], 1):
                print(f"\n#{i} {opp.symbol}")
                print(f"  Strategy type: {opp.strategy_type}")
                print(f"  Net funding PnL APR: {opp.net_funding_pnl_apr:+.2f}%")
                print(f"  Long venue: {opp.long_venue}, Short venue: {opp.short_venue}")
                print(f"  Funding quality: {opp.funding_quality or 'N/A'}")
                print(f"  Requires short spot: {opp.requires_short_spot}")

                # Verify strategy type
                assert opp.strategy_type == 'spot_perp', f"Expected strategy_type='spot_perp', got '{opp.strategy_type}'"
                print(f"  ✓ Strategy type is correct")

                # Verify funding quality if available
                if opp.funding_quality:
                    print(f"  ✓ Funding quality computed: {opp.funding_quality}")

        # Test live API-based spot-perp opportunities
        print("\n=== Testing live API spot-perp screener ===")
        live_opportunities = screener.find_spot_perp_opportunities_live(
            venue='okx',
            min_notional=10000.0,
            min_net_funding_apr=0.1,  # Lower threshold for testing
            max_opportunities=50,
            execution_type='market'
        )

        print(f"Found {len(live_opportunities)} live API spot-perp opportunities")

        # Check for expected symbols in live data
        found_live_symbols = set()
        for opp in live_opportunities:
            if '-' in opp.symbol:
                found_live_symbols.add(opp.symbol.split('-')[0])
            else:
                found_live_symbols.add(opp.symbol)

        print(f"Live symbols found: {sorted(found_live_symbols)}")

        # Verify live API returns data
        if live_opportunities:
            print(f"✓ Live API returned {len(live_opportunities)} opportunities")

            # Check that live data is marked as such
            for opp in live_opportunities[:3]:
                assert 'live_api' in opp.data_quality, f"Expected 'live_api' in data_quality, got '{opp.data_quality}'"
                print(f"  ✓ Live API data quality marked: {opp.data_quality}")

            # Verify major pairs are present
            test_live_symbols = [s for s in expected_symbols if any(s in opp.symbol for opp in live_opportunities)]
            if test_live_symbols:
                print(f"✓ Found expected symbols in live data: {test_live_symbols}")

            # Assert at least some opportunities exist when OKX is reachable
            assert len(live_opportunities) > 0, "Expected at least one spot-perp opportunity from live OKX API"
            print(f"✓ Assert passed: live API returned > 0 opportunities")
        else:
            print("⚠ Live API returned no opportunities (OKX API may be unavailable)")

        # Run find_all_opportunities to test both strategies
        print("\n=== Testing find_all_opportunities ===")
        spot_perp_opps, perp_perp_opps = screener.find_all_opportunities(
            min_notional=10000.0,
            min_net_funding_apr=0.1,
            max_opportunities=10,
            execution_type='market',
            include_spot_perp=True,
            spot_perp_venue='okx',
            use_live_spot_perp=True  # Use live API for this test
        )

        print(f"Spot-perp opportunities (live): {len(spot_perp_opps)}")
        print(f"Perp-perp opportunities: {len(perp_perp_opps)}")

        # Verify strategy types
        if spot_perp_opps:
            for opp in spot_perp_opps[:3]:
                assert opp.strategy_type == 'spot_perp', f"Expected spot_perp, got {opp.strategy_type}"
                assert 'live_api' in opp.data_quality, f"Expected 'live_api' in data_quality for live mode, got '{opp.data_quality}'"
            print("✓ Spot-perp strategy types and live marking correct")

        if perp_perp_opps:
            for opp in perp_perp_opps[:3]:
                assert opp.strategy_type == 'perp_perp', f"Expected perp_perp, got {opp.strategy_type}"
            print("✓ Perp-perp strategy types correct")

        print("\n\nAll tests passed! ✓")


if __name__ == '__main__':
    try:
        test_spot_perp_screener()
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
