"""Dual-write manual DEPOSIT/WITHDRAW and TRANSFER into vault_cashflows and pm_cashflows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Optional, Tuple


class ManualDualWriteError(ValueError):
    """Invalid strategy or DB constraint violation surfaced to API as 400."""


def _pm_account_id(account_id: Optional[str]) -> str:
    """pm_cashflows.account_id is NOT NULL; use empty string when omitted."""
    if account_id is None:
        return ""
    return account_id.strip()


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
    account_id: Optional[str],
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

    acc = _pm_account_id(account_id)
    meta = json.dumps({"source": "manual", "strategy_id": strategy_id})
    cur_p = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (None, None, None, acc, ts, cf_type, signed, currency, description, meta),
    )
    pm_id = int(cur_p.lastrowid)
    return vault_id, pm_id


def insert_manual_transfer_dual(
    db: sqlite3.Connection,
    *,
    from_strategy_id: str,
    to_strategy_id: str,
    account_id: Optional[str],
    amount: float,
    currency: str,
    ts: int,
    description: Optional[str],
    now_ms: int,
) -> Tuple[int, int, int]:
    """Insert one vault TRANSFER and two pm rows (WITHDRAW / DEPOSIT) in one transaction.

    Does not commit. Returns (vault_cashflow_id, pm_withdraw_id, pm_deposit_id).
    ``amount`` is positive; vault row matches ``POST /api/vault/cashflows`` TRANSFER shape.
    """
    require_active_strategy(db, from_strategy_id)
    require_active_strategy(db, to_strategy_id)

    internal_id = str(uuid.uuid4())

    cur_v = db.execute(
        """
        INSERT INTO vault_cashflows(
            ts, cf_type, amount, from_strategy_id, to_strategy_id,
            currency, description, created_at_ms
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            ts,
            "TRANSFER",
            amount,
            from_strategy_id,
            to_strategy_id,
            currency,
            description,
            now_ms,
        ),
    )
    vault_id = int(cur_v.lastrowid)

    acc = _pm_account_id(account_id)
    meta_w = json.dumps(
        {
            "source": "manual",
            "strategy_id": from_strategy_id,
            "internal_transfer_id": internal_id,
        }
    )
    meta_d = json.dumps(
        {
            "source": "manual",
            "strategy_id": to_strategy_id,
            "internal_transfer_id": internal_id,
        }
    )

    cur_pw = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            None,
            None,
            acc,
            ts,
            "WITHDRAW",
            -amount,
            currency,
            description,
            meta_w,
        ),
    )
    pm_w = int(cur_pw.lastrowid)

    cur_pd = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            None,
            None,
            acc,
            ts,
            "DEPOSIT",
            amount,
            currency,
            description,
            meta_d,
        ),
    )
    pm_d = int(cur_pd.lastrowid)
    return vault_id, pm_w, pm_d
