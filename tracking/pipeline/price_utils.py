"""Shared price resolution for pipeline steps.

Two-tier lookup
---------------
Tier 1 — ``prices_v3``:
    Covers HL spot, HL perp, Felix equities (after ``pull_felix_market.py``
    runs), and any future venue that writes to ``prices_v3``.

Tier 2 — ``pm_legs.current_price``:
    Fallback for venues not yet writing to ``prices_v3``.  The position
    puller populates this field via ``write_leg_snapshots()`` for every
    venue it manages (Felix writes HL-mark proxies here).

Extensibility
-------------
A new venue automatically works through either path:
  a) Write real-time prices to ``prices_v3`` (preferred — e.g. Felix via
     ``pull_felix_market.py``).
  b) Have the puller call ``write_leg_snapshots()`` with a valid
     ``current_price`` — no code change needed.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional


def resolve_price(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
    *,
    leg_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the latest price dict for ``(venue, inst_id)``.

    Args:
        con:     Open SQLite connection.
        venue:   Venue identifier (e.g. ``"felix"``, ``"hyperliquid"``).
        inst_id: Instrument ID as stored in ``pm_legs`` (e.g. ``"MUon/USDC"``).
        leg_id:  Optional leg primary key — enables Tier 2 fallback.

    Returns:
        Dict with keys ``bid``, ``ask``, ``mid``, ``last``, ``ts``, or
        ``None`` if no price is available from either tier.
    """
    # Tier 1: canonical price store (preferred source)
    row = con.execute(
        "SELECT bid, ask, mid, last, ts FROM prices_v3"
        " WHERE venue = ? AND inst_id = ? ORDER BY ts DESC LIMIT 1",
        (venue, inst_id),
    ).fetchone()
    if row is not None:
        return {
            "bid": row[0],
            "ask": row[1],
            "mid": row[2],
            "last": row[3],
            "ts": row[4],
        }

    # Tier 2: pm_legs.current_price written by the position puller.
    # Works for any venue whose puller calls write_leg_snapshots() with a
    # valid current_price (e.g. Felix puller writes HL-mark proxy).
    if leg_id:
        lr = con.execute(
            "SELECT current_price FROM pm_legs WHERE leg_id = ?",
            (leg_id,),
        ).fetchone()
        if lr and lr[0] is not None:
            m = float(lr[0])
            return {"bid": m, "ask": m, "mid": m, "last": m, "ts": 0}

    return None
