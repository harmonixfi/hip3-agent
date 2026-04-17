"""Trade aggregation endpoints.

GET  /api/trades               list with filters
GET  /api/trades/:id           detail + linked fills

(POST/PATCH/DELETE/transitions added in Task B3.)
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.models.trade_schemas import (
    TradeItem,
    TradeListResponse,
    TradeDetailResponse,
    LinkedFillItem,
)


router = APIRouter(prefix="/api/trades", tags=["trades"])


def _row_to_item(row: sqlite3.Row, unassigned: Optional[int] = None) -> TradeItem:
    """Convert a sqlite3.Row from pm_trades SELECT * into TradeItem."""
    d = {k: row[k] for k in row.keys()}
    d["unassigned_fills_count"] = unassigned
    return TradeItem(**d)


@router.get("", response_model=TradeListResponse)
def list_trades(
    position_id: Optional[str] = None,
    trade_type: Optional[str] = Query(None, pattern="^(OPEN|CLOSE)$"),
    state: Optional[str] = Query(None, pattern="^(DRAFT|FINALIZED)$"),
    start_ts_gte: Optional[int] = None,
    end_ts_lte: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    """List pm_trades filtered by optional query params. Limit 500."""
    clauses: list[str] = []
    args: list = []
    if position_id:
        clauses.append("position_id = ?"); args.append(position_id)
    if trade_type:
        clauses.append("trade_type = ?"); args.append(trade_type)
    if state:
        clauses.append("state = ?"); args.append(state)
    if start_ts_gte is not None:
        clauses.append("start_ts >= ?"); args.append(start_ts_gte)
    if end_ts_lte is not None:
        clauses.append("end_ts <= ?"); args.append(end_ts_lte)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = db.execute(
        f"SELECT * FROM pm_trades {where} ORDER BY start_ts DESC LIMIT 500",
        args,
    ).fetchall()

    warn_map = {
        r["trade_id"]: r["unassigned_count"]
        for r in db.execute(
            "SELECT trade_id, unassigned_count FROM pm_trade_reconcile_warnings"
        ).fetchall()
    }

    items = [_row_to_item(r, warn_map.get(r["trade_id"])) for r in rows]
    return TradeListResponse(items=items, total=len(items))


@router.get("/{trade_id}", response_model=TradeDetailResponse)
def get_trade(
    trade_id: str,
    db: sqlite3.Connection = Depends(get_db),
):
    row = db.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"trade not found: {trade_id}")

    warn_row = db.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?",
        (trade_id,),
    ).fetchone()
    warn = warn_row["unassigned_count"] if warn_row else None

    fill_rows = db.execute(
        """
        SELECT tf.fill_id, tf.leg_side, f.inst_id, f.side, f.px, f.sz, f.fee, f.ts
        FROM pm_trade_fills tf
        JOIN pm_fills f ON f.fill_id = tf.fill_id
        WHERE tf.trade_id = ?
        ORDER BY f.ts
        """,
        (trade_id,),
    ).fetchall()
    fills = [
        LinkedFillItem(
            fill_id=r["fill_id"],
            leg_side=r["leg_side"],
            inst_id=r["inst_id"],
            side=r["side"],
            px=r["px"],
            sz=r["sz"],
            fee=r["fee"],
            ts=r["ts"],
        )
        for r in fill_rows
    ]

    d = {k: row[k] for k in row.keys()}
    d["unassigned_fills_count"] = warn
    d["fills"] = fills
    return TradeDetailResponse(**d)
