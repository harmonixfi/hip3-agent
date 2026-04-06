"""Vault API endpoints."""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db, get_db_writable
from api.models.vault_schemas import (
    StrategyDetail,
    StrategySnapshot,
    StrategySummary,
    VaultCashflowItem,
    VaultCashflowRequest,
    VaultCashflowResponse,
    VaultOverview,
    VaultSnapshot,
)

router = APIRouter(prefix="/api/vault", tags=["vault"])


def _vault_name_from_db(db: sqlite3.Connection) -> str:
    row = db.execute(
        "SELECT config_json FROM vault_strategies ORDER BY strategy_id LIMIT 1"
    ).fetchone()
    if row and row["config_json"]:
        try:
            cfg = json.loads(row["config_json"])
            if isinstance(cfg, dict) and cfg.get("vault_name"):
                return str(cfg["vault_name"])
        except (json.JSONDecodeError, TypeError):
            pass
    return "OpenClaw Vault"


@router.get("/overview", response_model=VaultOverview)
def vault_overview(db: sqlite3.Connection = Depends(get_db)):
    snap = db.execute(
        "SELECT * FROM vault_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()

    rows = db.execute(
        """
        SELECT s.strategy_id, s.name, s.type, s.status, s.target_weight_pct,
               ss.equity_usd, ss.apr_since_inception, ss.apr_30d, ss.apr_7d
        FROM vault_strategies s
        LEFT JOIN vault_strategy_snapshots ss ON ss.strategy_id = s.strategy_id
            AND ss.ts = (
                SELECT MAX(ts) FROM vault_strategy_snapshots WHERE strategy_id = s.strategy_id
            )
        ORDER BY s.target_weight_pct DESC
        """
    ).fetchall()

    total_equity = float(snap["total_equity_usd"]) if snap else 0.0

    strategies = []
    for r in rows:
        equity = float(r["equity_usd"]) if r["equity_usd"] is not None else None
        weight = (equity / total_equity * 100) if equity is not None and total_equity > 0 else None
        strategies.append(
            StrategySummary(
                strategy_id=r["strategy_id"],
                name=r["name"],
                type=r["type"],
                status=r["status"],
                equity_usd=equity,
                weight_pct=round(weight, 2) if weight is not None else None,
                target_weight_pct=r["target_weight_pct"],
                apr_since_inception=r["apr_since_inception"],
                apr_30d=r["apr_30d"],
                apr_7d=r["apr_7d"],
            )
        )

    as_of = (
        datetime.fromtimestamp(snap["ts"] / 1000, tz=timezone.utc).isoformat()
        if snap
        else None
    )

    return VaultOverview(
        vault_name=_vault_name_from_db(db),
        total_equity_usd=total_equity,
        total_apr=snap["total_apr"] if snap else None,
        apr_30d=snap["apr_30d"] if snap else None,
        apr_7d=snap["apr_7d"] if snap else None,
        net_deposits_alltime=snap["net_deposits_alltime"] if snap else None,
        strategies=strategies,
        as_of=as_of,
    )


@router.get("/strategies", response_model=List[StrategySummary])
def list_strategies_api(db: sqlite3.Connection = Depends(get_db)):
    """List all strategies with latest snapshot metrics."""
    snap = db.execute(
        "SELECT total_equity_usd FROM vault_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()
    total_equity = float(snap["total_equity_usd"]) if snap else 0.0

    rows = db.execute(
        """
        SELECT s.strategy_id, s.name, s.type, s.status, s.target_weight_pct,
               ss.equity_usd, ss.apr_since_inception, ss.apr_30d, ss.apr_7d
        FROM vault_strategies s
        LEFT JOIN vault_strategy_snapshots ss ON ss.strategy_id = s.strategy_id
            AND ss.ts = (
                SELECT MAX(ts) FROM vault_strategy_snapshots WHERE strategy_id = s.strategy_id
            )
        ORDER BY s.target_weight_pct DESC
        """
    ).fetchall()

    out: List[StrategySummary] = []
    for r in rows:
        equity = float(r["equity_usd"]) if r["equity_usd"] is not None else None
        weight = (equity / total_equity * 100) if equity is not None and total_equity > 0 else None
        out.append(
            StrategySummary(
                strategy_id=r["strategy_id"],
                name=r["name"],
                type=r["type"],
                status=r["status"],
                equity_usd=equity,
                weight_pct=round(weight, 2) if weight is not None else None,
                target_weight_pct=r["target_weight_pct"],
                apr_since_inception=r["apr_since_inception"],
                apr_30d=r["apr_30d"],
                apr_7d=r["apr_7d"],
            )
        )
    return out


@router.get("/strategies/{strategy_id}", response_model=StrategyDetail)
def strategy_detail(strategy_id: str, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM vault_strategies WHERE strategy_id = ?", (strategy_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    snap = db.execute(
        """
        SELECT * FROM vault_strategy_snapshots WHERE strategy_id = ?
        ORDER BY ts DESC LIMIT 1
        """,
        (strategy_id,),
    ).fetchone()

    return StrategyDetail(
        strategy_id=row["strategy_id"],
        name=row["name"],
        type=row["type"],
        status=row["status"],
        target_weight_pct=row["target_weight_pct"],
        equity_usd=snap["equity_usd"] if snap else None,
        apr_since_inception=snap["apr_since_inception"] if snap else None,
        apr_30d=snap["apr_30d"] if snap else None,
        apr_7d=snap["apr_7d"] if snap else None,
        equity_breakdown=json.loads(snap["equity_breakdown_json"])
        if snap and snap["equity_breakdown_json"]
        else None,
        wallets=json.loads(row["wallets_json"]) if row["wallets_json"] else None,
    )


@router.get("/snapshots", response_model=List[VaultSnapshot])
def vault_snapshots(
    limit: int = Query(30, ge=1, le=365),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM vault_snapshots WHERE 1=1"
    params: list = []
    if from_ts is not None:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts is not None:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        VaultSnapshot(
            ts=r["ts"],
            total_equity_usd=r["total_equity_usd"],
            total_apr=r["total_apr"],
            apr_30d=r["apr_30d"],
            apr_7d=r["apr_7d"],
            strategy_weights=json.loads(r["strategy_weights_json"])
            if r["strategy_weights_json"]
            else None,
        )
        for r in rows
    ]


@router.get("/strategies/{strategy_id}/snapshots", response_model=List[StrategySnapshot])
def strategy_snapshots(
    strategy_id: str,
    limit: int = Query(30, ge=1, le=365),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM vault_strategy_snapshots WHERE strategy_id = ?"
    params: list = [strategy_id]
    if from_ts is not None:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts is not None:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        StrategySnapshot(
            ts=r["ts"],
            equity_usd=r["equity_usd"],
            apr_since_inception=r["apr_since_inception"],
            apr_30d=r["apr_30d"],
            apr_7d=r["apr_7d"],
        )
        for r in rows
    ]


@router.get("/cashflows", response_model=List[VaultCashflowItem])
def list_cashflows(
    strategy_id: Optional[str] = None,
    cf_type: Optional[str] = None,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM vault_cashflows WHERE 1=1"
    params: list = []
    if strategy_id:
        sql += " AND (strategy_id = ? OR from_strategy_id = ? OR to_strategy_id = ?)"
        params.extend([strategy_id, strategy_id, strategy_id])
    if cf_type:
        sql += " AND cf_type = ?"
        params.append(cf_type)
    if from_ts is not None:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts is not None:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        VaultCashflowItem(
            cashflow_id=r["cashflow_id"],
            ts=r["ts"],
            cf_type=r["cf_type"],
            amount=r["amount"],
            currency=r["currency"],
            strategy_id=r["strategy_id"],
            from_strategy_id=r["from_strategy_id"],
            to_strategy_id=r["to_strategy_id"],
            description=r["description"],
        )
        for r in rows
    ]


@router.post("/cashflows", response_model=VaultCashflowResponse, status_code=201)
def create_cashflow(
    body: VaultCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    ts = body.ts if body.ts is not None else int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    if body.cf_type == "TRANSFER":
        if not body.from_strategy_id or not body.to_strategy_id:
            raise HTTPException(
                status_code=400,
                detail="TRANSFER requires from_strategy_id and to_strategy_id",
            )
        cur = db.execute(
            """
            INSERT INTO vault_cashflows(
                ts, cf_type, amount, from_strategy_id, to_strategy_id,
                currency, description, created_at_ms
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                ts,
                "TRANSFER",
                body.amount,
                body.from_strategy_id,
                body.to_strategy_id,
                body.currency,
                body.description,
                now_ms,
            ),
        )
    else:
        if not body.strategy_id:
            raise HTTPException(
                status_code=400,
                detail="DEPOSIT/WITHDRAW requires strategy_id",
            )
        signed = body.amount if body.cf_type == "DEPOSIT" else -body.amount
        cur = db.execute(
            """
            INSERT INTO vault_cashflows(
                ts, cf_type, amount, strategy_id, currency, description, created_at_ms
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (ts, body.cf_type, signed, body.strategy_id, body.currency, body.description, now_ms),
        )

    db.commit()
    cf_id = cur.lastrowid

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

    return VaultCashflowResponse(
        cashflow_id=cf_id,
        recalculated=recalculated,
        recalc_snapshots_affected=recalc_count,
        message=msg,
    )
