"""Dual-write manual DEPOSIT/WITHDRAW into vault_cashflows and pm_cashflows."""

from __future__ import annotations

import json
import sqlite3
from typing import Optional, Tuple


class ManualDualWriteError(ValueError):
    """Invalid strategy or DB constraint violation surfaced to API as 400."""


def require_active_strategy(db: sqlite3.Connection, strategy_id: str) -> None:
    row = db.execute(
        "SELECT status FROM vault_strategies WHERE strategy_id = ?",
        (strategy_id,),
    ).fetchone()
    if not row:
        raise ManualDualWriteError(f"Unknown strategy_id: {strategy_id!r}")
    if row["status"] != "ACTIVE":
        raise ManualDualWriteError(
            f"Strategy {strategy_id!r} is not ACTIVE (status={row['status']!r})"
        )


def insert_manual_deposit_withdraw_dual(
    db: sqlite3.Connection,
    *,
    strategy_id: str,
    account_id: str,
    cf_type: str,
    amount: float,
    currency: str,
    ts: int,
    description: Optional[str],
    now_ms: int,
) -> Tuple[int, int]:
    """Insert matching rows in vault_cashflows and pm_cashflows.

    Does not commit. Returns (vault_cashflow_id, pm_cashflow_id).
    Amount sign: DEPOSIT positive, WITHDRAW negative (same as vault API).
    """
    signed = amount if cf_type == "DEPOSIT" else -amount
    cur_v = db.execute(
        """
        INSERT INTO vault_cashflows(
            ts, cf_type, amount, strategy_id, currency, description, created_at_ms
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (ts, cf_type, signed, strategy_id, currency, description, now_ms),
    )
    vault_id = int(cur_v.lastrowid)

    meta = json.dumps({"source": "manual", "strategy_id": strategy_id})
    cur_p = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (None, None, None, account_id, ts, cf_type, signed, currency, description, meta),
    )
    pm_id = int(cur_p.lastrowid)
    return vault_id, pm_id
