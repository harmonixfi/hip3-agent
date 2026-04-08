"""Entry/Exit Spread Calculator (ADR-008, Phase 1b).

Computes entry spread, exit spread, and spread P&L in bps for each sub-pair
within a position. For split-leg positions (1 LONG + N SHORTs), each SHORT
pairs with the LONG to form an independent sub-pair.

Formulas:
  entry_spread     = long_avg_entry / short_avg_entry - 1
  exit_spread      = long_exit_bid  / short_exit_ask  - 1
  spread_pnl_bps   = (exit_spread - entry_spread) * 10_000

Writes to pm_spreads using DELETE + INSERT upsert pattern on
(position_id, long_leg_id, short_leg_id).
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------

def entry_spread(long_avg_entry: float, short_avg_entry: float) -> float:
    """Ratio spread at entry: long_avg_entry / short_avg_entry - 1."""
    return long_avg_entry / short_avg_entry - 1.0


def exit_spread(long_exit_bid: float, short_exit_ask: float) -> float:
    """Ratio spread at exit: long_exit_bid / short_exit_ask - 1."""
    return long_exit_bid / short_exit_ask - 1.0


def spread_pnl_bps(entry: float, exit_val: float) -> float:
    """Spread P&L in basis points: (exit - entry) * 10_000."""
    return (exit_val - entry) * 10_000.0


# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def _fetch_latest_price(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
    *,
    leg_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Fetch latest price row for (venue, inst_id) from prices_v3.

    For ``venue=felix``, if there is no ``prices_v3`` row (equities often absent),
    fall back to ``pm_legs.current_price`` from the position puller (registry match).
    """
    row = con.execute(
        "SELECT bid, ask, mid, last, ts FROM prices_v3"
        " WHERE venue = ? AND inst_id = ? ORDER BY ts DESC LIMIT 1",
        (venue, inst_id),
    ).fetchone()
    if row is not None:
        return {"bid": row[0], "ask": row[1], "mid": row[2], "last": row[3], "ts": row[4]}
    if venue == "felix" and leg_id:
        lr = con.execute(
            "SELECT current_price FROM pm_legs WHERE leg_id = ? AND venue = 'felix'",
            (leg_id,),
        ).fetchone()
        if lr and lr[0] is not None:
            m = float(lr[0])
            return {"bid": m, "ask": m, "mid": m, "last": m, "ts": 0}
    return None


def _get_exit_bid(price_row: Dict[str, Any]) -> Optional[float]:
    """Best available bid for LONG exit: bid → mid → last."""
    for key in ("bid", "mid", "last"):
        v = price_row.get(key)
        if v is not None:
            return float(v)
    return None


def _get_exit_ask(price_row: Dict[str, Any]) -> Optional[float]:
    """Best available ask for SHORT exit: ask → mid → last."""
    for key in ("ask", "mid", "last"):
        v = price_row.get(key)
        if v is not None:
            return float(v)
    return None


# ---------------------------------------------------------------------------
# Core computation
# ---------------------------------------------------------------------------

def compute_spreads(
    con: sqlite3.Connection,
    *,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Compute entry/exit spreads for all non-CLOSED positions.

    For each position, creates sub-pairs: every LONG leg × every SHORT leg.
    Skips sub-pairs missing entry prices.
    Writes to pm_spreads (DELETE + INSERT upsert).

    Args:
        con: DB connection.
        position_ids: optional filter; processes all non-CLOSED if None.

    Returns:
        List of result dicts, one per sub-pair written.
    """
    now = int(time.time() * 1000)

    # --- load positions ---
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        positions = con.execute(
            f"SELECT position_id FROM pm_positions"
            f" WHERE position_id IN ({placeholders}) AND status != 'CLOSED'",
            position_ids,
        ).fetchall()
    else:
        positions = con.execute(
            "SELECT position_id FROM pm_positions WHERE status != 'CLOSED'"
        ).fetchall()

    if not positions:
        return []

    results: List[Dict[str, Any]] = []

    for (position_id,) in positions:
        # Load legs with entry prices
        legs = con.execute(
            """
            SELECT l.leg_id, l.venue, l.inst_id, l.side, e.avg_entry_price
            FROM pm_legs l
            JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            WHERE l.position_id = ?
            """,
            (position_id,),
        ).fetchall()

        long_legs = [
            {"leg_id": r[0], "venue": r[1], "inst_id": r[2], "avg_entry": r[4]}
            for r in legs if r[3] == "LONG"
        ]
        short_legs = [
            {"leg_id": r[0], "venue": r[1], "inst_id": r[2], "avg_entry": r[4]}
            for r in legs if r[3] == "SHORT"
        ]

        if not long_legs or not short_legs:
            continue

        for long_leg in long_legs:
            # Fetch LONG exit bid once per long leg
            long_price_row = _fetch_latest_price(
                con,
                long_leg["venue"],
                long_leg["inst_id"],
                leg_id=long_leg["leg_id"],
            )
            long_exit_bid = _get_exit_bid(long_price_row) if long_price_row else None

            for short_leg in short_legs:
                long_avg = long_leg["avg_entry"]
                short_avg = short_leg["avg_entry"]

                # Entry spread (always computable when entry prices exist)
                es = entry_spread(long_avg, short_avg)

                # Exit spread (requires live prices)
                xs: Optional[float] = None
                spnl: Optional[float] = None
                long_exit_price: Optional[float] = long_exit_bid
                short_exit_price: Optional[float] = None

                short_price_row = _fetch_latest_price(
                    con,
                    short_leg["venue"],
                    short_leg["inst_id"],
                    leg_id=short_leg["leg_id"],
                )
                short_exit_ask = _get_exit_ask(short_price_row) if short_price_row else None
                short_exit_price = short_exit_ask

                if long_exit_bid is not None and short_exit_ask is not None:
                    xs = exit_spread(long_exit_bid, short_exit_ask)
                    spnl = spread_pnl_bps(es, xs)

                meta = {}

                # Upsert: DELETE then INSERT
                con.execute(
                    "DELETE FROM pm_spreads"
                    " WHERE position_id = ? AND long_leg_id = ? AND short_leg_id = ?",
                    (position_id, long_leg["leg_id"], short_leg["leg_id"]),
                )
                con.execute(
                    """
                    INSERT INTO pm_spreads (
                        position_id, long_leg_id, short_leg_id,
                        entry_spread, long_avg_entry, short_avg_entry,
                        exit_spread, long_exit_price, short_exit_price,
                        spread_pnl_bps, computed_at_ms, meta_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        position_id,
                        long_leg["leg_id"],
                        short_leg["leg_id"],
                        es,
                        long_avg,
                        short_avg,
                        xs,
                        long_exit_price,
                        short_exit_price,
                        spnl,
                        now,
                        json.dumps(meta) if meta else None,
                    ),
                )

                results.append({
                    "position_id": position_id,
                    "long_leg_id": long_leg["leg_id"],
                    "short_leg_id": short_leg["leg_id"],
                    "entry_spread": es,
                    "long_avg_entry": long_avg,
                    "short_avg_entry": short_avg,
                    "exit_spread": xs,
                    "long_exit_price": long_exit_price,
                    "short_exit_price": short_exit_price,
                    "spread_pnl_bps": spnl,
                })

    con.commit()
    return results
