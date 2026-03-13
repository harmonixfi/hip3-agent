#!/usr/bin/env python3
"""Test private connector scaffolding (requires credentials)."""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.paradex_private import ParadexPrivateConnector
from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector
from tracking.connectors.ethereal_private import EtherealPrivateConnector
from tracking.connectors.lighter_private import LighterPrivateConnector


def test_connector(connector_class, venue, env_vars):
    """Test a connector class."""
    print(f"\nTesting {venue}...")

    # Check if credentials are set
    creds_present = all(os.environ.get(var) for var in env_vars)
    if not creds_present:
        print(f"  Skipped (credentials not set: {', '.join(env_vars)})")
        return

    try:
        connector = connector_class()
        print(f"  ✓ Connector instantiated")

        # Fetch account snapshot
        account = connector.fetch_account_snapshot()
        print(f"  ✓ Account snapshot fetched: {account['account_id']}")

        # Fetch positions
        positions = connector.fetch_open_positions()
        print(f"  ✓ Positions fetched: {len(positions)} positions")

        return True
    except Exception as e:
        print(f"  ✗ Error: {e}")
        return False


def main():
    print("Testing private connector scaffolding...")
    print("=" * 60)

    results = {}

    # Test each connector
    results["paradex"] = test_connector(
        ParadexPrivateConnector,
        "Paradex",
        ["PARADEX_JWT"],
    )

    results["hyperliquid"] = test_connector(
        HyperliquidPrivateConnector,
        "Hyperliquid",
        ["ETHEREAL_ACCOUNT_ADDRESS"],
    )

    results["ethereal"] = test_connector(
        EtherealPrivateConnector,
        "Ethereal",
        ["ETHEREAL_ACCOUNT_ADDRESS"],
    )

    results["lighter"] = test_connector(
        LighterPrivateConnector,
        "Lighter",
        ["ETHEREAL_ACCOUNT_ADDRESS"],
    )

    # Summary
    print("\n" + "=" * 60)
    tested = sum(1 for v in results.values() if v is not None)
    passed = sum(1 for v in results.values() if v is True)
    print(f"Tested: {tested}/4 connectors")
    print(f"Passed: {passed}/{tested} tested connectors")

    # Note about missing credentials
    missing = [venue for venue, result in results.items() if result is None]
    if missing:
        print(f"\nNote: {len(missing)} connectors skipped due to missing credentials")
        print(f"Set the following environment variables to test:")
        for venue in missing:
            if venue == "paradex":
                print(f"  - PARADEX_PRIVATE_KEY, PARADEX_ACCOUNT_ADDRESS")
            elif venue == "hyperliquid":
                print(f"  - ETHEREAL_ACCOUNT_ADDRESS (or HYPERLIQUID_ADDRESS)")
            elif venue == "ethereal":
                print(f"  - ETHEREAL_ACCOUNT_ADDRESS")
            elif venue == "lighter":
                print(f"  - ETHEREAL_ACCOUNT_ADDRESS (or LIGHTER_L1_ADDRESS)")

    if passed < tested:
        sys.exit(1)


if __name__ == "__main__":
    main()
