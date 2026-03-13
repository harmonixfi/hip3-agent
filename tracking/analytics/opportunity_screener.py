"""
Opportunity screener for cross-venue funding arbitrage.

Computes funding arbitrage opportunities between venues, including:
- Net funding carry (receive - pay)
- Execution slippage (cross-spread)
- Trading fees per venue and product type
- Minimum hold breakeven time
- Simulated PnL over 7-day and 14-day hold
- Annualized return (APR) derived from PnL

Assumptions:
- Fees: loaded from config/fees.json per venue and product type
- Default execution: market (taker) for both legs, both entry+exit
- Execution: cross spread (bid for sell, ask for buy), fallback to proxy if missing
- Funding: prefer 14D average; fallback to latest if unavailable
- Cost: roundtrip fees+spread applied once at position entry
"""

import json
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass

# Import symbols module for quote-aware key parsing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from tracking.symbols import get_quote_aware_key, parse_okx_inst

# Import OKX public connector for live API calls
sys.path.insert(0, str(Path(__file__).parent.parent / "connectors"))
from okx_public import get_spot_tickers, get_mark_prices, get_orderbook, get_funding

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FundingData:
    """Funding rate data for a venue/symbol."""
    venue: str
    symbol: str
    funding_rate: float  # Per funding interval
    funding_interval_hours: int
    funding_apr: float  # Annualized percentage
    data_quality: str  # '14d', 'limited', 'point'


@dataclass
class PriceData:
    """Price data for a venue/symbol."""
    venue: str
    symbol: str
    bid: Optional[float]
    ask: Optional[float]
    mid: Optional[float]
    mark_price: Optional[float]
    price_source: str  # 'bid_ask', 'mid', 'mark'
    contract_type: Optional[str]  # 'PERP' or 'SPOT'


@dataclass
class Opportunity:
    """Arbitrage opportunity record."""
    symbol: str
    norm_symbol: str
    long_venue: str  # Venue for long leg
    short_venue: str  # Venue for short leg
    long_price: float
    short_price: float
    long_funding_apr: float  # Exchange funding APR (same sign as funding_rate)
    short_funding_apr: float  # Exchange funding APR (same sign as funding_rate)
    net_funding_pnl_apr: float  # Position PnL: (-long_funding_apr) + short_funding_apr
    execution_cost_pct: float  # Cross-spread cost
    fee_cost_pct: float  # Total trading fees (both legs, entry+exit)
    spread_cost_pct: float  # Spread cost (or proxy if unavailable)
    total_cost_pct: float  # Total: fee_cost + spread_cost
    cost_min_pct: float  # Fees-only cost
    cost_est_pct: float  # Estimated total cost (fees + spread/proxy)
    breakeven_days: Optional[float]  # Days to recoup costs
    pnl_7d_pct: float  # PnL% over 7-day hold (using cost_est)
    pnl_7d_usd: float  # $ PnL on $10k notional (7-day)
    pnl_14d_pct: float  # PnL% over 14-day hold (using cost_est)
    pnl_14d_usd: float  # $ PnL on $10k notional (14-day)
    apr_from_7d: float  # APR derived from 7D PnL: pnl_7d_pct * (365/7)
    apr_from_14d: float  # APR derived from 14D PnL: pnl_14d_pct * (365/14)
    data_quality: str  # Data quality notes
    direction: str  # 'long_short' description
    spread_source: str  # 'cross_spread', 'proxy', 'no_price'
    strategy_type: str  # 'spot_perp' or 'perp_perp'
    funding_quality: str = ''  # Stability metrics for funding history
    requires_short_spot: bool = False  # Flag if opportunity requires shorting spot


class OpportunityScreener:
    """Screen for funding arbitrage opportunities across venues."""

    def __init__(self, db_path: str, config_path: Optional[str] = None):
        """
        Initialize the opportunity screener.

        Args:
            db_path: Path to SQLite database
            config_path: Path to config directory (default: tracking/../config)
        """
        self.db_path = db_path
        self.conn = None

        # Load fee config
        if config_path is None:
            # Default: assume we're in tracking/analytics/
            config_path = str(Path(__file__).parent.parent.parent / "config")

        self.fee_config = self._load_fee_config(config_path)
        self.strategy_config = self._load_strategy_config(config_path)

    def _load_fee_config(self, config_path: str) -> Dict:
        """Load fee configuration from config/fees.json."""
        fee_path = Path(config_path) / "fees.json"

        if not fee_path.exists():
            logger.warning(f"Fee config not found at {fee_path}, using defaults")
            return {
                "default_assumptions": {"execution_type": "market", "proxy_slippage_bps": 10},
                "venues": {}
            }

        with open(fee_path, 'r') as f:
            config = json.load(f)

        logger.info(f"Loaded fee config from {fee_path}")
        return config

    def _load_strategy_config(self, config_path: str) -> Dict:
        """Load strategy configuration from config/strategy.json or use defaults."""
        strategy_path = Path(config_path) / "strategy.json"

        defaults = {
            "spot_perp": {
                "min_funding_apr": 1.0,  # Minimum perp funding APR to consider
                "allow_short_spot": False  # Allow opportunities that require shorting spot
            },
            "perp_perp": {
                "extreme_funding_threshold": 20.0  # Threshold for 'extreme' funding (APR%)
            }
        }

        if not strategy_path.exists():
            logger.warning(f"Strategy config not found at {strategy_path}, using defaults")
            return defaults

        try:
            with open(strategy_path, 'r') as f:
                config = json.load(f)
            # Merge with defaults
            merged = defaults.copy()
            merged.update(config)
            logger.info(f"Loaded strategy config from {strategy_path}")
            return merged
        except Exception as e:
            logger.warning(f"Error loading strategy config: {e}, using defaults")
            return defaults

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

        Args:
            venue: Venue identifier
            symbol: Original symbol string

        Returns:
            Normalized symbol string
        """
        # Ethereal: strip 'USD' suffix
        if venue == 'ethereal' and symbol.endswith('USD'):
            return symbol[:-3]

        # OKX: strip '-USDT-SWAP' or '-USD-SWAP' suffix (perps)
        # For spot, keep as-is (e.g., BTC-USDT)
        if venue == 'okx':
            if '-SWAP' in symbol:
                # Perpetual
                for suffix in ['-USDT-SWAP', '-USD-SWAP', '-USD_UM-SWAP']:
                    if symbol.endswith(suffix):
                        return symbol[:-len(suffix)]
            elif '-USDT' in symbol or '-USD' in symbol:
                # Spot: strip quote currency for normalization
                parts = symbol.split('-')
                if len(parts) == 2:
                    return parts[0]  # Return base currency

        # Hyperliquid: strip '$' suffix if present (HLP uses this)
        if venue == 'hyperliquid' and symbol.endswith('$'):
            return symbol[:-1]

        # Paradex: strip 'USDC' suffix
        if venue == 'paradex' and symbol.endswith('USDC'):
            return symbol[:-4]

        # Lighter: keep as-is
        return symbol

    def get_contract_type(self, venue: str, symbol: str) -> str:
        """
        Determine contract type (PERP or SPOT) for a venue/symbol.

        Args:
            venue: Venue identifier
            symbol: Original symbol string

        Returns:
            'PERP' or 'SPOT'
        """
        if venue == 'okx':
            if '-SWAP' in symbol:
                return 'PERP'
            elif '-USDT' in symbol or '-USD' in symbol:
                return 'SPOT'

        # Default to PERP for other venues
        return 'PERP'

    def get_fees(self, venue: str, contract_type: str, execution_type: str = 'market') -> Tuple[float, float]:
        """
        Get maker and taker fees for a venue and contract type.

        Args:
            venue: Venue identifier (lowercase)
            contract_type: 'PERP' or 'SPOT'
            execution_type: 'market' (taker) or 'limit' (maker)

        Returns:
            Tuple of (maker_fee_bps, taker_fee_bps)
        """
        venues = self.fee_config.get('venues', {})

        if venue not in venues:
            logger.warning(f"No fee data for venue {venue}, using 0")
            return (0.0, 0.0)

        venue_config = venues[venue]

        # Try to get specific product type config
        if contract_type.lower() in venue_config:
            product_config = venue_config[contract_type.lower()]
            maker_bps = product_config.get('maker_bps', 0)
            taker_bps = product_config.get('taker_bps', 0)
            return (maker_bps, taker_bps)

        # Fallback to 'perp' if contract_type not found
        if 'perp' in venue_config:
            product_config = venue_config['perp']
            maker_bps = product_config.get('maker_bps', 0)
            taker_bps = product_config.get('taker_bps', 0)
            logger.warning(f"No fee data for {venue} {contract_type}, using perp fees")
            return (maker_bps, taker_bps)

        logger.warning(f"No fee data for {venue} {contract_type}, using 0")
        return (0.0, 0.0)

    def compute_roundtrip_fee_pct(self, venue1: str, venue2: str, contract_type1: str,
                                  contract_type2: str, execution_type: str = 'market') -> float:
        """
        Compute total roundtrip fee percentage for both legs (entry + exit).

        Args:
            venue1: First venue (e.g., for long leg)
            venue2: Second venue (e.g., for short leg)
            contract_type1: Contract type for venue1
            contract_type2: Contract type for venue2
            execution_type: 'market' (taker) or 'limit' (maker)

        Returns:
            Total roundtrip fee percentage
        """
        # Get fees for both venues
        maker1_bps, taker1_bps = self.get_fees(venue1, contract_type1, execution_type)
        maker2_bps, taker2_bps = self.get_fees(venue2, contract_type2, execution_type)

        # Determine which fee to use based on execution type
        if execution_type == 'market':
            fee1_bps = taker1_bps
            fee2_bps = taker2_bps
        else:
            fee1_bps = maker1_bps
            fee2_bps = maker2_bps

        # Total roundtrip: entry + exit for both legs
        # Entry: fee1 (buy) + fee2 (sell)
        # Exit: fee1 (sell) + fee2 (buy)
        total_bps = fee1_bps + fee2_bps + fee1_bps + fee2_bps

        # Convert bps to percentage
        return total_bps / 100.0

    def get_funding_rates(self) -> Dict[Tuple[str, str], FundingData]:
        """
        Get latest funding rates per venue+symbol.

        Attempts to use 14-day average if available; otherwise uses latest point.

        Returns:
            Dict mapping (venue, symbol) → FundingData
        """
        query = """
        SELECT
            venue,
            symbol,
            funding_rate,
            funding_interval_hours,
            next_funding_ts,
            ts
        FROM funding
        WHERE (venue, symbol, ts) IN (
            SELECT venue, symbol, MAX(ts)
            FROM funding
            GROUP BY venue, symbol
        )
        """

        cursor = self.conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        funding_data = {}
        current_time = datetime.now().timestamp()

        for row in rows:
            venue = row['venue']
            symbol = row['symbol']
            funding_rate = row['funding_rate'] or 0.0
            interval_hours = row['funding_interval_hours'] or 8

            # Check for 14D historical data
            fourteen_days_ago = (current_time - 14 * 24 * 3600) * 1000  # ms

            cursor.execute("""
                SELECT COUNT(*) as count, AVG(funding_rate) as avg_rate
                FROM funding
                WHERE venue = ? AND symbol = ? AND ts >= ?
            """, (venue, symbol, fourteen_days_ago))

            hist_row = cursor.fetchone()
            count_14d = hist_row['count'] if hist_row else 0

            # Use 14D average if available (>= 100 data points for hourly)
            if count_14d >= 100:
                avg_rate = hist_row['avg_rate'] or 0.0
                funding_rate_to_use = avg_rate
                data_quality = '14d'
            elif count_14d > 0:
                # Use available average
                avg_rate = hist_row['avg_rate'] or 0.0
                funding_rate_to_use = avg_rate
                data_quality = f'limited({count_14d}pts)'
            else:
                funding_rate_to_use = funding_rate
                data_quality = 'point'

            # Convert to APR
            if interval_hours > 0:
                # APR = rate * (24/interval) * 365
                funding_apr = funding_rate_to_use * (24 / interval_hours) * 365
            else:
                funding_apr = 0.0

            funding_data[(venue, symbol)] = FundingData(
                venue=venue,
                symbol=symbol,
                funding_rate=funding_rate_to_use,
                funding_interval_hours=interval_hours,
                funding_apr=funding_apr,
                data_quality=data_quality
            )

        logger.info(f"Loaded {len(funding_data)} funding records")
        return funding_data

    def compute_funding_stability(self, venue: str, symbol: str, funding_apr: float) -> str:
        """
        Compute funding stability metrics from historical data.

        Calculates:
        - 7D and 14D average funding APR
        - Positive/negative consistency (percentage of intervals with same sign as latest)

        Args:
            venue: Venue identifier
            symbol: Symbol to analyze
            funding_apr: Current funding APR for sign comparison

        Returns:
            String describing funding stability metrics
        """
        current_time = datetime.now().timestamp()

        # Get 14D historical data
        fourteen_days_ago = (current_time - 14 * 24 * 3600) * 1000  # ms

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT funding_rate, funding_interval_hours
            FROM funding
            WHERE venue = ? AND symbol = ? AND ts >= ?
            ORDER BY ts DESC
        """, (venue, symbol, fourteen_days_ago))

        rows = cursor.fetchall()

        if not rows:
            return 'no_history'

        # Calculate 7D and 14D averages
        seven_days_ago = (current_time - 7 * 24 * 3600) * 1000  # ms

        # 7D average
        cursor.execute("""
            SELECT AVG(funding_rate) as avg_rate
            FROM funding
            WHERE venue = ? AND symbol = ? AND ts >= ?
        """, (venue, symbol, seven_days_ago))

        row_7d = cursor.fetchone()
        avg_7d = row_7d['avg_rate'] if row_7d and row_7d['avg_rate'] else 0.0

        # 14D average
        cursor.execute("""
            SELECT AVG(funding_rate) as avg_rate
            FROM funding
            WHERE venue = ? AND symbol = ? AND ts >= ?
        """, (venue, symbol, fourteen_days_ago))

        row_14d = cursor.fetchone()
        avg_14d = row_14d['avg_rate'] if row_14d and row_14d['avg_rate'] else 0.0

        # Get funding interval for APR conversion
        funding_interval_hours = rows[0]['funding_interval_hours'] or 8

        # Convert averages to APR
        if funding_interval_hours > 0:
            apr_7d = avg_7d * (24 / funding_interval_hours) * 365
            apr_14d = avg_14d * (24 / funding_interval_hours) * 365
        else:
            apr_7d = 0.0
            apr_14d = 0.0

        # Calculate sign consistency
        current_sign = 1 if funding_apr > 0 else -1 if funding_apr < 0 else 0

        same_sign_count = sum(
            1 for row in rows
            if (row['funding_rate'] or 0) * current_sign >= 0
        )
        consistency_pct = (same_sign_count / len(rows)) * 100 if rows else 0

        # Build quality string
        parts = []
        if apr_7d != 0:
            parts.append(f"7d_avg:{apr_7d:+.2f}%")
        if apr_14d != 0:
            parts.append(f"14d_avg:{apr_14d:+.2f}%")
        parts.append(f"stable:{consistency_pct:.0f}%")

        return ', '.join(parts)

    def get_prices(self) -> Dict[Tuple[str, str], PriceData]:
        """
        Get latest prices per venue+symbol.

        Returns:
            Dict mapping (venue, symbol) → PriceData
        """
        query = """
        SELECT
            venue,
            symbol,
            mark_price,
            mid,
            last_price,
            bid,
            ask,
            ts
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

            # Determine price source
            bid = row['bid']
            ask = row['ask']
            mid = row['mid']
            mark_price = row['mark_price']
            last_price = row['last_price']

            price_source = 'none'
            if bid is not None and ask is not None:
                price_source = 'bid_ask'
            elif mid is not None:
                price_source = 'mid'
            elif mark_price is not None:
                price_source = 'mark'

            # Determine contract type
            contract_type = self.get_contract_type(venue, symbol)

            prices[(venue, symbol)] = PriceData(
                venue=venue,
                symbol=symbol,
                bid=bid,
                ask=ask,
                mid=mid,
                mark_price=mark_price,
                price_source=price_source,
                contract_type=contract_type
            )

        logger.info(f"Loaded {len(prices)} price records")
        return prices

    def compute_execution_cost(
        self,
        long_price_data: PriceData,
        short_price_data: PriceData
    ) -> Tuple[float, str]:
        """
        Compute execution cost using cross-spread method.

        For long leg: pay ask (higher price)
        For short leg: receive bid (lower price)
        Cost = (ask_long - bid_short) / mid - 1

        Falls back to proxy slippage if bid/ask unavailable.

        Args:
            long_price_data: Price data for long venue
            short_price_data: Price data for short venue

        Returns:
            Tuple of (execution_cost_pct, quality_note)
        """
        # Get effective prices for both legs
        mid_long = long_price_data.mid or long_price_data.mark_price or long_price_data.last_price
        mid_short = short_price_data.mid or short_price_data.mark_price or short_price_data.last_price

        if not mid_long or not mid_short:
            return 0.0, 'no_price'

        # Sanity check: prices should be within 10% of each other
        # (accounting for different contract specifications, etc.)
        if abs(mid_long - mid_short) / max(mid_long, mid_short) > 0.10:
            # Prices too far apart - likely different contract types or stale data
            # Use zero cost but flag it
            return 0.0, 'price_mismatch'

        # Try cross-spread method
        if long_price_data.ask is not None and short_price_data.bid is not None:
            long_entry = long_price_data.ask
            short_entry = short_price_data.bid

            avg_mid = (mid_long + mid_short) / 2

            # Cost = (long_entry - short_entry) / avg_mid
            # Positive = cost (paying more to enter)
            cost_pct = ((long_entry - short_entry) / avg_mid) * 100

            # Sanity check: if cost is extreme (>5%), use proxy
            if abs(cost_pct) > 5.0:
                return cost_pct, 'extreme_cost'

            return cost_pct, 'cross_spread'

        # Fallback to proxy slippage
        proxy_slippage_bps = self.fee_config.get('default_assumptions', {}).get('proxy_slippage_bps', 10)
        proxy_cost_pct = proxy_slippage_bps / 100.0
        return proxy_cost_pct, 'proxy'

    def find_opportunities(
        self,
        min_notional: float = 10000.0,
        min_net_funding_apr: float = 1.0,
        max_opportunities: Optional[int] = None,
        execution_type: str = 'market'
    ) -> List[Opportunity]:
        """
        Find funding arbitrage opportunities across venues.

        Args:
            min_notional: Minimum notional for filtering (USD)
            min_net_funding_apr: Minimum net funding APR (percentage)
            max_opportunities: Max opportunities to return (None = all)
            execution_type: 'market' (taker) or 'limit' (maker)

        Returns:
            List of Opportunity objects sorted by net funding APR (descending)
        """
        funding_data = self.get_funding_rates()
        price_data = self.get_prices()

        # Group by normalized symbol
        symbol_map: Dict[str, List[Tuple[str, str]]] = {}

        for (venue, symbol), f_data in funding_data.items():
            norm_symbol = self.normalize_symbol(venue, symbol)

            # Only include if we have price data
            if (venue, symbol) not in price_data:
                continue

            if norm_symbol not in symbol_map:
                symbol_map[norm_symbol] = []
            symbol_map[norm_symbol].append((venue, symbol))

        # Filter to symbols with >= 2 venues
        shared_symbols = {
            sym: venues for sym, venues in symbol_map.items()
            if len(venues) >= 2
        }

        logger.info(f"Found {len(shared_symbols)} shared symbols")

        # Find all pairs
        opportunities = []

        for norm_symbol, venue_list in shared_symbols.items():
            for i in range(len(venue_list)):
                for j in range(i + 1, len(venue_list)):
                    venue_a, symbol_a = venue_list[i]
                    venue_b, symbol_b = venue_list[j]

                    f_data_a = funding_data.get((venue_a, symbol_a))
                    f_data_b = funding_data.get((venue_b, symbol_b))

                    if not f_data_a or not f_data_b:
                        continue

                    # Check both directions
                    for direction in ['a_long', 'b_long']:
                        if direction == 'a_long':
                            long_venue, long_symbol = venue_a, symbol_a
                            short_venue, short_symbol = venue_b, symbol_b
                            long_funding = f_data_a.funding_apr
                            short_funding = f_data_b.funding_apr
                            long_quality = f_data_a.data_quality
                            short_quality = f_data_b.data_quality
                        else:
                            long_venue, long_symbol = venue_b, symbol_b
                            short_venue, short_symbol = venue_a, symbol_a
                            long_funding = f_data_b.funding_apr
                            short_funding = f_data_a.funding_apr
                            long_quality = f_data_b.data_quality
                            short_quality = f_data_a.data_quality

                        # Net funding PnL = pnl_long + pnl_short = (-long_funding) + short_funding
                        # Position PnL: long pays when funding > 0, short receives when funding > 0
                        pnl_long_apr = -long_funding
                        pnl_short_apr = short_funding
                        net_funding_pnl_apr = pnl_long_apr + pnl_short_apr  # = short_funding - long_funding

                        # Skip if net funding PnL is too low
                        if net_funding_pnl_apr < min_net_funding_apr:
                            continue

                        # Get price data
                        long_price_data = price_data.get((long_venue, long_symbol))
                        short_price_data = price_data.get((short_venue, short_symbol))

                        if not long_price_data or not short_price_data:
                            continue

                        # Get entry prices (use mid for reference)
                        long_price = long_price_data.mid or long_price_data.mark_price
                        short_price = short_price_data.mid or short_price_data.mark_price

                        if not long_price or not short_price:
                            continue

                        # Compute execution cost (spread cost)
                        exec_cost_pct, exec_source = self.compute_execution_cost(
                            long_price_data, short_price_data
                        )

                        # Get contract types for fee calculation
                        long_contract_type = long_price_data.contract_type
                        short_contract_type = short_price_data.contract_type

                        # Compute roundtrip fees
                        fee_cost_pct = self.compute_roundtrip_fee_pct(
                            long_venue, short_venue,
                            long_contract_type, short_contract_type,
                            execution_type
                        )

                        # Spread cost = execution cost (slippage)
                        spread_cost_pct = exec_cost_pct

                        # Total costs
                        cost_min_pct = fee_cost_pct  # Fees only
                        cost_est_pct = fee_cost_pct + spread_cost_pct  # Fees + spread
                        total_cost_pct = cost_est_pct

                        # Compute breakeven days
                        # breakeven = total_cost / (net_funding_pnl / 365)
                        if net_funding_pnl_apr > 0:
                            breakeven_days = total_cost_pct / (net_funding_pnl_apr / 365)
                        else:
                            breakeven_days = None

                        # Compute 7D PnL (using cost_est)
                        # PnL% = net_funding_pnl * (7/365) - total_cost
                        # Note: cost_est_pct applied once (roundtrip fees+spread)
                        pnl_7d_pct = net_funding_pnl_apr * (7 / 365) - total_cost_pct
                        pnl_7d_usd = pnl_7d_pct / 100 * min_notional

                        # Compute 14D PnL (using cost_est)
                        # PnL% = net_funding_pnl * (14/365) - total_cost
                        # Note: cost_est_pct applied once (roundtrip fees+spread)
                        pnl_14d_pct = net_funding_pnl_apr * (14 / 365) - total_cost_pct
                        pnl_14d_usd = pnl_14d_pct / 100 * min_notional

                        # Compute APR derived from PnL
                        # APR = pnl_pct * (365/days)
                        apr_from_7d = pnl_7d_pct * (365 / 7)
                        apr_from_14d = pnl_14d_pct * (365 / 14)

                        # Data quality notes
                        quality_notes = []
                        if long_quality != '14d':
                            quality_notes.append(f"long_funding:{long_quality}")
                        if short_quality != '14d':
                            quality_notes.append(f"short_funding:{short_quality}")
                        if exec_source != 'cross_spread':
                            quality_notes.append(f"exec:{exec_source}")
                        data_quality = ', '.join(quality_notes) if quality_notes else 'good'

                        # Direction description
                        direction_desc = f"Long {long_venue}, Short {short_venue}"

                        opp = Opportunity(
                            symbol=norm_symbol,
                            norm_symbol=norm_symbol,
                            long_venue=long_venue,
                            short_venue=short_venue,
                            long_price=long_price,
                            short_price=short_price,
                            long_funding_apr=long_funding,
                            short_funding_apr=short_funding,
                            net_funding_pnl_apr=net_funding_pnl_apr,
                            execution_cost_pct=exec_cost_pct,
                            fee_cost_pct=fee_cost_pct,
                            spread_cost_pct=spread_cost_pct,
                            total_cost_pct=total_cost_pct,
                            cost_min_pct=cost_min_pct,
                            cost_est_pct=cost_est_pct,
                            breakeven_days=breakeven_days,
                            pnl_7d_pct=pnl_7d_pct,
                            pnl_7d_usd=pnl_7d_usd,
                            pnl_14d_pct=pnl_14d_pct,
                            pnl_14d_usd=pnl_14d_usd,
                            apr_from_7d=apr_from_7d,
                            apr_from_14d=apr_from_14d,
                            data_quality=data_quality,
                            direction=direction_desc,
                            spread_source=exec_source,
                            strategy_type='perp_perp',
                            funding_quality='',
                            requires_short_spot=False
                        )

                        opportunities.append(opp)

        # Sort by net funding PnL APR (descending), then by 14D PnL
        opportunities.sort(key=lambda o: (o.net_funding_pnl_apr, o.pnl_14d_pct), reverse=True)

        if max_opportunities:
            opportunities = opportunities[:max_opportunities]

        logger.info(f"Found {len(opportunities)} opportunities")
        return opportunities

    def find_spot_perp_opportunities(
        self,
        venue: str = 'okx',
        min_notional: float = 10000.0,
        min_net_funding_apr: Optional[float] = None,
        max_opportunities: Optional[int] = None,
        execution_type: str = 'market'
    ) -> List[Opportunity]:
        """
        Find spot-perp carry opportunities within a single venue (OKX first).

        Strategy: Long SPOT + Short PERP to be delta-neutral and collect funding.
        - If perp funding > 0: Short perp (receive funding), Long spot (hedge)
        - If perp funding < 0: Would require long perp + short spot (not feasible without margin/borrow)
           For now, skip or flag as 'requires_short_spot' if allow_short_spot=False

        Args:
            venue: Venue to use (default: 'okx')
            min_notional: Minimum notional for filtering (USD)
            min_net_funding_apr: Minimum net funding APR (percentage). If None, use config.
            max_opportunities: Max opportunities to return (None = all)
            execution_type: 'market' (taker) or 'limit' (maker)

        Returns:
            List of Opportunity objects sorted by net funding APR (descending)
        """
        # Get config thresholds
        spot_perp_config = self.strategy_config.get('spot_perp', {})
        allow_short_spot = spot_perp_config.get('allow_short_spot', False)
        if min_net_funding_apr is None:
            min_net_funding_apr = spot_perp_config.get('min_funding_apr', 1.0)

        funding_data = self.get_funding_rates()
        price_data = self.get_prices()

        # Group spot and perp symbols by quote-aware key (base-quote)
        spot_map: Dict[str, List[Tuple[str, str]]] = {}
        perp_map: Dict[str, List[Tuple[str, str]]] = {}

        for (v, symbol), f_data in funding_data.items():
            if v != venue:
                continue

            # Only include if we have price data
            if (v, symbol) not in price_data:
                continue

            price_info = price_data[(v, symbol)]
            contract_type = price_info.contract_type

            # Use quote-aware key for OKX to match spot with perp
            quote_key = get_quote_aware_key(v, symbol)

            if contract_type == 'SPOT':
                if quote_key not in spot_map:
                    spot_map[quote_key] = []
                spot_map[quote_key].append((v, symbol))
            elif contract_type == 'PERP':
                if quote_key not in perp_map:
                    perp_map[quote_key] = []
                perp_map[quote_key].append((v, symbol))

        logger.info(f"Found {len(spot_map)} spot and {len(perp_map)} perp symbols for {venue}")

        # Find spot-perp pairs
        opportunities = []

        for quote_key in perp_map:
            # Skip if no spot available
            if quote_key not in spot_map:
                continue

            perp_list = perp_map[quote_key]
            spot_list = spot_map[quote_key]

            for perp_venue, perp_symbol in perp_list:
                for spot_venue, spot_symbol in spot_list:
                    f_data_perp = funding_data.get((perp_venue, perp_symbol))

                    if not f_data_perp:
                        continue

                    # Get perp funding APR
                    perp_funding_apr = f_data_perp.funding_apr
                    perp_quality = f_data_perp.data_quality

                    # Determine hedge direction
                    # For spot-perp, we want to be delta-neutral:
                    # - Long spot + Short perp
                    # Net funding PnL = pnl_long_spot + pnl_short_perp = 0 + perp_funding_apr
                    # (since short perp receives when funding > 0)

                    net_funding_pnl_apr = perp_funding_apr  # Spot has 0 funding

                    # Skip if net funding PnL is too low
                    if net_funding_pnl_apr < min_net_funding_apr:
                        continue

                    # For now, enforce Long spot, Short perp (the delta-neutral hedge)
                    # If funding is negative, we would need to Short spot + Long perp
                    # which may not be feasible without margin/borrow
                    requires_short_spot = False
                    if perp_funding_apr < 0:
                        if not allow_short_spot:
                            # Skip opportunities that would require shorting spot
                            continue
                        else:
                            requires_short_spot = True
                            # For negative funding, we'd be: Short spot + Long perp
                            # Net funding PnL = -perp_funding_apr (long perp receives negative funding = pays)
                            # Actually, long perp pays when funding is negative (receives positive when funding is negative)
                            # Wait, funding < 0 means long receives, short pays
                            # So: Short spot (0 funding) + Long perp (-perp_funding_apr to receive, so pnl = +abs(perp_funding))
                            # Let me re-check:
                            # funding_apr < 0: funding is negative
                            # Position PnL: long pnl = -funding_apr (positive, receives), short pnl = +funding_apr (negative, pays)
                            # So for funding < 0: we want Long perp (receives abs(funding)), Short spot (0)
                            # But we only have Long spot available, so we can't do this without shorting spot
                            requires_short_spot = True
                            net_funding_pnl_apr = -perp_funding_apr  # Long perp PnL when funding < 0

                    # Get price data
                    spot_price_data = price_data.get((spot_venue, spot_symbol))
                    perp_price_data = price_data.get((perp_venue, perp_symbol))

                    if not spot_price_data or not perp_price_data:
                        continue

                    # Get entry prices
                    spot_price = spot_price_data.mid or spot_price_data.mark_price
                    perp_price = perp_price_data.mid or perp_price_data.mark_price

                    if not spot_price or not perp_price:
                        continue

                    # For spot-perp, execution is on the same venue but different products
                    # Use spot as long, perp as short (or vice versa based on funding sign)
                    if perp_funding_apr >= 0:
                        # Funding >= 0: Long spot, Short perp
                        long_price_data = spot_price_data
                        short_price_data = perp_price_data
                        long_venue, long_symbol = spot_venue, spot_symbol
                        short_venue, short_symbol = perp_venue, perp_symbol
                        long_funding_apr = 0.0
                        short_funding_apr = perp_funding_apr
                    else:
                        # Funding < 0: Long perp, Short spot (if allowed)
                        long_price_data = perp_price_data
                        short_price_data = spot_price_data
                        long_venue, long_symbol = perp_venue, perp_symbol
                        short_venue, short_symbol = spot_venue, spot_symbol
                        long_funding_apr = perp_funding_apr
                        short_funding_apr = 0.0

                    # Compute execution cost
                    exec_cost_pct, exec_source = self.compute_execution_cost(
                        long_price_data, short_price_data
                    )

                    # Get contract types for fee calculation
                    long_contract_type = long_price_data.contract_type
                    short_contract_type = short_price_data.contract_type

                    # Compute roundtrip fees
                    fee_cost_pct = self.compute_roundtrip_fee_pct(
                        long_venue, short_venue,
                        long_contract_type, short_contract_type,
                        execution_type
                    )

                    # Spread cost = execution cost (slippage)
                    spread_cost_pct = exec_cost_pct

                    # Total costs
                    cost_min_pct = fee_cost_pct  # Fees only
                    cost_est_pct = fee_cost_pct + spread_cost_pct  # Fees + spread
                    total_cost_pct = cost_est_pct

                    # Compute breakeven days
                    if net_funding_pnl_apr > 0:
                        breakeven_days = total_cost_pct / (net_funding_pnl_apr / 365)
                    else:
                        breakeven_days = None

                    # Compute 7D PnL
                    pnl_7d_pct = net_funding_pnl_apr * (7 / 365) - total_cost_pct
                    pnl_7d_usd = pnl_7d_pct / 100 * min_notional

                    # Compute 14D PnL
                    pnl_14d_pct = net_funding_pnl_apr * (14 / 365) - total_cost_pct
                    pnl_14d_usd = pnl_14d_pct / 100 * min_notional

                    # Compute APR derived from PnL
                    apr_from_7d = pnl_7d_pct * (365 / 7)
                    apr_from_14d = pnl_14d_pct * (365 / 14)

                    # Compute funding quality (stability metrics)
                    funding_quality = self.compute_funding_stability(
                        perp_venue, perp_symbol, perp_funding_apr
                    )

                    # Data quality notes
                    quality_notes = []
                    if perp_quality != '14d':
                        quality_notes.append(f"perp_funding:{perp_quality}")
                    if exec_source != 'cross_spread':
                        quality_notes.append(f"exec:{exec_source}")
                    if requires_short_spot:
                        quality_notes.append("requires_short_spot")
                    data_quality = ', '.join(quality_notes) if quality_notes else 'good'

                    # Direction description
                    direction_desc = f"Long {long_symbol}, Short {short_symbol}"

                    # Symbol is the base quote key
                    opp = Opportunity(
                        symbol=quote_key,
                        norm_symbol=quote_key,
                        long_venue=long_venue,
                        short_venue=short_venue,
                        long_price=long_price,
                        short_price=short_price,
                        long_funding_apr=long_funding_apr,
                        short_funding_apr=short_funding_apr,
                        net_funding_pnl_apr=net_funding_pnl_apr,
                        execution_cost_pct=exec_cost_pct,
                        fee_cost_pct=fee_cost_pct,
                        spread_cost_pct=spread_cost_pct,
                        total_cost_pct=total_cost_pct,
                        cost_min_pct=cost_min_pct,
                        cost_est_pct=cost_est_pct,
                        breakeven_days=breakeven_days,
                        pnl_7d_pct=pnl_7d_pct,
                        pnl_7d_usd=pnl_7d_usd,
                        pnl_14d_pct=pnl_14d_pct,
                        pnl_14d_usd=pnl_14d_usd,
                        apr_from_7d=apr_from_7d,
                        apr_from_14d=apr_from_14d,
                        data_quality=data_quality,
                        direction=direction_desc,
                        spread_source=exec_source,
                        strategy_type='spot_perp',
                        funding_quality=funding_quality,
                        requires_short_spot=requires_short_spot
                    )

                    opportunities.append(opp)

        # Sort by net funding PnL APR (descending), then by 14D PnL
        opportunities.sort(key=lambda o: (o.net_funding_pnl_apr, o.pnl_14d_pct), reverse=True)

        if max_opportunities:
            opportunities = opportunities[:max_opportunities]

        logger.info(f"Found {len(opportunities)} spot-perp opportunities")
        return opportunities

    def find_spot_perp_opportunities_live(
        self,
        venue: str = 'okx',
        min_notional: float = 10000.0,
        min_net_funding_apr: Optional[float] = None,
        max_opportunities: Optional[int] = None,
        execution_type: str = 'market',
        quotes: Optional[List[str]] = None
    ) -> List[Opportunity]:
        """
        Find spot-perp carry opportunities using live OKX API data.

        This method bypasses the DB and fetches live data from OKX public API,
        ensuring spot and perp instruments are correctly paired by quote-aware keys.

        Strategy: Long SPOT + Short PERP to be delta-neutral and collect funding.
        - If perp funding > 0: Short perp (receive funding), Long spot (hedge)
        - If perp funding < 0: Would require long perp + short spot (not feasible without margin/borrow)

        Args:
            venue: Venue to use (default: 'okx')
            min_notional: Minimum notional for filtering (USD)
            min_net_funding_apr: Minimum net funding APR (percentage). If None, use config.
            max_opportunities: Max opportunities to return (None = all)
            execution_type: 'market' (taker) or 'limit' (maker)
            quotes: List of quote currencies to include (default: ['USDT'])

        Returns:
            List of Opportunity objects sorted by net funding APR (descending)

        Note:
            This method uses live API data and is labeled accordingly in data_quality.
        """
        if venue.lower() != 'okx':
            logger.warning(f"Live spot-perp only supported for OKX, got {venue}")
            return []

        # Get config thresholds
        spot_perp_config = self.strategy_config.get('spot_perp', {})
        allow_short_spot = spot_perp_config.get('allow_short_spot', False)
        if min_net_funding_apr is None:
            min_net_funding_apr = spot_perp_config.get('min_funding_apr', 1.0)
        if quotes is None:
            quotes = spot_perp_config.get('quotes', ['USDT'])

        logger.info(f"Fetching live OKX data for spot-perp analysis (quotes: {quotes})")

        # Fetch live data from OKX API
        try:
            spot_tickers = get_spot_tickers()
            perp_mark_prices = get_mark_prices()

            logger.info(f"  Retrieved {len(spot_tickers)} spot tickers")
            logger.info(f"  Retrieved {len(perp_mark_prices)} perp mark prices")
        except Exception as e:
            logger.error(f"Failed to fetch live OKX data: {e}")
            return []

        # Filter by quote currencies
        spot_filtered = {}
        perp_filtered = {}

        for inst_id, data in spot_tickers.items():
            base, quote, kind = parse_okx_inst(inst_id)
            if kind == 'SPOT' and quote in quotes:
                spot_filtered[inst_id] = {
                    **data,
                    'base': base,
                    'quote': quote,
                    'inst_id': inst_id,
                }

        for inst_id, data in perp_mark_prices.items():
            base, quote, kind = parse_okx_inst(inst_id)
            if kind == 'PERP' and quote in quotes:
                perp_filtered[inst_id] = {
                    **data,
                    'base': base,
                    'quote': quote,
                    'inst_id': inst_id,
                }

        logger.info(f"  Filtered to {len(spot_filtered)} spot and {len(perp_filtered)} perp instruments")

        # Group by quote-aware key (base-quote)
        spot_groups: Dict[str, Dict] = {}
        for inst_id, data in spot_filtered.items():
            key = f"{data['base']}-{data['quote']}"
            spot_groups[key] = data

        perp_groups: Dict[str, Dict] = {}
        for inst_id, data in perp_filtered.items():
            key = f"{data['base']}-{data['quote']}"
            perp_groups[key] = data

        # Find matching pairs and collect their perp inst_ids for funding query
        matched_pairs = []
        for key in spot_groups.keys():
            if key in perp_groups:
                matched_pairs.append((key, spot_groups[key], perp_groups[key]))

        logger.info(f"  Found {len(matched_pairs)} spot-perp pairs")

        # Fetch funding rates ONLY for matched perp instruments
        perp_funding_filtered = {}
        if matched_pairs:
            logger.info(f"  Fetching funding rates for {len(matched_pairs)} matched perp instruments...")
            for _, spot_data, perp_data in matched_pairs:
                perp_inst_id = perp_data['inst_id']
                try:
                    # Query funding rate for this specific instrument
                    import urllib.request
                    import urllib.parse
                    import json
                    url = "https://www.okx.com/api/v5/public/funding-rate"
                    params = {"instId": perp_inst_id}
                    full_url = url + "?" + urllib.parse.urlencode(params)
                    req = urllib.request.Request(
                        full_url,
                        headers={"Accept": "application/json", "User-Agent": "arbit-connector/0.1"},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        if data.get("data"):
                            funding_rate_bps = float(data["data"][0].get("fundingRate", 0))
                            perp_funding_filtered[perp_inst_id] = funding_rate_bps
                except Exception as e:
                    logger.debug(f"Failed to get funding for {perp_inst_id}: {e}")
                    # Use zero as fallback
                    perp_funding_filtered[perp_inst_id] = 0.0

            logger.info(f"  Retrieved {len(perp_funding_filtered)} funding rates")

        # Build opportunities
        opportunities = []

        for key, spot_data, perp_data in matched_pairs:
            perp_inst_id = perp_data['inst_id']

            # Get funding rate for perp
            funding_rate_bps = perp_funding_filtered.get(perp_inst_id, 0.0)

            # OKX returns funding rate as a decimal (e.g., 0.0001 = 0.01%)
            # funding_rate_bps is already in decimal format from API
            funding_rate = funding_rate_bps

            # Get funding interval (default 8 hours for OKX)
            funding_interval_hours = 8

            # Convert to APR
            perp_funding_apr = funding_rate * (24 / funding_interval_hours) * 365

            # Skip if net funding PnL is too low
            net_funding_pnl_apr = perp_funding_apr  # Long spot (0) + Short perp (receives)
            if net_funding_pnl_apr < min_net_funding_apr:
                continue

            # Check if we need to short spot (negative funding case)
            requires_short_spot = False
            if perp_funding_apr < 0:
                if not allow_short_spot:
                    continue
                else:
                    requires_short_spot = True
                    # For negative funding: Long perp receives, Short spot needed
                    net_funding_pnl_apr = -perp_funding_apr

            # Get prices
            spot_price = spot_data.get('mid') or spot_data.get('lastPrice', 0)
            perp_price = perp_data.get('mid') or perp_data.get('markPrice', 0)

            if not spot_price or not perp_price:
                continue

            # Determine direction
            if perp_funding_apr >= 0:
                # Funding >= 0: Long spot, Short perp
                long_price = spot_price
                short_price = perp_price
                long_venue = 'okx'
                short_venue = 'okx'
                long_symbol = spot_data['inst_id']
                short_symbol = perp_data['inst_id']
                long_funding_apr = 0.0
                short_funding_apr = perp_funding_apr
                perp_quality = 'live_api'
            else:
                # Funding < 0: Long perp, Short spot
                long_price = perp_price
                short_price = spot_price
                long_venue = 'okx'
                short_venue = 'okx'
                long_symbol = perp_data['inst_id']
                short_symbol = spot_data['inst_id']
                long_funding_apr = perp_funding_apr
                short_funding_apr = 0.0
                perp_quality = 'live_api'

            # Compute execution cost using cross-spread
            # For now, use proxy slippage since we don't have bid/ask from mark prices
            proxy_slippage_bps = self.fee_config.get('default_assumptions', {}).get('proxy_slippage_bps', 10)
            exec_cost_pct = proxy_slippage_bps / 100.0
            exec_source = 'proxy_live'

            # Get contract types for fee calculation
            long_contract_type = 'SPOT' if perp_funding_apr >= 0 else 'PERP'
            short_contract_type = 'PERP' if perp_funding_apr >= 0 else 'SPOT'

            # Compute roundtrip fees
            fee_cost_pct = self.compute_roundtrip_fee_pct(
                long_venue, short_venue,
                long_contract_type, short_contract_type,
                execution_type
            )

            # Spread cost = execution cost (slippage)
            spread_cost_pct = exec_cost_pct

            # Total costs
            cost_min_pct = fee_cost_pct  # Fees only
            cost_est_pct = fee_cost_pct + spread_cost_pct  # Fees + spread
            total_cost_pct = cost_est_pct

            # Compute breakeven days
            if net_funding_pnl_apr > 0:
                breakeven_days = total_cost_pct / (net_funding_pnl_apr / 365)
            else:
                breakeven_days = None

            # Compute 7D PnL
            pnl_7d_pct = net_funding_pnl_apr * (7 / 365) - total_cost_pct
            pnl_7d_usd = pnl_7d_pct / 100 * min_notional

            # Compute 14D PnL
            pnl_14d_pct = net_funding_pnl_apr * (14 / 365) - total_cost_pct
            pnl_14d_usd = pnl_14d_pct / 100 * min_notional

            # Compute APR derived from PnL
            apr_from_7d = pnl_7d_pct * (365 / 7)
            apr_from_14d = pnl_14d_pct * (365 / 14)

            # Data quality notes
            quality_notes = ['live_api']
            if requires_short_spot:
                quality_notes.append("requires_short_spot")
            data_quality = ', '.join(quality_notes)

            # Direction description
            if perp_funding_apr >= 0:
                direction_desc = f"Long {spot_data['inst_id']}, Short {perp_data['inst_id']}"
            else:
                direction_desc = f"Long {perp_data['inst_id']}, Short {spot_data['inst_id']}"

            # Create opportunity
            opp = Opportunity(
                symbol=key,
                norm_symbol=key,
                long_venue=long_venue,
                short_venue=short_venue,
                long_price=long_price,
                short_price=short_price,
                long_funding_apr=long_funding_apr,
                short_funding_apr=short_funding_apr,
                net_funding_pnl_apr=net_funding_pnl_apr,
                execution_cost_pct=exec_cost_pct,
                fee_cost_pct=fee_cost_pct,
                spread_cost_pct=spread_cost_pct,
                total_cost_pct=total_cost_pct,
                cost_min_pct=cost_min_pct,
                cost_est_pct=cost_est_pct,
                breakeven_days=breakeven_days,
                pnl_7d_pct=pnl_7d_pct,
                pnl_7d_usd=pnl_7d_usd,
                pnl_14d_pct=pnl_14d_pct,
                pnl_14d_usd=pnl_14d_usd,
                apr_from_7d=apr_from_7d,
                apr_from_14d=apr_from_14d,
                data_quality=data_quality,
                direction=direction_desc,
                spread_source=exec_source,
                strategy_type='spot_perp',
                funding_quality='live_api_no_history',
                requires_short_spot=requires_short_spot
            )

            opportunities.append(opp)

        # Sort by net funding PnL APR (descending), then by 14D PnL
        opportunities.sort(key=lambda o: (o.net_funding_pnl_apr, o.pnl_14d_pct), reverse=True)

        if max_opportunities:
            opportunities = opportunities[:max_opportunities]

        logger.info(f"Found {len(opportunities)} live spot-perp opportunities")
        return opportunities

    def find_all_opportunities(
        self,
        min_notional: float = 10000.0,
        min_net_funding_apr: float = 1.0,
        max_opportunities: Optional[int] = None,
        execution_type: str = 'market',
        include_spot_perp: bool = True,
        spot_perp_venue: str = 'okx',
        use_live_spot_perp: bool = False
    ) -> Tuple[List[Opportunity], List[Opportunity]]:
        """
        Find all opportunities, split by strategy type.

        Args:
            min_notional: Minimum notional for filtering (USD)
            min_net_funding_apr: Minimum net funding APR (percentage)
            max_opportunities: Max opportunities per strategy type to return
            execution_type: 'market' (taker) or 'limit' (maker)
            include_spot_perp: Include spot-perp carry opportunities
            spot_perp_venue: Venue for spot-perp opportunities (default: 'okx')
            use_live_spot_perp: Use live OKX API for spot-perp (default: False, uses DB)

        Returns:
            Tuple of (spot_perp_opps, perp_perp_opps)
        """
        # Find perp-perp opportunities
        perp_perp_opps = self.find_opportunities(
            min_notional=min_notional,
            min_net_funding_apr=min_net_funding_apr,
            max_opportunities=max_opportunities,
            execution_type=execution_type
        )

        # Find spot-perp opportunities
        spot_perp_opps = []
        if include_spot_perp:
            if use_live_spot_perp:
                spot_perp_opps = self.find_spot_perp_opportunities_live(
                    venue=spot_perp_venue,
                    min_notional=min_notional,
                    min_net_funding_apr=min_net_funding_apr,
                    max_opportunities=max_opportunities,
                    execution_type=execution_type
                )
            else:
                spot_perp_opps = self.find_spot_perp_opportunities(
                    venue=spot_perp_venue,
                    min_notional=min_notional,
                    min_net_funding_apr=min_net_funding_apr,
                    max_opportunities=max_opportunities,
                    execution_type=execution_type
                )

        return (spot_perp_opps, perp_perp_opps)

    def format_opportunity(self, opp: Opportunity, include_quality: bool = True) -> str:
        """
        Format an opportunity for display.

        Args:
            opp: Opportunity to format
            include_quality: Include data quality notes

        Returns:
            Formatted string
        """
        lines = [
            f"{opp.symbol} | {opp.direction}",
            f"  Funding APR (exchange): Long {opp.long_funding_apr:+.2f}%, Short {opp.short_funding_apr:+.2f}%",
            f"  Net Funding PnL APR: {opp.net_funding_pnl_apr:+.2f}% (position PnL from funding)",
            f"  Cost Breakdown: Fee {opp.fee_cost_pct:+.3f}% | Spread {opp.spread_cost_pct:+.3f}% ({opp.spread_source}) | Total {opp.total_cost_pct:.3f}%",
            f"  Cost Min (fees only): {opp.cost_min_pct:.3f}% | Cost Est (fees+spread): {opp.cost_est_pct:.3f}%",
            f"  Breakeven: {opp.breakeven_days:.1f} days" if opp.breakeven_days else "  Breakeven: N/A",
            f"  7D Hold PnL: {opp.pnl_7d_pct:+.2f}% (${opp.pnl_7d_usd:+.2f} on $10k) | APR: {opp.apr_from_7d:+.1f}%",
            f"  14D Hold PnL: {opp.pnl_14d_pct:+.2f}% (${opp.pnl_14d_usd:+.2f} on $10k) | APR: {opp.apr_from_14d:+.1f}%",
        ]

        if include_quality and opp.data_quality:
            lines.append(f"  Data Quality: {opp.data_quality}")

        return '\n'.join(lines)


def main():
    """Run the opportunity screener."""
    db_path = '/mnt/data/agents/arbit/tracking/db/arbit.db'

    with OpportunityScreener(db_path) as screener:
        opportunities = screener.find_opportunities(
            min_notional=10000.0,
            min_net_funding_apr=1.0,
            max_opportunities=20,
            execution_type='market'
        )

        print(f"\n=== Top {len(opportunities)} Funding Arbitrage Opportunities ===\n")

        for i, opp in enumerate(opportunities, 1):
            print(f"#{i}")
            print(screener.format_opportunity(opp))
            print()


if __name__ == '__main__':
    main()
