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

from api.deps import get_db, get_db_writable
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
    WindowedMetrics,
)
from api.models.trade_schemas import PositionCreateRequest

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _ts_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _gross_notional_usd_from_leg_rows(leg_rows: list[sqlite3.Row]) -> Optional[float]:
    """Sum abs(size * price) per leg (mark gross notional). pm_legs has no total_balance.

    Price: current_price, else avg_entry_price from pm_entry_prices join, else pm_legs.entry_price.
    Skips legs missing both price and size. Aligns with report script fallback logic.
    """
    total = 0.0
    found_any = False
    for lr in leg_rows:
        px = lr["current_price"]
        if px is None:
            px = lr["avg_entry_price"]
        if px is None:
            px = lr["entry_price"]
        sz = lr["size"]
        if px is None or sz is None:
            continue
        total += abs(float(px) * float(sz))
        found_any = True
    return total if found_any else None


def _windowed_metrics(
    db: sqlite3.Connection,
    position_id: str,
    amount_usd_raw: Optional[float],
    leg_rows: list[sqlite3.Row],
    now_ms: int,
    created_at_ms: Optional[int] = None,
) -> Optional[WindowedMetrics]:
    """Compute realized windowed funding and APR from pm_cashflows.

    Returns None if amount_usd_raw is unavailable.
    APR values are in percent form (e.g. 38.5 means 38.5%).
    All apr_* are None when incomplete_notional=True (unreliable denominator).
    funding_* are None when the window sum is 0.0 (no cashflows in that period).
    """
    # Step 1: detect incomplete notional (mirror _gross_notional_usd_from_leg_rows logic)
    missing_leg_ids: list[str] = []
    for lr in leg_rows:
        px = lr["current_price"]
        if px is None:
            px = lr["avg_entry_price"]
        if px is None:
            px = lr["entry_price"]
        sz = lr["size"]
        if px is None or sz is None:
            missing_leg_ids.append(lr["leg_id"])

    incomplete_notional = len(missing_leg_ids) > 0

    if amount_usd_raw is None or amount_usd_raw <= 0:
        return None

    # Step 2: single batched funding query (positional ? placeholders)
    ms_1d  = now_ms - 1  * 86400 * 1000
    ms_3d  = now_ms - 3  * 86400 * 1000
    ms_7d  = now_ms - 7  * 86400 * 1000
    ms_14d = now_ms - 14 * 86400 * 1000

    row = db.execute(
        """
        SELECT
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_1d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_3d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_7d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_14d
        FROM pm_cashflows
        WHERE position_id = ? AND cf_type = 'FUNDING'
        """,
        (ms_1d, ms_3d, ms_7d, ms_14d, position_id),
    ).fetchone()

    def _to_funding(v: Optional[float]) -> Optional[float]:
        """0.0 treated as None — no cashflows in this window."""
        if v is None or v == 0.0:
            return None
        return round(v, 4)

    funding_1d  = _to_funding(row["funding_1d"]  if row else None)
    funding_3d  = _to_funding(row["funding_3d"]  if row else None)
    funding_7d  = _to_funding(row["funding_7d"]  if row else None)
    funding_14d = _to_funding(row["funding_14d"] if row else None)

    # Step 3: derive APR (percent form). All None if incomplete_notional.
    def _apr(funding: Optional[float], days: float) -> Optional[float]:
        if incomplete_notional or funding is None or days <= 0:
            return None
        return round((funding / days) * 365 / amount_usd_raw * 100, 4)

    apr_1d  = _apr(funding_1d, 1)
    apr_3d  = _apr(funding_3d, 3)
    apr_7d  = _apr(funding_7d, 7)
    apr_14d = _apr(funding_14d, 14)

    # Step 4: null out windows wider than position age.
    # For partial windows (3d <= age < 7d, 7d <= age < 14d), show all-time total
    # with APR computed over actual elapsed days instead of the full window.
    if created_at_ms is not None:
        days_open = (now_ms - created_at_ms) / (86400 * 1000)
        if days_open < 3:
            funding_3d = None; apr_3d = None
        if days_open < 3:
            funding_7d = None; apr_7d = None
        elif days_open < 7:
            apr_7d = _apr(funding_7d, days_open)
        if days_open < 7:
            funding_14d = None; apr_14d = None
        elif days_open < 14:
            apr_14d = _apr(funding_14d, days_open)

    return WindowedMetrics(
        funding_1d=funding_1d,
        funding_3d=funding_3d,
        funding_7d=funding_7d,
        funding_14d=funding_14d,
        apr_1d=apr_1d,
        apr_3d=apr_3d,
        apr_7d=apr_7d,
        apr_14d=apr_14d,
        incomplete_notional=incomplete_notional,
        missing_leg_ids=missing_leg_ids,
    )


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

    base = pos["base"] or meta.get("base") or position_id
    strategy = (
        pos["strategy_type"]
        or meta.get("strategy_type")
        or (pos["strategy"] if "strategy" in pos.keys() else None)
        or "SPOT_PERP"
    )

    leg_rows = db.execute(
        """
        SELECT l.*, ep.avg_entry_price
        FROM pm_legs l
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        WHERE l.position_id = ?
        """,
        (position_id,),
    ).fetchall()

    status = pos["status"]

    # Exclude CLOSED legs from active positions — prevents stale replaced legs
    # (e.g. pos_xyz_MSTR_SPOT after migrating to Felix) from triggering
    # incomplete_notional=True and blanking all APR fields.
    if status != "CLOSED":
        leg_rows = [lr for lr in leg_rows if lr["status"] != "CLOSED"]

    # OPEN/PAUSED/EXITING: amount = sum of abs(size * price) across legs (no total_balance on pm_legs).
    if status == "CLOSED":
        amount_usd = meta.get("amount_usd")
    else:
        amount_usd = _gross_notional_usd_from_leg_rows(leg_rows)

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

    # Funding and fees for this position — only from created_at_ms onwards
    # (prevents pre-migration cashflows from contaminating carry_apr)
    cf_start_ms = pos["created_at_ms"] or 0
    funding = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING' AND ts >= ?",
        (position_id, cf_start_ms),
    ).fetchone()[0]

    fees = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FEE' AND ts >= ?",
        (position_id, cf_start_ms),
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

    # Windowed realized metrics
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    windowed = _windowed_metrics(
        db, position_id, amount_usd, leg_rows, now_ms,
        created_at_ms=pos["created_at_ms"],
    )

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
        windowed=windowed,
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
                amount_usd=round(amount_usd, 2) if amount_usd else None,
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

    # Derived from pm_trades (Trade layer). Returns NULLs if table absent or no FINALIZED trades.
    trades_agg = None
    try:
        trades_agg = db.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN 1 ELSE 0 END), 0) AS open_count,
              COALESCE(SUM(CASE WHEN state='FINALIZED' AND trade_type='CLOSE' THEN 1 ELSE 0 END), 0) AS close_count,
              CASE
                WHEN SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN long_size ELSE 0 END) > 0
                THEN SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN spread_bps * long_size ELSE 0 END)
                     / SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN long_size ELSE 0 END)
                ELSE NULL
              END AS weighted_avg_entry_spread_bps
            FROM pm_trades
            WHERE position_id = ?
            """,
            (position_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        # pm_trades table not yet created (Trade layer not initialized)
        pass

    return PositionDetail(
        **summary.model_dump(),
        fills_summary=fills_summary,
        cashflows=cashflows,
        daily_funding_series=daily_funding,
        weighted_avg_entry_spread_bps=trades_agg["weighted_avg_entry_spread_bps"] if trades_agg else None,
        open_trades_count=trades_agg["open_count"] if trades_agg else None,
        close_trades_count=trades_agg["close_count"] if trades_agg else None,
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


@router.post("", status_code=201)
def create_position(
    req: PositionCreateRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Create a Position + its two legs. Trade-layer equivalent of positions.json entry."""
    if req.long_leg.side != "LONG" or req.short_leg.side != "SHORT":
        raise HTTPException(status_code=422, detail="long_leg.side must be LONG and short_leg.side must be SHORT")

    now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    existing = db.execute(
        "SELECT 1 FROM pm_positions WHERE position_id = ?", (req.position_id,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail=f"position already exists: {req.position_id}")

    # Resolve wallet_label -> account_id from strategies config (mirrors db_sync.py logic)
    venue_accounts: dict = {}
    try:
        from tracking.position_manager.accounts import resolve_venue_accounts
        venue_accounts = resolve_venue_accounts(req.venue)
    except Exception:
        pass  # best-effort; account_id stays empty if config unavailable

    db.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (req.position_id, req.venue, "OPEN", now, now, req.base, req.strategy_type),
    )
    for leg in (req.long_leg, req.short_leg):
        account_id = leg.account_id or ""
        if not account_id and leg.wallet_label:
            account_id = venue_accounts.get(leg.wallet_label, "")
        db.execute(
            "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, meta_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                leg.leg_id, req.position_id, leg.venue, leg.inst_id, leg.side,
                0.0, "OPEN", now, account_id,
                json.dumps({"wallet_label": leg.wallet_label}) if leg.wallet_label else None,
            ),
        )
    db.commit()
    return {"position_id": req.position_id, "status": "OPEN"}