#!/usr/bin/env python3
"""
Migration script to normalize existing symbol data in arbit.db.

This script updates the 'symbol' column in all tables (instruments, funding, prices)
to use canonical symbols (base asset only, uppercase) while preserving venue-specific
identifiers in the 'inst_id' column.

Usage:
    python scripts/normalize_symbols_db.py [--dry-run] [--yes]

Options:
    --dry-run: Show what would be changed without modifying the database
    --yes: Skip confirmation prompt (for automation)

The script:
1. Backs up the database (unless --dry-run)
2. Updates symbols in instruments table
3. Updates symbols in funding table
4. Updates symbols in prices table
5. Reports statistics on changes made
"""

import sys
from pathlib import Path
import sqlite3
import shutil
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking"))

from symbols import normalize_symbol

DB_PATH = ROOT / "tracking" / "db" / "arbit.db"


def backup_database(db_path: Path) -> Path:
    """
    Create a backup of the database.

    Args:
        db_path: Path to the database file

    Returns:
        Path to the backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.parent / f"{db_path.stem}_backup_{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_venues(conn: sqlite3.Connection) -> list:
    """Get list of unique venues in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT venue FROM instruments ORDER BY venue")
    return [row[0] for row in cursor.fetchall()]


def migrate_instruments(
    conn: sqlite3.Connection,
    dry_run: bool = False
) -> dict:
    """
    Normalize symbols in the instruments table.

    Args:
        conn: Database connection
        dry_run: If True, don't modify the database

    Returns:
        Dictionary with statistics
    """
    cursor = conn.cursor()
    stats = {
        "total_rows": 0,
        "changed_rows": 0,
        "errors": 0,
        "venue_stats": {}
    }

    # Get all instruments
    cursor.execute("SELECT id, venue, symbol, inst_id FROM instruments")
    rows = cursor.fetchall()

    stats["total_rows"] = len(rows)

    for row in rows:
        inst_id_db, venue, old_symbol, inst_id = row

        try:
            # Normalize the symbol
            # For OKX and Paradex, inst_id = symbol (raw format)
            # For Ethereal and Lighter, inst_id is the venue-specific ID (UUID/market_id)
            # So we normalize based on the existing symbol column which has the raw format
            new_symbol = normalize_symbol(venue, old_symbol)

            if old_symbol != new_symbol:
                if not dry_run:
                    cursor.execute(
                        "UPDATE instruments SET symbol = ? WHERE id = ?",
                        (new_symbol, inst_id_db)
                    )

                # Track statistics
                if venue not in stats["venue_stats"]:
                    stats["venue_stats"][venue] = {"changed": 0, "examples": []}
                stats["venue_stats"][venue]["changed"] += 1

                # Keep a few examples
                if len(stats["venue_stats"][venue]["examples"]) < 3:
                    stats["venue_stats"][venue]["examples"].append({
                        "old": old_symbol,
                        "new": new_symbol,
                        "inst_id": inst_id
                    })

                stats["changed_rows"] += 1

        except Exception as e:
            # If normalization fails, skip this record but track it
            stats["errors"] += 1
            # Suppress error output for known special symbols to reduce noise
            if not (venue == "hyperliquid" and old_symbol.startswith("@")):
                print(f"ERROR processing instrument {venue}:{old_symbol} - {e}", file=sys.stderr)

    if not dry_run and stats["changed_rows"] > 0:
        conn.commit()

    return stats


def migrate_funding(
    conn: sqlite3.Connection,
    dry_run: bool = False
) -> dict:
    """
    Normalize symbols in the funding table.

    Args:
        conn: Database connection
        dry_run: If True, don't modify the database

    Returns:
        Dictionary with statistics
    """
    cursor = conn.cursor()
    stats = {
        "total_rows": 0,
        "changed_rows": 0,
        "errors": 0,
        "venue_stats": {}
    }

    # Get all funding records
    cursor.execute("SELECT id, venue, symbol FROM funding")
    rows = cursor.fetchall()

    stats["total_rows"] = len(rows)

    # Build inst_id lookup from instruments table
    cursor.execute("SELECT venue, inst_id, symbol FROM instruments")
    inst_map = {}
    for venue, inst_id, symbol in cursor.fetchall():
        key = (venue, symbol)
        if key not in inst_map:
            inst_map[key] = inst_id

    for row in rows:
        fund_id, venue, old_symbol = row

        try:
            # Try to normalize existing symbol directly first
            # This works for all venues where symbol is in raw format
            try:
                new_symbol = normalize_symbol(venue, old_symbol)
            except Exception:
                # Fallback: Look up inst_id from instruments table
                inst_id = inst_map.get((venue, old_symbol))
                if inst_id and inst_id != old_symbol:
                    # For venues where inst_id is different (e.g., ethereal with UUID),
                    # normalize based on inst_id if available and different
                    new_symbol = normalize_symbol(venue, inst_id)
                else:
                    # Last resort: try normalizing old_symbol again to get better error message
                    new_symbol = normalize_symbol(venue, old_symbol)

            if old_symbol != new_symbol:
                if not dry_run:
                    cursor.execute(
                        "UPDATE funding SET symbol = ? WHERE id = ?",
                        (new_symbol, fund_id)
                    )

                # Track statistics
                if venue not in stats["venue_stats"]:
                    stats["venue_stats"][venue] = {"changed": 0, "examples": []}
                stats["venue_stats"][venue]["changed"] += 1

                # Keep a few examples
                if len(stats["venue_stats"][venue]["examples"]) < 3:
                    stats["venue_stats"][venue]["examples"].append({
                        "old": old_symbol,
                        "new": new_symbol
                    })

                stats["changed_rows"] += 1

        except Exception as e:
            # If normalization fails, skip this record but track it
            stats["errors"] += 1
            # Suppress error output for known special symbols to reduce noise
            if not (venue == "hyperliquid" and old_symbol.startswith("@")):
                print(f"ERROR processing funding {venue}:{old_symbol} - {e}", file=sys.stderr)

    if not dry_run and stats["changed_rows"] > 0:
        conn.commit()

    return stats


def migrate_prices(
    conn: sqlite3.Connection,
    dry_run: bool = False
) -> dict:
    """
    Normalize symbols in the prices table.

    Args:
        conn: Database connection
        dry_run: If True, don't modify the database

    Returns:
        Dictionary with statistics
    """
    cursor = conn.cursor()
    stats = {
        "total_rows": 0,
        "changed_rows": 0,
        "errors": 0,
        "venue_stats": {}
    }

    # Get all price records
    cursor.execute("SELECT id, venue, symbol FROM prices")
    rows = cursor.fetchall()

    stats["total_rows"] = len(rows)

    # Build inst_id lookup from instruments table
    cursor.execute("SELECT venue, inst_id, symbol FROM instruments")
    inst_map = {}
    for venue, inst_id, symbol in cursor.fetchall():
        key = (venue, symbol)
        if key not in inst_map:
            inst_map[key] = inst_id

    for row in rows:
        price_id, venue, old_symbol = row

        try:
            # Try to normalize existing symbol directly first
            # This works for all venues where symbol is in raw format
            try:
                new_symbol = normalize_symbol(venue, old_symbol)
            except Exception:
                # Fallback: Look up inst_id from instruments table
                inst_id = inst_map.get((venue, old_symbol))
                if inst_id and inst_id != old_symbol:
                    # For venues where inst_id is different (e.g., ethereal with UUID),
                    # normalize based on inst_id if available and different
                    new_symbol = normalize_symbol(venue, inst_id)
                else:
                    # Last resort: try normalizing old_symbol again to get better error message
                    new_symbol = normalize_symbol(venue, old_symbol)

            if old_symbol != new_symbol:
                if not dry_run:
                    cursor.execute(
                        "UPDATE prices SET symbol = ? WHERE id = ?",
                        (new_symbol, price_id)
                    )

                # Track statistics
                if venue not in stats["venue_stats"]:
                    stats["venue_stats"][venue] = {"changed": 0, "examples": []}
                stats["venue_stats"][venue]["changed"] += 1

                # Keep a few examples
                if len(stats["venue_stats"][venue]["examples"]) < 3:
                    stats["venue_stats"][venue]["examples"].append({
                        "old": old_symbol,
                        "new": new_symbol
                    })

                stats["changed_rows"] += 1

        except Exception as e:
            # If normalization fails, skip this record but track it
            # Special symbols like @1, @100 on hyperliquid may fail validation
            stats["errors"] += 1
            # Suppress error output for known special symbols to reduce noise
            if not (venue == "hyperliquid" and old_symbol.startswith("@")):
                print(f"ERROR processing price {venue}:{old_symbol} - {e}", file=sys.stderr)

    if not dry_run and stats["changed_rows"] > 0:
        conn.commit()

    return stats


def print_stats(table_name: str, stats: dict):
    """Print migration statistics for a table."""
    print(f"\n{'=' * 60}")
    print(f"Table: {table_name}")
    print(f"{'=' * 60}")
    print(f"Total rows: {stats['total_rows']}")
    print(f"Changed rows: {stats['changed_rows']}")
    print(f"Errors: {stats['errors']}")

    if stats['venue_stats']:
        print(f"\nBy venue:")
        for venue, venue_stats in stats['venue_stats'].items():
            print(f"  {venue}:")
            print(f"    Changed: {venue_stats['changed']}")
            if venue_stats['examples']:
                print(f"    Examples:")
                for ex in venue_stats['examples']:
                    if 'inst_id' in ex:
                        print(f"      {ex['old']} -> {ex['new']} (inst_id: {ex['inst_id']})")
                    else:
                        print(f"      {ex['old']} -> {ex['new']}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Normalize symbols in arbit.db")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying the database"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("Symbol Normalization Migration")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Dry run: {args.dry_run}")

    if not DB_PATH.exists():
        print(f"ERROR: Database not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    # Check for symbols module
    try:
        from symbols import normalize_symbol, get_supported_venues
        print(f"Supported venues: {', '.join(get_supported_venues())}")
    except ImportError as e:
        print(f"ERROR: Cannot import symbols module: {e}", file=sys.stderr)
        sys.exit(1)

    # Confirm unless --yes or --dry-run
    if not args.yes and not args.dry_run:
        response = input("\nThis will modify the database. Continue? (yes/no): ")
        if response.lower() not in ['yes', 'y']:
            print("Aborted.")
            sys.exit(0)

    # Backup database
    if not args.dry_run:
        print("\nBacking up database...")
        backup_path = backup_database(DB_PATH)
        print(f"Backup created: {backup_path}")

    # Connect to database
    conn = sqlite3.connect(DB_PATH)

    # Enable foreign keys
    conn.execute("PRAGMA foreign_keys = OFF")

    try:
        # Check current venues
        print("\nCurrent venues in database:")
        venues = get_venues(conn)
        for venue in venues:
            print(f"  - {venue}")

        # Migrate instruments table
        print("\nMigrating instruments table...")
        inst_stats = migrate_instruments(conn, dry_run=args.dry_run)
        print_stats("instruments", inst_stats)

        # Migrate funding table
        print("\nMigrating funding table...")
        fund_stats = migrate_funding(conn, dry_run=args.dry_run)
        print_stats("funding", fund_stats)

        # Migrate prices table
        print("\nMigrating prices table...")
        price_stats = migrate_prices(conn, dry_run=args.dry_run)
        print_stats("prices", price_stats)

        # Summary
        total_changed = inst_stats['changed_rows'] + fund_stats['changed_rows'] + price_stats['changed_rows']
        total_errors = inst_stats['errors'] + fund_stats['errors'] + price_stats['errors']

        print("\n" + "=" * 60)
        print("Summary")
        print("=" * 60)
        print(f"Total rows changed: {total_changed}")
        print(f"Total errors: {total_errors}")

        if args.dry_run:
            print("\n(Dry run - no changes made)")
        else:
            print("\nMigration complete!")

    except Exception as e:
        print(f"\nERROR during migration: {e}", file=sys.stderr)
        if not args.dry_run:
            print("\nAttempting to restore from backup...", file=sys.stderr)
            try:
                shutil.copy2(backup_path, DB_PATH)
                print(f"Database restored from: {backup_path}")
            except Exception as restore_error:
                print(f"ERROR restoring backup: {restore_error}", file=sys.stderr)
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    main()
