"""VWAP entry price computation from fills.

Computes average entry price per leg using opening fills only:
- LONG legs: opening fills are side='BUY'
- SHORT legs: opening fills are side='SELL'

Formula: avg_entry = SUM(px * sz) / SUM(sz)

Writes results to pm_entry_prices (INSERT OR REPLACE on leg_id PK)
and updates pm_legs.entry_price.
"""

from __future__ import annotations
import sqlite3
import time
from typing import Any, Dict, List, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def _opening_side(leg_side: str) -> str:
    return "BUY" if leg_side == "LONG" else "SELL"


def compute_entry_prices(
    con: sqlite3.Connection,
    *,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Compute VWAP entry prices for all legs that have fills.
    Processes ALL positions (including CLOSED) for historical analysis.
    Returns list of result dicts.
    """
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        legs = con.execute(
            f"SELECT leg_id, position_id, side FROM pm_legs WHERE position_id IN ({placeholders})",
            position_ids,
        ).fetchall()
    else:
        legs = con.execute("SELECT leg_id, position_id, side FROM pm_legs").fetchall()

    if not legs:
        return []

    now = _now_ms()
    results: List[Dict[str, Any]] = []

    for leg_id, position_id, side in legs:
        opening_side = _opening_side(side)
        row = con.execute(
            "SELECT SUM(px * sz), SUM(sz), COUNT(*), MIN(ts), MAX(ts) FROM pm_fills WHERE leg_id = ? AND side = ?",
            (leg_id, opening_side),
        ).fetchone()

        total_cost = row[0]
        total_qty = row[1]
        fill_count = row[2] or 0
        first_ts = row[3]
        last_ts = row[4]

        if fill_count == 0 or total_qty is None or total_qty <= 0:
            continue

        avg_entry = total_cost / total_qty

        con.execute(
            """INSERT OR REPLACE INTO pm_entry_prices
              (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
               fill_count, first_fill_ts, last_fill_ts, computed_at_ms, method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'VWAP')""",
            (leg_id, position_id, avg_entry, total_qty, total_cost,
             fill_count, first_ts, last_ts, now),
        )
        con.execute("UPDATE pm_legs SET entry_price = ? WHERE leg_id = ?", (avg_entry, leg_id))

        results.append({
            "leg_id": leg_id,
            "position_id": position_id,
            "avg_entry_price": avg_entry,
            "total_filled_qty": total_qty,
            "total_cost": total_cost,
            "fill_count": fill_count,
            "first_fill_ts": first_ts,
            "last_fill_ts": last_ts,
        })

    con.commit()
    return results
