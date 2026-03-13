"""Paradex -> DB v3 writer (append-only, idempotent).

Writes:
- instruments_v3 (upsert-ish via INSERT OR REPLACE on PK)
- prices_v3 (INSERT OR IGNORE on PK)
- funding_v3 (INSERT OR IGNORE on PK)

Note: Paradex instruments are perps only.
"""

from __future__ import annotations

import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def upsert_instruments(con: sqlite3.Connection, inst_rows: List[Dict]) -> int:
    """Insert or update Paradex perp instruments."""
    sql = """
    INSERT OR REPLACE INTO instruments_v3(
      venue, inst_id, base, quote, contract_type, symbol_key, symbol_base,
      raw_symbol, specs_json, status, created_at_ms, updated_at_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now_ms = int(time.time() * 1000)
    vals = []
    for r in inst_rows:
        # Paradex symbols are like "BTC-USD-PERP"
        raw_symbol = r["symbol"]
        parts = raw_symbol.split("-")
        base = parts[0] if len(parts) > 0 else raw_symbol
        quote = parts[1] if len(parts) > 1 else "USD"

        symbol_key = f"{base}:{quote}"
        symbol_base = base

        specs = {
            "priceTickSize": r.get("price_tick_size", 1.0),
            "orderSizeIncrement": r.get("order_size_increment", 1.0),
            "minOrderSize": r.get("min_order_size", 1.0),
        }

        vals.append(
            (
                "paradex",
                raw_symbol,  # Use symbol as inst_id
                base,
                quote,
                "PERP",
                symbol_key,
                symbol_base,
                raw_symbol,
                json.dumps(specs, separators=(",", ":"), sort_keys=True),
                r.get("status", "ACTIVE"),
                now_ms,  # created_at_ms
                now_ms,  # updated_at_ms
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def insert_prices(con: sqlite3.Connection, rows: List[Dict]) -> int:
    """Insert price data from orderbook mid-price."""
    sql = """
    INSERT OR IGNORE INTO prices_v3(
      venue, inst_id, ts, mid, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?)
    """
    vals = []
    for r in rows:
        vals.append(
            (
                "paradex",
                r["instId"],
                int(r["ts"]),
                r.get("mid"),
                r.get("source", "paradex:orderbook_mid"),
                json.dumps(r.get("quality_flags", {}), separators=(",", ":")),
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def insert_funding(con: sqlite3.Connection, rows: List[Dict]) -> int:
    """Insert funding rate data."""
    sql = """
    INSERT OR IGNORE INTO funding_v3(
      venue, inst_id, ts, funding_rate, interval_hours, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    vals = []
    for r in rows:
        vals.append(
            (
                "paradex",
                r["instId"],
                int(r["ts"]),
                float(r["fundingRate"]),
                r.get("interval_hours", 8),
                r.get("source", "paradex:funding_rate"),
                json.dumps(r.get("quality_flags", {}), separators=(",", ":")),
            )
        )
    con.executemany(sql, vals)
    return len(vals)
