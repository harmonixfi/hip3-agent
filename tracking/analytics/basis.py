"""
Basis/spread computation for cross-venue arbitrage.

Computes basis spreads between venues for shared symbols.
"""

import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from symbols import normalize_symbol

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BasisEngine:
    """Compute basis/spread across venues for shared symbols."""

    def __init__(self, db_path: str):
        """
        Initialize the basis engine.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Establish database connection."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def normalize_symbol(self, venue: str, symbol: str) -> str:
        """
        Normalize symbol string for cross-venue comparison.

        Delegates to the shared symbols.normalize_symbol utility.

        Args:
            venue: Venue identifier
            symbol: Original symbol string

        Returns:
            Normalized symbol string
        """
        # Delegate to shared normalization utility
        return normalize_symbol(venue, symbol)

    def get_latest_prices(self) -> Dict[Tuple[str, str], dict]:
        """
        Load latest prices per venue+symbol.

        Returns:
            Dict mapping (venue, symbol) → price_data dict
        """
        query = """
        SELECT venue, symbol, mark_price, mid, last_price, ts
        FROM prices
        WHERE (venue, symbol, ts) IN (
            SELECT venue, symbol, MAX(ts)
            FROM prices
            GROUP BY venue, symbol
        )
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        prices = {}
        for row in rows:
            venue = row['venue']
            symbol = row['symbol']

            # Get effective price: prefer mid > mark_price > last_price
            price = None
            price_source = None
            if row['mid'] is not None:
                price = row['mid']
                price_source = 'mid'
            elif row['mark_price'] is not None:
                price = row['mark_price']
                price_source = 'mark_price'
            elif row['last_price'] is not None:
                price = row['last_price']
                price_source = 'last_price'

            if price is not None:
                prices[(venue, symbol)] = {
                    'price': price,
                    'price_source': price_source,
                    'ts': row['ts']
                }

        logger.info(f"Loaded {len(prices)} price records")
        return prices

    def get_shared_symbols(self, prices: Dict[Tuple[str, str], dict]) -> Dict[str, List[Tuple[str, str]]]:
        """
        Find symbols shared across multiple venues.

        Args:
            prices: Dict of (venue, symbol) → price_data

        Returns:
            Dict mapping normalized_symbol → list of (venue, original_symbol) tuples
        """
        # Group by normalized symbol
        symbol_map: Dict[str, List[Tuple[str, str]]] = {}

        for (venue, symbol), data in prices.items():
            norm_symbol = self.normalize_symbol(venue, symbol)
            if norm_symbol not in symbol_map:
                symbol_map[norm_symbol] = []
            symbol_map[norm_symbol].append((venue, symbol))

        # Filter to only symbols with >= 2 venues
        shared_symbols = {
            sym: venues for sym, venues in symbol_map.items()
            if len(venues) >= 2
        }

        logger.info(f"Found {len(shared_symbols)} shared symbols across venues")
        return shared_symbols

    def compute_basis_spread(
        self,
        price_a: float,
        price_b: float
    ) -> float:
        """
        Compute basis spread between two prices.

        basis_spread = (price_a - price_b) / price_b

        Args:
            price_a: Price from venue A
            price_b: Price from venue B (denominator)

        Returns:
            Basis spread as a percentage (e.g., 0.01 = 1%)
        """
        if price_b == 0:
            return 0.0
        return (price_a - price_b) / price_b

    def compute_annualized_basis(
        self,
        basis_pct: float,
        horizon_days: float = 1.0
    ) -> float:
        """
        Convert basis to annualized percentage.

        Assumes basis mean-reverts over the given horizon (default 1 day).

        Args:
            basis_pct: Basis as percentage (e.g., 0.01 = 1%)
            horizon_days: Expected mean reversion horizon in days

        Returns:
            Annualized basis percentage
        """
        if horizon_days <= 0:
            return 0.0
        days_per_year = 365.0
        return basis_pct * (days_per_year / horizon_days)

    def compute_all_basis(
        self,
        horizon_days: float = 1.0,
        min_price: float = 0.0
    ) -> List[dict]:
        """
        Compute basis for all shared symbols across all venue pairs.

        Args:
            horizon_days: Mean reversion horizon in days (default 1)
            min_price: Minimum price threshold (filter low-liquidity tokens)

        Returns:
            List of basis records with keys:
                - symbol: Normalized symbol
                - leg_a_venue: Venue A
                - leg_b_venue: Venue B
                - leg_a_symbol: Original symbol from venue A
                - leg_b_symbol: Original symbol from venue B
                - leg_a_price: Price from venue A
                - leg_b_price: Price from venue B
                - basis_spread: Basis spread (price_a - price_b) / price_b
                - basis_pct: Basis as percentage
                - annualized_basis_pct: Annualized basis
                - ts: Timestamp
        """
        prices = self.get_latest_prices()
        shared_symbols = self.get_shared_symbols(prices)

        basis_records = []
        current_ts = int(datetime.now().timestamp() * 1000)  # ms

        for norm_symbol, venue_list in shared_symbols.items():
            # Generate all unique venue pairs
            for i in range(len(venue_list)):
                for j in range(i + 1, len(venue_list)):
                    venue_a, symbol_a = venue_list[i]
                    venue_b, symbol_b = venue_list[j]

                    price_data_a = prices.get((venue_a, symbol_a))
                    price_data_b = prices.get((venue_b, symbol_b))

                    if not price_data_a or not price_data_b:
                        continue

                    price_a = price_data_a['price']
                    price_b = price_data_b['price']

                    # Filter low prices
                    if price_a < min_price or price_b < min_price:
                        continue

                    # Compute both directions (A→B and B→A)
                    for forward in [True, False]:
                        if forward:
                            leg_a_venue, leg_a_symbol = venue_a, symbol_a
                            leg_b_venue, leg_b_symbol = venue_b, symbol_b
                            pa, pb = price_a, price_b
                        else:
                            leg_a_venue, leg_a_symbol = venue_b, symbol_b
                            leg_b_venue, leg_b_symbol = venue_a, symbol_a
                            pa, pb = price_b, price_a

                        basis_spread = self.compute_basis_spread(pa, pb)
                        basis_pct = basis_spread * 100  # Convert to percentage
                        annualized = self.compute_annualized_basis(basis_pct / 100, horizon_days) * 100

                        basis_records.append({
                            'symbol': norm_symbol,
                            'leg_a_venue': leg_a_venue,
                            'leg_b_venue': leg_b_venue,
                            'leg_a_symbol': leg_a_symbol,
                            'leg_b_symbol': leg_b_symbol,
                            'leg_a_price': pa,
                            'leg_b_price': pb,
                            'basis_spread': basis_spread,
                            'basis_pct': basis_pct,
                            'annualized_basis_pct': annualized,
                            'ts': current_ts
                        })

        logger.info(f"Computed {len(basis_records)} basis records")
        return basis_records

    def store_basis(self, basis_records: List[dict]):
        """
        Store basis records to the database.

        For idempotency, deletes existing records for the same symbol+venue pairs
        before inserting. The table has a unique constraint on
        (symbol, leg_a_venue, leg_b_venue, ts), so we must handle this manually.

        Args:
            basis_records: List of basis records from compute_all_basis()
        """
        if not basis_records:
            return

        cursor = self.conn.cursor()

        # Delete existing records for the same symbol+venue pairs
        delete_query = """
        DELETE FROM basis
        WHERE symbol = ? AND leg_a_venue = ? AND leg_b_venue = ?
        """

        for r in basis_records:
            cursor.execute(delete_query, (
                r['symbol'],
                r['leg_a_venue'],
                r['leg_b_venue']
            ))

        deleted = cursor.rowcount

        # Insert new records
        insert_query = """
        INSERT INTO basis (
            symbol,
            leg_a_venue,
            leg_b_venue,
            leg_a_price,
            leg_b_price,
            basis_spread,
            basis_pct,
            annualized_basis_pct,
            ts
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        cursor.executemany(insert_query, [
            (
                r['symbol'],
                r['leg_a_venue'],
                r['leg_b_venue'],
                r['leg_a_price'],
                r['leg_b_price'],
                r['basis_spread'],
                r['basis_pct'],
                r['annualized_basis_pct'],
                r['ts']
            )
            for r in basis_records
        ])

        self.conn.commit()
        logger.info(f"Deleted {deleted} old records, inserted {len(basis_records)} new records into basis table")

    def run(self, horizon_days: float = 1.0, min_price: float = 0.0):
        """
        Run full basis computation and storage pipeline.

        Args:
            horizon_days: Mean reversion horizon in days (default 1)
            min_price: Minimum price threshold

        Returns:
            List of computed basis records
        """
        basis_records = self.compute_all_basis(horizon_days, min_price)
        self.store_basis(basis_records)
        return basis_records
