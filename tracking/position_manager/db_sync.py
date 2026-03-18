"""Database synchronization for position registry.

Syncs PositionConfig objects to pm_positions and pm_legs tables.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import List

from .registry import PositionConfig, LegConfig


def connect(db_path: Path) -> sqlite3.Connection:
    """Create a database connection with foreign keys enabled."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def ensure_multi_wallet_columns(con: sqlite3.Connection) -> None:
    """Add account_id columns to pm_legs and pm_leg_snapshots if missing."""
    for table in ("pm_legs", "pm_leg_snapshots"):
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN account_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
    try:
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_account "
            "ON pm_leg_snapshots(account_id, leg_id)"
        )
    except sqlite3.OperationalError:
        pass
    con.commit()


def sync_registry(con: sqlite3.Connection, positions: List[PositionConfig], delete_missing: bool = False) -> int:
    """
    Sync position configurations to database.

    Upserts positions and legs. Does NOT delete automatically unless
    delete_missing=True is explicitly passed.

    Args:
        con: Database connection
        positions: List of position configurations to sync
        delete_missing: If True, delete positions/legs not in registry

    Returns:
        Number of positions synced
    """
    now_ms = int(time.time() * 1000)

    # Upsert positions
    for pos in positions:
        upsert_position(con, pos, now_ms)

        # Upsert legs for this position
        for leg in pos.legs:
            upsert_leg(con, pos.position_id, leg, now_ms)

    con.commit()

    if delete_missing:
        # Delete legs not in any position
        all_leg_ids = {leg.leg_id for pos in positions for leg in pos.legs if leg.leg_id}
        if all_leg_ids:
            placeholders = ",".join("?" * len(all_leg_ids))
            con.execute(f"DELETE FROM pm_legs WHERE leg_id NOT IN ({placeholders})", list(all_leg_ids))

        # Delete positions not in registry
        all_position_ids = {pos.position_id for pos in positions}
        if all_position_ids:
            placeholders = ",".join("?" * len(all_position_ids))
            con.execute(f"DELETE FROM pm_positions WHERE position_id NOT IN ({placeholders})", list(all_position_ids))

        con.commit()

    return len(positions)


def upsert_position(con: sqlite3.Connection, pos: PositionConfig, now_ms: int) -> None:
    """Upsert a position to pm_positions table."""
    # Build meta_json with extra fields not in schema
    meta = {
        "strategy_type": pos.strategy_type,
        "base": pos.base,
    }
    if pos.amount_usd is not None:
        meta["amount_usd"] = pos.amount_usd
    if pos.open_fees_usd is not None:
        meta["open_fees_usd"] = pos.open_fees_usd
    if pos.thresholds:
        meta["thresholds"] = pos.thresholds

    sql = """
    INSERT INTO pm_positions(
      position_id, venue, strategy, status,
      created_at_ms, updated_at_ms, meta_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(position_id) DO UPDATE SET
      venue = excluded.venue,
      strategy = excluded.strategy,
      status = excluded.status,
      updated_at_ms = excluded.updated_at_ms,
      meta_json = excluded.meta_json
    """

    # Use first leg's venue as the position venue (or "MULTI" if multiple venues)
    venues = set(leg.venue for leg in pos.legs)
    venue = venues.pop() if len(venues) == 1 else "MULTI"

    con.execute(sql, (
        pos.position_id,
        venue,
        pos.strategy_type,  # Map strategy_type to strategy field
        pos.status,
        now_ms,  # created_at_ms (or preserve existing)
        now_ms,  # updated_at_ms
        json.dumps(meta, separators=(",", ":")),
    ))


def upsert_leg(con: sqlite3.Connection, position_id: str, leg: LegConfig, now_ms: int) -> None:
    """Upsert a leg to pm_legs table."""
    # Build meta_json with optional fields not in schema
    meta = {}
    if leg.qty_type:
        meta["qty_type"] = leg.qty_type
    if leg.leverage is not None:
        meta["leverage"] = leg.leverage
    if leg.margin_mode:
        meta["margin_mode"] = leg.margin_mode
    if leg.collateral is not None:
        meta["collateral"] = leg.collateral

    sql = """
    INSERT INTO pm_legs(
      leg_id, position_id, venue, inst_id, side, size,
      status, opened_at_ms, meta_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(leg_id) DO UPDATE SET
      position_id = excluded.position_id,
      venue = excluded.venue,
      inst_id = excluded.inst_id,
      side = excluded.side,
      size = excluded.size,
      status = excluded.status,
      meta_json = excluded.meta_json
    """

    con.execute(sql, (
        leg.leg_id,
        position_id,
        leg.venue,
        leg.inst_id,
        leg.side,
        leg.qty,
        "OPEN",  # registry legs are treated as OPEN by default; close via explicit workflow later
        now_ms,  # opened_at_ms
        json.dumps(meta, separators=(",", ":")) if meta else None,
    ))


def list_positions(con: sqlite3.Connection) -> List[dict]:
    """
    List all positions with their legs.

    Args:
        con: Database connection

    Returns:
        List of position dicts with legs nested
    """
    # Query positions
    pos_sql = """
    SELECT position_id, venue, strategy, status,
           created_at_ms, updated_at_ms, closed_at_ms,
           meta_json
    FROM pm_positions
    ORDER BY created_at_ms DESC
    """
    cursor = con.execute(pos_sql)
    positions = []

    for row in cursor.fetchall():
        pos = {
            "position_id": row[0],
            "venue": row[1],
            "strategy": row[2],
            "status": row[3],
            "created_at_ms": row[4],
            "updated_at_ms": row[5],
            "closed_at_ms": row[6],
            "meta": json.loads(row[7]) if row[7] else {},
            "legs": [],
        }
        positions.append(pos)

    # Query legs and group by position
    leg_sql = """
    SELECT leg_id, position_id, venue, inst_id, side, size,
           entry_price, current_price, unrealized_pnl, realized_pnl,
           status, opened_at_ms, closed_at_ms, meta_json
    FROM pm_legs
    ORDER BY position_id, leg_id
    """
    cursor = con.execute(leg_sql)

    pos_dict = {pos["position_id"]: pos for pos in positions}
    for row in cursor.fetchall():
        leg = {
            "leg_id": row[0],
            "position_id": row[1],
            "venue": row[2],
            "inst_id": row[3],
            "side": row[4],
            "size": row[5],
            "entry_price": row[6],
            "current_price": row[7],
            "unrealized_pnl": row[8],
            "realized_pnl": row[9],
            "status": row[10],
            "opened_at_ms": row[11],
            "closed_at_ms": row[12],
            "meta": json.loads(row[13]) if row[13] else {},
        }

        if row[1] in pos_dict:
            pos_dict[row[1]]["legs"].append(leg)

    return positions
