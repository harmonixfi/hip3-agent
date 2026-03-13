#!/usr/bin/env python3
"""Pull Hyperliquid market data and insert into arbit.db."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
import time
from datetime import datetime, timezone
from hyperliquid_public import get_instruments, get_funding, get_mark_prices, get_orderbook
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
            canonical_symbol = normalize_symbol("hyperliquid", raw_symbol)
            inst_id = normalize_instrument_id("hyperliquid", raw_symbol)

            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "hyperliquid",
                    canonical_symbol,  # Use canonical symbol
                    inst_id,            # Keep venue-specific inst_id
                    "PERP",
                    1.0,  # default tick size
                    1.0,  # Hyperliquid contract size is 1
                    inst.get("quote", "USD"),
                    inst.get("base", inst.get("symbol")),
                    1,  # funding interval = 1h
                    epoch_ms(),
                ),
            )
            count += 1
        except Exception as e:
            print(f"ERROR inserting instrument {inst.get('name')}: {e}", file=sys.stderr)
    conn.commit()
    return count


def insert_funding(conn, funding_data: dict, ts_ms: int) -> int:
    """Insert funding rates into DB."""
    cursor = conn.cursor()
    count = 0
    skipped = 0
    for symbol, rate in funding_data.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("hyperliquid", symbol)

            cursor.execute(
                """
                INSERT OR REPLACE INTO funding
                (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("hyperliquid", canonical_symbol, float(rate) / 10000.0, 1, None, ts_ms),
            )
            count += 1
        except ValueError as e:
            # Skip symbols that don't match expected format (e.g., prediction markets)
            skipped += 1
        except Exception as e:
            print(f"ERROR inserting funding {symbol}: {e}", file=sys.stderr)
    conn.commit()
    if skipped > 0:
        print(f"  (skipped {skipped} invalid symbols)")
    return count


def insert_prices(conn, prices: dict, ts_ms: int) -> int:
    """Insert mark prices into DB."""
    cursor = conn.cursor()
    count = 0
    skipped = 0
    for symbol, price_info in prices.items():
        try:
            # Normalize symbol to canonical form (base asset only)
            canonical_symbol = normalize_symbol("hyperliquid", symbol)

            mid = price_info.get("midPrice", 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("hyperliquid", canonical_symbol, mid, None, None, None, None, mid, ts_ms),
            )
            count += 1
        except ValueError as e:
            # Skip symbols that don't match expected format (e.g., prediction markets)
            skipped += 1
        except Exception as e:
            print(f"ERROR inserting price {symbol}: {e}", file=sys.stderr)
    conn.commit()
    if skipped > 0:
        print(f"  (skipped {skipped} invalid symbols)")
    return count


def main() -> int:
    print("=== Hyperliquid Market Data Pull ===")
    print(f"Database: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)

    ts = epoch_ms()

    # 1. Pull instruments
    print("Pulling instruments...")
    instruments = get_instruments()
    n_inst = insert_instruments(conn, instruments)
    print(f"Inserted {n_inst} instruments")

    # 2. Pull funding rates
    print("Pulling funding rates...")
    funding_data = get_funding()
    n_funding = insert_funding(conn, funding_data, ts)
    print(f"Inserted {n_funding} funding entries")

    # 3. Pull mark prices
    print("Pulling mark prices...")
    prices = get_mark_prices()
    n_prices = insert_prices(conn, prices, ts)
    print(f"Inserted {n_prices} price entries")

    # 4. Pull orderbooks for top 5 symbols (disabled - endpoint not yet implemented)
    # TODO: Find correct Hyperliquid orderbook endpoint
    print("Skipping orderbooks (endpoint TBD)...")
    n_books = 0
    # for inst in instruments[:5]:
    #     symbol = inst["symbol"]
    #     try:
    #         ob = get_orderbook(symbol, limit=20)
    #         mid = ob.get("mid", 0.0)
    #         if mid > 0:
    #             cursor = conn.cursor()
    #             cursor.execute(
    #                 """
    #                 INSERT OR REPLACE INTO prices
    #                 (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
    #                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    #                 """,
    #                 ("hyperliquid", symbol, mid, None, None, ob.get("bid"), ob.get("ask"), mid, ts),
    #             )
    #             conn.commit()
    #             n_books += 1
    #         # Rate limit: sleep 0.2s between orderbooks
    #         time.sleep(0.2)
    #     except Exception as e:
    #         print(f"ERROR orderbook for {symbol}: {e}", file=sys.stderr)

    conn.close()
    print(f"Total: {n_inst} inst + {n_funding} funding + {n_prices} prices + {n_books} orderbooks")
    print("=== Done ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
