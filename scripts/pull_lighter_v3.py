#!/usr/bin/env python3
"""Pull Lighter public data and write into DB v3.

Writes:
- instruments_v3 (perps)
- prices_v3 (mid/last)
- funding_v3 (funding rates)

Minimal ingestion runner for V3-033.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import lighter_public
from tracking.writers.lighter_v3_writer import connect, upsert_instruments, insert_prices, insert_funding

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--inst-limit", type=int, default=50)
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)

    # Get instruments
    all_insts = lighter_public.get_instruments()
    # Limit to avoid timeout
    insts = all_insts[:args.inst_limit] if args.inst_limit > 0 else all_insts

    # Get mark prices
    mark_prices = lighter_public.get_mark_prices()

    # Prepare instrument rows
    inst_rows = []
    for inst in insts:
        inst_rows.append({
            "symbol": inst["symbol"],
            "tick_size": inst.get("tickSize", 1.0),
            "step_size": inst.get("step_size", 1.0),
            "min_order_size": inst.get("min_order_size", 1.0),
            "status": inst.get("status", "ACTIVE"),
        })

    # Prepare price rows
    price_rows = []
    for inst in insts:
        inst_id = inst["symbol"]
        if inst_id not in mark_prices:
            continue

        price_data = mark_prices[inst_id]
        mid = None
        if price_data.get("markPrice") and price_data.get("indexPrice"):
            mid = (price_data["markPrice"] + price_data["indexPrice"]) / 2

        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "mid": mid,
            "last": price_data.get("lastPrice"),
            "source": "lighter:mark_price",
            "quality_flags": {},
        })

    # Prepare funding rows (empty for now - Lighter doesn't provide public funding API)
    funding_rows = []

    # Write to DB
    con = connect(args.db)
    try:
        n_inst = upsert_instruments(con, inst_rows)
        n_price = insert_prices(con, price_rows)
        n_funding = insert_funding(con, funding_rows)
        con.commit()

        print(f"Lighter v3: {n_inst} instruments, {n_price} prices, {n_funding} funding records")
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
