"""Unrealized PnL computation using bid/ask prices (ADR-001)."""

from __future__ import annotations
import json, sqlite3, time
from typing import Any, Dict, List, Optional, Tuple

def _now_ms() -> int:
    return int(time.time() * 1000)

def _fetch_latest_price(con, venue, inst_id):
    row = con.execute(
        "SELECT bid, ask, mid, last, ts FROM prices_v3 WHERE venue = ? AND inst_id = ? ORDER BY ts DESC LIMIT 1",
        (venue, inst_id),
    ).fetchone()
    if row is None: return None
    return {"bid": row[0], "ask": row[1], "mid": row[2], "last": row[3], "ts": row[4]}

def _resolve_exit_price(price_row, side):
    preferred = price_row.get("bid") if side == "LONG" else price_row.get("ask")
    preferred_type = "bid" if side == "LONG" else "ask"
    if preferred is not None: return float(preferred), preferred_type
    mid = price_row.get("mid")
    if mid is not None: return float(mid), "mid"
    last = price_row.get("last")
    if last is not None: return float(last), "last"
    return None, "none"

def compute_leg_upnl(side, avg_entry, exit_price, size):
    if side == "LONG": return (exit_price - avg_entry) * size
    else: return -(exit_price - avg_entry) * size

def compute_unrealized_pnl(con, *, position_ids=None):
    """Compute uPnL for all OPEN legs with entry prices."""
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        sql = f"""
            SELECT l.leg_id, l.position_id, l.venue, l.inst_id, l.side, l.size, e.avg_entry_price
            FROM pm_legs l JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE l.position_id IN ({placeholders}) AND p.status != 'CLOSED'"""
        legs = con.execute(sql, position_ids).fetchall()
    else:
        sql = """
            SELECT l.leg_id, l.position_id, l.venue, l.inst_id, l.side, l.size, e.avg_entry_price
            FROM pm_legs l JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE p.status != 'CLOSED'"""
        legs = con.execute(sql).fetchall()

    if not legs: return []

    results = []
    pos_upnl = {}

    for leg_id, position_id, venue, inst_id, side, size, avg_entry in legs:
        price_row = _fetch_latest_price(con, venue, inst_id)
        if price_row is None:
            results.append({"leg_id": leg_id, "position_id": position_id, "skipped": True, "skip_reason": "no_price"})
            continue

        exit_price, price_type = _resolve_exit_price(price_row, side)
        if exit_price is None:
            results.append({"leg_id": leg_id, "position_id": position_id, "skipped": True, "skip_reason": "no_usable_price"})
            continue

        upnl = compute_leg_upnl(side, avg_entry, exit_price, size)
        con.execute("UPDATE pm_legs SET unrealized_pnl = ?, current_price = ? WHERE leg_id = ?", (upnl, exit_price, leg_id))

        results.append({
            "leg_id": leg_id, "position_id": position_id, "unrealized_pnl": upnl,
            "price_used": exit_price, "price_type": price_type, "avg_entry": avg_entry,
            "size": size, "side": side,
        })
        pos_upnl[position_id] = pos_upnl.get(position_id, 0.0) + upnl

    con.commit()
    for pid, total in pos_upnl.items():
        results.append({"position_id": pid, "position_upnl": total})
    return results
