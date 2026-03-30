"""Felix equity fill ingester.

Takes parsed fills from FelixPrivateConnector.fetch_fills() and ingests them
into pm_fills with position/leg mapping. Uses the same insert_fills() and
map_fill_to_leg() infrastructure from the HL fill ingester.

Usage:
    from tracking.connectors.felix_private import FelixPrivateConnector
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills_from_api

    connector = FelixPrivateConnector(jwt="...", wallet_address="0x...")
    count = ingest_felix_fills_from_api(con, connector)
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from tracking.pipeline.fill_ingester import (
    insert_fills,
    load_fill_targets,
    map_fill_to_leg,
)


def ingest_felix_fills(
    con: sqlite3.Connection,
    raw_fills: List[Dict[str, Any]],
    *,
    include_closed: bool = False,
    position_ids: Optional[List[str]] = None,
) -> int:
    """Map raw Felix fills to position legs and insert into pm_fills.

    Args:
        con: DB connection
        raw_fills: list of fill dicts from FelixPrivateConnector.fetch_fills()
                   or directly constructed (for testing)
        include_closed: include CLOSED positions when mapping
        position_ids: limit mapping to these positions

    Returns:
        Number of newly inserted fills
    """
    if not raw_fills:
        return 0

    # Load mapping targets (felix venue legs)
    targets = load_fill_targets(
        con,
        include_closed=include_closed,
        position_ids=position_ids,
    )

    # Map each fill to its position/leg
    mapped_fills = []
    for fill in raw_fills:
        inst_id = fill.get("inst_id", "")
        account_id = fill.get("account_id", "")

        target = map_fill_to_leg(inst_id, account_id, targets)

        mapped = dict(fill)
        if target:
            mapped["position_id"] = target["position_id"]
            mapped["leg_id"] = target["leg_id"]
        # If no target found, position_id and leg_id remain as-is (None)

        mapped_fills.append(mapped)

    return insert_fills(con, mapped_fills)


def ingest_felix_fills_from_api(
    con: sqlite3.Connection,
    connector: Any,  # FelixPrivateConnector
    *,
    include_closed: bool = False,
    since_ms: Optional[int] = None,
) -> int:
    """Full Felix fill ingestion: fetch from API + map + insert.

    Args:
        con: DB connection
        connector: FelixPrivateConnector instance with valid JWT
        include_closed: include CLOSED positions when mapping
        since_ms: only fetch fills since this timestamp

    Returns:
        Number of newly inserted fills
    """
    # Get watermark from DB if not specified
    if since_ms is None:
        row = con.execute(
            "SELECT MAX(ts) FROM pm_fills WHERE venue = 'felix'"
        ).fetchone()
        since_ms = int(row[0]) if row and row[0] else None

    raw_fills = connector.fetch_fills(since_ms=since_ms)

    if not raw_fills:
        return 0

    return ingest_felix_fills(
        con,
        raw_fills,
        include_closed=include_closed,
    )
