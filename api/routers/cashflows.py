"""Manual cashflow endpoint.

POST /api/cashflows/manual — record deposit/withdraw/transfer (dual-write vault + pm).
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
    insert_manual_transfer_dual,
    require_active_strategy,
)
from tracking.vault.snapshot import refresh_vault_snapshots_after_cashflow_event

router = APIRouter(prefix="/api/cashflows", tags=["cashflows"])


@router.get("/manual", response_model=ManualCashflowListResponse)
def list_manual_cashflows(
    limit: int = Query(50, description="Clamped to [1, 100]."),
    db: sqlite3.Connection = Depends(get_db),
):
    """List manual pm rows (meta_json source=manual), newest first.

    Internal transfers appear as paired WITHDRAW/DEPOSIT with the same internal_transfer_id.
    """
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
          description,
          json_extract(meta_json, '$.internal_transfer_id') AS internal_transfer_id
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
            account_id=row["account_id"] or None,
            description=row["description"],
            internal_transfer_id=row["internal_transfer_id"],
        )
        for row in cur.fetchall()
    ]
    return ManualCashflowListResponse(items=items, limit=lim)


@router.post("/manual", response_model=ManualCashflowResponse, status_code=201)
def record_manual_cashflow(
    body: ManualCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Record a manual deposit, withdrawal, or internal strategy transfer.

    Dual-writes vault_cashflows and pm_cashflows in one transaction.
    DEPOSIT/WITHDRAW: amount sign DEPOSIT positive, WITHDRAW negative.
    TRANSFER: one vault TRANSFER row; two pm rows (WITHDRAW/DEPOSIT) linked by internal_transfer_id.
    """
    ts = body.ts or int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    if body.cf_type == "TRANSFER":
        assert body.from_strategy_id is not None and body.to_strategy_id is not None
        if body.from_strategy_id == body.to_strategy_id:
            raise HTTPException(
                status_code=400,
                detail="from_strategy_id and to_strategy_id must differ",
            )
        try:
            require_active_strategy(db, body.from_strategy_id)
            require_active_strategy(db, body.to_strategy_id)
        except ManualDualWriteError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        try:
            vault_id, pm_w, pm_d = insert_manual_transfer_dual(
                db,
                from_strategy_id=body.from_strategy_id,
                to_strategy_id=body.to_strategy_id,
                account_id=body.account_id,
                amount=body.amount,
                currency=body.currency,
                ts=ts,
                description=body.description,
                now_ms=now_ms,
            )
        except sqlite3.IntegrityError as e:
            raise HTTPException(status_code=400, detail=f"Invalid cashflow data: {e}") from e

        pm_ids = [pm_w, pm_d]
        msg = (
            f"TRANSFER of {body.amount} {body.currency} "
            f"from {body.from_strategy_id} to {body.to_strategy_id} recorded"
        )
    else:
        try:
            require_active_strategy(db, body.strategy_id)  # type: ignore[arg-type]
        except ManualDualWriteError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        try:
            vault_id, pm_id = insert_manual_deposit_withdraw_dual(
                db,
                strategy_id=body.strategy_id,  # type: ignore[arg-type]
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

        pm_ids = [pm_id]
        msg = f"{body.cf_type} of {body.amount} {body.currency} recorded"

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

    if recalculated:
        msg += f" ({recalc_count} snapshots recalculated)"

    snapshot_refreshed, snapshot_error = refresh_vault_snapshots_after_cashflow_event(db)
    if snapshot_refreshed:
        msg += " Vault metrics refreshed."
    elif snapshot_error:
        msg += f" Warning: vault metrics refresh failed ({snapshot_error})."

    return ManualCashflowResponse(
        cashflow_id=pm_ids[0],
        vault_cashflow_id=vault_id,
        message=msg,
        pm_cashflow_ids=pm_ids,
        snapshot_refreshed=snapshot_refreshed,
        snapshot_error=snapshot_error,
    )
