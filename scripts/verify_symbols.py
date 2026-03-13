#!/usr/bin/env python3
"""Verify symbol normalization worked correctly by checking BERA across venues."""

import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit.db"

print("=" * 60)
print("Symbol Normalization Verification")
print("=" * 60)
print(f"Database: {DB_PATH}\n")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check for BERA across all venues
print("Checking BERA across venues:")
print("-" * 60)

# Instruments
cursor.execute("""
    SELECT venue, symbol, inst_id, quote_currency, base_currency
    FROM instruments
    WHERE UPPER(symbol) = 'BERA'
    ORDER BY venue
""")
instruments = cursor.fetchall()
print(f"\nInstruments ({len(instruments)} rows):")
for row in instruments:
    venue, symbol, inst_id, quote, base = row
    print(f"  {venue:12} | symbol={symbol:6} | inst_id={inst_id:40} | quote={quote:4} | base={base}")

# Funding
cursor.execute("""
    SELECT venue, symbol, funding_rate, funding_interval_hours, ts
    FROM funding
    WHERE UPPER(symbol) = 'BERA'
    ORDER BY venue, ts DESC
""")
funding = cursor.fetchall()
print(f"\nFunding ({len(funding)} rows, showing latest per venue):")
seen_venues = set()
for row in funding:
    venue, symbol, rate, interval, ts = row
    if venue not in seen_venues:
        print(f"  {venue:12} | symbol={symbol:6} | rate={rate:.6f} | interval={interval}h")
        seen_venues.add(venue)

# Prices
cursor.execute("""
    SELECT venue, symbol, mark_price, mid, ts
    FROM prices
    WHERE UPPER(symbol) = 'BERA'
    ORDER BY venue, ts DESC
""")
prices = cursor.fetchall()
print(f"\nPrices ({len(prices)} rows, showing latest per venue):")
seen_venues = set()
for row in prices:
    venue, symbol, mark, mid, ts = row
    if venue not in seen_venues:
        price_to_show = mid if mid and mid > 0 else mark
        print(f"  {venue:12} | symbol={symbol:6} | price=${price_to_show:.2f}")
        seen_venues.add(venue)

# Check a few other common symbols
print("\n" + "=" * 60)
print("Checking other common symbols (BTC, ETH, SOL):")
print("-" * 60)

for test_symbol in ['BTC', 'ETH', 'SOL']:
    cursor.execute("""
        SELECT venue, COUNT(DISTINCT symbol)
        FROM instruments
        WHERE UPPER(symbol) = ?
        GROUP BY venue
    """, (test_symbol,))
    rows = cursor.fetchall()
    if rows:
        venues = [r[0] for r in rows]
        print(f"\n{test_symbol:6} found in {len(venues)} venue(s): {', '.join(venues)}")
    else:
        print(f"\n{test_symbol:6} NOT FOUND")

# Check for cross-venue join capability
print("\n" + "=" * 60)
print("Cross-venue join test:")
print("-" * 60)

# Query to show symbols that exist in multiple venues
cursor.execute("""
    SELECT symbol, COUNT(DISTINCT venue) as venue_count
    FROM instruments
    WHERE symbol IN ('BTC', 'ETH', 'SOL', 'BERA')
    GROUP BY symbol
    ORDER BY venue_count DESC
""")
rows = cursor.fetchall()
for row in rows:
    symbol, count = row
    # Get venues for this symbol
    cursor.execute("""
        SELECT DISTINCT venue FROM instruments WHERE symbol = ?
    """, (symbol,))
    venues = [r[0] for r in cursor.fetchall()]
    print(f"  {symbol:6} -> {count} venues: {', '.join(venues)}")

# Check for raw symbols that still exist (indicates incomplete migration)
print("\n" + "=" * 60)
print("Checking for symbols that may not be fully normalized:")
print("-" * 60)

# Check for symbols with hyphens or underscores (likely not normalized)
cursor.execute("""
    SELECT venue, symbol, COUNT(*) as count
    FROM instruments
    WHERE symbol LIKE '%-%' OR symbol LIKE '%_%'
    GROUP BY venue, symbol
    ORDER BY venue, count DESC
    LIMIT 20
""")
rows = cursor.fetchall()
if rows:
    print(f"\nFound {len(rows)} symbols with hyphens/underscores (may need attention):")
    for row in rows:
        venue, symbol, count = row
        print(f"  {venue:12} | {symbol:30} | {count} rows")
else:
    print("\nNo symbols with hyphens/underscores found - migration looks clean!")

conn.close()

print("\n" + "=" * 60)
print("Verification complete!")
print("=" * 60)
