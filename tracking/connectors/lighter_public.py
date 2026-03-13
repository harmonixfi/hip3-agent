"""Lighter public connector for market data.

Functions: get_instruments, get_funding, get_mark_prices, get_orderbook

Note: Lighter's REST API has limitations:
- Funding rates: Not available via REST (requires WebSocket market_stats channel)
- Mark/Index/Last prices: Available via orderBookDetails endpoint (requires per-market call)
- Orderbooks: Available via orderBookOrders endpoint

This connector efficiently fetches available data from REST endpoints.
"""

from __future__ import annotations

from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import json
import time


BASE_URL = "https://mainnet.zklighter.elliot.ai"

# Cache for instruments to avoid repeated API calls
_instruments_cache = None
_instruments_cache_time = 0


def _get(path: str, params: Optional[Dict[str, str]] = None, timeout: int = 30) -> dict:
    """Make GET request to Lighter API."""
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
    """Get list of perp instruments from Lighter.

    Args:
        force_refresh: Force refresh of cached instruments

    Returns:
        List of instrument dicts with symbol, inst_id, base, quote, etc.
    """
    global _instruments_cache, _instruments_cache_time

    # Use cache if available and less than 5 minutes old
    current_time = time.time()
    if not force_refresh and _instruments_cache and (current_time - _instruments_cache_time < 300):
        return _instruments_cache

    data = _get("/api/v1/orderBooks")
    order_books = data.get("order_books", [])

    instruments = []
    for book in order_books:
        if book.get("market_type") == "perp" and book.get("status") == "active":
            price_decimals = book.get("supported_price_decimals", 2)
            tick_size = float(10 ** (-price_decimals)) if price_decimals >= 0 else 0.01
            instruments.append({
                "symbol": book.get("symbol"),
                "inst_id": str(book.get("market_id")),
                "base": book.get("symbol"),
                "quote": "USD",  # Lighter perps are USD-denominated
                "tickSize": tick_size,
                "contractSize": 1.0,
                "fundingIntervalHours": 1,  # Lighter funding is 1-hour
            })

    _instruments_cache = instruments
    _instruments_cache_time = current_time
    return instruments


def _get_market_id(symbol: str) -> Optional[str]:
    """Get market_id for a symbol from cached instruments."""
    instruments = get_instruments()
    for inst in instruments:
        if inst["symbol"] == symbol:
            return inst["inst_id"]
    return None


def _get_symbol_for_market_id(market_id: str) -> Optional[str]:
    """Get symbol for a market_id from cached instruments."""
    instruments = get_instruments()
    for inst in instruments:
        if inst["inst_id"] == str(market_id):
            return inst["symbol"]
    return None


def get_funding() -> Dict[str, Dict[str, str]]:
    """Get funding rates.

    Note: Lighter's REST API doesn't provide funding rates directly.
    Funding is available via WebSocket market_stats channel.
    Returns empty dict.
    """
    return {}


def get_mark_prices(limit: int = 20) -> Dict[str, Dict[str, float]]:
    """Get mark prices for instruments.

    Args:
        limit: Maximum number of instruments to fetch prices for (to avoid excessive API calls)

    Returns:
        Dict mapping symbol to price info (last_trade_price)

    Note: This calls orderBookDetails for each market, which can be slow.
    For production, consider using WebSocket market_stats channel instead.
    """
    instruments = get_instruments()
    result = {}

    # Limit the number of instruments to avoid excessive API calls
    for inst in instruments[:limit]:
        market_id = inst["inst_id"]
        symbol = inst["symbol"]

        try:
            data = _get(f"/api/v1/orderBookDetails", {"market_id": market_id})
            details = data.get("order_book_details", [])

            if details:
                d = details[0]
                last_price = float(d.get("last_trade_price", 0))
                result[symbol] = {
                    "lastPrice": last_price,
                    # Use last_price as mark price since Lighter REST doesn't separate them
                    "markPrice": last_price,
                    "indexPrice": last_price,  # No separate index price in REST
                }
        except Exception as e:
            # If we can't get price for one instrument, skip it
            print(f"Warning: Could not get price for {symbol}: {e}", file=sys.stderr)
            continue

    return result


def get_orderbook(symbol: str, limit: int = 20) -> Dict[str, float]:
    """Get orderbook for a specific instrument.

    Args:
        symbol: Market symbol (e.g., "ETH", "BTC")
        limit: Number of price levels to return (default 20)

    Returns:
        Dict with top bid, ask, and mid price
    """
    # Get market_id from cached instruments (efficient)
    market_id = _get_market_id(symbol)

    if not market_id:
        return {"bid": 0.0, "ask": 0.0, "mid": 0.0}

    # Get orderbook orders
    try:
        data = _get(f"/api/v1/orderBookOrders", {"market_id": market_id, "limit": str(limit)})
    except Exception as e:
        print(f"Error fetching orderbook for {symbol}: {e}", file=sys.stderr)
        return {"bid": 0.0, "ask": 0.0, "mid": 0.0}

    # Extract bids and asks
    asks = data.get("asks", [])[:limit]
    bids = data.get("bids", [])[:limit]

    # Handle case where structure might be different
    if not bids and not asks and "order_book_orders" in data:
        order_list = data["order_book_orders"]
        # Parse flat list separated by is_ask flag
        for order in order_list:
            if order.get("is_ask"):
                asks.append(order)
            else:
                bids.append(order)
        # Sort and limit
        asks = sorted(asks, key=lambda x: float(x.get("price", 0)))[:limit]
        bids = sorted(bids, key=lambda x: float(x.get("price", 0)), reverse=True)[:limit]

    top_bid = float(bids[0]["price"]) if bids and len(bids) > 0 else 0.0
    top_ask = float(asks[0]["price"]) if asks and len(asks) > 0 else 0.0
    mid = (top_bid + top_ask) / 2.0 if (top_bid > 0 and top_ask > 0) else 0.0

    return {
        "bid": top_bid,
        "ask": top_ask,
        "mid": mid,
    }


if __name__ == "__main__":
    import sys

    # Quick test
    print("Testing Lighter connector...")
    instruments = get_instruments()
    print(f"Instruments: {len(instruments)}")
    print(f"First 5 instruments: {instruments[:5]}")

    print("\nTesting mark prices (limited to 5)...")
    prices = get_mark_prices(limit=5)
    print(f"Mark prices: {len(prices)}")
    print(f"Sample mark prices: {prices}")

    print("\nTesting funding...")
    funding = get_funding()
    print(f"Funding entries: {len(funding)}")

    print("\nTesting orderbook for ETH...")
    ob = get_orderbook("ETH")
    print(f"Orderbook ETH: {ob}")

    print("\nTesting orderbook for BTC...")
    ob = get_orderbook("BTC")
    print(f"Orderbook BTC: {ob}")
