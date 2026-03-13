#!/usr/bin/env python3
"""PERP↔PERP Extreme screener (cross-venue) - V3-022

Screens for funding arbitrage opportunities across venues by pairing perp instruments.

Strategy:
- Long perp on venue A + short perp on venue B (or vice versa)
- Pairs by symbol_base (and compatible quote currencies)
- Focus on extreme funding differentials (high APR potential)
- Outputs: funding PnL, APR differential, stability flags

Requirements:
- instruments_v3 table populated with perp instruments from multiple venues
- funding_v3 table with historical data (at least 14 days)
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Tuple

ROOT = Path(__file__).parent.parent.parent
DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"
OUTPUT_PATH = ROOT / "tracking" / "reports" / "perp_perp_screener_v3.json"

# Constants
MS_PER_DAY = 86400000
HOURS_PER_FUNDING_INTERVAL = 8  # Standard


@dataclass
class PerpPairOpportunity:
    """A perp↔perp funding arbitrage opportunity."""
    venue_long: str
    venue_short: str
    base: str
    quote_long: str
    quote_short: str
    inst_id_long: str
    inst_id_short: str

    # Funding rates
    funding_rate_long_7d_avg: float  # Decimal per interval
    funding_rate_long_14d_avg: float
    funding_rate_long_current: float

    funding_rate_short_7d_avg: float
    funding_rate_short_14d_avg: float
    funding_rate_short_current: float

    # Differential (what we earn)
    funding_diff_7d_avg: float  # long - short (positive means we earn)
    funding_diff_14d_avg: float
    funding_diff_current: float

    # Stability
    consistency_long_14d: float  # 0-1, higher = more consistent
    consistency_short_14d: float
    consistency_diff_14d: float  # Consistency of the differential

    # Cost analysis (in basis points)
    entry_cost_bps: float
    exit_cost_bps: float
    total_cost_bps: float
    used_proxy: bool

    # Profitability
    breakeven_hours: float
    pnl_7d_pct: float
    pnl_14d_pct: float
    apr_7d: float  # 7-day APR %
    apr_14d: float  # 14-day APR %

    # Flags
    quality_flags: List[str]


@dataclass
class PerpPerpScreenerResult:
    """Complete screener results."""
    timestamp: str  # ISO UTC
    venues: List[str]
    opportunities: List[PerpPairOpportunity]
    summary: Dict[str, int]


class PerpPerpScreenerV3:
    """Screener for cross-venue perp↔perp funding arbitrage."""

    # Compatible quote currencies (can be paired)
    QUOTE_COMPATIBLE = {
        "USDT": {"USDT", "USDC", "USD"},
        "USDC": {"USDT", "USDC", "USD"},
        "USD": {"USDT", "USDC", "USD"},
    }

    # Fee schedule (taker fees in basis points)
    FEES = {
        "okx": 5,
        "paradex": 5,
        "lighter": 5,
        "ethereal": 5,
        "hyperliquid": 5,
    }

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize screener with database connection."""
        if db_path is None:
            db_path = DB_PATH

        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), detect_types=sqlite3.PARSE_DECLTYPES)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        """Close database connection."""
        self.conn.close()

    def get_perp_instruments(
        self, venue: Optional[str] = None, min_open_interest_rank: int = 200
    ) -> List[sqlite3.Row]:
        """Get perp instruments, optionally filtered by venue.

        Args:
            venue: Venue name (or None for all venues)
            min_open_interest_rank: Maximum OI rank (more liquid = lower number)

        Returns:
            List of perp instrument rows
        """
        query = """
        SELECT * FROM instruments_v3
        WHERE contract_type = 'PERP'
        AND (specs_json IS NULL OR json_extract(specs_json, '$.oi_rank') IS NULL OR
             json_extract(specs_json, '$.oi_rank') <= ?)
        """

        params = [min_open_interest_rank]
        if venue:
            query += " AND venue = ?"
            params.append(venue)

        query += " ORDER BY base, quote, venue"

        cursor = self.conn.execute(query, params)
        return cursor.fetchall()

    def are_quotes_compatible(self, quote1: str, quote2: str) -> bool:
        """Check if two quote currencies are compatible for arbitrage.

        Args:
            quote1: First quote currency
            quote2: Second quote currency

        Returns:
            True if compatible, False otherwise
        """
        quote1_set = self.QUOTE_COMPATIBLE.get(quote1.upper(), {quote1.upper()})
        quote2_set = self.QUOTE_COMPATIBLE.get(quote2.upper(), {quote2.upper()})
        return bool(quote1_set & quote2_set)

    def get_funding_metrics(
        self, venue: str, inst_id: str, days: int = 14
    ) -> Dict[str, float]:
        """Calculate funding rate metrics for a perp.

        Args:
            venue: Venue name
            inst_id: Perp instrument ID
            days: Number of days to analyze

        Returns:
            Dict with avg_7d, avg_14d, current, consistency_7d, consistency_14d
        """
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        cutoff_ms_7d = now_ms - (7 * MS_PER_DAY)
        cutoff_ms_14d = now_ms - (14 * MS_PER_DAY)

        query = """
        SELECT funding_rate, ts
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
                "history_7d": [],
                "history_14d": [],
            }

        # Separate by time window
        rates_7d = [(row["funding_rate"], row["ts"]) for row in rows if row["ts"] >= cutoff_ms_7d]
        rates_14d = [(row["funding_rate"], row["ts"]) for row in rows]

        # Calculate averages
        avg_7d = sum(r[0] for r in rates_7d) / len(rates_7d) if rates_7d else 0.0
        avg_14d = sum(r[0] for r in rates_14d) / len(rates_14d) if rates_14d else 0.0
        current = rates_14d[-1][0] if rates_14d else 0.0

        # Calculate consistency (coefficient of variation inverse)
        def calc_consistency(rates: List[Tuple[float, int]]) -> float:
            if not rates or len(rates) < 2:
                return 0.0
            values = [r[0] for r in rates]
            mean = sum(values) / len(values)
            if mean == 0:
                return 0.0
            variance = sum((r - mean) ** 2 for r in values) / len(values)
            std_dev = variance ** 0.5
            cv = std_dev / abs(mean) if abs(mean) > 0 else float('inf')
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
            "history_7d": rates_7d,
            "history_14d": rates_14d,
        }

    def estimate_cost(
        self,
        venue_long: str,
        venue_short: str,
        used_proxy: bool = True,
    ) -> Dict[str, float]:
        """Estimate total trading cost for cross-venue perp↔perp.

        Args:
            venue_long: Venue for long position
            venue_short: Venue for short position
            used_proxy: Whether we used proxy spread costs

        Returns:
            Dict with entry_cost_bps, exit_cost_bps, total_cost_bps, used_proxy
        """
        fee_long = self.FEES.get(venue_long.lower(), 10)
        fee_short = self.FEES.get(venue_short.lower(), 10)

        # Entry: taker fees
        entry_cost_bps = fee_long + fee_short

        # Exit: taker fees
        exit_cost_bps = fee_long + fee_short

        # Spread cost (proxy)
        spread_cost_bps = 15  # Conservative 0.15% for cross-venue

        total_cost_bps = (entry_cost_bps + exit_cost_bps) + (spread_cost_bps * 2)

        return {
            "entry_cost_bps": entry_cost_bps + spread_cost_bps,
            "exit_cost_bps": exit_cost_bps + spread_cost_bps,
            "total_cost_bps": total_cost_bps,
            "used_proxy": used_proxy,
        }

    def calculate_opportunity(
        self,
        inst_long: sqlite3.Row,
        inst_short: sqlite3.Row,
        funding_long: Dict[str, float],
        funding_short: Dict[str, float],
        min_apr: float = 20.0,
    ) -> Optional[PerpPairOpportunity]:
        """Calculate funding arbitrage opportunity for a perp pair.

        Strategy: Long on low-funding venue, Short on high-funding venue
        We earn funding from the differential (short funding - long funding)

        Args:
            inst_long: Long instrument (lower funding)
            inst_short: Short instrument (higher funding)
            funding_long: Funding metrics for long instrument
            funding_short: Funding metrics for short instrument
            min_apr: Minimum APR threshold

        Returns:
            PerpPairOpportunity if meets criteria, None otherwise
        """
        # Calculate differential (what we earn)
        # We long the cheaper-to-fund perp, short the expensive one
        diff_7d = funding_short["avg_7d"] - funding_long["avg_7d"]
        diff_14d = funding_short["avg_14d"] - funding_long["avg_14d"]
        diff_current = funding_short["current"] - funding_long["current"]

        # Calculate APR from differential
        # APR = funding_diff * 3 * 365 * 100 (3 intervals per day)
        apr_7d = diff_7d * 3 * 365 * 100
        apr_14d = diff_14d * 3 * 365 * 100

        # Filter by minimum APR
        if apr_14d < min_apr:
            return None

        # Estimate costs
        costs = self.estimate_cost(inst_long["venue"], inst_short["venue"])

        # Calculate breakeven time (in hours)
        # Hourly funding income = diff_14d * 3 (3 intervals per day)
        hourly_funding_bps = diff_14d * 3 * 10000  # Convert to bps
        if hourly_funding_bps > 0:
            breakeven_hours = costs["total_cost_bps"] / hourly_funding_bps
        else:
            breakeven_hours = float('inf')

        # Calculate expected PnL
        funding_7d_bps = diff_7d * 10000 * 3 * 7  # 7 days, 3 intervals/day
        funding_14d_bps = diff_14d * 10000 * 3 * 14  # 14 days, 3 intervals/day

        pnl_7d_bps = funding_7d_bps - costs["total_cost_bps"]
        pnl_14d_bps = funding_14d_bps - costs["total_cost_bps"]

        pnl_7d_pct = pnl_7d_bps / 100
        pnl_14d_pct = pnl_14d_bps / 100

        # Calculate consistency of the differential
        def calc_diff_consistency(
            rates1: List[Tuple[float, int]],
            rates2: List[Tuple[float, int]]
        ) -> float:
            """Calculate consistency of the funding differential."""
            if len(rates1) < 2 or len(rates2) < 2:
                return 0.0

            # Match by timestamp (nearest within small tolerance)
            matched_diffs = []
            i, j = 0, 0
            tolerance_ms = 60000  # 1 minute

            while i < len(rates1) and j < len(rates2):
                r1, ts1 = rates1[i]
                r2, ts2 = rates2[j]

                diff = abs(ts1 - ts2)
                if diff <= tolerance_ms:
                    matched_diffs.append(r2 - r1)
                    i += 1
                    j += 1
                elif ts1 < ts2:
                    i += 1
                else:
                    j += 1

            if not matched_diffs or len(matched_diffs) < 2:
                return 0.0

            mean = sum(matched_diffs) / len(matched_diffs)
            if mean == 0:
                return 0.0
            variance = sum((d - mean) ** 2 for d in matched_diffs) / len(matched_diffs)
            std_dev = variance ** 0.5
            cv = std_dev / abs(mean) if abs(mean) > 0 else float('inf')
            consistency = min(1.0, 1.0 / (cv + 0.1))
            return consistency

        consistency_diff_14d = calc_diff_consistency(
            funding_long["history_14d"],
            funding_short["history_14d"]
        )

        # Quality flags
        quality_flags = []
        if funding_long["consistency_14d"] < 0.5:
            quality_flags.append("low_consistency_long")
        if funding_short["consistency_14d"] < 0.5:
            quality_flags.append("low_consistency_short")
        if consistency_diff_14d < 0.4:
            quality_flags.append("unstable_diff")
        if breakeven_hours > 48:
            quality_flags.append("long_breakeven")
        if diff_current < 0:
            quality_flags.append("diff_flipped")

        return PerpPairOpportunity(
            venue_long=inst_long["venue"],
            venue_short=inst_short["venue"],
            base=inst_long["base"],
            quote_long=inst_long["quote"],
            quote_short=inst_short["quote"],
            inst_id_long=inst_long["inst_id"],
            inst_id_short=inst_short["inst_id"],
            funding_rate_long_7d_avg=funding_long["avg_7d"],
            funding_rate_long_14d_avg=funding_long["avg_14d"],
            funding_rate_long_current=funding_long["current"],
            funding_rate_short_7d_avg=funding_short["avg_7d"],
            funding_rate_short_14d_avg=funding_short["avg_14d"],
            funding_rate_short_current=funding_short["current"],
            funding_diff_7d_avg=diff_7d,
            funding_diff_14d_avg=diff_14d,
            funding_diff_current=diff_current,
            consistency_long_14d=funding_long["consistency_14d"],
            consistency_short_14d=funding_short["consistency_14d"],
            consistency_diff_14d=consistency_diff_14d,
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
        venues: Optional[List[str]] = None,
        min_apr: float = 20.0,
        min_open_interest_rank: int = 200,
        max_results: int = 50,
    ) -> PerpPerpScreenerResult:
        """Run the complete cross-venue perp↔perp screener.

        Args:
            venues: List of venues to analyze (or None for all)
            min_apr: Minimum APR threshold (%)
            min_open_interest_rank: Maximum OI rank (more liquid = lower number)
            max_results: Maximum number of opportunities to return

        Returns:
            PerpPerpScreenerResult with opportunities and summary
        """
        # Get all perp instruments
        if venues:
            all_insts = []
            for venue in venues:
                all_insts.extend(self.get_perp_instruments(venue, min_open_interest_rank))
        else:
            all_insts = self.get_perp_instruments(None, min_open_interest_rank)

        # Group by base symbol
        by_base: Dict[str, List[sqlite3.Row]] = {}
        for inst in all_insts:
            base = inst["base"]
            by_base.setdefault(base, []).append(inst)

        # Find pairs across venues
        opportunities = []
        pairs_analyzed = 0

        for base, insts in by_base.items():
            # Try all pairs with compatible quotes
            for i, inst_a in enumerate(insts):
                for inst_b in insts[i+1:]:
                    # Skip same venue
                    if inst_a["venue"] == inst_b["venue"]:
                        continue

                    # Check quote compatibility
                    if not self.are_quotes_compatible(inst_a["quote"], inst_b["quote"]):
                        continue

                    pairs_analyzed += 1

                    # Get funding metrics
                    funding_a = self.get_funding_metrics(inst_a["venue"], inst_a["inst_id"], days=14)
                    funding_b = self.get_funding_metrics(inst_b["venue"], inst_b["inst_id"], days=14)

                    # Determine long/short based on funding rate
                    # We long the lower funding, short the higher
                    if funding_a["avg_14d"] < funding_b["avg_14d"]:
                        inst_long, inst_short = inst_a, inst_b
                        funding_long, funding_short = funding_a, funding_b
                    else:
                        inst_long, inst_short = inst_b, inst_a
                        funding_long, funding_short = funding_b, funding_a

                    # Calculate opportunity
                    opp = self.calculate_opportunity(
                        inst_long, inst_short, funding_long, funding_short, min_apr
                    )
                    if opp:
                        opportunities.append(opp)

        # Sort by APR descending
        opportunities.sort(key=lambda x: x.apr_14d, reverse=True)
        opportunities = opportunities[:max_results]

        summary = {
            "venues_analyzed": venues or ["all"],
            "pairs_analyzed": pairs_analyzed,
            "opportunities_found": len(opportunities),
            "min_apr_threshold": min_apr,
        }

        return PerpPerpScreenerResult(
            timestamp=datetime.now(timezone.utc).isoformat(),
            venues=summary["venues_analyzed"],
            opportunities=opportunities,
            summary=summary,
        )

    def save_results(self, result: PerpPerpScreenerResult, output_path: Optional[Path] = None) -> None:
        """Save screener results to JSON file."""
        if output_path is None:
            output_path = OUTPUT_PATH

        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "timestamp": result.timestamp,
            "venues": result.venues,
            "summary": result.summary,
            "opportunities": [asdict(opp) for opp in result.opportunities],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)


def print_summary(result: PerpPerpScreenerResult) -> None:
    """Print a human-readable summary of screener results."""
    print(f"\n=== PERP↔PERP Funding Arb Screener (Cross-Venue) ===")
    print(f"Timestamp: {result.timestamp}")
    print(f"Venues: {', '.join(result.venues)}")
    print(f"Analyzed: {result.summary['pairs_analyzed']} pairs")
    print(f"Found: {result.summary['opportunities_found']} opportunities (APR >= {result.summary['min_apr_threshold']}%)")
    print()

    if not result.opportunities:
        print("No opportunities found meeting criteria.")
        return

    print(f"{'Base':<8} {'Long':<10} {'Short':<10} {'APR 14D':<10} {'Diff%':<8} {'Breakeven':<10} {'Flags'}")
    print("-" * 80)

    for opp in result.opportunities[:10]:  # Show top 10
        diff_pct = opp.funding_diff_14d_avg * 10000 / 100  # Convert to %
        flags_str = ",".join(opp.quality_flags) if opp.quality_flags else "-"
        print(
            f"{opp.base:<8} {opp.venue_long:<10} {opp.venue_short:<10} "
            f"{opp.apr_14d:<10.2f} {diff_pct:<8.2f} {opp.breakeven_hours:<10.2f} {flags_str}"
        )

    if len(result.opportunities) > 10:
        print(f"\n... and {len(result.opportunities) - 10} more opportunities")


def main() -> int:
    """Run screener and save results."""
    screener = PerpPerpScreenerV3()

    try:
        result = screener.run_screener(
            venues=None,  # All venues
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
