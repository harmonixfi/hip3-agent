#!/usr/bin/env python3
"""Run all v3 screeners and generate reports.

Runs:
- SPOT↔PERP Carry screener (OKX)
- PERP↔PERP Extreme screener (cross-venue)

Saves results to tracking/reports/ and prints summary.
"""

from __future__ import annotations

import sys
import json
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.analytics.spot_perp_screener_v3 import SpotPerpScreenerV3
from tracking.analytics.perp_perp_screener_v3 import PerpPerpScreenerV3

DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"
REPORTS_DIR = ROOT / "tracking" / "reports"


def main() -> int:
    """Run all screeners and save reports."""
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"\n{'='*60}")
    print(f"Running V3 Screeners")
    print(f"{'='*60}")
    print(f"Timestamp: {timestamp}\n")

    # Run SPOT↔PERP screener
    print("1. Running SPOT↔PERP Carry screener (OKX)...")
    try:
        spot_screener = SpotPerpScreenerV3()
        spot_result = spot_screener.run_screener(
            min_apr=20.0,
            max_results=20,
        )
        spot_screener.save_results(spot_result)

        # Print summary
        if spot_result.opportunities:
            print(f"   Found {len(spot_result.opportunities)} opportunities")
            for opp in spot_result.opportunities[:5]:
                print(f"      {opp.symbol}: APR {opp.apr_14d:.2f}% (14D)")
        else:
            print("   No opportunities found")
        spot_screener.close()
    except Exception as e:
        print(f"   ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Run PERP↔PERP screener
    print("\n2. Running PERP↔PERP Extreme screener (cross-venue)...")
    try:
        perp_screener = PerpPerpScreenerV3()
        perp_result = perp_screener.run_screener(
            min_apr=20.0,
            min_open_interest_rank=200,
            max_results=20,
        )
        perp_screener.save_results(perp_result)

        # Print summary
        if perp_result.opportunities:
            print(f"   Found {len(perp_result.opportunities)} opportunities")
            for opp in perp_result.opportunities[:5]:
                print(f"      {opp.base}: {opp.venue_long}/{opp.venue_short} APR {opp.apr_14d:.2f}%")
        else:
            print("   No opportunities found")
        perp_screener.close()
    except Exception as e:
        print(f"   ERROR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Summary
    print(f"\n{'='*60}")
    print("Screener Summary")
    print(f"{'='*60}")
    print(f"SPOT↔PERP: {len(spot_result.opportunities)} opportunities")
    print(f"PERP↔PERP: {len(perp_result.opportunities)} opportunities")

    # Check if any opportunities found
    total_opp = len(spot_result.opportunities) + len(perp_result.opportunities)
    if total_opp > 0:
        print(f"\n✅ {total_opp} opportunities found (APR >= 20%)")
        print(f"Reports saved to: {REPORTS_DIR}")
    else:
        print(f"\nℹ️  No opportunities found (APR >= 20%)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
