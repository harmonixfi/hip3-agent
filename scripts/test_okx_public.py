#!/usr/bin/env python3
"""Integration test for OKX public connector using in-memory SQLite DB."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SQL_PATH = ROOT / "tracking" / "sql" / "schema.sql"

sys.path.insert(0, str(ROOT / "tracking" / "connectors"))

from okx_public import get_instruments, get_funding, get_mark_prices


def main() -> int:
    print("=== OKX Connector Integration Test ===")
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
                    "okx",
                    inst["symbol"],
                    inst["instId"],
                    "PERP",
                    inst["tickSize"],
                    inst["ctMult"],
                    inst["ctVal"],
                    inst["ctMult"],  # quote
                    inst["instId"],  # base
                    inst.get("fundingIntervalHours", 8),
                    0,  # created_at not used in test
                ),
            )
            n_inst += 1
        except Exception as e:
            print(f"   ERROR inserting {inst.get('instId')}: {e}", file=sys.stderr)
            return 1

    print(f"   Inserted {n_inst} instruments")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM instruments WHERE venue='okx'").fetchone()[0]
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
    for inst_id, rate in list(funding.items())[:3]:
        try:
            cursor.execute(
                """
                INSERT OR REPLACE INTO funding
                (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("okx", inst_id, float(rate) / 10000.0, 8, None, 0),
            )
            n_fund += 1
        except Exception as e:
            print(f"   ERROR inserting funding {inst_id}: {e}", file=sys.stderr)
            return 1

    print(f"   Inserted {n_fund} funding entries")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM funding WHERE venue='okx'").fetchone()[0]
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
    for inst_id, price_info in list(prices.items())[:3]:
        try:
            mark = price_info.get("markPrice", 0.0)
            idx = price_info.get("indexPrice", 0.0)
            cursor.execute(
                """
                INSERT OR REPLACE INTO prices
                (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("okx", inst_id, mark, idx, None, None, None, None, 0),
            )
            n_price += 1
        except Exception as e:
            pull = f"   ERROR inserting price {inst_id}: {e}"
            print(pull, file=sys.stderr)
            return 1

    print(f"   Inserted {n_price} price entries")

    # Verify insertion
    count = cursor.execute("SELECT COUNT(*) FROM prices WHERE venue='okx'").fetchone()[0]
    if count != n_price:
        print(f"   FAIL: Expected {n_price} prices, found {count}")
        return 1
    print(f"   OK: Found {count} price entries")

    # Test UNIQUE constraint (insert duplicate)
    print("\n[4] Testing UNIQUE constraint (insert duplicate)...")
    try:
        # Try inserting same funding entry again
        inst_id, rate = list(funding.items())[0]
        cursor.execute(
            """
            INSERT INTO funding (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("okx", inst_id, float(rate) / 10000.0, 8, None, 1),
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
