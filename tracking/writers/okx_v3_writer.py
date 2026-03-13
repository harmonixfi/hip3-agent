"""OKX -> DB v3 writer (append-only, idempotent).

Writes:
- instruments_v3 (upsert-ish via INSERT OR REPLACE on PK)
- prices_v3 / funding_v3 (INSERT OR IGNORE on PK)

Note: time-series is append-only. Instruments can be replaced when metadata changes.
"""

from __future__ import annotations

import json
import time
import sqlite3
from pathlib import Path
from typing import Dict, List

from tracking.normalize import parse_okx_inst_id


def connect(db_path: Path) -> sqlite3.Connection:
    # Use a generous timeout + WAL so concurrent readers don't block writers.
    con = sqlite3.connect(str(db_path), timeout=60)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 60000")
    return con


def upsert_instruments(con: sqlite3.Connection, inst_rows: List[Dict]) -> int:
    sql = """
    INSERT OR REPLACE INTO instruments_v3(
      venue, inst_id, base, quote, contract_type, symbol_key, symbol_base,
      raw_symbol, specs_json, status, created_at_ms, updated_at_ms
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    now_ms = int(time.time() * 1000)
    vals = []
    for r in inst_rows:
        ni = parse_okx_inst_id(r["instId"], r["instType"])
        specs = {
            "tickSize": r.get("tickSize"),
            "contractSize": r.get("contractSize"),
        }
        vals.append(
            (
                "okx",
                ni.inst_id,
                ni.base,
                ni.quote,
                ni.contract_type,
                ni.symbol_key,
                ni.symbol_base,
                ni.raw_symbol,
                json.dumps(specs, separators=(",", ":"), sort_keys=True),
                r.get("status"),
                r.get("created_at_ms"),
                now_ms,
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def insert_prices(con: sqlite3.Connection, rows: List[Dict]) -> int:
    sql = """
    INSERT OR IGNORE INTO prices_v3(
      venue, inst_id, ts, bid, ask, last, mid, mark, index_price, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    vals = []
    for r in rows:
        vals.append(
            (
                "okx",
                r["instId"],
                int(r["ts"]),
                r.get("bid"),
                r.get("ask"),
                r.get("last"),
                r.get("mid"),
                r.get("mark"),
                r.get("index"),
                r.get("source"),
                json.dumps(r.get("quality_flags") or {}, separators=(",", ":"), sort_keys=True),
            )
        )
    con.executemany(sql, vals)
    return len(vals)


def insert_funding(con: sqlite3.Connection, rows: List[Dict]) -> int:
    sql = """
    INSERT OR IGNORE INTO funding_v3(
      venue, inst_id, ts, funding_rate, interval_hours, next_funding_ts, source, quality_flags
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """
    vals = []
    for r in rows:
        vals.append(
            (
                "okx",
                r["instId"],
                int(r["ts"]),
                float(r["funding_rate"]),
                float(r.get("interval_hours") or 8),
                int(r.get("next_funding_ts") or 0) or None,
                r.get("source"),
                json.dumps(r.get("quality_flags") or {}, separators=(",", ":"), sort_keys=True),
            )
        )
    con.executemany(sql, vals)
    return len(vals)
