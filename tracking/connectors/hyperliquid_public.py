"""Hyperliquid public connector for market data.

Functions: get_instruments, get_spot_instruments, get_funding, get_mark_prices, get_orderbook
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse
import json


BASE_URL = "https://api.hyperliquid.xyz"


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> dict:
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


def _perp_instruments_from_meta(dex: str = "") -> List[Dict[str, str]]:
    """Perp universe for one builder DEX. dex '' = first/native perp DEX."""
    payload: Dict[str, Any] = {"type": "meta"}
    if dex:
        payload["dex"] = dex
    data = _get("/info", payload)
    universe = data.get("universe", [])

    instruments = []
    for mkt in universe:
        if mkt.get("isDelisted"):
            continue
        name = mkt.get("name")
        if not name:
            continue
        instruments.append({
            "symbol": name,
            "base": name,
            "quote": "USD",
            "type": "PERP",
            "szDecimals": mkt.get("szDecimals", 0),
            "maxLeverage": mkt.get("maxLeverage", 0),
        })
    return instruments


# HIP-3 builder-deployed perps (e.g. xyz:MU) live on a separate perp DEX from core markets.
_EXTRA_PERP_DEXES_FOR_META_AND_MIDS: tuple[str, ...] = ("xyz",)


def get_instruments() -> List[Dict[str, str]]:
    """Get list of perp instruments: native/first DEX plus HIP-3 DEXes (e.g. xyz:*)."""
    merged: List[Dict[str, str]] = []
    seen: set[str] = set()
    for dex in ("",) + _EXTRA_PERP_DEXES_FOR_META_AND_MIDS:
        for row in _perp_instruments_from_meta(dex):
            sym = row.get("symbol")
            if not sym or sym in seen:
                continue
            seen.add(sym)
            merged.append(row)
    return merged


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
    """Mid prices for perps: first DEX + HIP-3 DEXes (must pass dex or xyz:* keys are missing)."""
    result: Dict[str, Dict[str, float]] = {}
    for dex in ("",) + _EXTRA_PERP_DEXES_FOR_META_AND_MIDS:
        payload: Dict[str, Any] = {"type": "allMids"}
        if dex:
            payload["dex"] = dex
        data = _get("/info", payload)
        if not isinstance(data, dict):
            continue
        for symbol, price_str in data.items():
            try:
                result[symbol] = {"midPrice": float(price_str)}
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


def get_l2book(coin: str) -> Dict[str, float]:
    """Fetch L2 orderbook via /info endpoint (supports spot @index format).

    Uses POST /info {"type":"l2Book","coin":"..."} which works for:
    - Native perps: coin="HYPE"
    - Spot pairs: coin="@107" (universe index from spotMeta)

    Does NOT work for builder dex perps (use allMids with dex= instead).

    Returns {"bid": float, "ask": float, "mid": float} or empty dict on failure.
    """
    try:
        data = _get("/info", {"type": "l2Book", "coin": coin})
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}

    levels = data.get("levels", [])

    # HL L2Book response: {"levels": [[bids...], [asks...]], "coin": "...", "time": ...}
    # Each side is a list of dicts: [{"px": "38.13", "sz": "1.24", "n": 1}, ...]
    best_bid = 0.0
    best_ask = 0.0

    if len(levels) >= 1 and isinstance(levels[0], list) and levels[0]:
        best_bid = float(levels[0][0].get("px", 0))

    if len(levels) >= 2 and isinstance(levels[1], list) and levels[1]:
        best_ask = float(levels[1][0].get("px", 0))

    if best_bid <= 0 and best_ask <= 0:
        return {}

    mid = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else best_bid or best_ask

    return {"bid": best_bid, "ask": best_ask, "mid": mid}


if __name__ == "__main__":
    # Quick test
    print("Testing Hyperliquid connector...")
    print("Instruments:", len(get_instruments()))
    print("Funding entries:", len(get_funding()))
    print("Mark prices:", len(get_mark_prices()))
    print("Orderbook BTC:", get_orderbook("BTC"))
