#!/usr/bin/env python3
"""Migrate arbit.db from v1 schema to v2 schema.

v1: instruments use (symbol) as key, with inst_id optional
v2: instruments use (venue, inst_id) as unique key

Key changes:
- instruments_v2: UNIQUE(venue, inst_id) - allows same symbol for SPOT and PERP
- prices_v2: joins on (venue, inst_id) instead of (venue, symbol)
- funding_v2: joins on (venue, inst_id) instead of (venue, symbol)
- Added symbol_key for composite lookups (e.g., "BTC:USDT" or "BTC:PERP")
"""

import sqlite3
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit.db"
SCHEMA_V2_PATH = ROOT / "tracking" / "sql" / "schema_v2.sql"


def parse_okx_inst_id(inst_id: str, contract_type: str, base_currency: str, quote_currency: str):
    """Parse OKX inst_id to extract base, quote, symbol_base.

    OKX inst_id formats:
    - SPOT: BTC-USDT, ETH-USD, etc.
    - PERP: BTC-USDT-SWAP, BTC-USD-SWAP, BTC-USD_UM-SWAP

    Returns: (base, quote, symbol_base) or (None, None, None) if unparseable
    """
    if not inst_id:
        return None, None, None

    # For SPOT: simple BASE-QUOTE format
    if contract_type == "SPOT":
        parts = inst_id.split("-")
        if len(parts) == 2:
            base = parts[0]
            quote = parts[1]
            return base, quote, base

    # For PERP: various formats
    # BTC-USDT-SWAP -> base=BTC, quote=USDT
    # BTC-USD-SWAP -> base=BTC, quote=None (USD-margined)
    # BTC-USD_UM-SWAP -> base=BTC, quote=None (USD-margined USDT-margined)
    elif contract_type == "PERP":
        if inst_id.endswith("-SWAP"):
            # Remove -SWAP suffix
            core = inst_id[:-5]
            parts = core.split("-")

            if len(parts) == 2:
                base = parts[0]
                quote = parts[1]
                # USD-margined perps have quote=USD but we might want to set it to None
                # to indicate they're not truly QUOTE-margined
                if quote == "USD" and "_UM" not in inst_id:
                    # Traditional USD-margined futures
                    return base, None, base
                elif "_UM" in inst_id:
                    # USDT-margined (Universal Margin)
                    return base, None, base
                else:
                    # Standard USDT/USDC-margined
                    return base, quote, base

    # Fallback: use base_currency/quote_currency if available
    if base_currency and quote_currency:
        return base_currency, quote_currency, base_currency

    return None, None, None


def build_symbol_key(venue: str, inst_id: str, contract_type: str, base: str, quote: str) -> str:
    """Build symbol_key for composite lookups.

    For USD-margined perps: "BTC:PERP"
    For quote-margined perps: "BTC:USDT"
    For spot: "BTC:USDT"
    """
    if quote:
        return f"{base}:{quote}"
    else:
        # USD-margined or no quote currency
        return f"{base}:PERP" if contract_type == "PERP" else base


def migrate():
    """Migrate database from v1 to v2 schema."""

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    print(f"Migrating database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Step 1: Create v2 tables
    print("\n=== Step 1: Creating v2 tables ===")
    schema_sql = SCHEMA_V2_PATH.read_text()
    cursor.executescript(schema_sql)
    print("✓ v2 tables created")

    # Step 2: Check existing v1 data
    print("\n=== Step 2: Analyzing v1 data ===")
    cursor.execute("SELECT COUNT(*) FROM instruments")
    v1_instrument_count = cursor.fetchone()[0]
    print(f"v1 instruments: {v1_instrument_count}")

    cursor.execute("SELECT venue, inst_id, COUNT(*) as cnt FROM instruments GROUP BY venue, inst_id HAVING cnt > 1 ORDER BY cnt DESC LIMIT 10")
    duplicates = cursor.fetchall()
    if duplicates:
        print(f"\nWARNING: Found {len(duplicates)} duplicate (venue, inst_id) pairs")
        for dup in duplicates[:5]:
            print(f"  {dup['venue']:12} {dup['inst_id']:25} {dup['cnt']:3} duplicates")
    else:
        print("✓ No duplicate (venue, inst_id) pairs found")

    # Step 3: Migrate instruments
    print("\n=== Step 3: Migrating instruments ===")

    # Get all instruments, de-duplicated by taking the one with latest created_at
    cursor.execute("""
        SELECT
            venue,
            inst_id,
            contract_type,
            symbol,
            base_currency,
            quote_currency,
            tick_size,
            contract_size,
            funding_interval_hours,
            MAX(created_at) as created_at
        FROM instruments
        GROUP BY venue, inst_id
    """)
    instruments = cursor.fetchall()

    migrated_instruments = 0
    skipped_instruments = 0
    parse_warnings = []

    for inst in instruments:
        venue = inst['venue']
        inst_id = inst['inst_id']
        contract_type = inst['contract_type']
        base_currency = inst['base_currency']
        quote_currency = inst['quote_currency']
        tick_size = inst['tick_size']
        contract_size = inst['contract_size']
        funding_interval_hours = inst['funding_interval_hours']
        created_at = inst['created_at']

        # Parse inst_id for base/quote
        if venue == 'okx' and inst_id:
            base, quote, symbol_base = parse_okx_inst_id(inst_id, contract_type, base_currency, quote_currency)
        else:
            # For other venues, use base_currency/quote_currency or fallback to inst_id parsing
            base = base_currency
            quote = quote_currency
            symbol_base = base_currency if base_currency else inst_id.split('-')[0] if inst_id and '-' in inst_id else None

        if not base:
            skipped_instruments += 1
            parse_warnings.append(f"Could not parse base for {venue}:{inst_id}")
            continue

        # Build symbol_key
        symbol_key = build_symbol_key(venue, inst_id, contract_type, base, quote)

        # Insert into instruments_v2
        try:
            cursor.execute("""
                INSERT INTO instruments_v2 (
                    venue, inst_id, base, quote, contract_type, symbol_base, symbol_key,
                    tick_size, contract_size, funding_interval_hours, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (venue, inst_id, base, quote, contract_type, symbol_base, symbol_key,
                  tick_size, contract_size, funding_interval_hours, created_at))
            migrated_instruments += 1
        except sqlite3.IntegrityError as e:
            print(f"  ERROR inserting {venue}:{inst_id}: {e}")
            skipped_instruments += 1

    print(f"✓ Migrated {migrated_instruments} instruments")
    if skipped_instruments > 0:
        print(f"  Skipped {skipped_instruments} instruments due to parse errors")
    if parse_warnings:
        print(f"  Parse warnings (first 5):")
        for warning in parse_warnings[:5]:
            print(f"    - {warning}")

    # Step 4: Migrate prices
    print("\n=== Step 4: Migrating prices ===")

    # Count v1 prices
    cursor.execute("SELECT COUNT(*) FROM prices")
    v1_prices_count = cursor.fetchone()[0]
    print(f"v1 prices: {v1_prices_count}")

    # Get instruments_v2 for mapping
    cursor.execute("SELECT venue, inst_id FROM instruments_v2")
    v2_instruments = {(row[0], row[1]): True for row in cursor.fetchall()}

    # Migrate prices with best-effort mapping
    cursor.execute("""
        SELECT
            p.venue,
            p.symbol,
            p.mark_price,
            p.index_price,
            p.last_price,
            p.bid,
            p.ask,
            p.mid,
            p.ts
        FROM prices p
    """)
    prices = cursor.fetchall()

    migrated_prices = 0
    skipped_prices = 0
    ambiguous_mappings = {}

    for price in prices:
        venue = price['venue']
        symbol = price['symbol']

        # Find matching inst_id in instruments_v2
        # For OKX, multiple instruments can have the same symbol (SPOT vs PERP)
        cursor.execute("""
            SELECT inst_id FROM instruments_v2
            WHERE venue = ? AND symbol_base = ?
            LIMIT 1
        """, (venue, symbol))
        inst_row = cursor.fetchone()

        if not inst_row:
            skipped_prices += 1
            continue

        inst_id = inst_row[0]

        # Check for ambiguous mappings (multiple instruments with same symbol)
        cursor.execute("""
            SELECT COUNT(*) FROM instruments_v2
            WHERE venue = ? AND symbol_base = ?
        """, (venue, symbol))
        count = cursor.fetchone()[0]
        if count > 1:
            key = f"{venue}:{symbol}"
            ambiguous_mappings[key] = ambiguous_mappings.get(key, 0) + 1

        # Insert into prices_v2
        try:
            cursor.execute("""
                INSERT INTO prices_v2 (
                    venue, inst_id, bid, ask, mid, mark_price, index_price, last_price, ts
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (venue, inst_id, price['bid'], price['ask'], price['mid'],
                  price['mark_price'], price['index_price'], price['last_price'], price['ts']))
            migrated_prices += 1
        except sqlite3.IntegrityError:
            # Duplicate (venue, inst_id, ts) - skip
            skipped_prices += 1

    print(f"✓ Migrated {migrated_prices} prices")
    if skipped_prices > 0:
        print(f"  Skipped {skipped_prices} prices (no mapping or duplicates)")
    if ambiguous_mappings:
        print(f"  Ambiguous mappings (first 10):")
        for key, count in list(ambiguous_mappings.items())[:10]:
            print(f"    {key}: {count} rows mapped to one instrument")

    # Step 5: Migrate funding
    print("\n=== Step 5: Migrating funding ===")

    # Count v1 funding
    cursor.execute("SELECT COUNT(*) FROM funding")
    v1_funding_count = cursor.fetchone()[0]
    print(f"v1 funding: {v1_funding_count}")

    # Migrate funding with best-effort mapping
    cursor.execute("""
        SELECT
            f.venue,
            f.symbol,
            f.funding_rate,
            f.funding_interval_hours,
            f.next_funding_ts,
            f.ts
        FROM funding f
    """)
    funding_rows = cursor.fetchall()

    migrated_funding = 0
    skipped_funding = 0

    for funding in funding_rows:
        venue = funding['venue']
        symbol = funding['symbol']

        # Find matching inst_id in instruments_v2
        cursor.execute("""
            SELECT inst_id FROM instruments_v2
            WHERE venue = ? AND symbol_base = ?
            LIMIT 1
        """, (venue, symbol))
        inst_row = cursor.fetchone()

        if not inst_row:
            skipped_funding += 1
            continue

        inst_id = inst_row[0]

        # Insert into funding_v2
        try:
            cursor.execute("""
                INSERT INTO funding_v2 (
                    venue, inst_id, funding_rate, funding_interval_hours, next_funding_ts, ts
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (venue, inst_id, funding['funding_rate'], funding['funding_interval_hours'],
                  funding['next_funding_ts'], funding['ts']))
            migrated_funding += 1
        except sqlite3.IntegrityError:
            # Duplicate (venue, inst_id, ts) - skip
            skipped_funding += 1

    print(f"✓ Migrated {migrated_funding} funding rows")
    if skipped_funding > 0:
        print(f"  Skipped {skipped_funding} funding rows (no mapping or duplicates)")

    # Commit changes
    conn.commit()

    # Summary
    print("\n=== Migration Summary ===")
    print(f"Instruments: {v1_instrument_count} → {migrated_instruments} (skipped {skipped_instruments})")
    print(f"Prices:      {v1_prices_count} → {migrated_prices} (skipped {skipped_prices})")
    print(f"Funding:     {v1_funding_count} → {migrated_funding} (skipped {skipped_funding})")

    # Verify v2 tables
    print("\n=== Verification ===")
    cursor.execute("SELECT COUNT(*) FROM instruments_v2")
    print(f"v2 instruments: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM prices_v2")
    print(f"v2 prices: {cursor.fetchone()[0]}")
    cursor.execute("SELECT COUNT(*) FROM funding_v2")
    print(f"v2 funding: {cursor.fetchone()[0]}")

    conn.close()
    print("\n✓ Migration complete!")


if __name__ == "__main__":
    migrate()
