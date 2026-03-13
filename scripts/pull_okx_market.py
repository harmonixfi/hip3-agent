#!/usr/bin/env python3
"""Pull OKX market data and insert into arbit.db."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
import time
from datetime import datetime, timezone
from okx_public import get_instruments, get_funding, get_mark_prices, get_orderbook, get_spot_instruments, get_spot_tickers
from symbols import normalize_symbol, normalize_instrument_id

DB_PATH = ROOT / "tracking" / "db" / "arbit.db"


def epoch_ms() -> int:
    """Current UTC timestamp in milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def insert_instruments(conn, instruments: list, contract_type: str = "PERP") -> int:
    """Insert instruments into DB."""
    cursor = conn.cursor()
    count = 0
    for inst in instruments:
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("okx", inst["instId"])
            inst_id = normalize_instrument_id("okx", inst["instId"])

            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "okx",
                    canonical_symbol,  # Use canonical symbol
                    inst_id,           # Keep venue-specific inst_id
                    contract_type,
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
            print(f"ERROR inserting instrument {inst.get('instId')}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_funding(conn, funding_data: dict, ts_ms: int) -> int:
    """Insert funding rates into DB."""
    cursor = conn.cursor()
    count = 0
    for inst_id, rate_info in funding_data.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("okx", inst_id)

            # rate_info is a dict: {"fundingRate": float, "nextFundingTime": float}
            funding_rate = float(rate_info.get("fundingRate", 0) or 0)
            next_funding_ts = int(rate_info.get("nextFundingTime", 0) or 0) or None

            cursor.execute(
                """
                INSERT OR REPLACE INTO funding
                (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("okx", canonical_symbol, funding_rate, 8, next_funding_ts, ts_ms),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting funding {inst_id}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_prices(conn, prices: dict, ts_ms: int) -> int:
    """Insert mark/index/last/orderbook mid into DB."""
    cursor = conn.cursor()
    count = 0
    for inst_id, price_info in prices.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("okx", inst_id)

            mark = price_info.get("markPrice", 0.0)
            index = price_info.get("indexPrice", 0.0)
            last = price_info.get("lastPrice", 0.0)
            # Insert mid price from orderbook if available
            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("okx", canonical_symbol, mark, index, last, None, None, (mark + index) / 2.0, ts_ms),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting price {inst_id}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_spot_prices(conn, prices: dict, ts_ms: int) -> int:
    """Insert spot prices (last/bid/ask/mid) into DB."""
    cursor = conn.cursor()
    count = 0
    for inst_id, price_info in prices.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("okx", inst_id)

            last = price_info.get("lastPrice", 0.0)
            bid = price_info.get("bid", 0.0)
            ask = price_info.get("ask", 0.0)
            mid = price_info.get("mid", 0.0)

            # For spot, we use last as mark_price (no mark price for spot)
            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("okx", canonical_symbol, last, None, last, bid, ask, mid, ts_ms),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting spot price {inst_id}: {e}", file=sys.stderr)
    conn.commit()
    return count


def main() -> int:
    print("=== OKX Market Data Pull ===")
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    ts = epoch_ms()

    # 1. Pull PERP instruments (idempotent via OR REPLACE)
    print("Pulling PERP instruments...")
    instruments = get_instruments()
    n_inst = insert_instruments(conn, instruments, contract_type="PERP")
    print(f"Inserted {n_inst} PERP instruments")

    # 2. Pull SPOT instruments
    print("Pulling SPOT instruments...")
    spot_instruments = get_spot_instruments()
    n_spot_inst = insert_instruments(conn, spot_instruments, contract_type="SPOT")
    print(f"Inserted {n_spot_inst} SPOT instruments")

    # 3. Pull funding rates (PERP only)
    # Limit to top 50 instruments for faster hourly cron execution
    print("Pulling funding rates (top 50)...")
    funding_data = get_funding(limit=50)
    n_funding = insert_funding(conn, funding_data, ts)
    print(f"Inserted {n_funding} funding entries")

    # 4. Pull mark/index/last prices (PERP)
    print("Pulling PERP mark prices...")
    prices = get_mark_prices()
    n_prices = insert_prices(conn, prices, ts)
    print(f"Inserted {n_prices} PERP price entries")

    # 5. Pull SPOT tickers (last/bid/ask/mid)
    print("Pulling SPOT tickers...")
    spot_tickers = get_spot_tickers()
    n_spot_prices = insert_spot_prices(conn, spot_tickers, ts)
    print(f"Inserted {n_spot_prices} SPOT price entries")

    # 6. Pull orderbooks for top symbols (limited to 5 for demo)
    print("Pulling orderbooks for top 5 symbols...")
    n_books = 0
    for inst in instruments[:5]:
        inst_id = inst["instId"]
        try:
            # Normalize symbol for orderbook insertion
            canonical_symbol = normalize_symbol("okx", inst_id)

            ob = get_orderbook(inst_id, limit=20)
            mid = ob.get("mid", 0.0)
            if mid > 0:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO prices
                    (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("okx", canonical_symbol, mid, None, None, ob.get("bid"), ob.get("ask"), mid, ts),
                )
                conn.commit()
                n_books += 1
            # Rate limit: sleep 0.1s between orderbooks
            time.sleep(0.1)
        except Exception as e:
            print(f"ERROR orderbook for {inst_id}: {e}", file=sys.stderr)

    conn.close()
    print(f"Total: {n_inst} PERP inst + {n_spot_inst} SPOT inst + {n_funding} funding + {n_prices} PERP prices + {n_spot_prices} SPOT prices + {n_books} orderbooks")
    print("=== Done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
