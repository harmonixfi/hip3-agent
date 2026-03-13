#!/usr/bin/env python3
"""Pull Lighter market data and insert into arbit.db."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
import time
from datetime import datetime, timezone
from lighter_public import get_instruments, get_funding, get_mark_prices, get_orderbook
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
            canonical_symbol = normalize_symbol("lighter", raw_symbol)
            inst_id = inst["inst_id"]  # Keep the market_id as inst_id

            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "lighter",
                    canonical_symbol,  # Use canonical symbol
                    inst_id,            # Keep venue-specific inst_id (market_id)
                    "PERP",
                    inst["tickSize"],
                    inst["contractSize"],
                    inst["quote"],
                    inst["base"],
                    inst["fundingIntervalHours"],
                    epoch_ms(),
                ),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting instrument {inst.get('symbol')}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_funding(conn, funding_data: dict, ts_ms: int) -> int:
    """Insert funding rates into DB.

    Note: Lighter's REST API doesn't provide funding rates directly.
    This function is a no-op for now.
    """
    # Lighter REST API doesn't provide funding rates
    # Funding is available via WebSocket market_stats channel
    return 0


def insert_prices(conn, prices: dict, ts_ms: int) -> int:
    """Insert mark/index/last prices into DB."""
    cursor = conn.cursor()
    count = 0
    for symbol, price_info in prices.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("lighter", symbol)

            mark = price_info.get("markPrice", 0.0)
            index = price_info.get("indexPrice", 0.0)
            last = price_info.get("lastPrice", 0.0)

            # Only insert if we have valid prices (> 0)
            if mark > 0:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO prices
                    (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("lighter", canonical_symbol, mark, index, last, None, None, (mark + index) / 2.0 if mark > 0 and index > 0 else mark, ts_ms),
                )
                count += 1
        except Exception as e:
            print(f"ERROR inserting price {symbol}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_orderbooks(conn, instruments: list, limit: int = 10, ts_ms: int = None) -> int:
    """Insert orderbook data for top instruments.

    Args:
        conn: SQLite connection
        instruments: List of instrument dicts
        limit: Number of instruments to fetch orderbooks for
        ts_ms: Timestamp (epoch ms)

    Returns:
        Number of orderbooks inserted
    """
    if ts_ms is None:
        ts_ms = epoch_ms()

    cursor = conn.cursor()
    count = 0

    for inst in instruments[:limit]:
        symbol = inst["symbol"]
        try:
            # Normalize symbol for orderbook insertion
            canonical_symbol = normalize_symbol("lighter", symbol)

            ob = get_orderbook(symbol, limit=20)
            bid = ob.get("bid", 0.0)
            ask = ob.get("ask", 0.0)
            mid = ob.get("mid", 0.0)

            if mid > 0:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO prices
                    (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("lighter", canonical_symbol, mid, None, None, bid, ask, mid, ts_ms),
                )
                conn.commit()
                count += 1

            # Rate limit: sleep 0.1s between orderbooks
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR orderbook for {symbol}: {e}", file=sys.stderr)

    return count


def main() -> int:
    print("=== Lighter Market Data Pull ===")
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    ts = epoch_ms()

    # 1. Pull instruments (idempotent via OR REPLACE)
    print("Pulling instruments...")
    instruments = get_instruments()
    n_inst = insert_instruments(conn, instruments)
    print(f"Inserted {n_inst} instruments")

    # 2. Pull funding rates (not available via REST)
    print("Pulling funding rates...")
    n_funding = insert_funding(conn, get_funding(), ts)
    print(f"Inserted {n_funding} funding entries (REST API doesn't provide funding)")

    # 3. Pull mark/index/last prices (limited to top 20 to avoid excessive API calls)
    print("Pulling mark prices (top 20 instruments)...")
    prices = get_mark_prices(limit=20)
    n_prices = insert_prices(conn, prices, ts)
    print(f"Inserted {n_prices} price entries")

    # 4. Pull orderbooks for top symbols
    print("Pulling orderbooks for top 10 symbols...")
    n_books = insert_orderbooks(conn, instruments, limit=10, ts_ms=ts)
    print(f"Inserted {n_books} orderbook entries")

    conn.close()
    print(f"Total: {n_inst} inst + {n_funding} funding + {n_prices} prices + {n_books} orderbooks")
    print("=== Done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
