"""Paradex public connector for market data (REST + WebSocket).

Functions: get_instruments, get_funding, get_mark_prices, get_orderbook
"""

from __future__ import annotations

import sys
import time
from typing import Dict, List, Optional
import urllib.request
import urllib.parse
import json

BASE_URL = "https://api.prod.paradex.trade/v1"
WS_URL = "wss://ws.api.prod.paradex.trade/v1"


def _get(path: str, params: Optional[Dict[str, str]] = None, timeout: int = 30) -> dict:
    """Make GET request to Paradex API."""
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


def get_instruments() -> List[Dict[str, str]]:
    """Get list of perps/markets from Paradex API."""
    try:
        data = _get("/markets")
        if data and isinstance(data, dict):
            if "results" in data and isinstance(data["results"], list):
                return data["results"]
            elif "data" in data and isinstance(data["data"], list):
                return data["data"]
            elif "instruments" in data and isinstance(data["instruments"], list):
                return data["instruments"]
    except Exception as e:
        print(f"Error fetching instruments: {e}", file=sys.stderr)
    
    return []


def get_funding() -> Dict[str, Dict[str, any]]:
    """
    Get current funding rates from Paradex WebSocket API.
    
    Uses the public 'funding_data' WebSocket channel.
    
    Returns:
        Dict mapping symbol -> {
            'funding_rate': float (per-funding-interval rate, usually 8h),
            'funding_interval_hours': int,
            'next_funding_ts': int (epoch_ms, if available),
        }
    
    Units:
        - funding_rate is provided as a decimal per-funding-period (typically 8 hours)
        - For example, -0.0107034 means -1.07% per 8-hour interval
        - APR = funding_rate * (24 / funding_interval_hours) * 365
    """
    try:
        import websocket
        import ssl
        import threading
        import time
    except ImportError:
        print("ERROR: websocket-client library required for funding data", file=sys.stderr)
        return {}
    
    result = {}
    collected = set()
    running = [True]
    
    def on_message(ws, message):
        if not running[0]:
            return
        try:
            data = json.loads(message)
            if data.get('method') == 'subscription' and "params" in data:
                d = data["params"]["data"]
                market = d.get('market')
                if market and market not in collected:
                    funding_rate = d.get('funding_rate')
                    if funding_rate is not None:
                        # Parse funding_rate as decimal (not bps or scaled int)
                        rate = float(funding_rate)
                        interval = int(d.get('funding_period_hours', 8))
                        
                        result[market] = {
                            'funding_rate': rate,
                            'funding_interval_hours': interval,
                            'next_funding_ts': None,  # Not provided in WebSocket data
                        }
                        collected.add(market)
                        sys.stdout.write(f".")
                        sys.stdout.flush()
        except Exception as e:
            print(f"ERROR parsing funding message: {e}", file=sys.stderr)
    
    def on_error(ws, error):
        pass  # Silent on errors
    
    def on_close(ws, *args):
        running[0] = False
    
    def on_open(ws):
        ws.send(json.dumps({
            "id": 1,
            "jsonrpc": "2.0",
            "method": "subscribe",
            "params": {"channel": "funding_data"}
        }))
    
    try:
        ws = websocket.WebSocketApp(
            WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        # Run in a thread with timeout
        def run_ws():
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        thread = threading.Thread(target=run_ws)
        thread.daemon = True
        thread.start()
        
        # Wait for 15 seconds to collect data
        start = time.time()
        while running[0] and time.time() - start < 15:
            time.sleep(0.1)
        
        # Close connection
        running[0] = False
        ws.close()
        thread.join(timeout=2)
        
    except Exception as e:
        print(f"ERROR connecting to WebSocket: {e}", file=sys.stderr)
    
    print(f" Collected {len(result)} funding rates", file=sys.stderr)
    return result


def get_orderbook(symbol: str, depth: int = 15, frequency: str = "100ms", timeout_s: int = 3) -> Dict[str, float]:
    """Get top-of-book (bid/ask/mid) for a market via Paradex public WebSocket.

    Paradex orderbook snapshots are published on channels of the form:
      order_book.{market}.snapshot@15@100ms

    The payload contains `inserts/updates/deletes` rather than a simple bids/asks array.
    We compute best bid/ask from `inserts`.

    Returns:
      {bid, ask, mid}
    """
    try:
        import websocket
        import ssl
        import threading
    except ImportError:
        print("ERROR: websocket-client library required for orderbook data", file=sys.stderr)
        return {"bid": 0.0, "ask": 0.0, "mid": 0.0}

    channel = f"order_book.{symbol}.snapshot@{depth}@{frequency}"

    result = {"bid": 0.0, "ask": 0.0, "mid": 0.0}
    running = [True]

    def on_open(ws):
        ws.send(
            json.dumps(
                {
                    "id": 1,
                    "jsonrpc": "2.0",
                    "method": "subscribe",
                    "params": {"channel": channel},
                }
            )
        )

    def on_message(ws, message):
        if not running[0]:
            return
        try:
            data = json.loads(message)
            if data.get("method") != "subscription":
                return
            d = data.get("params", {}).get("data", {})
            inserts = d.get("inserts", []) or []

            best_bid = 0.0
            best_ask = 0.0
            for it in inserts:
                side = it.get("side")
                px = float(it.get("price", 0) or 0)
                if side == "BUY":
                    if px > best_bid:
                        best_bid = px
                elif side == "SELL":
                    if best_ask == 0.0 or px < best_ask:
                        best_ask = px

            mid = (best_bid + best_ask) / 2.0 if (best_bid and best_ask) else 0.0
            result.update({"bid": best_bid, "ask": best_ask, "mid": mid})
            running[0] = False
            ws.close()
        except Exception:
            # ignore parse errors
            return

    def on_error(ws, error):
        running[0] = False

    def on_close(ws, *args):
        running[0] = False

    ws = websocket.WebSocketApp(WS_URL, on_open=on_open, on_message=on_message, on_error=on_error, on_close=on_close)

    def run_ws():
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE}, ping_interval=5, ping_timeout=3)

    thread = threading.Thread(target=run_ws)
    thread.daemon = True
    thread.start()

    start = time.time()
    while running[0] and time.time() - start < timeout_s:
        time.sleep(0.05)

    try:
        ws.close()
    except Exception:
        pass
    thread.join(timeout=1)

    return result


def get_mark_prices(limit: int = 25) -> Dict[str, Dict[str, float]]:
    """Get price proxies for markets.

    Paradex REST /markets is static and does NOT contain last/mark/index prices.
    We therefore derive prices from the WS orderbook snapshot mid.

    Args:
      limit: number of markets to sample (to avoid long WS loops)

    Returns dict: symbol -> {markPrice, indexPrice, lastPrice, bid, ask, mid}
    """
    instruments = get_instruments()
    result: Dict[str, Dict[str, float]] = {}

    for inst in instruments[:limit]:
        sym = inst.get("symbol")
        if not sym:
            continue
        ob = get_orderbook(sym)
        mid = ob.get("mid", 0.0)
        if mid and mid > 0:
            result[sym] = {
                "markPrice": mid,
                "indexPrice": mid,
                "lastPrice": mid,
                "bid": ob.get("bid"),
                "ask": ob.get("ask"),
                "mid": mid,
            }

    return result


if __name__ == "__main__":
    import sys
    from pathlib import Path
    
    ROOT = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(ROOT / "tracking" / "connectors"))
    
    # Quick test
    print("Testing Paradex connector...")
    print("Instruments:", len(get_instruments()))
    funding = get_funding()
    print("Funding entries:", len(funding))
    if funding:
        print("Sample funding:", list(funding.items())[:3])
    print("Mark prices:", len(get_mark_prices()))
