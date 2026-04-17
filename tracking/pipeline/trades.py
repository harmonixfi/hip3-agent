"""Trade aggregation layer.

Pure math first (this file); DB I/O layered on top in later tasks.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


VALID_TYPES = {"OPEN", "CLOSE"}
VALID_SIDES = {"LONG", "SHORT"}


@dataclass(frozen=True)
class FillRow:
    """Minimal fill projection used by aggregate_fills. Maps to pm_fills columns."""
    fill_id: int
    px: float
    sz: float
    fee: Optional[float] = None


@dataclass(frozen=True)
class LegAggregate:
    """Aggregate of a set of fills for one leg+side: size, notional, VWAP avg_px, total fees, count."""
    size: float
    notional: float
    avg_px: Optional[float]  # None when size == 0
    fees: float
    fill_count: int


# ---------------------------------------------------------------------------
# Pure math helpers (no I/O, no DB)
# ---------------------------------------------------------------------------


def aggregate_fills(fills: Iterable[FillRow]) -> LegAggregate:
    """Compute VWAP aggregate for a set of fills (all same leg + side).

    Returns zeroed aggregate when no fills. avg_px is None iff size == 0.
    """
    fills = list(fills)
    if not fills:
        return LegAggregate(size=0.0, notional=0.0, avg_px=None, fees=0.0, fill_count=0)

    notional = 0.0
    size = 0.0
    fees = 0.0
    for f in fills:
        notional += f.px * f.sz
        size += f.sz
        if f.fee is not None:
            fees += f.fee

    avg_px: Optional[float] = notional / size if size > 0 else None
    return LegAggregate(
        size=size,
        notional=notional,
        avg_px=avg_px,
        fees=fees,
        fill_count=len(fills),
    )


def compute_spread_bps(long_avg_px: Optional[float], short_avg_px: Optional[float]) -> Optional[float]:
    """spread_bps = (long_avg_px / short_avg_px - 1) * 10_000.

    Returns None if either side has no fills (avg_px is None).
    Raises ValueError on zero short price.
    """
    if long_avg_px is None or short_avg_px is None:
        return None
    if short_avg_px == 0:
        raise ValueError("zero short price")
    return (long_avg_px / short_avg_px - 1.0) * 10_000.0


def compute_realized_pnl_bps(
    open_spreads_and_sizes: List[Tuple[float, float]],
    close_spread_bps: float,
) -> float:
    """Size-weighted avg of FINALIZED OPEN spreads minus close spread.

    Args:
        open_spreads_and_sizes: list of (spread_bps, long_size) for FINALIZED OPEN
                                trades of the same Position. Zero-size entries skipped.
        close_spread_bps: spread_bps of the current CLOSE trade.

    Returns:
        realized_pnl_bps = weighted_avg_open_spread - close_spread_bps.
    """
    weighted = [(s, w) for s, w in open_spreads_and_sizes if w > 0]
    if not weighted:
        raise ValueError("no FINALIZED OPEN trades with positive size")

    total_weight = sum(w for _, w in weighted)
    weighted_avg = sum(s * w for s, w in weighted) / total_weight
    return weighted_avg - close_spread_bps


def side_for(trade_type: str, leg_side: str) -> str:
    """Map trade_type + leg_side -> expected pm_fills.side value.

    OPEN+LONG->BUY; OPEN+SHORT->SELL; CLOSE+LONG->SELL; CLOSE+SHORT->BUY.
    """
    if trade_type not in VALID_TYPES:
        raise ValueError(f"invalid trade_type: {trade_type}")
    if leg_side not in VALID_SIDES:
        raise ValueError(f"invalid leg_side: {leg_side}")

    if trade_type == "OPEN":
        return "BUY" if leg_side == "LONG" else "SELL"
    # CLOSE
    return "SELL" if leg_side == "LONG" else "BUY"


# ---------------------------------------------------------------------------
# Trade ID + window helpers (pure)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradeWindow:
    """Half-open interval [start_ts, end_ts) in epoch ms."""
    start_ts: int
    end_ts: int


def overlaps(a: TradeWindow, b: TradeWindow) -> bool:
    """True iff half-open intervals overlap. Touching edges and zero-width intervals do not overlap."""
    if a.start_ts >= a.end_ts or b.start_ts >= b.end_ts:
        return False
    return a.start_ts < b.end_ts and b.start_ts < a.end_ts


def resolve_trade_id(
    base: str,
    trade_type: str,
    anchor_ts_ms: int,
    existing_ids: set[str],
) -> str:
    """Generate deterministic trade_id.

    Format: trd_<base>_<YYYYMMDDHHmm>_<open|close>[_<n>]
    Suffix _2, _3, ... on collision.
    """
    if trade_type not in VALID_TYPES:
        raise ValueError(f"invalid trade_type: {trade_type}")
    if not base or not re.fullmatch(r"[A-Za-z0-9-]+", base):
        raise ValueError(f"invalid base (must be alphanumeric or dashes, non-empty): {base!r}")
    dt = datetime.fromtimestamp(anchor_ts_ms / 1000, tz=timezone.utc)
    stamp = dt.strftime("%Y%m%d%H%M")
    base_id = f"trd_{base}_{stamp}_{trade_type.lower()}"
    if base_id not in existing_ids:
        return base_id
    n = 2
    while f"{base_id}_{n}" in existing_ids:
        n += 1
    return f"{base_id}_{n}"


# ---------------------------------------------------------------------------
# DB-backed trade creation
# ---------------------------------------------------------------------------


class TradeCreateError(Exception):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fetch_position_legs(
    con: sqlite3.Connection, position_id: str
) -> Dict[str, Dict[str, Any]]:
    """Return {'LONG': {leg_id, account_id, inst_id, venue}, 'SHORT': {...}}."""
    rows = con.execute(
        "SELECT leg_id, side, account_id, inst_id, venue FROM pm_legs WHERE position_id = ?",
        (position_id,),
    ).fetchall()
    legs: Dict[str, Dict[str, Any]] = {}
    for leg_id, side, account_id, inst_id, venue in rows:
        legs[side] = {
            "leg_id": leg_id,
            "account_id": account_id,
            "inst_id": inst_id,
            "venue": venue,
        }
    return legs


def _fetch_window_fills(
    con: sqlite3.Connection,
    leg_id: str,
    fill_side: str,
    start_ts: int,
    end_ts: int,
) -> List[FillRow]:
    """Fetch fills for a leg in [start_ts, end_ts) with matching side, excluding
    fills already bound to another trade via pm_trade_fills."""
    rows = con.execute(
        """
        SELECT f.fill_id, f.px, f.sz, f.fee
        FROM pm_fills f
        WHERE f.leg_id = ?
          AND f.side = ?
          AND f.ts >= ?
          AND f.ts < ?
          AND NOT EXISTS (SELECT 1 FROM pm_trade_fills tf WHERE tf.fill_id = f.fill_id)
        ORDER BY f.ts
        """,
        (leg_id, fill_side, start_ts, end_ts),
    ).fetchall()
    return [FillRow(fill_id=r[0], px=r[1], sz=r[2], fee=r[3]) for r in rows]


def _fetch_finalized_open_spreads(
    con: sqlite3.Connection, position_id: str
) -> List[Tuple[float, float]]:
    """(spread_bps, long_size) of FINALIZED OPEN trades."""
    rows = con.execute(
        "SELECT spread_bps, long_size FROM pm_trades "
        "WHERE position_id = ? AND trade_type = 'OPEN' AND state = 'FINALIZED' "
        "AND spread_bps IS NOT NULL AND long_size IS NOT NULL AND long_size > 0",
        (position_id,),
    ).fetchall()
    return [(float(r[0]), float(r[1])) for r in rows]


def create_draft_trade(
    con: sqlite3.Connection,
    position_id: str,
    trade_type: str,
    start_ts: int,
    end_ts: int,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Create DRAFT trade, materialize pm_trade_fills, compute aggregates.

    Raises TradeCreateError on validation failure.
    """
    if trade_type not in VALID_TYPES:
        raise TradeCreateError(f"invalid trade_type: {trade_type}")
    if start_ts >= end_ts:
        raise TradeCreateError("invalid window: start_ts must be < end_ts")

    pos_row = con.execute(
        "SELECT base, status FROM pm_positions WHERE position_id = ?",
        (position_id,),
    ).fetchone()
    if not pos_row:
        raise TradeCreateError(f"position not found: {position_id}")
    base, pos_status = pos_row
    if pos_status == "CLOSED":
        raise TradeCreateError(f"position {position_id} is CLOSED")
    if not base:
        raise TradeCreateError(f"position {position_id} missing base — run migration")

    legs = _fetch_position_legs(con, position_id)
    if "LONG" not in legs or "SHORT" not in legs:
        raise TradeCreateError(f"position {position_id} missing LONG or SHORT leg")

    long_leg = legs["LONG"]
    short_leg = legs["SHORT"]

    long_side_filter = side_for(trade_type, "LONG")
    short_side_filter = side_for(trade_type, "SHORT")

    long_fills = _fetch_window_fills(con, long_leg["leg_id"], long_side_filter, start_ts, end_ts)
    short_fills = _fetch_window_fills(con, short_leg["leg_id"], short_side_filter, start_ts, end_ts)

    if not long_fills and not short_fills:
        raise TradeCreateError(
            "no fills in window (empty window, already linked to another trade, or wrong wallet)"
        )

    long_agg = aggregate_fills(long_fills)
    short_agg = aggregate_fills(short_fills)
    spread_bps = compute_spread_bps(long_agg.avg_px, short_agg.avg_px)

    realized_pnl_bps: Optional[float] = None
    if trade_type == "CLOSE" and spread_bps is not None:
        opens = _fetch_finalized_open_spreads(con, position_id)
        if opens:
            realized_pnl_bps = compute_realized_pnl_bps(opens, spread_bps)

    existing_ids = {
        r[0] for r in con.execute("SELECT trade_id FROM pm_trades").fetchall()
    }
    trade_id = resolve_trade_id(base, trade_type, start_ts, existing_ids)

    now = _now_ms()
    con.execute(
        """
        INSERT INTO pm_trades (
            trade_id, position_id, trade_type, state, start_ts, end_ts, note,
            long_leg_id, long_size, long_notional, long_avg_px, long_fees, long_fill_count,
            short_leg_id, short_size, short_notional, short_avg_px, short_fees, short_fill_count,
            spread_bps, realized_pnl_bps,
            created_at_ms, computed_at_ms
        ) VALUES (?,?,?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?,?, ?,?, ?,?)
        """,
        (
            trade_id, position_id, trade_type, "DRAFT", start_ts, end_ts, note,
            long_leg["leg_id"], long_agg.size, long_agg.notional, long_agg.avg_px, long_agg.fees, long_agg.fill_count,
            short_leg["leg_id"], short_agg.size, short_agg.notional, short_agg.avg_px, short_agg.fees, short_agg.fill_count,
            spread_bps, realized_pnl_bps,
            now, now,
        ),
    )

    for f in long_fills:
        con.execute(
            "INSERT INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?, ?, 'LONG')",
            (trade_id, f.fill_id),
        )
    for f in short_fills:
        con.execute(
            "INSERT INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?, ?, 'SHORT')",
            (trade_id, f.fill_id),
        )

    con.commit()

    return {
        "trade_id": trade_id,
        "position_id": position_id,
        "trade_type": trade_type,
        "state": "DRAFT",
        "start_ts": start_ts,
        "end_ts": end_ts,
        "note": note,
        "long_leg_id": long_leg["leg_id"],
        "long_size": long_agg.size,
        "long_notional": long_agg.notional,
        "long_avg_px": long_agg.avg_px,
        "long_fees": long_agg.fees,
        "long_fill_count": long_agg.fill_count,
        "short_leg_id": short_leg["leg_id"],
        "short_size": short_agg.size,
        "short_notional": short_agg.notional,
        "short_avg_px": short_agg.avg_px,
        "short_fees": short_agg.fees,
        "short_fill_count": short_agg.fill_count,
        "spread_bps": spread_bps,
        "realized_pnl_bps": realized_pnl_bps,
        "created_at_ms": now,
        "computed_at_ms": now,
    }
