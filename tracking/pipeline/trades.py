"""Trade aggregation layer.

Pure math first (this file); DB I/O layered on top in later tasks.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List, Optional, Tuple


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
    """True iff half-open intervals overlap. Touching edges do not overlap."""
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
    dt = datetime.fromtimestamp(anchor_ts_ms / 1000)
    stamp = dt.strftime("%Y%m%d%H%M")
    base_id = f"trd_{base}_{stamp}_{trade_type.lower()}"
    if base_id not in existing_ids:
        return base_id
    n = 2
    while f"{base_id}_{n}" in existing_ids:
        n += 1
    return f"{base_id}_{n}"
