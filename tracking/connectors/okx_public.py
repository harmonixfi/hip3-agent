"""OKX public connector for market data.

Functions: get_instruments, get_funding, get_mark_prices, get_orderbook
"""

from __future__ import annotations

import sys
import time
from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import json


BASE_URL = "https://www.okx.com/api/v5/public"


def _get(path: str, params: Optional[Dict[str, str]] = None) -> dict:
    """Make GET request to OKX public API.

    If path starts with '/', it's relative to BASE_URL.
    If path starts with 'http', it's an absolute URL.
    Otherwise, it's appended to BASE_URL.
    """
    if path.startswith('/market/'):
        # Use market endpoint base
        url = "https://www.okx.com/api/v5" + path
    elif path.startswith('/'):
        url = BASE_URL + path
    else:
        url = BASE_URL + "/" + path

    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw)


def get_instruments() -> List[Dict[str, str]]:
    """Get list of SWAP (perpetual) instruments."""
    data = _get("/instruments", {"instType": "SWAP"})
    instruments = data.get("data", [])
    out = []
    for inst in instruments:
        inst_id = inst.get("instId", "")
        if not inst_id:
            continue
        parts = inst_id.split("-")
        base = parts[0] if len(parts) >= 1 else None
        quote = parts[1] if len(parts) >= 2 else None
        out.append(
            {
                "instId": inst_id,
                "symbol": inst_id,  # e.g., "BTC-USDT-SWAP"
                "base": base,
                "quote": quote,
                "tickSize": float(inst.get("tickSz") or 0),
                "contractSize": float(inst.get("ctMult") or 0),
                # OKX swaps are typically 8h. API does not reliably return interval per instrument.
                "fundingIntervalHours": 8,
                "raw": inst,
            }
        )
    return out


def get_spot_instruments() -> List[Dict[str, str]]:
    """Get list of SPOT instruments."""
    data = _get("/instruments", {"instType": "SPOT"})
    instruments = data.get("data", [])
    return [
        {
            "instId": inst.get("instId"),
            "symbol": inst.get("instId"),  # e.g., "BTC-USDT"
            "base": inst.get("instId", "").split("-")[0],
            "quote": inst.get("instId", "").split("-")[1] if "-" in inst.get("instId", "") else None,
            "tickSize": float(inst.get("tickSz") or 0),
            "contractSize": float(inst.get("lotSz") or 0),  # Minimum order size for spot
            "fundingIntervalHours": 0,  # No funding for spot
        }
        for inst in instruments
        if inst.get("instId", "")
    ]


def get_funding(limit: int = None) -> Dict[str, Dict[str, float]]:
    """Get current funding rates for SWAP instruments.

    OKX /funding-rate returns:
    - fundingRate: decimal per interval (e.g. 0.0001)
    - nextFundingTime: epoch ms

    Returns mapping: instId -> {fundingRate, nextFundingTime}
    """
    instruments = get_instruments()
    out: Dict[str, Dict[str, float]] = {}

    if limit:
        instruments = instruments[:limit]

    for inst in instruments:
        inst_id = inst["instId"]
        try:
            data = _get("/funding-rate", {"instId": inst_id})
            if data.get("data"):
                d0 = data["data"][0]
                out[inst_id] = {
                    "fundingRate": float(d0.get("fundingRate", 0) or 0),
                    "nextFundingTime": float(d0.get("nextFundingTime", 0) or 0),
                }
            time.sleep(0.05)
        except Exception as e:
            print(f"WARNING: Failed to get funding for {inst_id}: {e}", file=sys.stderr)

    return out


def get_mark_prices() -> Dict[str, Dict[str, float]]:
    """Get mark price and index price for all SWAP instruments."""
    data = _get("/mark-price", {"instType": "SWAP"})
    prices = data.get("data", [])
    result = {}
    for item in prices:
        inst_id = item.get("instId", "")
        result[inst_id] = {
            "markPrice": float(item.get("markPx", 0)),
            "indexPrice": float(item.get("idxPx", 0)),
            "lastPrice": float(item.get("last", 0)),
        }
    return result


def get_spot_tickers() -> Dict[str, Dict[str, float]]:
    """Get ticker (last/bid/ask) for all SPOT instruments.

    Uses the /market/tickers endpoint which provides last, bid, ask, and volume
    without needing individual orderbook calls.
    """
    # Note: tickers endpoint is under /market/, not /public/
    url = "/market/tickers"
    data = _get(url, {"instType": "SPOT"})
    tickers = data.get("data", [])
    result = {}
    for item in tickers:
        inst_id = item.get("instId", "")
        last = float(item.get("last", 0))
        bid = float(item.get("bidPx", 0))
        ask = float(item.get("askPx", 0))
        mid = (bid + ask) / 2.0 if (bid and ask) else last

        result[inst_id] = {
            "lastPrice": last,
            "bid": bid,
            "ask": ask,
            "mid": mid,
        }
    return result


def get_orderbook(symbol: str, limit: int = 20) -> Dict[str, float]:
    """Get orderbook for a specific instrument (top bids/asks)."""
    # Note: orderbook uses /market endpoint, not /public
    url = BASE_URL.replace("/public", "/market") + "/books"
    if symbol:
        url = url + "?" + urllib.parse.urlencode({"instId": symbol, "sz": str(limit)})
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)

    orderbook = data.get("data", [{}])[0]

    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])

    top_bid = float(bids[0][0]) if bids else 0.0
    top_ask = float(asks[0][0]) if asks else 0.0
    mid = (top_bid + top_ask) / 2.0 if (top_bid and top_ask) else 0.0

    return {
        "bid": top_bid,
        "ask": top_ask,
        "mid": mid,
    }


if __name__ == "__main__":
    # Quick test
    print("Testing OKX connector...")
    print("Instruments:", len(get_instruments()))
    print("Funding entries:", len(get_funding()))
    print("Mark prices:", len(get_mark_prices()))
    print("Orderbook BTC-USDT-SWAP:", get_orderbook("BTC-USDT-SWAP"))
    print("\n--- SPOT ---")
    print("Spot instruments:", len(get_spot_instruments()))
    print("Spot tickers:", len(get_spot_tickers()))
    # Sample spot ticker
    tickers = get_spot_tickers()
    if tickers:
        sample = list(tickers.keys())[0]
        print(f"Sample spot ticker ({sample}):", tickers[sample])
