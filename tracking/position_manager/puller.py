"""Position puller for fetching live data from venue APIs.

Queries configured positions (from DB or registry), fetches live account
and position data from venue private APIs, and writes snapshots to the database.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

# Connector imports
from ..connectors.paradex_private import ParadexPrivateConnector
from ..connectors.hyperliquid_private import HyperliquidPrivateConnector
from ..connectors.hyena_private import HyenaPrivateConnector
from ..connectors.ethereal_private import EtherealPrivateConnector
from ..connectors.lighter_private import LighterPrivateConnector
from ..connectors.okx_private import OKXPrivateConnector

# Registry imports
from .registry import load_registry
from .db_sync import sync_registry


# Venue -> connector class mapping
CONNECTORS = {
    "paradex": ParadexPrivateConnector,
    "hyperliquid": HyperliquidPrivateConnector,
    "hyena": HyenaPrivateConnector,
    "ethereal": EtherealPrivateConnector,
    "lighter": LighterPrivateConnector,
    "okx": OKXPrivateConnector,
}


def connect(db_path: Path) -> sqlite3.Connection:
    """Create a database connection with foreign keys enabled."""
    con = sqlite3.connect(str(db_path), timeout=60)
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA busy_timeout = 60000")
    return con


def load_positions_from_db(con: sqlite3.Connection, venues_filter: Optional[Set[str]] = None) -> List[Dict]:
    """Load managed positions from DB (pm_positions/pm_legs).

    Note: we do NOT filter by `pm_positions.venue` because multi-venue positions store venue as "multi".
    If a venues_filter is provided, we apply it later by intersecting `venues_to_pull`.
    """
    sql = """
    SELECT p.position_id, p.venue, p.status,
           l.leg_id, l.venue as leg_venue, l.inst_id, l.side, l.size
    FROM pm_positions p
    LEFT JOIN pm_legs l ON p.position_id = l.position_id
    WHERE p.status IN ('OPEN', 'PAUSED', 'EXITING')
    """

    cursor = con.execute(sql)

    positions: Dict[str, Dict] = {}
    for row in cursor.fetchall():
        position_id, venue, status, leg_id, leg_venue, inst_id, side, size = row

        if position_id not in positions:
            positions[position_id] = {
                "position_id": position_id,
                "venue": venue,
                "status": status,
                "legs": [],
            }

        if leg_id:
            positions[position_id]["legs"].append({
                "leg_id": leg_id,
                "venue": leg_venue,
                "inst_id": inst_id,
                "side": side,
                "size": size,
            })

    return list(positions.values())


def load_positions_from_registry(registry_path: Path, venues_filter: Optional[Set[str]] = None) -> List[Dict]:
    """
    Load managed positions from registry JSON file.

    Args:
        registry_path: Path to registry JSON file
        venues_filter: Optional set of venues to filter by

    Returns:
        List of position dicts with legs nested
    """
    positions = load_registry(registry_path)

    result = []
    for pos in positions:
        # Filter by venue if specified (check if any leg matches)
        if venues_filter:
            leg_venues = {leg.venue for leg in pos.legs}
            if not leg_venues.intersection(venues_filter):
                continue

        leg_venues = {leg.venue for leg in pos.legs}
        venue = next(iter(leg_venues)) if len(leg_venues) == 1 else "MULTI"

        result.append({
            "position_id": pos.position_id,
            "venue": venue,
            "status": pos.status,
            "legs": [
                {
                    "leg_id": leg.leg_id,
                    "venue": leg.venue,
                    "inst_id": leg.inst_id,
                    "side": leg.side,
                    "size": leg.qty,
                }
                for leg in pos.legs
            ],
        })

    return result


def pull_venue_positions(venue: str) -> Dict:
    """
    Fetch account and position data from a single venue.

    Args:
        venue: Venue identifier (e.g., 'paradex', 'hyperliquid')

    Returns:
        Dict with keys:
        - success: bool
        - account_snapshot: dict or None
        - positions: list of position dicts
        - error: str or None
    """
    if venue not in CONNECTORS:
        return {
            "success": False,
            "account_snapshot": None,
            "positions": [],
            "error": f"No connector available for venue: {venue}",
        }

    try:
        connector_class = CONNECTORS[venue]
        connector = connector_class()
    except RuntimeError as e:
        # Credentials missing - return gracefully
        return {
            "success": False,
            "account_snapshot": None,
            "positions": [],
            "error": str(e),
        }

    try:
        account_snapshot = connector.fetch_account_snapshot()
        positions = connector.fetch_open_positions()

        return {
            "success": True,
            "account_snapshot": account_snapshot,
            "positions": positions,
            "error": None,
        }
    except Exception as e:
        return {
            "success": False,
            "account_snapshot": None,
            "positions": [],
            "error": f"API call failed: {e}",
        }


def write_account_snapshot(con: sqlite3.Connection, venue: str, snapshot: Dict, ts_ms: int) -> None:
    """
    Write account snapshot to pm_account_snapshots table.

    Args:
        con: Database connection
        venue: Venue identifier
        snapshot: Account snapshot dict
        ts_ms: Timestamp in milliseconds since epoch
    """
    sql = """
    INSERT INTO pm_account_snapshots(
      venue, account_id, ts, total_balance, available_balance,
      margin_balance, unrealized_pnl, position_value, raw_json, meta_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    con.execute(sql, (
        venue,
        snapshot.get("account_id", ""),
        ts_ms,
        snapshot.get("total_balance"),
        snapshot.get("available_balance"),
        snapshot.get("margin_balance"),
        snapshot.get("unrealized_pnl"),
        snapshot.get("position_value"),
        json.dumps(snapshot.get("raw_json", {}), separators=(",", ":")),
        None,  # meta_json
    ))


def write_leg_snapshots(con: sqlite3.Connection, venue: str, positions: List[Dict], ts_ms: int) -> None:
    """
    Write leg snapshots to pm_leg_snapshots table.

    Args:
        con: Database connection
        venue: Venue identifier
        positions: List of position dicts
        ts_ms: Timestamp in milliseconds since epoch
    """
    sql = """
    INSERT INTO pm_leg_snapshots(
      leg_id, position_id, venue, inst_id, ts, side, size,
      entry_price, current_price, unrealized_pnl, realized_pnl,
      raw_json, meta_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for pos in positions:
        con.execute(sql, (
            pos.get("leg_id", ""),
            pos.get("position_id", ""),
            venue,
            pos.get("inst_id", ""),
            ts_ms,
            pos.get("side", ""),
            pos.get("size", 0.0),
            pos.get("entry_price"),
            pos.get("current_price"),
            pos.get("unrealized_pnl"),
            pos.get("realized_pnl"),
            json.dumps(pos.get("raw_json", {}), separators=(",", ":")),
            None,  # meta_json
        ))

        # Best-effort update latest fields on pm_legs (useful for quick queries).
        try:
            con.execute(
                """
                UPDATE pm_legs
                SET current_price = COALESCE(?, current_price),
                    unrealized_pnl = COALESCE(?, unrealized_pnl),
                    realized_pnl = COALESCE(?, realized_pnl)
                WHERE leg_id = ?
                """,
                (
                    pos.get("current_price"),
                    pos.get("unrealized_pnl"),
                    pos.get("realized_pnl"),
                    pos.get("leg_id", ""),
                ),
            )
        except Exception:
            pass


def run_pull(
    db_path: Path,
    registry_path: Optional[Path] = None,
    venues_filter: Optional[List[str]] = None,
    verbose: bool = True,
) -> Dict:
    """
    Run the position pull process.

    Args:
        db_path: Path to database file
        registry_path: Optional path to registry JSON file (if not using DB)
        venues_filter: Optional list of venues to pull from
        verbose: Whether to print progress messages

    Returns:
        Summary dict with keys:
        - success: bool
        - venues_pulled: list of venue names successfully pulled
        - venues_skipped: list of venue names skipped (missing creds, etc.)
        - venues_failed: list of venue names that failed
        - snapshots_written: int (total snapshots written)
        - errors: list of error messages
    """
    venues_set = set(venues_filter) if venues_filter else None

    # Load managed positions
    if registry_path:
        if verbose:
            print(f"Loading positions from registry: {registry_path}")
        # Ensure managed positions/legs exist in DB so snapshot inserts won't FK-fail.
        con0 = connect(db_path)
        try:
            reg_positions = load_registry(registry_path)
            sync_registry(con0, reg_positions, delete_missing=False)
        finally:
            con0.close()

        positions = load_positions_from_registry(registry_path, venues_set)
    else:
        if verbose:
            print("Loading positions from database")
        con0 = connect(db_path)
        try:
            positions = load_positions_from_db(con0, venues_set)
        finally:
            con0.close()

    if verbose:
        print(f"Found {len(positions)} managed positions")

    # Determine unique venues to pull from
    venues_to_pull: Set[str] = set()
    for pos in positions:
        for leg in pos.get("legs", []):
            venue = leg.get("venue")
            if venue:
                venues_to_pull.add(venue)

    # Filter if requested
    if venues_set:
        venues_to_pull = venues_to_pull.intersection(venues_set)

    if verbose:
        print(f"Venues to pull from: {sorted(venues_to_pull)}")

    # Pull from each venue
    ts_ms = int(time.time() * 1000)
    summary = {
        "success": True,
        "venues_pulled": [],
        "venues_skipped": [],
        "venues_failed": [],
        "snapshots_written": 0,
        "errors": [],
    }

    con = connect(db_path)

    for venue in sorted(venues_to_pull):
        if verbose:
            print(f"  Pulling from {venue}...", end=" ")

        result = pull_venue_positions(venue)

        if not result["success"]:
            error_msg = result.get("error", "")
            error_lower = error_msg.lower()

            # Skip if no connector or credentials missing (expected scenarios)
            if "no connector available" in error_lower or "credentials missing" in error_lower:
                summary["venues_skipped"].append(venue)
                if verbose:
                    print(f"SKIPPED ({error_msg})")
            else:
                # Unexpected error
                summary["venues_failed"].append(venue)
                summary["errors"].append(error_msg)
                summary["success"] = False
                if verbose:
                    print(f"FAILED ({error_msg})")
            continue

        # Write snapshots
        try:
            # Only write account snapshot if there are managed legs for this venue
            # (don't overwrite with empty data if API returns no positions)
            has_managed_legs = any(
                leg.get("venue") == venue 
                for mp in positions 
                for leg in mp.get("legs", [])
            )
            
            if result["account_snapshot"] and has_managed_legs:
                write_account_snapshot(con, venue, result["account_snapshot"], ts_ms)
                summary["snapshots_written"] += 1

            mapped = []
            if result["positions"]:
                # Map venue open-positions -> managed legs only, to satisfy FKs.
                venue_positions = result["positions"]
                managed_legs = []
                for mp in positions:
                    for leg in mp.get("legs", []):
                        if leg.get("venue") == venue:
                            managed_legs.append(
                                {
                                    "position_id": mp.get("position_id"),
                                    "leg_id": leg.get("leg_id"),
                                    "inst_id": leg.get("inst_id"),
                                    "side": (leg.get("side") or "").upper(),
                                }
                            )

                # index venue positions by (inst_id, side)
                idx = {}
                for vp in venue_positions:
                    key = ((vp.get("inst_id") or ""), (vp.get("side") or "").upper())
                    # pick the first; if duplicates exist, keep the first for now
                    idx.setdefault(key, vp)

                for ml in managed_legs:
                    key = (ml.get("inst_id") or "", ml.get("side") or "")
                    vp = idx.get(key)
                    if not vp:
                        continue
                    mapped.append(
                        {
                            "leg_id": ml["leg_id"],
                            "position_id": ml["position_id"],
                            "inst_id": vp.get("inst_id"),
                            "side": (vp.get("side") or "").upper(),
                            "size": vp.get("size"),
                            "entry_price": vp.get("entry_price"),
                            "current_price": vp.get("current_price"),
                            "unrealized_pnl": vp.get("unrealized_pnl"),
                            "realized_pnl": vp.get("realized_pnl"),
                            "raw_json": vp.get("raw_json", {}),
                        }
                    )

                if mapped:
                    write_leg_snapshots(con, venue, mapped, ts_ms)
                    summary["snapshots_written"] += len(mapped)

            con.commit()
            summary["venues_pulled"].append(venue)

            if verbose:
                pos_count = len(mapped)
                print(f"OK ({pos_count} managed legs)")

        except sqlite3.IntegrityError as e:
            summary["venues_failed"].append(venue)
            summary["errors"].append(f"DB integrity error: {e}")
            summary["success"] = False
            if verbose:
                print(f"FAILED (DB integrity error: {e})")
            continue

    con.close()

    if verbose:
        print(f"\nSummary:")
        print(f"  Venues pulled: {len(summary['venues_pulled'])}")
        print(f"  Venues skipped: {len(summary['venues_skipped'])}")
        print(f"  Venues failed: {len(summary['venues_failed'])}")
        print(f"  Snapshots written: {summary['snapshots_written']}")

    return summary
