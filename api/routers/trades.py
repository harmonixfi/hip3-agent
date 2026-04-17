"""Trade aggregation endpoints.

GET    /api/trades                   list with filters
GET    /api/trades/:id               detail + linked fills
POST   /api/trades                   create DRAFT
POST   /api/trades/preview           dry-run aggregation
PATCH  /api/trades/:id               edit DRAFT
POST   /api/trades/:id/finalize      DRAFT → FINALIZED
POST   /api/trades/:id/reopen        FINALIZED → DRAFT
POST   /api/trades/:id/recompute     force recompute
DELETE /api/trades/:id               delete trade
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import status

from api.deps import get_db, get_db_writable
from api.models.trade_schemas import (
    TradeItem,
    TradeListResponse,
    TradeDetailResponse,
    LinkedFillItem,
    TradeCreateRequest,
    TradePreviewRequest,
    TradeEditRequest,
)
from tracking.pipeline.trades import (
    create_draft_trade,
    recompute_trade,
    finalize_trade,
    reopen_trade,
    delete_trade,
    TradeCreateError,
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


# ---------------------------------------------------------------------------
# Write endpoints (Task B3)
# ---------------------------------------------------------------------------


def _dict_to_item(d: dict, unassigned: Optional[int] = None) -> TradeItem:
    """Convert a dict (from create_draft_trade / recompute_trade / finalize_trade) into TradeItem."""
    d = dict(d)  # copy so we don't mutate caller's
    d.setdefault("unassigned_fills_count", unassigned)
    return TradeItem(**d)


@router.post("", response_model=TradeItem, status_code=status.HTTP_201_CREATED)
def create_trade(
    req: TradeCreateRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    try:
        result = create_draft_trade(
            db,
            position_id=req.position_id,
            trade_type=req.trade_type,
            start_ts=req.start_ts,
            end_ts=req.end_ts,
            note=req.note,
        )
    except TradeCreateError as e:
        raise HTTPException(status_code=422, detail=str(e))
    db.commit()
    return _dict_to_item(result)


@router.post("/preview", response_model=TradeItem)
def preview_trade(
    req: TradePreviewRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Dry-run: create DRAFT inside a savepoint then roll back."""
    db.execute("SAVEPOINT preview")
    try:
        result = create_draft_trade(
            db, req.position_id, req.trade_type, req.start_ts, req.end_ts, req.note,
        )
    except TradeCreateError as e:
        db.execute("ROLLBACK TO preview")
        db.execute("RELEASE preview")
        raise HTTPException(status_code=422, detail=str(e))
    db.execute("ROLLBACK TO preview")
    db.execute("RELEASE preview")
    return _dict_to_item(result)


@router.patch("/{trade_id}", response_model=TradeItem)
def edit_trade(
    trade_id: str,
    req: TradeEditRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    row = db.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"trade not found: {trade_id}")
    if row["state"] != "DRAFT":
        raise HTTPException(
            status_code=409,
            detail=f"cannot edit trade in state {row['state']}; reopen first",
        )

    updates: list[str] = []
    args: list = []
    if req.start_ts is not None:
        updates.append("start_ts = ?"); args.append(req.start_ts)
    if req.end_ts is not None:
        updates.append("end_ts = ?"); args.append(req.end_ts)
    if req.trade_type is not None:
        updates.append("trade_type = ?"); args.append(req.trade_type)
    if req.note is not None:
        updates.append("note = ?"); args.append(req.note)
    if not updates:
        raise HTTPException(status_code=400, detail="no fields to update")

    # Clear link table: window/type change invalidates previous binding
    db.execute("DELETE FROM pm_trade_fills WHERE trade_id = ?", (trade_id,))
    args.append(trade_id)
    db.execute(f"UPDATE pm_trades SET {', '.join(updates)} WHERE trade_id = ?", args)
    db.commit()

    try:
        result = recompute_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _dict_to_item(result)


@router.post("/{trade_id}/finalize", response_model=TradeItem)
def finalize(trade_id: str, db: sqlite3.Connection = Depends(get_db_writable)):
    try:
        result = finalize_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _dict_to_item(result)


@router.post("/{trade_id}/reopen", response_model=TradeItem)
def reopen(trade_id: str, db: sqlite3.Connection = Depends(get_db_writable)):
    try:
        result = reopen_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _dict_to_item(result)


@router.post("/{trade_id}/recompute", response_model=TradeItem)
def recompute(trade_id: str, db: sqlite3.Connection = Depends(get_db_writable)):
    try:
        result = recompute_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _dict_to_item(result)


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_endpoint(trade_id: str, db: sqlite3.Connection = Depends(get_db_writable)):
    try:
        delete_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(status_code=404, detail=str(e))
