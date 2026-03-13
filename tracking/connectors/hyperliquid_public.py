"""Hyperliquid public connector for market data.

Functions: get_instruments, get_funding, get_mark_prices, get_orderbook
"""

from __future__ import annotations

from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import json


BASE_URL = "https://api.hyperliquid.xyz"


def _get(path: str, params: Optional[Dict[str, str]] = None) -> dict:
    """Make POST request to Hyperliquid API (Hyperliquid uses POST for all requests)."""
    url = BASE_URL + path
    payload = json.dumps(params or {})
    req = urllib.request.Request(
        url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "arbit-connector/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def get_instruments() -> List[Dict[str, str]]:
    """Get list of perp instruments using /info endpoint with type=meta."""
    # Hyperliquid uses {type: "meta"} to get market metadata
    data = _get("/info", {"type": "meta"})
    universe = data.get("universe", [])

    instruments = []
    for mkt in universe:
        # Filter out delisted markets
        if mkt.get("isDelisted"):
            continue

        instruments.append({
            "symbol": mkt.get("name"),
            "base": mkt.get("name"),  # Hyperliquid uses the same name for base
            "quote": "USD",  # Hyperliquid is USD-denominated
            "type": "PERP",
            "szDecimals": mkt.get("szDecimals", 0),
            "maxLeverage": mkt.get("maxLeverage", 0),
        })

    return instruments


def get_funding() -> Dict[str, float]:
    """Get current funding rates via metaAndAssetCtxs endpoint.

    Returns:
        Dict mapping symbol to funding rate (as decimal, e.g., 0.0001 for 0.01%)
    """
    # Use metaAndAssetCtxs to get both universe and current funding rates
    data = _get("/info", {"type": "metaAndAssetCtxs"})

    # data[0] is the meta response (universe, marginTables, collateralToken)
    # data[1] is the asset contexts (includes funding, markPx, openInterest, etc.)
    if len(data) < 2:
        return {}

    meta = data[0]
    universe = meta.get("universe", [])
    asset_ctxs = data[1]

    result = {}
    # Universe and asset contexts are aligned by index
    for i, (inst, ctx) in enumerate(zip(universe, asset_ctxs)):
        symbol = inst.get("name")
        if not symbol:
            continue

        funding_str = ctx.get("funding", "0")
        try:
            funding = float(funding_str)
            result[symbol] = funding
        except (ValueError, TypeError):
            continue

    return result


def get_mark_prices() -> Dict[str, Dict[str, float]]:
    """Get mark prices for all perps using /info endpoint with type=allMids."""
    data = _get("/info", {"type": "allMids"})

    result = {}
    for symbol, price_str in data.items():
        try:
            result[symbol] = {
                "midPrice": float(price_str),
            }
        except (ValueError, TypeError):
            continue

    return result


def get_orderbook(symbol: str, limit: int = 20) -> Dict[str, float]:
    """Get orderbook for a symbol using /l2Book endpoint."""
    data = _get("/l2Book", {"coin": symbol})

    # Hyperliquid returns format: {levels: [[px, sz, n], ...], levels2: [[px, sz, n], ...]}
    # levels = bids (sorted descending), levels2 = asks (sorted ascending)
    levels = data.get("levels", [])
    levels2 = data.get("levels2", [])

    # Get best bid and ask (first element)
    best_bid = float(levels[0][0]) if levels and len(levels[0]) > 0 else 0.0
    best_ask = float(levels2[0][0]) if levels2 and len(levels2[0]) > 0 else 0.0

    mid = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0.0

    return {
        "bid": best_bid,
        "ask": best_ask,
        "mid": mid,
    }


if __name__ == "__main__":
    # Quick test
    print("Testing Hyperliquid connector...")
    print("Instruments:", len(get_instruments()))
    print("Funding entries:", len(get_funding()))
    print("Mark prices:", len(get_mark_prices()))
    print("Orderbook BTC:", get_orderbook("BTC"))
