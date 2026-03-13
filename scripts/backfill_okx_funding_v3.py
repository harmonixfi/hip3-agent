#!/usr/bin/env python3
"""Backfill OKX historical funding rates from Loris into DB v3.

Why:
- OKX public API doesn't provide historical funding rates.
- Loris Tools has historical funding data we can backfill.
- This gives us history to compute 14D avg APR and stability metrics.

Data source:
- Loris API: https://loris.tools/api/funding/historical?symbol=...&start=...&end=...
- We only fetch OKX exchange data

Output:
- Writes to funding_v3 table (venue='okx')
- Uses INSERT OR IGNORE to avoid duplicates

Usage:
    python3 scripts/backfill_okx_funding_v3.py --days 14
    python3 scripts/backfill_okx_funding_v3.py --start 2026-01-25 --end 2026-02-08
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"

LORIS_HIST_URL = "https://loris.tools/api/funding/historical"
LORIS_LIVE_URL = "https://api.loris.tools/funding"


def http_get_json(url: str, params: Optional[Dict[str, str]] = None) -> dict:
    """Make HTTP GET request and return JSON."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "arbit-tracker/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def loris_symbol_to_okx_inst_id(symbol: str) -> str:
    """Convert Loris symbol to OKX instId format.

    Loris uses symbol names like 'BTC-USDT'.
    OKX perps use instId like 'BTC-USDT-SWAP'.

    Note: Some Loris symbols might not map 1:1 to OKX instIds.
    """
    return f"{symbol}-SWAP" if "-" in symbol else symbol


def parse_loris_timestamp(ts: str) -> datetime:
    """Parse Loris timestamp to UTC datetime."""
    # Loris returns "2026-02-01T00:00:00" (no timezone)
    d = datetime.fromisoformat(ts)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def get_okx_inst_ids_from_db(con: sqlite3.Connection) -> Dict[str, str]:
    """Get existing OKX perp inst_ids and their base symbols from DB.

    Returns mapping: base -> inst_id
    Prefers USDT over USD/USD_UM (higher liquidity).
    """
    sql = """
    SELECT inst_id, base, quote FROM instruments_v3
    WHERE venue = 'okx' AND contract_type = 'PERP'
    ORDER BY
      CASE quote
        WHEN 'USDT' THEN 1
        WHEN 'USD' THEN 2
        WHEN 'USD_UM' THEN 3
        ELSE 4
      END
    """
    cur = con.execute(sql)
    result = {}
    for row in cur.fetchall():
        inst_id, base, quote = row
        # Only take the first (preferred) inst_id per base
        if base not in result:
            result[base] = inst_id
    return result


def insert_funding_v3(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
    ts_ms: int,
    funding_rate: float,
    source: str,
) -> None:
    """Insert a funding rate into funding_v3 table."""
    sql = """
    INSERT OR IGNORE INTO funding_v3(
      venue, inst_id, ts, funding_rate, interval_hours,
      next_funding_ts, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    con.execute(
        sql,
        (
            venue,
            inst_id,
            ts_ms,
            funding_rate,
            8.0,  # OKX funding interval
            None,  # next_funding_ts not available from Loris historical
            source,
            json.dumps({}, separators=(",", ":")),
        ),
    )


def backfill(
    con: sqlite3.Connection,
    start: datetime,
    end: datetime,
    symbols: Optional[List[str]] = None,
    max_symbols: Optional[int] = None,
    sleep: float = 0.2,
) -> Dict[str, int]:
    """Backfill funding rates from Loris.

    Args:
        con: Database connection
        start: Start datetime (UTC)
        end: End datetime (UTC)
        symbols: Optional list of symbols to backfill (e.g., ['BTC', 'ETH'])
        max_symbols: Limit number of symbols (for testing)
        sleep: Sleep between requests (rate limiting)

    Returns:
        Dict with stats
    """
    # Get OKX inst_ids mapping
    okx_inst_map = get_okx_inst_ids_from_db(con)

    # Get live symbols from Loris
    live = http_get_json(LORIS_LIVE_URL)
    loris_symbols = list(live.get("symbols") or [])

    # Filter to symbols that exist in OKX DB
    symbols_to_fetch = []
    for sym in loris_symbols:
        if symbols and sym not in symbols:
            continue
        if sym not in okx_inst_map:
            # Skip if we don't have this instrument in OKX DB
            continue
        symbols_to_fetch.append(sym)

    if max_symbols:
        symbols_to_fetch = symbols_to_fetch[:max_symbols]

    symbols_to_fetch.sort()

    print(f"Fetching {len(symbols_to_fetch)} symbols from {start.date()} to {end.date()}")

    # Prepare query params
    start_q = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    end_q = end.strftime("%Y-%m-%dT%H:%M:%SZ")

    stats = {
        "symbols_processed": 0,
        "symbols_failed": 0,
        "rows_inserted": 0,
        "rows_skipped": 0,
    }

    for i, sym in enumerate(symbols_to_fetch, 1):
        try:
            okx_inst_id = okx_inst_map[sym]

            # Fetch historical data from Loris
            payload = http_get_json(
                LORIS_HIST_URL,
                {"symbol": sym, "start": start_q, "end": end_q},
            )

            series = payload.get("series", {}) or {}
            # Loris uses lowercase exchange names
            okx_points = series.get("okx", [])

            if not okx_points:
                print(f"  [{i}/{len(symbols_to_fetch)}] {sym}: no OKX data")
                stats["symbols_processed"] += 1
                time.sleep(sleep)
                continue

            # Insert hourly samples
            inserted = 0
            skipped = 0

            for point in okx_points:
                ts_raw = point.get("t")
                y = point.get("y")

                if not ts_raw or y is None:
                    continue

                # Parse timestamp and convert to ms
                dt_utc = parse_loris_timestamp(ts_raw)
                ts_ms = int(dt_utc.timestamp() * 1000)

                # Loris funding is scaled by 10,000
                funding_rate = float(y) / 10000.0

                try:
                    insert_funding_v3(
                        con,
                        venue="okx",
                        inst_id=okx_inst_id,
                        ts_ms=ts_ms,
                        funding_rate=funding_rate,
                        source="loris:historical_backfill",
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # Duplicate (INSERT OR IGNORE)
                    skipped += 1

            stats["symbols_processed"] += 1
            stats["rows_inserted"] += inserted
            stats["rows_skipped"] += skipped

            print(
                f"  [{i}/{len(symbols_to_fetch)}] {sym}: "
                f"inserted={inserted} skipped={skipped}"
            )

            time.sleep(sleep)

        except Exception as e:
            stats["symbols_failed"] += 1
            print(f"  [{i}/{len(symbols_to_fetch)}] {sym}: ERROR - {e}", file=sys.stderr)

    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill OKX funding from Loris to DB v3")
    ap.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help="Path to v3 database",
    )
    ap.add_argument(
        "--days",
        type=int,
        default=14,
        help="Backfill last N days (default: 14)",
    )
    ap.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD). Overrides --days",
    )
    ap.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD). Default: now UTC",
    )
    ap.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Comma-separated symbols to backfill (e.g. BTC,ETH)",
    )
    ap.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help="Limit number of symbols (for testing)",
    )
    ap.add_argument(
        "--sleep",
        type=float,
        default=0.2,
        help="Sleep seconds between requests (default: 0.2)",
    )

    args = ap.parse_args()

    # Parse date range
    now = datetime.now(timezone.utc).replace(microsecond=0)
    if args.end:
        end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    else:
        end = now

    if args.start:
        start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    else:
        start = end - timedelta(days=int(args.days))

    # Parse symbols
    symbols = None
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    # Connect to DB
    if not args.db.exists():
        print(f"ERROR: Database not found: {args.db}", file=sys.stderr)
        return 1

    con = sqlite3.connect(str(args.db), timeout=60)
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 60000")
    try:
        # Run backfill
        stats = backfill(
            con,
            start=start,
            end=end,
            symbols=symbols,
            max_symbols=args.max_symbols,
            sleep=args.sleep,
        )
        con.commit()

        # Print summary
        print("\n=== Backfill Summary ===")
        print(f"Symbols processed: {stats['symbols_processed']}")
        print(f"Symbols failed:    {stats['symbols_failed']}")
        print(f"Rows inserted:     {stats['rows_inserted']}")
        print(f"Rows skipped:      {stats['rows_skipped']}")
        print(f"Date range:        {start.date()} -> {end.date()}")

        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
