#!/usr/bin/env python3
"""Verify v2 schema migration.

Key verification points:
1. OKX has both BTC-USDT (SPOT) and BTC-USDT-SWAP (PERP) as distinct instruments_v2 rows
2. Latest prices_v2 rows exist for each instrument
3. symbol_key is correctly populated for lookups
"""

import sqlite3
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit.db"


def main():
    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    print(f"Verifying v2 migration at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if v2 tables exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '%_v2'
        ORDER BY name
    """)
    v2_tables = [row[0] for row in cursor.fetchall()]

    if not v2_tables:
        print("ERROR: No v2 tables found. Run migrate_db_v2.py first.")
        return

    print(f"\n✓ Found v2 tables: {v2_tables}")

    # Verification 1: OKX BTC instruments (SPOT vs PERP)
    print("\n=== Verification 1: OKX BTC Instruments ===")
    print("Checking that OKX has distinct rows for BTC-USDT (SPOT) and BTC-USDT-SWAP (PERP)")

    cursor.execute("""
        SELECT venue, inst_id, base, quote, contract_type, symbol_base, symbol_key
        FROM instruments_v2
        WHERE venue = 'okx' AND (inst_id LIKE 'BTC%' OR symbol_base = 'BTC')
        ORDER BY contract_type, inst_id
    """)

    btc_instruments = cursor.fetchall()
    print(f"\nFound {len(btc_instruments)} OKX BTC instruments:\n")

    for inst in btc_instruments:
        print(f"  inst_id: {inst['inst_id']:20} "
              f"type: {inst['contract_type']:5} "
              f"base: {inst['base']:4} "
              f"quote: {inst['quote'] or 'N/A':4} "
              f"symbol_key: {inst['symbol_key']}")

    print("\n--- Key Design Note ---")
    print("SPOT and PERP can share the same symbol_key (e.g., BTC:USDT)")
    print("They are distinguished by their inst_id and contract_type columns")

    # Check specifically for SPOT vs PERP distinction
    btc_usdt_spot = [i for i in btc_instruments if i['inst_id'] == 'BTC-USDT']
    btc_usdt_perp = [i for i in btc_instruments if i['inst_id'] in ['BTC-USDT-SWAP', 'BTC-USDT_UM-SWAP']]

    print("\n--- SPOT vs PERP Distinction ---")
    if btc_usdt_spot:
        print(f"✓ BTC-USDT SPOT found: {btc_usdt_spot[0]['symbol_key']}")
    else:
        print("✗ BTC-USDT SPOT NOT found")

    if btc_usdt_perp:
        print(f"✓ BTC-USDT-SWAP PERP found: {btc_usdt_perp[0]['symbol_key']}")
    else:
        print("✗ BTC-USDT-SWAP PERP NOT found")

    if btc_usdt_spot and btc_usdt_perp:
        print("✓ OKX has BOTH BTC-USDT SPOT and BTC-USDT-SWAP PERP as distinct rows!")
    else:
        print("✗ FAILED: Missing expected BTC instruments")

    # Verification 2: Latest prices exist for BTC instruments
    print("\n=== Verification 2: Latest Prices for BTC Instruments ===")

    for inst in btc_instruments:
        inst_id = inst['inst_id']
        venue = inst['venue']
        symbol_key = inst['symbol_key']

        # Get latest price for this instrument
        cursor.execute("""
            SELECT bid, ask, mid, mark_price, last_price, ts
            FROM prices_v2
            WHERE venue = ? AND inst_id = ?
            ORDER BY ts DESC
            LIMIT 1
        """, (venue, inst_id))

        price = cursor.fetchone()

        if price:
            ts_readable = datetime.fromtimestamp(price['ts'] / 1000).strftime('%Y-%m-%d %H:%M:%S')
            print(f"\n{inst_id} ({symbol_key}):")
            print(f"  Latest ts: {ts_readable}")
            print(f"  Bid: {price['bid'] or 'N/A':12}  Ask: {price['ask'] or 'N/A':12}  Mid: {price['mid'] or 'N/A':12}")
            print(f"  Mark: {price['mark_price'] or 'N/A':12}  Last: {price['last_price'] or 'N/A':12}")
            print(f"  ✓ Prices found")
        else:
            print(f"\n{inst_id} ({symbol_key}):")
            print(f"  ✗ No prices found")

    # Verification 3: Check for other venues with potential SPOT/PERP overlap
    print("\n=== Verification 3: Check for SPOT/PERP Overlap Across Venues ===")

    cursor.execute("""
        SELECT venue, base, COUNT(*) as cnt,
               GROUP_CONCAT(DISTINCT contract_type) as types
        FROM instruments_v2
        WHERE contract_type IN ('SPOT', 'PERP')
        GROUP BY venue, base
        HAVING COUNT(DISTINCT contract_type) > 1
        ORDER BY venue, base
        LIMIT 10
    """)

    overlaps = cursor.fetchall()

    if overlaps:
        print(f"Found {len(overlaps)} assets with both SPOT and PERP on same venue:\n")
        for overlap in overlaps:
            print(f"  {overlap['venue']:12} {overlap['base']:8} types: {overlap['types']:10} count: {overlap['cnt']}")
    else:
        print("No assets found with both SPOT and PERP on the same venue")
        print("  (This is expected for most venues, OKX is the main one with this pattern)")

    # Verification 4: Summary statistics
    print("\n=== Verification 4: v2 Table Statistics ===")

    for table in ['instruments_v2', 'prices_v2', 'funding_v2']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table:20} {count:,} rows")

    # Check instruments by venue and contract type
    cursor.execute("""
        SELECT venue, contract_type, COUNT(*) as cnt
        FROM instruments_v2
        GROUP BY venue, contract_type
        ORDER BY venue, contract_type
    """)

    print("\n  Instruments by venue and type:")
    for row in cursor.fetchall():
        print(f"    {row['venue']:12} {row['contract_type']:5} {row['cnt']:5}")

    # Check prices coverage
    cursor.execute("""
        SELECT
            COUNT(DISTINCT p.venue || ':' || p.inst_id) as instruments_with_prices,
            (SELECT COUNT(*) FROM instruments_v2) as total_instruments
        FROM prices_v2 p
    """)

    coverage = cursor.fetchone()
    if coverage:
        instruments_with_prices = coverage['instruments_with_prices']
        total_instruments = coverage['total_instruments']
        pct = (instruments_with_prices / total_instruments * 100) if total_instruments > 0 else 0
        print(f"\n  Price coverage: {instruments_with_prices:,}/{total_instruments:,} instruments ({pct:.1f}%)")

    conn.close()
    print("\n✓ Verification complete!")


if __name__ == "__main__":
    main()
