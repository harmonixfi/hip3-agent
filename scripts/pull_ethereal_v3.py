#!/usr/bin/env python3
"""Pull Ethereal public data and write into DB v3.

Writes:
- instruments_v3 (perps)
- prices_v3 (bestBid/bestAsk/last/oraclePrice)
- funding_v3 (funding rates)

Minimal ingestion runner for V3-031.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import ethereal_public
from tracking.writers.ethereal_v3_writer import connect, upsert_instruments, insert_prices, insert_funding

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--inst-limit", type=int, default=50)
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)

    # Get instruments
    all_insts = ethereal_public.get_instruments()
    # Limit to avoid timeout
    insts = all_insts[:args.inst_limit] if args.inst_limit > 0 else all_insts

    # Get market prices (includes bestBid/bestAsk/last/oraclePrice)
    market_prices = ethereal_public.get_mark_prices()

    # Get funding rates (1h interval)
    funding_map = ethereal_public.get_funding()

    # Prepare instrument rows
    inst_rows = []
    for inst in insts:
        inst_rows.append({
            "symbol": inst["symbol"],
            "minPriceTickSize": inst.get("minPriceTickSize", 0.1),
            "minQty": inst.get("minQty", 1.0),
            "status": inst.get("status", "ACTIVE"),
        })

    # Prepare price rows
    price_rows = []
    for inst_id, p in market_prices.items():
        mid = None
        if p.get("bestBid") and p.get("bestAsk"):
            mid = (p["bestBid"] + p["bestAsk"]) / 2

        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "bid": p.get("bestBid"),
            "ask": p.get("bestAsk"),
            "mid": mid or p.get("oraclePrice"),
            "last": p.get("lastPrice"),
            "source": "ethereal:market_price",
            "quality_flags": {} if mid else {"no_bid_ask": True},
        })

    # Prepare funding rows
    # Ethereal funding is hourly (fundingRate is 1h rate)
    inst_symbols = set(inst["symbol"] for inst in insts)

    funding_rows = []
    for inst in insts:
        inst_id = inst["symbol"]
        if inst_id not in inst_symbols:
            continue

        fr = (funding_map.get(inst_id) or {}) if isinstance(funding_map, dict) else {}
        funding_rate_1h = fr.get("fundingRate", 0.0)
        interval_hours = fr.get("fundingIntervalHours", 1)

        funding_rows.append({
            "instId": inst_id,
            "ts": ts,
            "fundingRate": funding_rate_1h,
            "interval_hours": interval_hours,
            "source": "ethereal:funding_rate",
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

        print(f"Ethereal v3: {n_inst} instruments, {n_price} prices, {n_funding} funding records")
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
