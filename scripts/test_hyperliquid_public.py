#!/usr/bin/env python3
"""Integration test for Hyperliquid public connector using in-memory SQLite DB."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SQL_PATH = ROOT / "tracking" / "sql" / "schema.sql"

sys.path.insert(0, str(ROOT / "tracking" / "connectors"))

from hyperliquid_public import get_instruments, get_funding, get_mark_prices


def main() -> int:
    print("=== Hyperliquid Connector Integration Test ===")
    print("Using in-memory SQLite database")

    # Use :memory: for test (no file cleanup needed)
    conn = sqlite3.connect(":memory:")

    # Initialize schema
    schema_sql = SQL_PATH.read_text()
    cursor = conn.cursor()
    cursor.executescript(schema_sql)

    # Test instruments
    print("\n[1] Testing get_instruments()...")
    instruments = get_instruments()
    print(f"   Retrieved {len(instruments)} instruments")

    # Insert and verify
    n_inst = 0
    for inst in instruments[:3]:  # Test first 3
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO instruments
                (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "hyperliquid",
                    inst["symbol"],
                    inst["symbol"],  # symbol as inst_id
                    "PERP",
                    1.0,  # default tick size
                    inst.get("contractSize", 1.0),  # if available
                    inst["quote"],
                    inst["base"],
                    1,  # funding interval = 1h
                    0,  # created_at not used in test
                ),
            )
            n_inst += 1
        except Exception as e:
            print(f"   ERROR inserting instrument {inst.get('name')}: {e}", file=sys.stderr)
            return 1

    print(f"   Inserted {n_inst} instruments")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM instruments WHERE venue='hyperliquid'").fetchone()[0]
    if count != n_inst:
        print(f"   FAIL: Expected {n_inst} instruments, found {count}")
        return 1
    print(f"   OK: Found {count} instruments")

    # Test funding
    print("\n[2] Testing get_funding()...")
    funding = get_funding()
    print(f"   Retrieved {len(funding)} funding entries")

    # Insert and verify
    n_fund = 0
    for symbol, rate in list(funding.items())[:3]:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO funding
                (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("hyperliquid", symbol, float(rate) / 10000.0, 1, None, 0),
            )
            n_fund += 1
        except Exception as e:
            print(f"   ERROR inserting funding {symbol}: {e}", file=sys.stderr)
            return 1

    print(f"   Inserted {n_fund} funding entries")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM funding WHERE venue='hyperliquid'").fetchone()[0]
    if count != n_fund:
        print(f"   FAIL: Expected {n_fund} funding, found {count}")
        return 1
    print(f"   OK: Found {count} funding entries")

    # Test mark prices
    print("\n[3] Testing get_mark_prices()...")
    prices = get_mark_prices()
    print(f"   Retrieved {len(prices)} price entries")

    # Insert and verify
    n_price = 0
    for symbol, price_info in list(prices.items())[:3]:
        try:
            mid = price_info.get("midPrice", 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("hyperliquid", symbol, mid, None, None, None, None, mid, 0),
            )
            n_price += 1
        except Exception as e:
            pull = f"   ERROR inserting price {symbol}: {e}"
            print(pull, file=sys.stderr)
            return 1

    print(f"   Inserted {n_price} price entries")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM prices WHERE venue='hyperliquid'").fetchone()[0]
    if count != n_price:
        print(f"   FAIL: Expected {n_price} prices, found {count}")
        return 1
    print(f"   OK: Found {count} price entries")

    # Test UNIQUE constraint (insert duplicate)
    print("\n[4] Testing UNIQUE constraint (insert duplicate)...")
    try:
        # Try inserting same funding entry again
        symbol, rate = list(funding.items())[0]
        cursor.execute(
            """
            INSERT INTO funding (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("hyperliquid", symbol, float(rate) / 10000.0, 1, None, 1),
        )
        print("   FAIL: UNIQUE constraint should prevent duplicate insertion")
        return 1
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e):
            print("   OK: UNIQUE constraint triggered correctly")
        else:
            print(f"   ERROR: Unexpected integrity error: {e}")
            return 1

    conn.close()
    print("\n=== Test PASS ===")
    print("Coverage: instruments, funding, mark prices, UNIQUE constraint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
