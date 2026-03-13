#!/usr/bin/env python3
"""Pull Paradex public data and write into DB v3.

Writes:
- instruments_v3 (perps)
- prices_v3 (orderbook mid-price)
- funding_v3 (funding rates)

Minimal ingestion runner for V3-030.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import paradex_public
from tracking.writers.paradex_v3_writer import connect, upsert_instruments, insert_prices, insert_funding

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--inst-limit", type=int, default=50)
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)

    # Get instruments
    all_insts = paradex_public.get_instruments()
    # Limit to avoid timeout
    insts = all_insts[:args.inst_limit] if args.inst_limit > 0 else all_insts

    # Get funding rates
    funding = paradex_public.get_funding()
    # Filter funding to only include instruments we're inserting
    inst_symbols = set(inst["symbol"] for inst in insts)
    funding_filtered = {k: v for k, v in funding.items() if k in inst_symbols}
    # Limit funding data
    funding_list = list(funding_filtered.items())[:args.funding_limit] if args.funding_limit > 0 else list(funding_filtered.items())

    # Get mark prices (orderbook mid-price)
    prices = {}
    for inst in insts:
        symbol = inst["symbol"]
        try:
            orderbook = paradex_public.get_orderbook(symbol)
            if orderbook and "bids" in orderbook and "asks" in orderbook:
                bids = orderbook["bids"]
                asks = orderbook["asks"]
                if bids and asks:
                    best_bid = float(bids[0]["price"]) if bids else None
                    best_ask = float(asks[0]["price"]) if asks else None
                    if best_bid and best_ask:
                        mid = (best_bid + best_ask) / 2
                        prices[symbol] = {
                            "mid": mid,
                            "best_bid": best_bid,
                            "best_ask": best_ask,
                        }
        except Exception as e:
            print(f"Error fetching orderbook for {symbol}: {e}", file=sys.stderr)

    # Prepare instrument rows
    inst_rows = []
    for inst in insts:
        inst_rows.append({
            "symbol": inst["symbol"],
            "price_tick_size": inst.get("price_tick_size"),
            "order_size_increment": inst.get("order_size_increment"),
            "min_order_size": inst.get("min_order_size"),
            "status": inst.get("status", "ACTIVE"),
        })

    # Prepare price rows
    price_rows = []
    for inst_id, p in prices.items():
        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "mid": p["mid"],
            "source": "paradex:orderbook_mid",
            "quality_flags": {},
        })

    # Prepare funding rows
    funding_rows = []
    for inst_id, fr in funding_list:
        funding_rows.append({
            "instId": inst_id,
            "ts": ts,
            "fundingRate": fr.get("funding_rate", 0.0),
            "interval_hours": fr.get("funding_interval_hours", 8),
            "source": "paradex:funding_rate",
            "quality_flags": {},
        })

    # Write to DB
    con = connect(args.db)
    try:
        n_inst = upsert_instruments(con, inst_rows)
        n_price = insert_prices(con, price_rows)
        n_funding = insert_funding(con, funding_rows)
        con.commit()

        print(f"Paradex v3: {n_inst} instruments, {n_price} prices, {n_funding} funding records")
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
