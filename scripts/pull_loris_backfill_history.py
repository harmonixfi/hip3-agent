#!/usr/bin/env python3
"""Backfill historical funding rate samples from Loris Tools into the local Harmonix CSV history.

Why:
- Our live collector (`pull_loris_funding.py`) builds history going forward.
- This script backfills past data so we can compute 30D and shorter carry windows immediately.

Data sources:
- Live symbols + OI ranks: https://api.loris.tools/funding
- Historical time series: https://loris.tools/api/funding/historical?symbol=...&start=...&end=...

Output:
- Appends hourly samples to: data/loris_funding_history.csv in this workspace
  columns: timestamp_utc, exchange, symbol, oi_rank, funding_8h_scaled, funding_8h_rate

Notes:
- Loris funding values are scaled by 10,000 (can be floats in historical endpoint).
- Treat timestamps as UTC (historical endpoint returns ISO timestamps without a 'Z').
- This is a *screener*. Verify funding/fees/orderbooks on venue before trading.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "config", "strategy.json")
OUT_PATH = os.path.join(ROOT, "data", "loris_funding_history.csv")

LIVE_URL = "https://api.loris.tools/funding"
HIST_URL = "https://loris.tools/api/funding/historical"
EXCHANGE_ALIASES = {
    "hyperliquid": "hyperliquid",
    "hl": "hyperliquid",
    "tradexyz": "tradexyz",
    "xyz": "tradexyz",
    "tradexyz_perp": "tradexyz",
    "felix": "felix",
    "kinetiq": "kinetiq",
    "hyena": "hyena",
}


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get_json(url: str, params: dict | None = None) -> dict:
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "arbit-tracker/0.1"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def normalize_exchange_name(name: str | None) -> str:
    key = str(name or "").strip().lower()
    return EXCHANGE_ALIASES.get(key, key)


def normalize_target_exchanges(values: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    normalized = {normalize_exchange_name(v) for v in (values or []) if str(v).strip()}
    return {v for v in normalized if v}


def ensure_header(path: str) -> None:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"])


def oi_rank_to_int(x) -> int:
    if x is None:
        return 9999
    s = str(x).strip()
    if not s:
        return 9999
    if s.endswith("+"):
        s = s[:-1]
    try:
        return int(s)
    except ValueError:
        return 9999


def parse_hist_timestamp_utc(ts: str) -> dt.datetime:
    # Loris historical endpoint can return either naive ISO timestamps
    # like "2026-02-01T00:00:00" or UTC timestamps like "...Z".
    ts_norm = ts.strip()
    if ts_norm.endswith("Z"):
        ts_norm = ts_norm[:-1] + "+00:00"
    d = dt.datetime.fromisoformat(ts_norm)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def load_existing_keys(path: str) -> set[tuple[str, str, str]]:
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return set()
    keys: set[tuple[str, str, str]] = set()
    with open(path, "r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            ts = row.get("timestamp_utc")
            ex = row.get("exchange")
            sym = row.get("symbol")
            if ts and ex and sym:
                keys.add((ts, ex, sym))
    return keys


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30, help="Backfill last N days (default: 30)")
    ap.add_argument("--start", type=str, default=None, help="Start date (YYYY-MM-DD). Overrides --days")
    ap.add_argument("--end", type=str, default=None, help="End date (YYYY-MM-DD). Default: now UTC")
    ap.add_argument("--symbols", type=str, default=None, help="Comma-separated symbols to backfill (e.g. BTC,ETH)")
    ap.add_argument("--max-symbols", type=int, default=None, help="Limit number of symbols (for testing)")
    ap.add_argument(
        "--sleep",
        type=float,
        default=None,
        help="Fixed sleep seconds between symbols. Overrides jitter range for backward compatibility.",
    )
    ap.add_argument(
        "--sleep-min",
        type=float,
        default=0.2,
        help="Minimum jitter sleep between symbols in seconds (default: 0.2)",
    )
    ap.add_argument(
        "--sleep-max",
        type=float,
        default=0.5,
        help="Maximum jitter sleep between symbols in seconds (default: 0.5)",
    )
    ap.add_argument(
        "--resolution",
        choices=["raw", "hourly"],
        default="hourly",
        help="Write raw samples or resample to hourly (default: hourly)",
    )
    args = ap.parse_args()

    if args.sleep is not None and args.sleep < 0:
        ap.error("--sleep must be >= 0")
    if args.sleep_min < 0 or args.sleep_max < 0:
        ap.error("--sleep-min/--sleep-max must be >= 0")
    if args.sleep is None and args.sleep_min > args.sleep_max:
        ap.error("--sleep-min must be <= --sleep-max")

    cfg = load_cfg()
    target_exchanges = normalize_target_exchanges(cfg.get("target_exchanges", []))
    oi_rank_max = int(cfg.get("oi_rank_max", 200))

    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    if args.end:
        end = dt.datetime.fromisoformat(args.end).replace(tzinfo=dt.timezone.utc)
    else:
        end = now

    if args.start:
        start = dt.datetime.fromisoformat(args.start).replace(tzinfo=dt.timezone.utc)
    else:
        start = end - dt.timedelta(days=int(args.days))

    # Loris expects Z timestamps
    start_q = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_q = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Pull live map for symbols + OI ranks
    live = http_get_json(LIVE_URL)
    oi_map = live.get("oi_rankings", {}) or {}

    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    else:
        # Use the union of currently active symbols, then filter by OI rank
        symbols = list((live.get("symbols") or []))
        symbols = [
            s
            for s in symbols
            if (rank := oi_rank_to_int(oi_map.get(s))) == 9999 or rank <= oi_rank_max
        ]

    symbols.sort()
    if args.max_symbols is not None:
        symbols = symbols[: int(args.max_symbols)]

    ensure_header(OUT_PATH)
    existing = load_existing_keys(OUT_PATH)

    appended = 0
    dupes = 0
    symbols_ok = 0
    symbols_fail = 0

    sleep_mode = (
        f"fixed:{args.sleep:.3f}s"
        if args.sleep is not None
        else f"jitter:{args.sleep_min:.3f}-{args.sleep_max:.3f}s"
    )
    print(
        f"backfill_range_utc={start.date()}..{end.date()} symbols={len(symbols)} "
        f"target_exchanges={sorted(target_exchanges)} sleep_mode={sleep_mode}"
    )

    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        for i, sym in enumerate(symbols, 1):
            try:
                payload = http_get_json(HIST_URL, {"symbol": sym, "start": start_q, "end": end_q})
                series = payload.get("series", {}) or {}

                sym_rank = oi_rank_to_int(oi_map.get(sym))

                wrote_any = False
                for ex, points in series.items():
                    ex_norm = normalize_exchange_name(ex)
                    if target_exchanges and ex_norm not in target_exchanges:
                        continue
                    if not isinstance(points, list):
                        continue

                    if args.resolution == "raw":
                        for p in points:
                            ts_raw = p.get("t")
                            y = p.get("y")
                            if not ts_raw or y is None:
                                continue
                            ts = parse_hist_timestamp_utc(ts_raw).isoformat()
                            key = (ts, ex_norm, sym)
                            if key in existing:
                                dupes += 1
                                continue
                            try:
                                scaled = float(y)
                            except Exception:
                                continue
                            rate = scaled / 10000.0
                            w.writerow([ts, ex_norm, sym, sym_rank, scaled, rate])
                            existing.add(key)
                            appended += 1
                            wrote_any = True
                    else:
                        # Resample to hourly so weighting matches our hourly live collector.
                        buckets: dict[str, list[float]] = {}
                        for p in points:
                            ts_raw = p.get("t")
                            y = p.get("y")
                            if not ts_raw or y is None:
                                continue
                            d = parse_hist_timestamp_utc(ts_raw)
                            d_hour = d.replace(minute=0, second=0, microsecond=0)
                            ts_hour = d_hour.isoformat()
                            try:
                                scaled = float(y)
                            except Exception:
                                continue
                            buckets.setdefault(ts_hour, []).append(scaled)

                        for ts_hour, vals in buckets.items():
                            if not vals:
                                continue
                            scaled_avg = sum(vals) / len(vals)
                            key = (ts_hour, ex_norm, sym)
                            if key in existing:
                                dupes += 1
                                continue
                            rate = scaled_avg / 10000.0
                            w.writerow([ts_hour, ex_norm, sym, sym_rank, scaled_avg, rate])
                            existing.add(key)
                            appended += 1
                            wrote_any = True

                symbols_ok += 1
                if i % 10 == 0:
                    print(f"progress {i}/{len(symbols)} appended={appended} dupes={dupes}")
            except Exception as e:
                symbols_fail += 1
                print(f"ERROR symbol={sym} err={e}", file=sys.stderr)

            # Sleep between symbols to avoid rate limiting
            if args.sleep is not None:
                sleep_s = float(args.sleep)
            else:
                sleep_s = random.uniform(float(args.sleep_min), float(args.sleep_max))
            time.sleep(sleep_s)

    print(f"done symbols_ok={symbols_ok} symbols_fail={symbols_fail} appended_rows={appended} dupes_skipped={dupes} out={OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
