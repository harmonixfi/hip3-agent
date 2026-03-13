#!/usr/bin/env python3
"""
Report OKX spot-perp basis opportunities using quote-aware matching.

This script identifies spot-perp arbitrage opportunities on OKX where
the spot price differs from the perpetual futures price, accounting for
the quote currency (e.g., BTC-USDT spot vs BTC-USDT-SWAP perp).

The quote-aware matching ensures that spot BTC-USDT only pairs with
perp BTC-USDT-SWAP, not BTC-USD-SWAP or other quote currencies.
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
sys.path.insert(0, str(ROOT / "tracking"))

import sqlite3
from symbols import parse_okx_inst, get_quote_aware_key, normalize_symbol
from okx_public import get_spot_tickers, get_mark_prices, get_orderbook

DB_PATH = ROOT / "tracking" / "db" / "arbit.db"
FEE_CONFIG_PATH = ROOT / "config" / "fees.json"


def load_fee_config() -> Dict:
    """Load fee configuration from config/fees.json."""
    with open(FEE_CONFIG_PATH, 'r') as f:
        return json.load(f)


def get_okx_fees(fee_config: Dict) -> Tuple[float, float, float, float]:
    """
    Get OKX spot and perp fees.

    Returns:
        Tuple of (spot_maker_bps, spot_taker_bps, perp_maker_bps, perp_taker_bps)
    """
    okx_config = fee_config.get('venues', {}).get('okx', {})
    spot_config = okx_config.get('spot', {})
    perp_config = okx_config.get('perp', {})

    return (
        spot_config.get('maker_bps', 8),
        spot_config.get('taker_bps', 10),
        perp_config.get('maker_bps', 2),
        perp_config.get('taker_bps', 5),
    )


def get_okx_instruments(conn: sqlite3.Connection) -> Dict[str, Dict]:
    """
    Get OKX instruments from database.

    Returns:
        Dict mapping inst_id -> instrument info dict
    """
    cursor = conn.cursor()

    cursor.execute("""
        SELECT inst_id, contract_type, quote_currency, base_currency
        FROM instruments
        WHERE venue = 'okx' AND quote_currency IN ('USDT', 'USD')
    """)

    inst_info = {}
    for row in cursor.fetchall():
        inst_id, contract_type, quote, base = row
        inst_info[inst_id] = {
            'contract_type': contract_type,
            'quote': quote,
            'base': base,
        }

    return inst_info


def get_okx_live_prices() -> Tuple[Dict[str, Dict], Dict[str, Dict]]:
    """
    Get live OKX prices from API for spot and perp instruments.

    Returns:
        Tuple of (spot_prices dict, perp_prices dict)
        Each dict maps inst_id -> price_data dict
    """
    # Fetch spot tickers from API
    print("Fetching spot prices from OKX API...")
    spot_tickers = get_spot_tickers()

    # Fetch perp mark prices from API
    print("Fetching perp prices from OKX API...")
    perp_mark_prices = get_mark_prices()

    # Process spot prices
    spot_prices = {}
    for inst_id, data in spot_tickers.items():
        base, quote, kind = parse_okx_inst(inst_id)
        if kind != 'SPOT':
            continue

        # Only include USDT/USD pairs
        if quote not in ['USDT', 'USD']:
            continue

        spot_prices[inst_id] = {
            'bid': data.get('bid', 0.0),
            'ask': data.get('ask', 0.0),
            'mid': data.get('mid', 0.0),
            'last': data.get('lastPrice', 0.0),
            'base': base,
            'quote': quote,
        }

    # Process perp prices
    perp_prices = {}
    for inst_id, data in perp_mark_prices.items():
        base, quote, kind = parse_okx_inst(inst_id)
        if kind != 'PERP':
            continue

        # Only include USDT/USD pairs
        if quote not in ['USDT', 'USD']:
            continue

        perp_prices[inst_id] = {
            'mark': data.get('markPrice', 0.0),
            'index': data.get('indexPrice', 0.0),
            'last': data.get('lastPrice', 0.0),
            'bid': 0.0,  # Not in mark prices response
            'ask': 0.0,  # Not in mark prices response
            'mid': data.get('markPrice', 0.0),  # Use mark as mid
            'base': base,
            'quote': quote,
        }

    print(f"  Retrieved {len(spot_prices)} spot prices (USDT/USD)")
    print(f"  Retrieved {len(perp_prices)} perp prices (USDT/USD)")
    print()

    return spot_prices, perp_prices


def find_spot_perp_pairs(spot_prices: Dict[str, Dict], perp_prices: Dict[str, Dict]) -> List[Tuple[str, str, Dict, Dict]]:
    """
    Find spot-perp pairs with matching base and quote currencies.

    Args:
        spot_prices: Dict of inst_id -> price_data
        perp_prices: Dict of inst_id -> price_data

    Returns:
        List of (spot_inst_id, perp_inst_id, spot_data, perp_data) tuples
    """
    # Group spot by quote-aware key (base-quote)
    spot_groups: Dict[str, Tuple[str, Dict]] = {}
    for inst_id, data in spot_prices.items():
        key = f"{data['base']}-{data['quote']}"
        spot_groups[key] = (inst_id, data)

    # Group perp by quote-aware key (base-quote)
    perp_groups: Dict[str, Tuple[str, Dict]] = {}
    for inst_id, data in perp_prices.items():
        key = f"{data['base']}-{data['quote']}"
        perp_groups[key] = (inst_id, data)

    # Find pairs with matching keys
    pairs = []
    for key in spot_groups.keys():
        if key in perp_groups:
            spot_inst_id, spot_data = spot_groups[key]
            perp_inst_id, perp_data = perp_groups[key]
            pairs.append((spot_inst_id, perp_inst_id, spot_data, perp_data))

    return pairs


def enrich_with_orderbooks(spot_inst_id: str, perp_inst_id: str, spot_data: Dict, perp_data: Dict) -> Tuple[Dict, Dict]:
    """
    Fetch orderbooks to get bid/ask for accurate cross-spread calculation.

    Args:
        spot_inst_id: Spot instrument ID
        perp_inst_id: Perp instrument ID
        spot_data: Existing spot data (will be updated)
        perp_data: Existing perp data (will be updated)

    Returns:
        Tuple of (updated_spot_data, updated_perp_data)
    """
    import time

    try:
        # Fetch spot orderbook
        spot_ob = get_orderbook(spot_inst_id, limit=5)
        if spot_ob.get('bid') and spot_ob.get('ask'):
            spot_data['bid'] = spot_ob['bid']
            spot_data['ask'] = spot_ob['ask']
            spot_data['mid'] = (spot_ob['bid'] + spot_ob['ask']) / 2.0
        time.sleep(0.1)  # Rate limit
    except Exception as e:
        pass  # Keep existing values

    try:
        # Fetch perp orderbook
        perp_ob = get_orderbook(perp_inst_id, limit=5)
        if perp_ob.get('bid') and perp_ob.get('ask'):
            perp_data['bid'] = perp_ob['bid']
            perp_data['ask'] = perp_ob['ask']
            perp_data['mid'] = (perp_ob['bid'] + perp_ob['ask']) / 2.0
        time.sleep(0.1)  # Rate limit
    except Exception as e:
        pass  # Keep existing values

    return spot_data, perp_data


def compute_basis(
    spot_data: Dict,
    perp_data: Dict,
    spot_taker_bps: float,
    perp_taker_bps: float,
) -> Dict:
    """
    Compute spot-perp basis and arbitrage metrics.

    Args:
        spot_data: Spot instrument data
        perp_data: Perpetual instrument data
        spot_taker_bps: Spot taker fee in basis points
        perp_taker_bps: Perp taker fee in basis points

    Returns:
        Dict with basis and PnL metrics
    """
    spot_mid = spot_data.get('mid') or spot_data.get('mark_price') or spot_data.get('bid') or spot_data.get('ask')
    perp_mid = perp_data.get('mid') or perp_data.get('mark_price') or perp_data.get('bid') or perp_data.get('ask')

    if not spot_mid or not perp_mid:
        return None

    # Compute basis (perp - spot)
    basis = perp_mid - spot_mid
    basis_pct = (basis / spot_mid) * 100 if spot_mid > 0 else 0

    # Compute cross-spread cost
    # For cash-and-carry: buy spot @ ask, sell perp @ bid
    spot_ask = spot_data.get('ask')
    perp_bid = perp_data.get('bid')

    if spot_ask and perp_bid:
        # Long spot, short perp
        cross_spread_cost = ((spot_ask - perp_bid) / spot_mid) * 100

        # Total fees (roundtrip: entry + exit)
        # Entry: buy spot (taker) + sell perp (taker)
        # Exit: sell spot (taker) + buy perp (taker)
        total_fee_pct = (spot_taker_bps + perp_taker_bps + spot_taker_bps + perp_taker_bps) / 100.0  # bps -> %

        # Estimated PnL from basis convergence
        # Assume basis mean-reverts to 0
        pnl_pct = basis_pct - cross_spread_cost - total_fee_pct

        return {
            'spot_mid': spot_mid,
            'perp_mid': perp_mid,
            'basis': basis,
            'basis_pct': basis_pct,
            'cross_spread_cost': cross_spread_cost,
            'total_fee_pct': total_fee_pct,
            'total_cost_pct': cross_spread_cost + total_fee_pct,
            'pnl_pct': pnl_pct,
        }
    else:
        # Fallback: no spread data
        total_fee_pct = (spot_taker_bps + perp_taker_bps + spot_taker_bps + perp_taker_bps) / 100.0
        return {
            'spot_mid': spot_mid,
            'perp_mid': perp_mid,
            'basis': basis,
            'basis_pct': basis_pct,
            'cross_spread_cost': None,
            'total_fee_pct': total_fee_pct,
            'total_cost_pct': total_fee_pct,
            'pnl_pct': None,
        }


def format_basis_report(record: Dict, rank: int) -> str:
    """Format a basis record for display."""
    lines = [
        f"#{rank} {record['symbol']}",
        f"  Spot: {record['spot_mid']:,.2f} | Perp: {record['perp_mid']:,.2f}",
        f"  Basis: {record['basis']:+,.2f} ({record['basis_pct']:+.3f}%)",
    ]

    if record['cross_spread_cost'] is not None:
        lines.append(f"  Cross-spread: {record['cross_spread_cost']:+.3f}%")
        lines.append(f"  Fees: {record['total_fee_pct']:.3f}%")
        lines.append(f"  Total cost: {record['total_cost_pct']:.3f}%")
        if record['pnl_pct'] is not None:
            lines.append(f"  Est PnL (convergence): {record['pnl_pct']:+.3f}%")
    else:
        lines.append(f"  Fees: {record['total_fee_pct']:.3f}%")
        lines.append(f"  (Spread data unavailable)")

    return '\n'.join(lines)


def main():
    """Main entry point."""
    print("=" * 70)
    print("OKX Spot-Perp Basis Report (Quote-Aware Matching)")
    print("=" * 70)
    print()

    # Load configuration
    fee_config = load_fee_config()
    spot_maker_bps, spot_taker_bps, perp_maker_bps, perp_taker_bps = get_okx_fees(fee_config)

    print(f"Fee Schedule (OKX):")
    print(f"  Spot: maker {spot_maker_bps} bps, taker {spot_taker_bps} bps")
    print(f"  Perp: maker {perp_maker_bps} bps, taker {perp_taker_bps} bps")
    print()

    # Get live prices from API
    spot_prices, perp_prices = get_okx_live_prices()

    # Find spot-perp pairs
    print("Finding spot-perp pairs (quote-aware matching)...")
    pairs = find_spot_perp_pairs(spot_prices, perp_prices)
    print(f"  Found {len(pairs)} spot-perp pairs")
    print()

    if not pairs:
        print("No spot-perp pairs found.")
        return 0

    # Compute basis for each pair
    results = []
    for spot_inst_id, perp_inst_id, spot_data, perp_data in pairs:
        basis = compute_basis(
            spot_data, perp_data, spot_taker_bps, perp_taker_bps
        )

        if basis:
            # Get quote-aware key for display
            key = f"{spot_data['base']}-{spot_data['quote']}"

            results.append({
                'symbol': key,
                'spot_inst_id': spot_inst_id,
                'perp_inst_id': perp_inst_id,
                'spot_mid': basis['spot_mid'],
                'perp_mid': basis['perp_mid'],
                'basis': basis['basis'],
                'basis_pct': basis['basis_pct'],
                'cross_spread_cost': basis['cross_spread_cost'],
                'total_fee_pct': basis['total_fee_pct'],
                'total_cost_pct': basis['total_cost_pct'],
                'pnl_pct': basis['pnl_pct'],
            })

    # Sort by absolute basis percentage (descending)
    results.sort(key=lambda x: abs(x['basis_pct']), reverse=True)

    # Display top 10
    print("=" * 70)
    print(f"Top 10 Spot-Perp Basis Opportunities (OKX)")
    print("=" * 70)
    print()

    for i, record in enumerate(results[:10], 1):
        print(format_basis_report(record, i))
        print()

    # Specific report for BTC/ETH/SOL USDT pairs
    print("=" * 70)
    print("Major Pairs: BTC/ETH/SOL USDT (with orderbook data)")
    print("=" * 70)
    print()

    for base in ['BTC', 'ETH', 'SOL']:
        key = f"{base}-USDT"
        matching = [r for r in results if r['symbol'] == key]
        if matching:
            record = matching[0]

            # Fetch orderbooks for accurate spread
            print(f"Fetching orderbooks for {key}...")
            spot_data = {
                'bid': 0.0,
                'ask': 0.0,
                'mid': record['spot_mid'],
                'base': base,
                'quote': 'USDT',
            }
            perp_data = {
                'bid': 0.0,
                'ask': 0.0,
                'mid': record['perp_mid'],
                'base': base,
                'quote': 'USDT',
            }

            spot_data, perp_data = enrich_with_orderbooks(
                record['spot_inst_id'],
                record['perp_inst_id'],
                spot_data,
                perp_data
            )

            # Recompute basis with orderbook data
            basis_with_ob = compute_basis(
                spot_data, perp_data, spot_taker_bps, perp_taker_bps
            )

            print(f"{key}:")
            print(f"  Spot: {basis_with_ob['spot_mid']:,.2f} (bid={spot_data.get('bid', 0):,.2f}, ask={spot_data.get('ask', 0):,.2f})")
            print(f"  Perp: {basis_with_ob['perp_mid']:,.2f} (bid={perp_data.get('bid', 0):,.2f}, ask={perp_data.get('ask', 0):,.2f})")
            print(f"  Basis: {basis_with_ob['basis']:+,.2f} ({basis_with_ob['basis_pct']:+.3f}%)")
            if basis_with_ob['pnl_pct'] is not None:
                print(f"  Cross-spread: {basis_with_ob['cross_spread_cost']:+.3f}%")
                print(f"  Fees: {basis_with_ob['total_fee_pct']:.3f}%")
                print(f"  Total cost: {basis_with_ob['total_cost_pct']:.3f}%")
                print(f"  Est PnL (basis convergence): {basis_with_ob['pnl_pct']:+.3f}%")
            print()

    print("=" * 70)
    print("Report complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(main())
