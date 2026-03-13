#!/usr/bin/env python3
"""Compute funding-arb candidates from locally collected history.

This script does NOT hit exchanges; it summarizes our sampled history from Loris.
Use it as a screener, then verify funding/fees/orderbooks on the venue before trading.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "config", "strategy.json")
HIST_PATH = os.path.join(ROOT, "data", "loris_funding_history.csv")


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_iso(ts: str) -> dt.datetime:
    # timestamps written by pull script are ISO with timezone
    return dt.datetime.fromisoformat(ts)


def annualize_apr_pct(funding_8h_rate: float) -> float:
    # 8h funding * 3 per day * 365 days
    return funding_8h_rate * 3.0 * 365.0 * 100.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None, help="window length in days (default from config)")
    ap.add_argument("--min-apr", type=float, default=None, help="min net APR %% threshold (default from config)")
    args = ap.parse_args()

    cfg = load_cfg()
    window_days = int(args.days or cfg.get("avg_window_days", 14))
    min_apr = float(args.min_apr or cfg.get("min_avg_apr_pct", 20))

    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=window_days)

    # Collect per (exchange,symbol) average funding rate over the window
    sums = defaultdict(float)
    counts = defaultdict(int)
    ranks = {}  # symbol -> best (min) rank seen

    with open(HIST_PATH, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = parse_iso(row["timestamp_utc"])
            if ts < cutoff:
                continue
            ex = row["exchange"]
            sym = row["symbol"]
            rate = float(row["funding_8h_rate"])
            oi_rank = int(row.get("oi_rank") or 9999)
            key = (ex, sym)
            sums[key] += rate
            counts[key] += 1
            ranks[sym] = min(ranks.get(sym, 9999), oi_rank)

    # Build per-symbol best cross-exchange spread
    by_symbol = defaultdict(list)  # sym -> [(ex, avg_rate, apr_pct)]
    for (ex, sym), s in sums.items():
        c = counts[(ex, sym)]
        if c <= 0:
            continue
        avg_rate = s / c
        by_symbol[sym].append((ex, avg_rate, annualize_apr_pct(avg_rate)))

    candidates = []  # (net_apr, sym, rank, short_ex, long_ex, short_apr, long_apr)
    for sym, lst in by_symbol.items():
        if len(lst) < 2:
            continue
        # choose ex with highest avg funding for SHORT, lowest for LONG
        lst_sorted = sorted(lst, key=lambda x: x[1])
        long_ex, long_rate, long_apr = lst_sorted[0]
        short_ex, short_rate, short_apr = lst_sorted[-1]
        spread_rate = short_rate - long_rate
        net_apr = annualize_apr_pct(spread_rate)
        if net_apr < min_apr:
            continue
        candidates.append((net_apr, sym, ranks.get(sym, 9999), short_ex, long_ex, short_apr, long_apr))

    candidates.sort(reverse=True, key=lambda x: x[0])

    print(f"window_days={window_days} min_net_apr_pct={min_apr} samples_used={(window_days)}")
    print("top_candidates (perp-perp):")
    for i, (net_apr, sym, rank, short_ex, long_ex, short_apr, long_apr) in enumerate(candidates[:30], 1):
        print(
            f"{i:02d}. {sym:8s} OI#{rank:<4d}  NET~{net_apr:6.1f}% APR | SHORT {short_ex} (avg {short_apr:6.1f}%) / LONG {long_ex} (avg {long_apr:6.1f}%)"
        )

    if not candidates:
        print("(none) — likely need more history samples. Run pull script hourly for a few days.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
