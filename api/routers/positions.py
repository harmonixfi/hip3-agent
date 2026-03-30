"""Position endpoints.

GET /api/positions           — list positions with computed metrics
GET /api/positions/closed    — closed position P&L analysis
GET /api/positions/{id}      — single position detail
GET /api/positions/{id}/fills — trade fills for a position
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.models.schemas import (
    ClosedPositionAnalysis,
    CashflowItem,
    DailyFundingItem,
    FillItem,
    FillsResponse,
    FillsSummaryItem,
    LegDetail,
    PositionDetail,
    PositionSummary,
    SubPairSpread,
)

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _ts_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _build_position_summary(
    pos: sqlite3.Row, db: sqlite3.Connection
) -> PositionSummary:
    """Build a PositionSummary from a pm_positions row + joined data."""
    position_id = pos["position_id"]

    # Parse meta_json for base and strategy
    meta = {}
    if pos["meta_json"]:
        try:
            meta = json.loads(pos["meta_json"])
        except (json.JSONDecodeError, TypeError):
            pass

    base = meta.get("base", position_id)
    strategy = meta.get("strategy_type", pos["strategy"] if "strategy" in pos.keys() else "SPOT_PERP")
    amount_usd = meta.get("amount_usd")

    # Legs
    leg_rows = db.execute(
        """
        SELECT l.*, ep.avg_entry_price
        FROM pm_legs l
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        WHERE l.position_id = ?
        """,
        (position_id,),
    ).fetchall()

    legs = []
    total_upnl = 0.0
    for lr in leg_rows:
        upnl = lr["unrealized_pnl"] or 0.0
        total_upnl += upnl
        legs.append(
            LegDetail(
                leg_id=lr["leg_id"],
                venue=lr["venue"],
                inst_id=lr["inst_id"],
                side=lr["side"],
                size=lr["size"],
                avg_entry_price=lr["avg_entry_price"],
                current_price=lr["current_price"],
                unrealized_pnl=round(upnl, 4) if upnl else None,
                account_id=lr["account_id"],
            )
        )

    # Sub-pair spreads
    spread_rows = db.execute(
        "SELECT * FROM pm_spreads WHERE position_id = ?", (position_id,)
    ).fetchall()

    sub_pairs = []
    for sr in spread_rows:
        sub_pairs.append(
            SubPairSpread(
                long_leg_id=sr["long_leg_id"],
                short_leg_id=sr["short_leg_id"],
                entry_spread_bps=(
                    round(sr["entry_spread"] * 10000, 1) if sr["entry_spread"] is not None else None
                ),
                exit_spread_bps=(
                    round(sr["exit_spread"] * 10000, 1) if sr["exit_spread"] is not None else None
                ),
                spread_pnl_bps=(
                    round(sr["spread_pnl_bps"], 1) if sr["spread_pnl_bps"] is not None else None
                ),
            )
        )

    # Funding and fees for this position
    funding = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
        (position_id,),
    ).fetchone()[0]

    fees = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FEE'",
        (position_id,),
    ).fetchone()[0]

    net_carry = funding + fees
    upnl_pct = (total_upnl / amount_usd * 100) if amount_usd and amount_usd > 0 else None

    # Carry APR: annualized from position open date
    carry_apr = None
    if amount_usd and amount_usd > 0 and pos["created_at_ms"]:
        days_open = (
            datetime.now(timezone.utc).timestamp() * 1000 - pos["created_at_ms"]
        ) / (86400 * 1000)
        if days_open > 0:
            carry_apr = round((net_carry / amount_usd) / days_open * 365 * 100, 2)

    return PositionSummary(
        position_id=position_id,
        base=base,
        strategy=strategy,
        status=pos["status"],
        amount_usd=round(amount_usd, 2) if amount_usd else None,
        unrealized_pnl=round(total_upnl, 2) if total_upnl else None,
        unrealized_pnl_pct=round(upnl_pct, 2) if upnl_pct is not None else None,
        funding_earned=round(funding, 2),
        fees_paid=round(fees, 2),
        net_carry=round(net_carry, 2),
        carry_apr=carry_apr,
        sub_pairs=sub_pairs,
        legs=legs,
        opened_at=_ts_to_iso(pos["created_at_ms"]),
    )


# -------------------------------------------------------------------
# IMPORTANT: /closed must be defined BEFORE /{position_id}
# so FastAPI matches it literally, not as a path parameter.
# -------------------------------------------------------------------

@router.get("/closed", response_model=list[ClosedPositionAnalysis])
def list_closed_positions(
    db: sqlite3.Connection = Depends(get_db),
):
    """Return closed position P&L analysis."""
    rows = db.execute(
        "SELECT * FROM pm_positions WHERE status = 'CLOSED' ORDER BY closed_at_ms DESC"
    ).fetchall()

    results = []
    for pos in rows:
        position_id = pos["position_id"]
        meta = {}
        if pos["meta_json"]:
            try:
                meta = json.loads(pos["meta_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        base = meta.get("base", position_id)
        amount_usd = meta.get("amount_usd")

        # Funding and fees
        funding = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
            (position_id,),
        ).fetchone()[0]

        fees = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FEE'",
            (position_id,),
        ).fetchone()[0]

        # Realized spread PnL from closed fills
        realized_spread = db.execute(
            "SELECT COALESCE(SUM(closed_pnl), 0) FROM pm_fills WHERE position_id = ?",
            (position_id,),
        ).fetchone()[0]

        net_pnl = realized_spread + funding + fees

        # Duration
        duration_days = None
        if pos["created_at_ms"] and pos["closed_at_ms"]:
            duration_days = int(
                (pos["closed_at_ms"] - pos["created_at_ms"]) / (86400 * 1000)
            )

        # APR
        net_apr = None
        if amount_usd and amount_usd > 0 and duration_days and duration_days > 0:
            net_apr = round((net_pnl / amount_usd) / duration_days * 365 * 100, 2)

        # Entry/exit spreads (avg across sub-pairs)
        spread_row = db.execute(
            """
            SELECT AVG(entry_spread), AVG(exit_spread)
            FROM pm_spreads WHERE position_id = ?
            """,
            (position_id,),
        ).fetchone()

        entry_spread_bps = (
            round(spread_row[0] * 10000, 1) if spread_row and spread_row[0] is not None else None
        )
        exit_spread_bps = (
            round(spread_row[1] * 10000, 1) if spread_row and spread_row[1] is not None else None
        )

        results.append(
            ClosedPositionAnalysis(
                position_id=position_id,
                base=base,
                opened_at=_ts_to_iso(pos["created_at_ms"]),
                closed_at=_ts_to_iso(pos["closed_at_ms"]),
                duration_days=duration_days,
                amount_usd=round(amount_usd, 2) if amount_usd is not None else None,
                realized_spread_pnl=round(realized_spread, 2),
                total_funding_earned=round(funding, 2),
                total_fees_paid=round(fees, 2),
                net_pnl=round(net_pnl, 2),
                net_apr=net_apr,
                entry_spread_bps=entry_spread_bps,
                exit_spread_bps=exit_spread_bps,
            )
        )

    return results


@router.get("", response_model=list[PositionSummary])
def list_positions(
    status: str = Query("OPEN", description="Filter: OPEN, CLOSED, PAUSED, ALL"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return all positions with computed metrics."""
    if status.upper() == "ALL":
        rows = db.execute(
            "SELECT * FROM pm_positions ORDER BY created_at_ms DESC"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM pm_positions WHERE status = ? ORDER BY created_at_ms DESC",
            (status.upper(),),
        ).fetchall()

    return [_build_position_summary(row, db) for row in rows]


@router.get("/{position_id}", response_model=PositionDetail)
def get_position(
    position_id: str,
    db: sqlite3.Connection = Depends(get_db),
):
    """Return detailed position with legs, spreads, cashflows, fills summary."""
    pos = db.execute(
        "SELECT * FROM pm_positions WHERE position_id = ?", (position_id,)
    ).fetchone()

    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    # Build base summary
    summary = _build_position_summary(pos, db)

    # Fills summary per leg
    fills_summary_rows = db.execute(
        """
        SELECT leg_id, COUNT(*) AS fill_count,
               MIN(ts) AS first_fill_ts, MAX(ts) AS last_fill_ts
        FROM pm_fills
        WHERE position_id = ? AND leg_id IS NOT NULL
        GROUP BY leg_id
        """,
        (position_id,),
    ).fetchall()

    fills_summary = [
        FillsSummaryItem(
            leg_id=r["leg_id"],
            fill_count=r["fill_count"],
            first_fill=_ts_to_iso(r["first_fill_ts"]),
            last_fill=_ts_to_iso(r["last_fill_ts"]),
        )
        for r in fills_summary_rows
    ]

    # Cashflows for this position
    cf_rows = db.execute(
        """
        SELECT cashflow_id, cf_type, amount, currency, ts, description
        FROM pm_cashflows
        WHERE position_id = ?
        ORDER BY ts DESC
        """,
        (position_id,),
    ).fetchall()

    cashflows = [
        CashflowItem(
            cashflow_id=r["cashflow_id"],
            cf_type=r["cf_type"],
            amount=round(r["amount"], 4),
            currency=r["currency"],
            ts=_ts_to_iso(r["ts"]),
            description=r["description"],
        )
        for r in cf_rows
    ]

    # Daily funding series (last 7 days)
    daily_funding_rows = db.execute(
        """
        SELECT DATE(ts / 1000, 'unixepoch') AS day, SUM(amount) AS daily_amount
        FROM pm_cashflows
        WHERE position_id = ? AND cf_type = 'FUNDING'
          AND ts >= (strftime('%s', 'now', '-7 days') * 1000)
        GROUP BY day
        ORDER BY day
        """,
        (position_id,),
    ).fetchall()

    daily_funding = [
        DailyFundingItem(date=r["day"], amount=round(r["daily_amount"], 4))
        for r in daily_funding_rows
    ]

    return PositionDetail(
        **summary.model_dump(),
        fills_summary=fills_summary,
        cashflows=cashflows,
        daily_funding_series=daily_funding,
    )


@router.get("/{position_id}/fills", response_model=FillsResponse)
def get_position_fills(
    position_id: str,
    leg_id: Optional[str] = Query(None, description="Filter by leg_id"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return paginated trade fills for a position."""
    # Verify position exists
    pos = db.execute(
        "SELECT position_id FROM pm_positions WHERE position_id = ?", (position_id,)
    ).fetchone()
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    # Build query
    where = "WHERE position_id = ?"
    params: list = [position_id]

    if leg_id:
        where += " AND leg_id = ?"
        params.append(leg_id)

    # Total count
    total = db.execute(
        f"SELECT COUNT(*) FROM pm_fills {where}", params
    ).fetchone()[0]

    # Paginated results
    rows = db.execute(
        f"""
        SELECT fill_id, leg_id, inst_id, side, px, sz, fee, ts, dir, tid
        FROM pm_fills {where}
        ORDER BY ts DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    fills = [
        FillItem(
            fill_id=r["fill_id"],
            leg_id=r["leg_id"],
            inst_id=r["inst_id"],
            side=r["side"],
            px=r["px"],
            sz=r["sz"],
            fee=r["fee"],
            ts=r["ts"],
            dir=r["dir"],
            tid=r["tid"],
        )
        for r in rows
    ]

    return FillsResponse(
        position_id=position_id,
        fills=fills,
        total=total,
        limit=limit,
        offset=offset,
    )