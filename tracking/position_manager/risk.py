"""Risk engine for managed positions.

Computes delta drift and basic risk flags from managed positions + latest snapshots.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any


def _enrich_leg_price_from_db(con, venue: str, inst_id: str) -> Optional[float]:
    """
    Query DB v3 prices_v3 for the latest price for a given (venue, inst_id).

    Prefers: mid > mark > last (first non-null).

    Args:
        con: SQLite database connection
        venue: Venue name
        inst_id: Instrument ID

    Returns:
        Price or None if no data found
    """
    sql = """
    SELECT mid, mark, last
    FROM prices_v3
    WHERE venue = ? AND inst_id = ?
    ORDER BY ts DESC
    LIMIT 1
    """
    cursor = con.execute(sql, (venue, inst_id))
    row = cursor.fetchone()
    if not row:
        return None

    mid, mark, last = row
    # Prefer mid, then mark, then last
    if mid is not None:
        return float(mid)
    if mark is not None:
        return float(mark)
    if last is not None:
        return float(last)
    return None


# Default risk thresholds
DEFAULT_WARN_DRIFT_USD = 50.0
DEFAULT_CRIT_DRIFT_USD = 150.0
DEFAULT_WARN_DRIFT_PCT = 0.02  # 2%
DEFAULT_CRIT_DRIFT_PCT = 0.04  # 4%


def load_managed_positions(con) -> List[Dict[str, Any]]:
    """
    Load all managed positions with their legs.

    Args:
        con: SQLite database connection

    Returns:
        List of position dicts with legs nested
    """
    # Query positions (only OPEN, PAUSED, EXITING - ignore CLOSED)
    pos_sql = """
    SELECT position_id, venue, strategy, status,
           created_at_ms, updated_at_ms, closed_at_ms,
           meta_json
    FROM pm_positions
    WHERE status IN ('OPEN', 'PAUSED', 'EXITING')
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
    WHERE status = 'OPEN'
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


def load_latest_leg_snapshots(con, position_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Load latest snapshot per leg_id for given positions.

    Args:
        con: SQLite database connection
        position_ids: List of position IDs to fetch snapshots for

    Returns:
        Dict mapping leg_id -> latest snapshot dict
    """
    if not position_ids:
        return {}

    placeholders = ",".join("?" * len(position_ids))
    sql = f"""
    SELECT
        leg_id, position_id, venue, inst_id, ts, side, size,
        entry_price, current_price, unrealized_pnl, realized_pnl,
        raw_json, meta_json
    FROM pm_leg_snapshots
    WHERE position_id IN ({placeholders})
    ORDER BY ts DESC
    """

    cursor = con.execute(sql, position_ids)
    latest_snapshots: Dict[str, Dict[str, Any]] = {}

    for row in cursor.fetchall():
        leg_id = row[0]
        # Only keep the first (latest) snapshot per leg_id
        if leg_id not in latest_snapshots:
            snapshot = {
                "leg_id": row[0],
                "position_id": row[1],
                "venue": row[2],
                "inst_id": row[3],
                "ts": row[4],
                "side": row[5],
                "size": row[6],
                "entry_price": row[7],
                "current_price": row[8],
                "unrealized_pnl": row[9],
                "realized_pnl": row[10],
                "raw": json.loads(row[11]) if row[11] else {},
                "meta": json.loads(row[12]) if row[12] else {},
            }
            latest_snapshots[leg_id] = snapshot

    return latest_snapshots


def compute_position_rollup(position: Dict[str, Any], leg_snapshots: Dict[str, Dict[str, Any]],
                            warn_drift_usd: float = DEFAULT_WARN_DRIFT_USD,
                            crit_drift_usd: float = DEFAULT_CRIT_DRIFT_USD,
                            warn_drift_pct: float = DEFAULT_WARN_DRIFT_PCT,
                            crit_drift_pct: float = DEFAULT_CRIT_DRIFT_PCT,
                            con=None) -> Dict[str, Any]:
    """
    Compute risk metrics for a position from leg snapshots.

    Args:
        position: Position dict with legs
        leg_snapshots: Dict mapping leg_id -> latest snapshot
        warn_drift_usd: Warning threshold for drift in USD
        crit_drift_usd: Critical threshold for drift in USD
        warn_drift_pct: Warning threshold for drift percentage
        crit_drift_pct: Critical threshold for drift percentage
        con: SQLite database connection for price enrichment (optional)

    Returns:
        Dict with risk metrics including:
        - gross_notional_usd (approx using current_price if available else None)
        - net_delta_usd (approx)
        - drift_usd, drift_pct (if gross_notional available)
        - warn/crit flags
        - snapshot status (ok/stale/missing/partial_price)
        - raw inputs for debugging
    """
    result = {
        "position_id": position["position_id"],
        "status": position["status"],
        "venue": position["venue"],
        "strategy": position.get("strategy"),
        "leg_count": len(position["legs"]),
        "snapshots_ok": True,
        "snapshots_status": "ok",  # ok, stale, missing, partial_price
        "legs": [],
    }

    # Process each leg
    legs_with_snapshots = 0
    legs_missing_price = 0
    gross_notional_usd = None
    net_delta_usd = 0.0
    net_size_units = 0.0

    for leg in position["legs"]:
        leg_id = leg["leg_id"]
        snapshot = leg_snapshots.get(leg_id)

        leg_result = {
            "leg_id": leg_id,
            "inst_id": leg.get("inst_id"),
            "side": leg.get("side"),
            "size": leg.get("size"),
            "entry_price": leg.get("entry_price"),
            "current_price": leg.get("current_price"),
            "has_snapshot": snapshot is not None,
            "snapshot_ts": snapshot.get("ts") if snapshot else None,
        }

        if snapshot:
            legs_with_snapshots += 1

            # Prefer snapshot data, fall back to leg data
            # IMPORTANT: size must come from the managed leg (registry/pm_legs),
            # not from venue account snapshot (which can include residual inventory).
            size = leg.get("size")
            side = snapshot.get("side", leg["side"])
            current_price = snapshot.get("current_price") or leg.get("current_price")
            entry_price = snapshot.get("entry_price") or leg.get("entry_price")

            # Enrich missing price from DB v3 prices_v3
            if current_price is None and con is not None:
                venue = snapshot.get("venue") or leg.get("venue")
                inst_id = snapshot.get("inst_id") or leg.get("inst_id")
                if venue and inst_id:
                    enriched_price = _enrich_leg_price_from_db(con, venue, inst_id)
                    if enriched_price is not None:
                        current_price = enriched_price
                        leg_result["enriched_from_db"] = True

            leg_result["snapshot_current_price"] = current_price
            leg_result["snapshot_entry_price"] = entry_price
            leg_result["snapshot_size"] = size

            # Track net size in base units as a fallback proxy
            signed_size = size if side == "LONG" else -size
            net_size_units += signed_size

            # Compute leg notional and delta (approx)
            if current_price is not None:
                leg_notional = size * current_price
                leg_result["notional_usd"] = leg_notional

                # Delta: LONG positive, SHORT negative
                delta = leg_notional if side == "LONG" else -leg_notional
                leg_result["delta_usd"] = delta
                net_delta_usd += delta

                # Accumulate gross notional
                if gross_notional_usd is None:
                    gross_notional_usd = 0.0
                gross_notional_usd += abs(leg_notional)
            else:
                legs_missing_price += 1
                leg_result["notional_usd"] = None
                leg_result["delta_usd"] = None
                result["snapshots_ok"] = False

            # Check for liquidation price in raw_json if available
            if snapshot.get("raw"):
                liq_price = snapshot["raw"].get("liquidation_price")
                if liq_price:
                    leg_result["liquidation_price"] = liq_price

        else:
            # No snapshot available
            result["snapshots_ok"] = False
            leg_result["notional_usd"] = None
            leg_result["delta_usd"] = None

        result["legs"].append(leg_result)

    # Determine snapshot status
    if legs_missing_price > 0:
        # Partial price data - some legs missing prices after enrichment
        result["snapshots_status"] = "partial_price"
    elif legs_with_snapshots == 0:
        result["snapshots_status"] = "missing"
    elif legs_with_snapshots < len(position["legs"]):
        result["snapshots_status"] = "partial"
    else:
        result["snapshots_status"] = "ok"

    # Compute rollup metrics
    result["gross_notional_usd"] = gross_notional_usd
    result["net_delta_usd"] = net_delta_usd

    # Set risk flags
    result["warn"] = False
    result["crit"] = False
    result["warn_reason"] = None
    result["crit_reason"] = None

    # If partial_price, set warn with reason missing_price instead of computing drift
    if result["snapshots_status"] == "partial_price":
        result["warn"] = True
        result["warn_reason"] = "missing_price"
        # Do NOT compute drift_pct or check thresholds
        result["drift_usd"] = None
        result["drift_pct"] = None
    else:
        # Compute drift (absolute deviation from delta-neutral)
        # For a delta-neutral position, net_delta_usd should be close to 0
        drift_usd = abs(net_delta_usd)
        result["drift_usd"] = drift_usd

        # Compute drift percentage if gross notional available
        if gross_notional_usd is not None and gross_notional_usd > 0:
            drift_pct = drift_usd / gross_notional_usd
            result["drift_pct"] = drift_pct
        else:
            result["drift_pct"] = None

        # Check USD thresholds
        if drift_usd >= crit_drift_usd:
            result["crit"] = True
            result["crit_reason"] = f"drift_usd >= ${crit_drift_usd:.0f}"
        elif drift_usd >= warn_drift_usd:
            result["warn"] = True
            result["warn_reason"] = f"drift_usd >= ${warn_drift_usd:.0f}"

        # Check percentage thresholds
        if result["drift_pct"] is not None:
            if drift_pct >= crit_drift_pct:
                result["crit"] = True
                if result["crit_reason"]:
                    result["crit_reason"] += f", drift_pct >= {crit_drift_pct*100:.0f}%"
                else:
                    result["crit_reason"] = f"drift_pct >= {crit_drift_pct*100:.0f}%"
            elif drift_pct >= warn_drift_pct:
                result["warn"] = True
                if result["warn_reason"]:
                    result["warn_reason"] += f", drift_pct >= {warn_drift_pct*100:.0f}%"
                else:
                    result["warn_reason"] = f"drift_pct >= {warn_drift_pct*100:.0f}%"

    # Include raw inputs for debugging
    result["raw_position"] = position
    result["raw_leg_snapshots"] = leg_snapshots

    return result


def compute_all_rollups(con, warn_drift_usd: float = DEFAULT_WARN_DRIFT_USD,
                        crit_drift_usd: float = DEFAULT_CRIT_DRIFT_USD,
                        warn_drift_pct: float = DEFAULT_WARN_DRIFT_PCT,
                        crit_drift_pct: float = DEFAULT_CRIT_DRIFT_PCT) -> List[Dict[str, Any]]:
    """
    Compute risk rollups for all managed positions.

    Args:
        con: SQLite database connection
        warn_drift_usd: Warning threshold for drift in USD
        crit_drift_usd: Critical threshold for drift in USD
        warn_drift_pct: Warning threshold for drift percentage
        crit_drift_pct: Critical threshold for drift percentage

    Returns:
        List of position rollup dicts with risk metrics
    """
    # Load positions
    positions = load_managed_positions(con)

    if not positions:
        return []

    # Load latest snapshots for all legs
    position_ids = [pos["position_id"] for pos in positions]
    leg_snapshots = load_latest_leg_snapshots(con, position_ids)

    # Compute rollups (pass con for price enrichment)
    rollups = []
    for position in positions:
        rollup = compute_position_rollup(
            position, leg_snapshots,
            warn_drift_usd, crit_drift_usd, warn_drift_pct, crit_drift_pct,
            con=con
        )
        rollups.append(rollup)

    return rollups
