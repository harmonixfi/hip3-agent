"""Hyperliquid -> DB v3 writer (append-only, idempotent).

Writes:
- instruments_v3 (upsert-ish via INSERT OR REPLACE on PK)
- prices_v3 (INSERT OR IGNORE on PK)
- funding_v3 (INSERT OR IGNORE on PK)

Supports both PERP and SPOT instruments.
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
    """Insert or update Hyperliquid perp instruments."""
    sql = """
    INSERT OR REPLACE INTO instruments_v3(
      venue, inst_id, base, quote, contract_type, symbol_key, symbol_base,
      raw_symbol, specs_json, status, created_at_ms, updated_at_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now_ms = int(time.time() * 1000)
    vals = []
    for r in inst_rows:
        # Hyperliquid symbols are like "BTC", "ETH" (base only)
        raw_symbol = r["symbol"]
        base = raw_symbol
        quote = "USD"  # Hyperliquid perps are USD-quoted

        symbol_key = f"{base}:USD"
        symbol_base = base

        specs = {
            "szDecimals": r.get("szDecimals", 3),
        }

        vals.append(
            (
                "hyperliquid",
                raw_symbol,  # Use symbol as inst_id
                base,
                quote,
                "PERP",
                symbol_key,
                symbol_base,
                raw_symbol,
                json.dumps(specs, separators=(",", ":"), sort_keys=True),
                r.get("status", "OPEN"),
                now_ms,  # created_at_ms
                now_ms,  # updated_at_ms
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def upsert_spot_instruments(con: sqlite3.Connection, inst_rows: List[Dict]) -> int:
    """Insert or update Hyperliquid spot instruments."""
    sql = """
    INSERT OR REPLACE INTO instruments_v3(
      venue, inst_id, base, quote, contract_type, symbol_key, symbol_base,
      raw_symbol, specs_json, status, created_at_ms, updated_at_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now_ms = int(time.time() * 1000)
    vals = []
    for r in inst_rows:
        base = r["symbol"]
        quote = r.get("quote", "USDC")
        pair_name = r.get("pair_name", f"{base}/{quote}")

        symbol_key = f"{base}:{quote}"
        symbol_base = base

        specs = {
            "szDecimals": r.get("szDecimals", 0),
            "isCanonical": r.get("isCanonical", False),
            "pairName": pair_name,
        }

        vals.append(
            (
                "hyperliquid",
                f"SPOT:{base}",  # Prefix to avoid PK collision with perps
                base,
                quote,
                "SPOT",
                symbol_key,
                symbol_base,
                pair_name,
                json.dumps(specs, separators=(",", ":"), sort_keys=True),
                "OPEN",
                now_ms,
                now_ms,
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def insert_prices(con: sqlite3.Connection, rows: List[Dict]) -> int:
    """Insert price data (mid, bid/ask, mark)."""
    sql = """
    INSERT OR IGNORE INTO prices_v3(
      venue, inst_id, ts, bid, ask, mid, mark, last, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    vals = []
    for r in rows:
        vals.append(
            (
                "hyperliquid",
                r["instId"],
                int(r["ts"]),
                r.get("bid"),
                r.get("ask"),
                r.get("mid"),
                r.get("mark"),
                r.get("last"),
                r.get("source", "hyperliquid:all_mids"),
                json.dumps(r.get("quality_flags", {}), separators=(",", ":")),
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def ensure_position_instruments(con: sqlite3.Connection, inst_ids: List[Dict]) -> int:
    """Ensure instruments_v3 rows exist for position leg inst_ids (FK constraint).

    Each dict: {inst_id, contract_type, base, quote}
    Uses INSERT OR IGNORE to be idempotent.
    """
    sql = """
    INSERT OR IGNORE INTO instruments_v3(
      venue, inst_id, base, quote, contract_type, symbol_key, symbol_base,
      raw_symbol, specs_json, status, created_at_ms, updated_at_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now_ms = int(time.time() * 1000)
    vals = []
    for r in inst_ids:
        base = r["base"]
        quote = r.get("quote", "USDC")
        vals.append((
            "hyperliquid", r["inst_id"], base, quote,
            r.get("contract_type", "PERP"),
            f"{base}:{quote}", base, r["inst_id"],
            "{}", "OPEN", now_ms, now_ms,
        ))
    if vals:
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
                "hyperliquid",
                r["instId"],
                int(r["ts"]),
                float(r["fundingRate"]),
                r.get("interval_hours", 1),  # Hyperliquid funding is hourly
                r.get("source", "hyperliquid:funding_rate"),
                json.dumps(r.get("quality_flags", {}), separators=(",", ":")),
            )
        )
    con.executemany(sql, vals)
    return len(vals)
