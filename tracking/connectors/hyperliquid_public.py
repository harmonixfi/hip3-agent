"""Hyperliquid public connector for market data.

Functions: get_instruments, get_spot_instruments, get_funding, get_mark_prices, get_orderbook
"""

from __future__ import annotations

import re
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


_TRAILING_DIGITS_RE = re.compile(r"^([A-Z]{2,})(\d+)$")


def _normalize_spot_base(raw_name: str) -> str:
    """Strip trailing version digits from Hyperliquid spot token names.

    Hyperliquid wraps some tokens with version suffixes (AAVE0, LINK0, XMR1).
    For matching against perp funding symbols, return the base without the suffix.
    """
    m = _TRAILING_DIGITS_RE.match(raw_name)
    if m:
        return m.group(1)
    return raw_name


def get_spot_instruments() -> List[Dict[str, str]]:
    """Get list of spot instruments using /info endpoint with type=spotMeta.

    Returns list of dicts with keys: symbol (base, normalized), raw_symbol (original),
    pair_name (e.g. "PURR/USDC"), quote, szDecimals, type, isCanonical.
    """
    data = _get("/info", {"type": "spotMeta"})
    tokens = {t["index"]: t for t in data.get("tokens", [])}
    universe = data.get("universe", [])

    instruments = []
    for mkt in universe:
        pair_name = mkt.get("name", "")
        # Names like "PURR/USDC" or "@1" (non-canonical index references)
        if "/" in pair_name:
            raw_base, quote = pair_name.split("/", 1)
        else:
            # Non-canonical name like "@1" — resolve from tokens list
            token_ids = mkt.get("tokens", [])
            base_token = tokens.get(token_ids[0]) if token_ids else None
            raw_base = base_token["name"] if base_token else pair_name
            quote_token = tokens.get(token_ids[1]) if len(token_ids) > 1 else None
            quote = quote_token["name"] if quote_token else "USDC"

        # Get szDecimals from the base token if available
        token_ids = mkt.get("tokens", [])
        base_token = tokens.get(token_ids[0]) if token_ids else None
        sz_decimals = base_token.get("szDecimals", 0) if base_token else 0

        instruments.append({
            "symbol": _normalize_spot_base(raw_base),
            "raw_symbol": raw_base,
            "pair_name": pair_name,
            "quote": quote,
            "type": "SPOT",
            "szDecimals": sz_decimals,
            "isCanonical": mkt.get("isCanonical", False),
            "index": mkt.get("index"),
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
