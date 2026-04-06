"""Manual cashflow endpoint.

POST /api/cashflows/manual — record deposit/withdraw events (strategy-scoped dual-write).
"""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db, get_db_writable
from api.models.schemas import (
    ManualCashflowListItem,
    ManualCashflowListResponse,
    ManualCashflowRequest,
    ManualCashflowResponse,
)
from tracking.vault.manual_dual_write import (
    ManualDualWriteError,
    insert_manual_deposit_withdraw_dual,
    require_active_strategy,
)

router = APIRouter(prefix="/api/cashflows", tags=["cashflows"])


@router.get("/manual", response_model=ManualCashflowListResponse)
def list_manual_cashflows(
    limit: int = Query(50, description="Clamped to [1, 100]."),
    db: sqlite3.Connection = Depends(get_db),
):
    """List manual DEPOSIT/WITHDRAW rows (meta_json source=manual), newest first."""
    lim = max(1, min(limit, 100))
    cur = db.execute(
        """
        SELECT
          cashflow_id,
          ts,
          cf_type,
          amount,
          currency,
          venue,
          json_extract(meta_json, '$.strategy_id') AS strategy_id,
          account_id,
          description
        FROM pm_cashflows
        WHERE cf_type IN ('DEPOSIT', 'WITHDRAW')
          AND json_extract(meta_json, '$.source') = 'manual'
        ORDER BY ts DESC
        LIMIT ?
        """,
        (lim,),
    )
    items = [
        ManualCashflowListItem(
            cashflow_id=row["cashflow_id"],
            ts=row["ts"],
            cf_type=row["cf_type"],
            amount=row["amount"],
            currency=row["currency"],
            strategy_id=row["strategy_id"],
            venue=row["venue"],
            account_id=row["account_id"],
            description=row["description"],
        )
        for row in cur.fetchall()
    ]
    return ManualCashflowListResponse(items=items, limit=lim)


@router.post("/manual", response_model=ManualCashflowResponse, status_code=201)
def record_manual_cashflow(
    body: ManualCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Record a manual deposit or withdrawal.

    Dual-writes vault_cashflows (strategy) and pm_cashflows (portfolio) in one transaction.
    Amount sign: DEPOSIT = positive, WITHDRAW = negative.
    """
    ts = body.ts or int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    try:
        require_active_strategy(db, body.strategy_id)
    except ManualDualWriteError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        vault_id, pm_id = insert_manual_deposit_withdraw_dual(
            db,
            strategy_id=body.strategy_id,
            account_id=body.account_id,
            cf_type=body.cf_type,
            amount=body.amount,
            currency=body.currency,
            ts=ts,
            description=body.description,
            now_ms=now_ms,
        )
    except sqlite3.IntegrityError as e:
        raise HTTPException(status_code=400, detail=f"Invalid cashflow data: {e}") from e

    db.commit()

    recalculated = False
    recalc_count = 0
    latest_snap_ts = db.execute(
        "SELECT MAX(ts) FROM vault_strategy_snapshots"
    ).fetchone()[0]
    if latest_snap_ts and ts < latest_snap_ts:
        from tracking.vault.recalc import recalc_snapshots

        recalc_count = recalc_snapshots(db, ts)
        recalculated = True

    msg = f"{body.cf_type} of {body.amount} {body.currency} recorded"
    if recalculated:
        msg += f" ({recalc_count} snapshots recalculated)"

    return ManualCashflowResponse(
        cashflow_id=pm_id,
        vault_cashflow_id=vault_id,
        message=msg,
    )
