#!/usr/bin/env python3
"""Pull OKX public data and write into DB v3.

Writes:
- instruments_v3 (spot + swap)
- prices_v3 (spot tickers + swap mark/index/last)
- funding_v3 (swap funding)

This is a minimal ingestion runner for V3-010/011.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import okx_public
from tracking.writers.okx_v3_writer import connect, upsert_instruments, insert_prices, insert_funding

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)

    swap_insts = okx_public.get_instruments()
    spot_insts = okx_public.get_spot_instruments()

    # Adapt to writer expected format
    inst_rows = []
    for r in spot_insts:
        inst_rows.append({
            "instId": r["instId"],
            "instType": "SPOT",
            "tickSize": r.get("tickSize"),
            "contractSize": r.get("contractSize"),
        })
    for r in swap_insts:
        inst_rows.append({
            "instId": r["instId"],
            "instType": "SWAP",
            "tickSize": r.get("tickSize"),
            "contractSize": r.get("contractSize"),
        })

    spot_ticks = okx_public.get_spot_tickers()
    swap_marks = okx_public.get_mark_prices()
    swap_funding = okx_public.get_funding(limit=args.funding_limit)

    price_rows = []
    for inst_id, t in spot_ticks.items():
        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "bid": t.get("bid"),
            "ask": t.get("ask"),
            "last": t.get("lastPrice"),
            "mid": t.get("mid"),
            "source": "okx:spot_tickers",
            "quality_flags": {},
        })

    for inst_id, p in swap_marks.items():
        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "mark": p.get("markPrice"),
            "index": p.get("indexPrice"),
            "last": p.get("lastPrice"),
            "mid": p.get("lastPrice"),
            "source": "okx:mark_price",
            "quality_flags": {"no_bid_ask": True},
        })

    funding_rows = []
    for inst_id, fr in swap_funding.items():
        funding_rows.append({
            "instId": inst_id,
            "ts": ts,
            "funding_rate": fr.get("fundingRate", 0.0),
            "interval_hours": 8,
            "next_funding_ts": int(fr.get("nextFundingTime", 0) or 0) or None,
            "source": "okx:funding_rate",
            "quality_flags": {},
        })

    con = connect(args.db)
    try:
        n_inst = upsert_instruments(con, inst_rows)
        n_px = insert_prices(con, price_rows)
        n_f = insert_funding(con, funding_rows)
        con.commit()
    finally:
        con.close()

    print(f"OK: wrote instruments={n_inst} prices={n_px} funding={n_f} to {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
