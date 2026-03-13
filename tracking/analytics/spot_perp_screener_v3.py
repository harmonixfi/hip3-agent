#!/usr/bin/env python3
"""SPOT↔PERP Carry screener (OKX) - V3-021

Pairs spot and perp instruments by symbol_key and calculates carry arbitrage opportunities.

Strategy:
- Default: long spot + short perp
- Pairs by symbol_key (BASE:QUOTE) on the same venue
- Stability: 7D/14D avg funding + consistency metrics
- Outputs: breakeven time, 7D/14D PnL, APR, cost analysis

Requirements:
- instruments_v3 table populated
- funding_v3 table with historical data (at least 14 days)
- prices_v3 table for current prices (optional, for spread costs)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"
OUTPUT_PATH = ROOT / "tracking" / "reports" / "spot_perp_screener_v3.json"

# Constants
SECONDS_PER_DAY = 86400
HOURS_PER_FUNDING_INTERVAL = 8  # OKX standard
MS_PER_HOUR = 3600000
MS_PER_DAY = 86400000


@dataclass
class CarryOpportunity:
    """A spot↔perp carry opportunity."""
    venue: str
    base: str
    quote: str
    spot_inst_id: str
    perp_inst_id: str
    symbol_key: str

    # Current prices
    spot_price: float
    perp_price: float

    # Funding metrics
    funding_rate_7d_avg: float  # Decimal per interval
    funding_rate_14d_avg: float  # Decimal per interval
    funding_rate_current: float  # Most recent
    funding_consistency_7d: float  # 0-1, higher = more consistent
    funding_consistency_14d: float  # 0-1, higher = more consistent

    # Cost analysis (in basis points)
    entry_cost_bps: float
    exit_cost_bps: float
    total_cost_bps: float
    used_proxy: bool

    # Profitability
    breakeven_hours: float  # Hours to recover costs
    pnl_7d_pct: float  # 7-day expected PnL %
    pnl_14d_pct: float  # 14-day expected PnL %
    apr_7d: float  # 7-day APR %
    apr_14d: float  # 14-day APR %

    # Flags
    quality_flags: List[str]  # e.g., ["high_risk", "low_liquidity"]


@dataclass
class ScreenerResult:
    """Complete screener results."""
    timestamp: str  # ISO UTC
    venue: str
    opportunities: List[CarryOpportunity]
    summary: Dict[str, int]


class SpotPerpScreenerV3:
    """Screener for spot↔perp carry opportunities."""

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize screener with database connection.

        Args:
            db_path: Path to SQLite database (defaults to tracking/db/arbit_v3.db)
        """
        if db_path is None:
            db_path = DB_PATH

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def get_instrument_pairs(
        self, venue: str = "okx", min_open_interest_rank: int = 200
    ) -> List[Tuple[sqlite3.Row, sqlite3.Row]]:
        """Get spot↔perp instrument pairs for a venue.

        Args:
            venue: Venue name (e.g., "okx")
            min_open_interest_rank: Maximum OI rank to consider (lower = more liquid)

        Returns:
            List of (spot_row, perp_row) tuples
        """
        query = """
        SELECT
            spot.venue,
            spot.inst_id as spot_inst_id,
            spot.base,
            spot.quote,
            spot.symbol_key,
            spot.raw_symbol as spot_symbol,
            perp.inst_id as perp_inst_id,
            perp.raw_symbol as perp_symbol
        FROM instruments_v3 spot
        JOIN instruments_v3 perp
            ON spot.venue = perp.venue
            AND spot.symbol_key = perp.symbol_key
            AND spot.contract_type = 'SPOT'
            AND perp.contract_type = 'PERP'
        WHERE spot.venue = ?
        AND (spot.specs_json IS NULL OR json_extract(spot.specs_json, '$.oi_rank') IS NULL OR
             json_extract(spot.specs_json, '$.oi_rank') <= ?)
        ORDER BY spot.base, spot.quote
        """

        cursor = self.conn.execute(query, (venue, min_open_interest_rank))
        rows = cursor.fetchall()

        pairs = []
        for row in rows:
            # Re-fetch full rows for each instrument
            spot_cursor = self.conn.execute(
                "SELECT * FROM instruments_v3 WHERE venue = ? AND inst_id = ?",
                (row["venue"], row["spot_inst_id"])
            )
            perp_cursor = self.conn.execute(
                "SELECT * FROM instruments_v3 WHERE venue = ? AND inst_id = ?",
                (row["venue"], row["perp_inst_id"])
            )
            pairs.append((spot_cursor.fetchone(), perp_cursor.fetchone()))

        return pairs

    def get_current_price(self, venue: str, inst_id: str) -> Optional[float]:
        """Get the most recent price for an instrument.

        Args:
            venue: Venue name
            inst_id: Instrument ID

        Returns:
            Latest price (mid mark or last) or None if no data
        """
        query = """
        SELECT
            COALESCE(mid, mark, last) as price
        FROM prices_v3
        WHERE venue = ? AND inst_id = ?
        ORDER BY ts DESC
        LIMIT 1
        """

        cursor = self.conn.execute(query, (venue, inst_id))
        row = cursor.fetchone()
        return row["price"] if row else None

    def get_funding_metrics(
        self, venue: str, inst_id: str, days: int = 14
    ) -> Dict[str, float]:
        """Calculate funding rate metrics for a perp.

        Args:
            venue: Venue name
            inst_id: Perp instrument ID
            days: Number of days to analyze

        Returns:
            Dict with:
                - avg_7d: 7-day average funding rate (per interval)
                - avg_14d: 14-day average funding rate (per interval)
                - current: Most recent funding rate
                - consistency_7d: 0-1 score (higher = more consistent)
                - consistency_14d: 0-1 score (higher = more consistent)
        """
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        cutoff_ms_7d = now_ms - (7 * MS_PER_DAY)
        cutoff_ms_14d = now_ms - (14 * MS_PER_DAY)

        # Get 14-day history
        query = """
        SELECT
            funding_rate,
            ts
        FROM funding_v3
        WHERE venue = ? AND inst_id = ? AND ts >= ?
        ORDER BY ts ASC
        """

        cursor = self.conn.execute(query, (venue, inst_id, cutoff_ms_14d))
        rows = cursor.fetchall()

        if not rows:
            return {
                "avg_7d": 0.0,
                "avg_14d": 0.0,
                "current": 0.0,
                "consistency_7d": 0.0,
                "consistency_14d": 0.0,
            }

        # Separate by time window
        rates_7d = [row["funding_rate"] for row in rows if row["ts"] >= cutoff_ms_7d]
        rates_14d = [row["funding_rate"] for row in rows]

        # Calculate averages
        avg_7d = sum(rates_7d) / len(rates_7d) if rates_7d else 0.0
        avg_14d = sum(rates_14d) / len(rates_14d) if rates_14d else 0.0
        current = rates_14d[-1] if rates_14d else 0.0

        # Calculate consistency (coefficient of variation inverse)
        def calc_consistency(rates: List[float]) -> float:
            if not rates or len(rates) < 2:
                return 0.0
            mean = sum(rates) / len(rates)
            if mean == 0:
                return 0.0
            variance = sum((r - mean) ** 2 for r in rates) / len(rates)
            std_dev = variance ** 0.5
            cv = std_dev / abs(mean) if abs(mean) > 0 else float('inf')
            # Inverse of CV, capped at 1
            consistency = min(1.0, 1.0 / (cv + 0.1))
            return consistency

        consistency_7d = calc_consistency(rates_7d)
        consistency_14d = calc_consistency(rates_14d)

        return {
            "avg_7d": avg_7d,
            "avg_14d": avg_14d,
            "current": current,
            "consistency_7d": consistency_7d,
            "consistency_14d": consistency_14d,
        }

    def estimate_cost(
        self,
        venue: str,
        spot_price: Optional[float] = None,
        perp_price: Optional[float] = None,
    ) -> Dict[str, float]:
        """Estimate total trading cost for spot↔perp carry.

        Uses conservative assumptions:
        - Taker fees for both legs (entry + exit)
        - Spread costs (proxy if no bid/ask data)

        Args:
            venue: Venue name
            spot_price: Current spot price (optional)
            perp_price: Current perp price (optional)

        Returns:
            Dict with entry_cost_bps, exit_cost_bps, total_cost_bps, used_proxy
        """
        # Fee assumptions (OKX: spot 0.10% taker, perp 0.05% taker)
        # In basis points
        fees = {
            "okx": {"spot": 10, "perp": 5},
        }

        venue_fees = fees.get(venue.lower(), {"spot": 15, "perp": 10})

        # Entry: taker fees
        entry_cost_bps = venue_fees["spot"] + venue_fees["perp"]

        # Exit: taker fees (we assume we'll exit with market orders)
        exit_cost_bps = venue_fees["spot"] + venue_fees["perp"]

        # Spread cost (proxy if we don't have bid/ask)
        spread_cost_bps = 10  # Conservative 0.10% proxy
        used_proxy = True

        # Total: entry + exit + spread (both sides)
        # Entry: enter spot, enter perp = fees + spread
        # Exit: exit spot, exit perp = fees + spread
        total_cost_bps = (entry_cost_bps + exit_cost_bps) + (spread_cost_bps * 2)

        return {
            "entry_cost_bps": entry_cost_bps + spread_cost_bps,
            "exit_cost_bps": exit_cost_bps + spread_cost_bps,
            "total_cost_bps": total_cost_bps,
            "used_proxy": used_proxy,
        }

    def calculate_opportunity(
        self,
        spot_row: sqlite3.Row,
        perp_row: sqlite3.Row,
        min_apr: float = 20.0,
    ) -> Optional[CarryOpportunity]:
        """Calculate carry opportunity metrics for a spot↔perp pair.

        Args:
            spot_row: Spot instrument row
            perp_row: Perp instrument row
            min_apr: Minimum APR threshold

        Returns:
            CarryOpportunity if meets criteria, None otherwise
        """
        venue = spot_row["venue"]
        base = spot_row["base"]
        quote = spot_row["quote"]
        symbol_key = spot_row["symbol_key"]

        spot_inst_id = spot_row["inst_id"]
        perp_inst_id = perp_row["inst_id"]

        # Get current prices
        spot_price = self.get_current_price(venue, spot_inst_id)
        perp_price = self.get_current_price(venue, perp_inst_id)

        if spot_price is None or perp_price is None:
            return None

        # Get funding metrics
        funding = self.get_funding_metrics(venue, perp_inst_id, days=14)

        # Calculate APR from average funding rate
        # funding_rate is per 8-hour interval
        # APR = funding_rate * (24/8) * 365 = funding_rate * 3 * 365
        apr_7d = funding["avg_7d"] * 3 * 365 * 100  # Convert to %
        apr_14d = funding["avg_14d"] * 3 * 365 * 100

        # Filter by minimum APR
        if apr_14d < min_apr:
            return None

        # Estimate costs
        costs = self.estimate_cost(venue, spot_price, perp_price)

        # Calculate breakeven time (in hours)
        # Hourly funding income = avg_14d * 3 (since 3 intervals per day)
        # We need to recover total_cost_bps
        # breakeven_hours = total_cost_bps / (hourly_funding_bps)
        hourly_funding_bps = funding["avg_14d"] * 3 * 10000  # Convert to bps
        if hourly_funding_bps > 0:
            breakeven_hours = costs["total_cost_bps"] / hourly_funding_bps
        else:
            breakeven_hours = float('inf')

        # Calculate expected PnL
        # 7-day: funding_7d - costs
        funding_7d_bps = funding["avg_7d"] * 10000 * 3 * 7  # 7 days, 3 intervals/day
        funding_14d_bps = funding["avg_14d"] * 10000 * 3 * 14  # 14 days, 3 intervals/day

        pnl_7d_bps = funding_7d_bps - costs["total_cost_bps"]
        pnl_14d_bps = funding_14d_bps - costs["total_cost_bps"]

        pnl_7d_pct = pnl_7d_bps / 100  # Convert bps to %
        pnl_14d_pct = pnl_14d_bps / 100

        # Quality flags
        quality_flags = []
        if funding["consistency_14d"] < 0.5:
            quality_flags.append("low_consistency")
        if breakeven_hours > 48:
            quality_flags.append("long_breakeven")

        return CarryOpportunity(
            venue=venue,
            base=base,
            quote=quote,
            spot_inst_id=spot_inst_id,
            perp_inst_id=perp_inst_id,
            symbol_key=symbol_key,
            spot_price=spot_price,
            perp_price=perp_price,
            funding_rate_7d_avg=funding["avg_7d"],
            funding_rate_14d_avg=funding["avg_14d"],
            funding_rate_current=funding["current"],
            funding_consistency_7d=funding["consistency_7d"],
            funding_consistency_14d=funding["consistency_14d"],
            entry_cost_bps=costs["entry_cost_bps"],
            exit_cost_bps=costs["exit_cost_bps"],
            total_cost_bps=costs["total_cost_bps"],
            used_proxy=costs["used_proxy"],
            breakeven_hours=breakeven_hours,
            pnl_7d_pct=pnl_7d_pct,
            pnl_14d_pct=pnl_14d_pct,
            apr_7d=apr_7d,
            apr_14d=apr_14d,
            quality_flags=quality_flags,
        )

    def run_screener(
        self,
        venue: str = "okx",
        min_apr: float = 20.0,
        min_open_interest_rank: int = 200,
        max_results: int = 50,
    ) -> ScreenerResult:
        """Run the complete screener analysis.

        Args:
            venue: Venue to analyze
            min_apr: Minimum APR threshold (%)
            min_open_interest_rank: Maximum OI rank (more liquid = lower number)
            max_results: Maximum number of opportunities to return

        Returns:
            ScreenerResult with opportunities and summary
        """
        pairs = self.get_instrument_pairs(venue, min_open_interest_rank)

        opportunities = []
        for spot_row, perp_row in pairs:
            opp = self.calculate_opportunity(spot_row, perp_row, min_apr)
            if opp:
                opportunities.append(opp)

        # Sort by APR descending
        opportunities.sort(key=lambda x: x.apr_14d, reverse=True)
        opportunities = opportunities[:max_results]

        summary = {
            "total_pairs_analyzed": len(pairs),
            "opportunities_found": len(opportunities),
            "venue": venue,
            "min_apr_threshold": min_apr,
        }

        return ScreenerResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            venue=venue,
            opportunities=opportunities,
            summary=summary,
        )

    def save_results(self, result: ScreenerResult, output_path: Optional[Path] = None) -> None:
        """Save screener results to JSON file.

        Args:
            result: ScreenerResult to save
            output_path: Output file path (defaults to tracking/reports/spot_perp_screener_v3.json)
        """
        if output_path is None:
            output_path = OUTPUT_PATH

        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": result.timestamp,
            "venue": result.venue,
            "summary": result.summary,
            "opportunities": [asdict(opp) for opp in result.opportunities],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


def print_summary(result: ScreenerResult) -> None:
    """Print a human-readable summary of screener results.

    Args:
        result: ScreenerResult to display
    """
    print(f"\n=== SPOT↔PERP Carry Screener ({result.venue.upper()}) ===")
    print(f"Timestamp: {result.timestamp}")
    print(f"Analyzed: {result.summary['total_pairs_analyzed']} pairs")
    print(f"Found: {result.summary['opportunities_found']} opportunities (APR >= {result.summary['min_apr_threshold']}%)")
    print()

    if not result.opportunities:
        print("No opportunities found meeting criteria.")
        return

    print(f"{'Base':<8} {'Quote':<6} {'APR 14D':<10} {'7D PnL':<9} {'Breakeven':<10} {'Flags'}")
    print("-" * 70)

    for opp in result.opportunities[:10]:  # Show top 10
        flags_str = ",".join(opp.quality_flags) if opp.quality_flags else "-"
        print(
            f"{opp.base:<8} {opp.quote:<6} {opp.apr_14d:<10.2f} "
            f"{opp.pnl_7d_pct:<9.2f} {opp.breakeven_hours:<10.2f} {flags_str}"
        )

    if len(result.opportunities) > 10:
        print(f"\n... and {len(result.opportunities) - 10} more opportunities")


def main() -> int:
    """Run screener and save results."""
    screener = SpotPerpScreenerV3()

    try:
        result = screener.run_screener(
            venue="okx",
            min_apr=20.0,
            min_open_interest_rank=200,
            max_results=50,
        )

        screener.save_results(result)
        print_summary(result)

        return 0
    except Exception as e:
        print(f"Error running screener: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        screener.close()


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
