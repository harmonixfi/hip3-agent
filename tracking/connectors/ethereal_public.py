"""Ethereal public connector for market data.

Functions: get_instruments, get_funding, get_mark_prices, get_orderbook

API Base URL: https://api.ethereal.trade

Endpoints:
- GET /v1/product - List all products (includes funding rate)
- GET /v1/product/market-price - Get current prices (bestBid, bestAsk, oraclePrice)

Note: Orderbooks are only available via WebSocket (BOOK_DEPTH/L2Book streams).
This connector uses bestBid/bestAsk from market-price endpoint as a top-level fallback.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import json
import time
import sys


BASE_URL = "https://api.ethereal.trade"

# Cache for instruments to avoid repeated API calls
_instruments_cache = None
_instruments_cache_time = None
_product_id_map = None  # Maps symbol to product_id
_product_id_map_time = None


def _get(path: str, params: Optional[Dict[str, str]] = None, timeout: int = 30) -> dict:
    """Make GET request to Ethereal API."""
    url = BASE_URL + path
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "arbit-connector/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def get_instruments(force_refresh: bool = False) -> List[Dict[str, str]]:
    """Get list of perp instruments from Ethereal.

    Args:
        force_refresh: Force refresh of cached instruments

    Returns:
        List of instrument dicts with symbol, inst_id, base, quote, etc.
    """
    global _instruments_cache, _instruments_cache_time, _product_id_map, _product_id_map_time

    # Use cache if available and less than 5 minutes old
    current_time = time.time()
    if not force_refresh and _instruments_cache and (current_time - _instruments_cache_time < 300):
        return _instruments_cache

    data = _get("/v1/product", {"order": "asc", "orderBy": "createdAt"})
    products = data.get("data", [])

    instruments = []
    product_id_map = {}

    for product in products:
        if product.get("status") != "ACTIVE":
            continue

        ticker = product.get("ticker", "")
        display_ticker = product.get("displayTicker", "")
        base = product.get("baseTokenName", "")
        quote = product.get("quoteTokenName", "")
        tick_size = float(product.get("tickSize", "1"))
        lot_size = float(product.get("lotSize", "1"))

        # Build product_id map (symbol -> product_id)
        product_id_map[ticker] = product.get("id")

        instruments.append({
            "symbol": ticker,
            "inst_id": product.get("id"),
            "base": base,
            "quote": quote,
            "displayTicker": display_ticker,
            "tickSize": tick_size,
            "contractSize": lot_size,
            "fundingIntervalHours": 1,  # Ethereal funding is 1-hour
        })

    _instruments_cache = instruments
    _instruments_cache_time = current_time
    _product_id_map = product_id_map
    _product_id_map_time = current_time

    return instruments


def _get_product_id(symbol: str) -> Optional[str]:
    """Get product_id for a symbol from cached instruments."""
    global _product_id_map, _product_id_map_time

    # Refresh map if old or not exists
    if not _product_id_map or (time.time() - _product_id_map_time > 300):
        get_instruments()

    return _product_id_map.get(symbol) if _product_id_map else None


def get_funding() -> Dict[str, Dict[str, float]]:
    """Get current funding rates.

    Returns:
        Dict mapping symbol to funding info (rate is 1h rate)
    """
    instruments = get_instruments()
    funding_map = {}

    for inst in instruments:
        symbol = inst["symbol"]

        try:
            # Fetch market data for this product
            product_id = inst["inst_id"]
            data = _get("/v1/product", {"order": "asc", "orderBy": "createdAt"})
            products = data.get("data", [])

            for product in products:
                if product.get("id") == product_id:
                    funding_rate_1h = float(product.get("fundingRate1h", "0"))
                    funding_map[symbol] = {
                        "fundingRate": funding_rate_1h,
                        "fundingIntervalHours": 1,
                    }
                    break
        except Exception as e:
            print(f"Warning: Could not get funding for {symbol}: {e}", file=sys.stderr)
            continue

    return funding_map


def get_mark_prices(limit: int = 20) -> Dict[str, Dict[str, float]]:
    """Get mark prices for instruments.

    Args:
        limit: Maximum number of instruments to fetch prices for

    Returns:
        Dict mapping symbol to price info (markPrice, indexPrice, lastPrice)

    Note: oraclePrice is the mark price from Pyth oracle
    """
    instruments = get_instruments()
    result = {}

    # Limit the number of instruments to avoid excessive API calls
    for inst in instruments[:limit]:
        product_id = inst["inst_id"]
        symbol = inst["symbol"]

        try:
            data = _get("/v1/product/market-price", {"productIds": product_id})
            prices = data.get("data", [])

            if prices:
                p = prices[0]
                oracle_price = float(p.get("oraclePrice", 0))
                bid_price = float(p.get("bestBidPrice", 0))
                ask_price = float(p.get("bestAskPrice", 0))
                price_24h_ago = float(p.get("price24hAgo", 0))

                result[symbol] = {
                    "markPrice": oracle_price,  # oraclePrice is the mark price
                    "indexPrice": oracle_price,  # Same as mark price (Pyth oracle)
                    "lastPrice": (bid_price + ask_price) / 2.0 if bid_price > 0 and ask_price > 0 else oracle_price,
                }
        except Exception as e:
            print(f"Warning: Could not get price for {symbol}: {e}", file=sys.stderr)
            continue

    return result


def get_orderbook(symbol: str, limit: int = 20) -> Dict[str, float]:
    """Get orderbook for a specific instrument.

    Args:
        symbol: Market symbol (e.g., "BTCUSD", "ETHUSD")
        limit: Number of price levels to return (default 20)

    Returns:
        Dict with top bid, ask, and mid price

    Note: Ethereal orderbooks are only available via WebSocket (BOOK_DEPTH/L2Book).
    This function uses bestBid/bestAsk from market-price endpoint as a top-level fallback.
    """
    product_id = _get_product_id(symbol)

    if not product_id:
        return {"bid": 0.0, "ask": 0.0, "mid": 0.0}

    try:
        data = _get("/v1/product/market-price", {"productIds": product_id})
        prices = data.get("data", [])

        if prices:
            p = prices[0]
            bid = float(p.get("bestBidPrice", 0))
            ask = float(p.get("bestAskPrice", 0))
            mid = (bid + ask) / 2.0 if (bid > 0 and ask > 0) else 0.0

            return {
                "bid": bid,
                "ask": ask,
                "mid": mid,
            }

    except Exception as e:
        print(f"Error fetching orderbook for {symbol}: {e}", file=sys.stderr)

    return {"bid": 0.0, "ask": 0.0, "mid": 0.0}


if __name__ == "__main__":
    import sys

    # Quick test
    print("Testing Ethereal connector...")
    instruments = get_instruments()
    print(f"Instruments: {len(instruments)}")
    print(f"First 3 instruments: {instruments[:3]}")

    print("\nTesting funding rates...")
    funding = get_funding()
    print(f"Funding entries: {len(funding)}")
    print(f"Sample funding: {list(funding.items())[:3]}")

    print("\nTesting mark prices (limited to 5)...")
    prices = get_mark_prices(limit=5)
    print(f"Mark prices: {len(prices)}")
    print(f"Sample mark prices: {prices}")

    print("\nTesting orderbook for BTCUSD...")
    ob = get_orderbook("BTCUSD")
    print(f"Orderbook BTCUSD: {ob}")

    print("\nTesting orderbook for ETHUSD...")
    ob = get_orderbook("ETHUSD")
    print(f"Orderbook ETHUSD: {ob}")
