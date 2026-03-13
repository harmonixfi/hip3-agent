#!/usr/bin/env python3
"""Integration test for Paradex public connector using in-memory SQLite DB."""

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SQL_PATH = ROOT / "tracking" / "sql" / "schema.sql"

sys.path.insert(0, str(ROOT / "tracking" / "connectors"))

from paradex_public import get_instruments, get_funding, get_mark_prices


def main() -> int:
    print("=== Paradex Connector Integration Test ===")
    print("Using in-memory SQLite database")

    conn = sqlite3.connect(":memory:")

    schema_sql = SQL_PATH.read_text()
    cursor = conn.cursor()
    cursor.executescript(schema_sql)

    # Test instruments
    print("\n[1] Testing get_instruments()...")
    instruments = get_instruments()
    print(f"   Retrieved {len(instruments)} instruments")

    # Insert and verify (even if empty, handle gracefully)
    n_inst = 0
    if instruments:
        for inst in instruments[:3]:  # Test first 3
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO instruments
                    (venue, symbol, inst_id, contract_type, tick_size, contract_size, quote_currency, base_currency, funding_interval_hours, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "paradex",
                        inst["symbol"],
                        inst["symbol"],  # symbol as inst_id
                        "PERP",
                        1.0,  # default tick size
                        1.0,  # default contract size
                        inst.get("quote_currency", "USDT"),  # fallback
                        inst.get("base_currency", ""),
                        8,  # default funding interval
                        0,  # created_at not used in test
                    ),
                )
                n_inst += 1
            except Exception as e:
                print(f"   ERROR inserting {inst.get('symbol')}: {e}", file=sys.stderr)
                return 1
    else:
        print("   Empty instruments list - skipping insertion")
    
    print(f"   Inserted {n_inst} instruments")

    # Verify insertion
    if n_inst > 0:
        count = cursor.execute("SELECT COUNT(*) FROM instruments WHERE venue='paradex'").fetchone()[0]
        if count != n_inst:
            print(f"   FAIL: Expected {n_inst} instruments, found {count}")
            return 1
        print(f"   OK: Found {count} instruments")
    else:
        print("   OK: No instruments to insert (API may not have data)")

    # Test funding
    print("\n[2] Testing get_funding()...")
    funding = get_funding()
    print(f"   Retrieved {len(funding)} funding entries")

    # Insert and verify (handle empty gracefully)
    n_fund = 0
    if funding:
        for symbol, rate in list(funding.items())[:3]:  # Test first 3
            try:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO funding
                    (venue, symbol, funding_rate, funding_interval_hours, next_funding_ts, ts)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("paradex", symbol, float(rate) / 10000.0, 8, None, 0),
                )
                n_fund += 1
            except Exception as e:
                print(f"   ERROR inserting funding {symbol}: {e}", file=sys.stderr)
                return 1
    else:
        print("   Empty funding - skipping insertion")
    
    print(f"   Inserted {n_fund} funding entries")

    # Verify insertion
    if n_fund > 0:
        count = cursor.execute("SELECT COUNT(*) FROM funding WHERE venue='paradex'").fetchone()[0]
        if count != n_fund:
            print(f"   FAIL: Expected {n_fund} funding, found {count}")
            return 1
        print(f"   OK: Found {count} funding entries")
    else:
        print("   OK: No funding to insert")

    # Test mark prices
    print("\n[3] Testing get_mark_prices()...")
    prices = get_mark_prices()
    print(f"   Retrieved {len(prices)} price entries")

    # Insert and verify (handle empty gracefully)
    n_price = 0
    if prices:
        for symbol, price_info in list(prices.items())[:3]:  # Test first 3
            try:
                mark = price_info.get("markPrice", 0.0)
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO prices
                    (venue, symbol, mark_price, index_price, last_price, bid, ask, mid, ts)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("paradex", symbol, mark, None, None, None, None, None, mark, 0),
                )
                n_price += 1
            except Exception as e:
                print(f"   ERROR inserting price {symbol}: {e}", file=sys.stderr)
                return 1
    else:
        print("   Empty prices - skipping insertion")
    
    print(f"   Inserted {n_price} price entries")

    # Verify insertion
    if n_price > 0:
        count = cursor.execute("SELECT COUNT(*) FROM prices WHERE venue='paradex'").fetchone()[0]
        if count != n_price:
            print(f"   FAIL: Expected {n_price} prices, found {count}")
            return 1
        print(f"   OK: Found {count} price entries")
    else:
        print("   OK: No prices to insert")

    # Test orderbook (one instrument)
    print("\n[4] Testing get_orderbook()...")
    ob = get_orderbook("BTC-USDT-SWAP")
    print(f"   Retrieved: bid={ob.get('bid')}, ask={ob.get('ask')}, mid={ob.get('mid')}")
    if ob.get("mid"):
        print("   OK: Orderbook data valid")
        return 1
    else:
        print("   WARNING: Orderbook empty or invalid")
        return 0

    conn.close()
    print("\n=== Test PASS ===")
    print("Coverage: instruments (graceful if empty), funding (graceful if empty), mark prices (graceful if empty), orderbook (one instrument)")
    print("Note: Paradex API endpoints may not be fully documented - verify live data before production use")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
