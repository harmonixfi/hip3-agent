#!/usr/bin/env python3
"""
Check which required environment variables are set.
Does NOT print actual values - just SET/UNSET status.
"""

import os
import sys


def check_env_vars():
    """Check environment variables and print status (without values)."""

    # Define required environment variables per venue
    required_vars = {
        "paradex": [
            "PARADEX_JWT",
            "PARADEX_ACCOUNT_ADDRESS",
        ],
        "ethereal": [
            "ETHEREAL_ACCOUNT_ADDRESS",
            "ETHEREAL_SUBACCOUNT_ID",
        ],
        "hyperliquid": [
            "HYPERLIQUID_ADDRESS",
        ],
        "lighter": [
            "LIGHTER_L1_ADDRESS",
        ],
    }

    print("=" * 60)
    print("Environment Variable Status Check")
    print("=" * 60)
    print()

    # Track overall status
    all_set = True
    venue_status = {}

    for venue, vars_list in required_vars.items():
        print(f"{venue.upper()}:")
        venue_status[venue] = {"total": len(vars_list), "set": 0}

        for var in vars_list:
            is_set = var in os.environ and os.environ[var].strip() != ""
            status = "SET" if is_set else "UNSET"
            if not is_set:
                all_set = False

            print(f"  {var:40s} {status}")

            if is_set:
                venue_status[venue]["set"] += 1

        print(f"  -> {venue_status[venue]['set']}/{venue_status[venue]['total']} variables set")
        print()

    # Summary
    print("=" * 60)
    total_vars = sum(len(v) for v in required_vars.values())
    total_set = sum(s["set"] for s in venue_status.values())

    print(f"Summary: {total_set}/{total_vars} variables set")

    if all_set:
        print("✅ All required environment variables are set!")
        return 0
    else:
        print("⚠️  Some required environment variables are missing.")
        print()
        print("To fix this:")
        print("  1. Copy /mnt/data/agents/arbit/.arbit_env.example (if it exists)")
        print("  2. Edit the file to add your values")
        print("  3. Source it: source /mnt/data/agents/arbit/scripts/source_env.sh")
        return 1


if __name__ == "__main__":
    sys.exit(check_env_vars())
