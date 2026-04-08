#!/usr/bin/env python3
"""Pull Felix Equities market prices and write to prices_v3.

Public endpoint — no JWT required.

Run order:
    source .arbit_env
    .venv/bin/python scripts/pull_felix_market.py   # before pipeline_hourly.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"
FELIX_PRICES_URL = (
    "https://spot-equities-proxy.white-star-bc1e.workers.dev/v1/market/prices"
)
_HEADERS = {
    "Accept": "*/*",
    "Origin": "https://trade.usefelix.xyz",
    "Referer": "https://trade.usefelix.xyz/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/146.0.0.0 Safari/537.36"
    ),
}


def fetch_felix_prices() -> list[dict]:
    """Fetch all Felix equity prices from the public market endpoint."""
    req = urllib.request.Request(FELIX_PRICES_URL, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        payload = json.loads(resp.read())
    return payload["data"]


def write_to_prices_v3(
    con: sqlite3.Connection, prices: list[dict], ts_ms: int
) -> int:
    """Write Felix prices into prices_v3.

    Mapping: Felix API symbol ``MUon`` → ``inst_id = "MUon/USDC"``.
    This matches the inst_id convention used in positions.json (``{symbol}/USDC``)
    and ensures ``_is_spot_leg()`` in carry.py detects the "/" correctly.
    """
    sql = """
    INSERT INTO prices_v3 (venue, inst_id, ts, mid, source)
    VALUES (?, ?, ?, ?, ?)
    ON CONFLICT (venue, inst_id, ts) DO UPDATE SET mid = excluded.mid
    """
    count = 0
    for item in prices:
        symbol = (item.get("symbol") or "").strip()
        price_str = item.get("price")
        if not symbol or not price_str:
            continue
        try:
            mid = float(price_str)
        except (ValueError, TypeError):
            continue
        inst_id = f"{symbol}/USDC"  # e.g. "MUon" → "MUon/USDC"
        con.execute(sql, ("felix", inst_id, ts_ms, mid, "felix:market_price"))
        count += 1
    con.commit()
    return count


def main() -> None:
    ts_ms = int(time.time() * 1000)
    prices = fetch_felix_prices()
    con = sqlite3.connect(str(DB_PATH))
    try:
        count = write_to_prices_v3(con, prices, ts_ms)
    finally:
        con.close()

    print(f"Felix market: {len(prices)} instruments fetched, {count} prices → prices_v3")
    # Spot-check managed positions
    for item in prices:
        if item.get("symbol") in ("MUon", "MSTRon"):
            print(f"  OK  {item['symbol']}/USDC  mid={item['price']}")


if __name__ == "__main__":
    main()
