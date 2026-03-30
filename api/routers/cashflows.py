"""Manual cashflow endpoint.

POST /api/cashflows/manual — record deposit/withdraw events.
Per ADR-010: manual entry via REST API for accurate cashflow-adjusted APR.
"""

from __future__ import annotations

import json
import sqlite3
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_db_writable
from api.models.schemas import ManualCashflowRequest, ManualCashflowResponse

router = APIRouter(prefix="/api/cashflows", tags=["cashflows"])


@router.post("/manual", response_model=ManualCashflowResponse, status_code=201)
def record_manual_cashflow(
    body: ManualCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Record a manual deposit or withdrawal.

    Writes to pm_cashflows with meta_json {"source": "manual"}.
    Amount sign is determined by cf_type: DEPOSIT = positive, WITHDRAW = negative.
    """
    ts = body.ts or int(time.time() * 1000)

    # Sign convention: DEPOSIT = +amount, WITHDRAW = -amount
    signed_amount = body.amount if body.cf_type == "DEPOSIT" else -body.amount

    meta = json.dumps({"source": "manual"})

    cursor = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,           # no position_id for deposits/withdrawals
            None,           # no leg_id
            body.venue,
            body.account_id,
            ts,
            body.cf_type,
            signed_amount,
            body.currency,
            body.description,
            meta,
        ),
    )
    db.commit()

    return ManualCashflowResponse(
        cashflow_id=cursor.lastrowid,
        message=f"{body.cf_type} of {body.amount} {body.currency} recorded",
    )
