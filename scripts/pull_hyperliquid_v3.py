#!/usr/bin/env python3
"""Pull Hyperliquid public data and write into DB v3.

Writes:
- instruments_v3 (perps)
- prices_v3 (mid/mark/last)
- funding_v3 (funding rates)

Minimal ingestion runner for V3-032.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import hyperliquid_public
from tracking.writers.hyperliquid_v3_writer import connect, upsert_instruments, insert_prices, insert_funding

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--inst-limit", type=int, default=50)
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)

    # Get instruments
    all_insts = hyperliquid_public.get_instruments()
    # Limit to avoid timeout
    insts = all_insts[:args.inst_limit] if args.inst_limit > 0 else all_insts

    # Get mark prices
    mark_prices = hyperliquid_public.get_mark_prices()

    # Get funding rates
    funding = hyperliquid_public.get_funding()

    # Prepare instrument rows
    inst_rows = []
    for inst in insts:
        inst_rows.append({
            "symbol": inst["symbol"],
            "szDecimals": inst.get("szDecimals", 3),
            "status": "OPEN",
        })

    # Prepare price rows
    price_rows = []
    for inst in insts:
        inst_id = inst["symbol"]
        if inst_id not in mark_prices:
            continue

        price_data = mark_prices[inst_id]
        mid = float(price_data.get("midPrice", 0.0)) if price_data.get("midPrice") else None

        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "mid": mid,
            "source": "hyperliquid:mark_price",
            "quality_flags": {"no_bid_ask": True},
        })

    # Prepare funding rows
    # Filter to only include instruments we're actually inserting
    inst_symbols = set(inst["symbol"] for inst in insts)

    funding_rows = []
    for inst_id, funding_rate in funding.items():
        if inst_id not in inst_symbols:
            continue

        funding_rows.append({
            "instId": inst_id,
            "ts": ts,
            "fundingRate": float(funding_rate),
            "interval_hours": 1,  # Hyperliquid funding is hourly
            "source": "hyperliquid:funding_rate",
            "quality_flags": {},
        })

    # Limit funding
    funding_rows = funding_rows[:args.funding_limit] if args.funding_limit > 0 else funding_rows

    # Write to DB
    con = connect(args.db)
    try:
        n_inst = upsert_instruments(con, inst_rows)
        n_price = insert_prices(con, price_rows)
        n_funding = insert_funding(con, funding_rows)
        con.commit()

        print(f"Hyperliquid v3: {n_inst} instruments, {n_price} prices, {n_funding} funding records")
        return 0
    except Exception as e:
        con.rollback()
        print(f"Error writing to DB: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
