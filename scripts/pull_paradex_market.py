#!/usr/bin/env python3
"""Pull Paradex market data and insert into arbit.db."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
import time
from datetime import datetime, timezone
from paradex_public import get_instruments, get_funding, get_mark_prices, get_orderbook
from symbols import normalize_symbol, normalize_instrument_id

DB_PATH = ROOT / "tracking" / "db" / "arbit.db"


def epoch_ms() -> int:
    """Current UTC timestamp in milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def insert_instruments(conn, instruments: list) -> int:
    """Insert instruments into DB."""
    cursor = conn.cursor()
    count = 0
    for inst in instruments:
        try:
            # Normalize symbol to canonical form (base asset only)
            raw_symbol = inst["symbol"]
            canonical_symbol = normalize_symbol("paradex", raw_symbol)
            inst_id = normalize_instrument_id("paradex", raw_symbol)

            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (id, venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    None,  # id - auto-increment
                    "paradex",
                    canonical_symbol,  # Use canonical symbol
                    inst_id,            # Keep venue-specific inst_id
                    "PERP",
                    float(inst.get("price_tick_size", 1.0)),
                    float(inst.get("order_size_increment", 1.0)),
                    inst.get("quote_currency", "USDT"),
                    inst.get("base_currency", ""),
                    int(inst.get("funding_period_hours", 8)),
                    epoch_ms(),
                ),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting instrument {inst.get('symbol')}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_funding(conn, funding_data: dict, ts_ms: int) -> int:
    """
    Insert funding rates into DB.

    Args:
        conn: Database connection
        funding_data: Dict mapping symbol -> {
            'funding_rate': float (per-interval rate, usually 8h),
            'funding_interval_hours': int,
            'next_funding_ts': int or None,
        }
        ts_ms: Current timestamp in milliseconds
    """
    cursor = conn.cursor()
    count = 0
    for symbol, fund_info in funding_data.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("paradex", symbol)

            rate = fund_info.get('funding_rate', 0.0)
            interval = fund_info.get('funding_interval_hours', 8)
            next_ts = fund_info.get('next_funding_ts')

            # funding_rate is already a decimal per-interval, no conversion needed
            cursor.execute(
                """
                INSERT OR REPLACE INTO funding
                (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("paradex", canonical_symbol, float(rate), int(interval), next_ts, ts_ms),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting funding {symbol}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_prices(conn, prices: dict, ts_ms: int) -> int:
    """Insert prices (mark/index/last + bid/ask/mid if available) into DB."""
    cursor = conn.cursor()
    count = 0
    for symbol, price_info in prices.items():
        try:
            canonical_symbol = normalize_symbol("paradex", symbol)

            mark = price_info.get("markPrice")
            indexp = price_info.get("indexPrice")
            last = price_info.get("lastPrice")
            bid = price_info.get("bid")
            ask = price_info.get("ask")
            mid = price_info.get("mid")

            # Fallbacks
            if mid is None:
                if bid and ask:
                    mid = (bid + ask) / 2.0
                elif mark is not None:
                    mid = mark
            if mark is None:
                mark = mid
            if indexp is None:
                indexp = mark
            if last is None:
                last = mark

            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("paradex", canonical_symbol, mark, indexp, last, bid, ask, mid, ts_ms),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting price {symbol}: {e}", file=sys.stderr)
    conn.commit()
    return count


def main() -> int:
    print("=== Paradex Market Data Pull ===")
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    ts = epoch_ms()

    # 1. Pull instruments (idempotent via OR REPLACE)
    print("Pulling instruments...")
    instruments = get_instruments()
    n_inst = insert_instruments(conn, instruments)
    print(f"Inserted {n_inst} instruments")

    # 2. Pull funding rates
    print("Pulling funding rates...")
    funding_data = get_funding()
    n_funding = insert_funding(conn, funding_data, ts)
    print(f"Inserted {n_funding} funding entries")

    # 3. Pull price proxies via WS orderbook snapshots
    # NOTE: REST /markets is static (no last/mark/index). We derive mid from orderbook.
    print("Pulling prices via WS orderbook snapshots...")
    # ensure BERA is included in the sample
    instruments_sorted = list(instruments)
    bera = [x for x in instruments_sorted if x.get('symbol') == 'BERA-USD-PERP']
    rest = [x for x in instruments_sorted if x.get('symbol') != 'BERA-USD-PERP']
    instruments_sample = bera + rest

    prices = get_mark_prices(limit=12)  # sample a small set to keep runtime bounded
    # Also force-fetch BERA orderbook if missing
    if 'BERA-USD-PERP' not in prices:
        ob = get_orderbook('BERA-USD-PERP')
        mid = ob.get('mid', 0.0)
        if mid and mid > 0:
            prices['BERA-USD-PERP'] = {
                'markPrice': mid,
                'indexPrice': mid,
                'lastPrice': mid,
                'bid': ob.get('bid'),
                'ask': ob.get('ask'),
                'mid': mid,
            }

    n_prices = insert_prices(conn, prices, ts)
    print(f"Inserted {n_prices} price entries")

    conn.close()
    print(f"Total: {n_inst} inst + {n_funding} funding + {n_prices} prices")
    print("=== Done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
