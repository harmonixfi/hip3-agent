"""Hyperliquid fill ingester.

Pulls trade fills from userFillsByTime for all managed wallets,
resolves spot @index coins, maps to position legs, and inserts into pm_fills.

Usage:
    from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills

    con = sqlite3.connect("tracking/db/arbit_v3.db")
    spot_cache = fetch_spot_index_map()
    count = ingest_hyperliquid_fills(con, spot_cache)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from tracking.pipeline.spot_meta import resolve_coin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_ms() -> int:
    return int(time.time() * 1000)


def generate_synthetic_tid(
    venue: str,
    account_id: str,
    inst_id: str,
    side: str,
    px: float,
    sz: float,
    ts: int,
) -> str:
    """Generate a deterministic synthetic trade ID for venues without native TIDs."""
    payload = f"{venue}|{account_id}|{inst_id}|{side}|{px}|{sz}|{ts}"
    h = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"syn_{h}"


# ---------------------------------------------------------------------------
# Target loading
# ---------------------------------------------------------------------------

def load_fill_targets(
    con: sqlite3.Connection,
    *,
    include_closed: bool = False,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Load all legs that should receive fill mappings.

    By default, excludes CLOSED positions (fills for closed positions have no
    active leg to map to). Set include_closed=True for backfill operations.

    Returns list of dicts: {leg_id, position_id, inst_id, side, account_id, venue}
    """
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        sql = f"""
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE l.position_id IN ({placeholders})
        """
        rows = con.execute(sql, position_ids).fetchall()
    elif include_closed:
        sql = """
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
        """
        rows = con.execute(sql).fetchall()
    else:
        sql = """
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE p.status != 'CLOSED'
        """
        rows = con.execute(sql).fetchall()

    return [
        {
            "leg_id": r[0],
            "position_id": r[1],
            "inst_id": r[2],
            "side": r[3],
            "account_id": r[4],
            "venue": r[5],
        }
        for r in rows
    ]


def map_fill_to_leg(
    inst_id: str,
    account_id: str,
    targets: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    """Find the matching leg for a fill based on inst_id + account_id.

    Returns the target dict or None if no match found.
    """
    for t in targets:
        if t["inst_id"] == inst_id and t["account_id"] == account_id:
            return t
    return None


# ---------------------------------------------------------------------------
# Fill insertion
# ---------------------------------------------------------------------------

_INSERT_FILL_SQL = """
    INSERT OR IGNORE INTO pm_fills (
        venue, account_id, tid, oid, inst_id, side, px, sz,
        fee, fee_currency, ts, closed_pnl, dir, builder_fee,
        position_id, leg_id, raw_json, meta_json
    ) VALUES (
        :venue, :account_id, :tid, :oid, :inst_id, :side, :px, :sz,
        :fee, :fee_currency, :ts, :closed_pnl, :dir, :builder_fee,
        :position_id, :leg_id, :raw_json, :meta_json
    )
"""


def insert_fills(con: sqlite3.Connection, fills: List[Dict[str, Any]]) -> int:
    """Insert fills into pm_fills, skipping duplicates via UNIQUE constraint.

    Returns number of newly inserted rows.
    """
    if not fills:
        return 0

    before = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]

    for fill in fills:
        params = {
            "venue": fill.get("venue", ""),
            "account_id": fill.get("account_id", ""),
            "tid": fill.get("tid"),
            "oid": fill.get("oid"),
            "inst_id": fill.get("inst_id", ""),
            "side": fill.get("side", ""),
            "px": fill.get("px", 0),
            "sz": fill.get("sz", 0),
            "fee": fill.get("fee"),
            "fee_currency": fill.get("fee_currency"),
            "ts": fill.get("ts", 0),
            "closed_pnl": fill.get("closed_pnl"),
            "dir": fill.get("dir"),
            "builder_fee": fill.get("builder_fee"),
            "position_id": fill.get("position_id"),
            "leg_id": fill.get("leg_id"),
            "raw_json": fill.get("raw_json"),
            "meta_json": fill.get("meta_json"),
        }
        con.execute(_INSERT_FILL_SQL, params)

    con.commit()

    after = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
    return after - before


# ---------------------------------------------------------------------------
# HL fill parsing
# ---------------------------------------------------------------------------

def parse_hl_fill(
    raw: Dict[str, Any],
    account_id: str,
    spot_index_map: Dict[int, str],
    targets: List[Dict[str, str]],
    *,
    dex: str = "",
) -> Optional[Dict[str, Any]]:
    """Parse a single HL userFillsByTime response item into a pm_fills dict.

    Returns None if the fill cannot be parsed or mapped.
    """
    ts = raw.get("time") or raw.get("ts") or raw.get("timestamp")
    if ts is None:
        return None
    ts_ms = int(ts)

    raw_coin = str(raw.get("coin") or raw.get("asset") or "")
    if not raw_coin:
        return None

    # Resolve coin to inst_id
    try:
        inst_id = resolve_coin(raw_coin, spot_index_map)
    except ValueError:
        return None

    # Map to leg
    target = map_fill_to_leg(inst_id, account_id, targets)

    # Parse fill fields
    px = float(raw.get("px", 0))
    sz = float(raw.get("sz", 0))
    if px <= 0 or sz <= 0:
        return None

    hl_side = str(raw.get("side", ""))
    side = "BUY" if hl_side == "B" else "SELL" if hl_side == "A" else ""
    if not side:
        return None

    fee = None
    raw_fee = raw.get("fee")
    if raw_fee is not None:
        try:
            fee = float(raw_fee)
        except (TypeError, ValueError):
            pass

    builder_fee = None
    raw_bfee = raw.get("builderFee")
    if raw_bfee is not None:
        try:
            builder_fee = float(raw_bfee)
        except (TypeError, ValueError):
            pass

    closed_pnl = None
    raw_cpnl = raw.get("closedPnl")
    if raw_cpnl is not None:
        try:
            closed_pnl = float(raw_cpnl)
        except (TypeError, ValueError):
            pass

    tid = str(raw.get("tid", "")) or None
    oid = str(raw.get("oid", "")) or None

    meta = {"raw_coin": raw_coin, "dex": dex}
    if raw_coin.startswith("@"):
        meta["resolved_from_spot_index"] = True

    return {
        "venue": "hyperliquid",
        "account_id": account_id,
        "tid": tid,
        "oid": oid,
        "inst_id": inst_id,
        "side": side,
        "px": px,
        "sz": sz,
        "fee": fee,
        "fee_currency": "USDC" if fee is not None else None,
        "ts": ts_ms,
        "closed_pnl": closed_pnl,
        "dir": str(raw.get("dir", "")) or None,
        "builder_fee": builder_fee,
        "position_id": target["position_id"] if target else None,
        "leg_id": target["leg_id"] if target else None,
        "raw_json": json.dumps(raw),
        "meta_json": json.dumps(meta),
    }


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def get_watermark(con: sqlite3.Connection, venue: str, account_id: str) -> int:
    """Get the latest fill timestamp for a venue+account, or 0 if none."""
    row = con.execute(
        "SELECT MAX(ts) FROM pm_fills WHERE venue = ? AND account_id = ?",
        (venue, account_id),
    ).fetchone()
    return int(row[0]) if row and row[0] else 0


_WINDOW_MS = 24 * 3600 * 1000  # 24 hours in milliseconds


def _iter_time_windows(start_ms: int, end_ms: int, window_ms: int = _WINDOW_MS):
    """Yield (win_start, win_end) chunks from start to end.

    Matches the windowing pattern in pm_cashflows.py to avoid
    response truncation on large time ranges.
    """
    cursor = start_ms
    while cursor < end_ms:
        win_end = min(cursor + window_ms, end_ms)
        yield cursor, win_end
        cursor = win_end


def ingest_hyperliquid_fills(
    con: sqlite3.Connection,
    spot_index_map: Dict[int, str],
    *,
    include_closed: bool = False,
    since_ms: Optional[int] = None,
    position_ids: Optional[List[str]] = None,
) -> int:
    """Pull and ingest fills from Hyperliquid for all managed wallets.

    Args:
        con: DB connection
        spot_index_map: from fetch_spot_index_map()
        include_closed: if True, also ingest for CLOSED positions (backfill)
        since_ms: override start time (epoch ms). Default: watermark from DB.
        position_ids: if set, only ingest for these specific positions.

    Returns: number of new fills inserted.
    """
    from tracking.connectors.hyperliquid_private import (
        post_info as hyperliquid_post_info,
        split_inst_id,
    )

    targets = load_fill_targets(
        con,
        include_closed=include_closed,
        position_ids=position_ids,
    )
    if not targets:
        return 0

    # Group targets by account_id
    accounts: Dict[str, List[Dict[str, str]]] = {}
    for t in targets:
        accounts.setdefault(t["account_id"], []).append(t)

    end_ms = now_ms()
    all_fills: List[Dict[str, Any]] = []

    for account_id, account_targets in accounts.items():
        # Determine which dexes this account needs
        dexes_needed: set = set()
        for t in account_targets:
            dex, _coin = split_inst_id(t["inst_id"])
            dexes_needed.add(dex)
        # Spot fills come through default (no dex) endpoint
        dexes_needed.add("")

        start_ms = since_ms if since_ms is not None else get_watermark(con, "hyperliquid", account_id)
        # Add 1ms to avoid re-fetching the last fill
        if start_ms > 0:
            start_ms += 1

        for dex in dexes_needed:
            # Use 24h windows to avoid response truncation (matches pm_cashflows pattern)
            for win_start, win_end in _iter_time_windows(start_ms, end_ms):
                try:
                    fills_raw = hyperliquid_post_info(
                        {
                            "type": "userFillsByTime",
                            "user": account_id,
                            "startTime": int(win_start),
                            "endTime": int(win_end),
                            "aggregateByTime": False,
                        },
                        dex=dex or "",
                    )
                except Exception as e:
                    print(f"  WARN: failed to fetch fills for {account_id} dex={dex!r} window={win_start}-{win_end}: {e}")
                    continue

                if not isinstance(fills_raw, list):
                    continue

                for raw_fill in fills_raw:
                    if not isinstance(raw_fill, dict):
                        continue
                    parsed = parse_hl_fill(
                        raw_fill, account_id, spot_index_map, targets, dex=dex,
                    )
                    if parsed:
                        all_fills.append(parsed)

    inserted = insert_fills(con, all_fills)
    print(f"  fills: {len(all_fills)} parsed, {inserted} new inserted")
    return inserted
