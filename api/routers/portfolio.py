"""Portfolio overview endpoint.

GET /api/portfolio/overview — aggregate portfolio metrics.

Reads from pm_portfolio_snapshots (latest), pm_account_snapshots (latest per account),
pm_cashflows (funding/fees aggregation), and pm_positions (open count).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.models.schemas import AccountEquity, PortfolioOverview

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _ts_to_iso(ts_ms: Optional[int]) -> str:
    """Convert epoch ms to ISO 8601 string."""
    if ts_ms is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _parse_ymd_strict(s: str) -> str:
    """Validate calendar date YYYY-MM-DD; return stripped string or raise ValueError."""
    raw = s.strip()
    datetime.strptime(raw, "%Y-%m-%d")
    return raw


@router.get("/overview", response_model=PortfolioOverview)
def portfolio_overview(
    tracking_start: Optional[str] = Query(
        None, description="Override tracking start date (YYYY-MM-DD)"
    ),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return aggregate portfolio metrics.

    Reads the latest pm_portfolio_snapshots row for pre-computed metrics.
    Supplements with live account equity from pm_account_snapshots and
    position/cashflow counts from source tables.
    """
    # 1. Latest portfolio snapshot (pre-computed by Phase 1b cron)
    snap = db.execute(
        "SELECT * FROM pm_portfolio_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()

    # 2. Latest account snapshots (equity per wallet)
    account_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    # 3. Open positions count
    open_count = db.execute(
        "SELECT COUNT(*) FROM pm_positions WHERE status IN ('OPEN', 'PAUSED')"
    ).fetchone()[0]

    # 4. Funding today — calendar day in UTC+0 only (not host local TZ).
    # SQLite 'now' is UTC; do not add 'localtime' here.
    today_start_sql = "strftime('%s', 'now', 'start of day') * 1000"
    funding_today = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0)
        FROM pm_cashflows
        WHERE cf_type = 'FUNDING' AND ts >= ({today_start_sql})
        """
    ).fetchone()[0]

    # 5. All-time funding and fees (with optional tracking_start override)
    # Use bound parameters only — never interpolate user/DB strings into SQL.
    tracking_date = ""
    tracking_filter = ""
    tracking_params: list[str] = []
    if tracking_start:
        try:
            tracking_date = _parse_ymd_strict(tracking_start)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail="tracking_start must be a valid YYYY-MM-DD date",
            ) from e
        tracking_filter = " AND ts >= (strftime('%s', ?) * 1000)"
        tracking_params = [tracking_date]
    elif snap and snap["tracking_start_date"]:
        raw_td = snap["tracking_start_date"]
        try:
            tracking_date = _parse_ymd_strict(str(raw_td))
        except ValueError as e:
            raise HTTPException(
                status_code=500,
                detail="Invalid tracking_start_date stored in portfolio snapshot",
            ) from e
        tracking_filter = " AND ts >= (strftime('%s', ?) * 1000)"
        tracking_params = [tracking_date]

    funding_alltime = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows
        WHERE cf_type = 'FUNDING'{tracking_filter}
        """,
        tracking_params,
    ).fetchone()[0]

    fees_alltime = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows
        WHERE cf_type = 'FEE'{tracking_filter}
        """,
        tracking_params,
    ).fetchone()[0]

    # Build equity_by_account
    equity_by_account: dict[str, AccountEquity] = {}
    total_equity = 0.0
    for row in account_rows:
        label = _account_label(row["account_id"])
        eq = row["total_balance"] or 0.0
        equity_by_account[label] = AccountEquity(
            address=row["account_id"],
            equity_usd=round(eq, 2),
            venue=row["venue"],
        )
        total_equity += eq

    # Use snapshot values if available, else compute from components
    # Snapshot REAL columns may be NULL — treat as 0.0 for math / Pydantic
    daily_change = float(snap["daily_change_usd"] or 0.0) if snap else 0.0
    apr = float(snap["apr_daily"] or 0.0) if snap else 0.0
    total_upnl = float(snap["total_unrealized_pnl"] or 0.0) if snap else 0.0
    snap_ts = snap["ts"] if snap else None

    # Override total_equity from snapshot if no live account data
    if not account_rows and snap:
        total_equity = snap["total_equity_usd"] or 0.0
        # Try to parse equity_by_account from snapshot
        if snap["equity_by_account_json"]:
            try:
                eq_json = json.loads(snap["equity_by_account_json"])
                for label, val in eq_json.items():
                    if isinstance(val, (int, float)):
                        equity_by_account[label] = AccountEquity(
                            address=label, equity_usd=round(val, 2), venue="hyperliquid"
                        )
            except (json.JSONDecodeError, TypeError):
                pass

    net_pnl = funding_alltime + fees_alltime
    daily_change_pct = (
        (daily_change / (total_equity - daily_change) * 100)
        if total_equity and total_equity != daily_change
        else 0.0
    )

    return PortfolioOverview(
        total_equity_usd=round(total_equity, 2),
        equity_by_account=equity_by_account,
        daily_change_usd=round(daily_change, 2),
        daily_change_pct=round(daily_change_pct, 2),
        cashflow_adjusted_apr=round(apr, 2) if apr else 0.0,
        funding_today_usd=round(funding_today, 2),
        funding_alltime_usd=round(funding_alltime, 2),
        fees_alltime_usd=round(fees_alltime, 2),
        net_pnl_alltime_usd=round(net_pnl, 2),
        tracking_start_date=tracking_date,
        open_positions_count=open_count,
        total_unrealized_pnl=round(total_upnl, 2) if total_upnl else 0.0,
        as_of=_ts_to_iso(snap_ts),
    )


def _account_label(account_id: str) -> str:
    """Derive a human-friendly label from account_id.

    Checks HYPERLIQUID_ACCOUNTS_JSON env var for label mapping.
    Supports both formats:
      - dict: {"main": "0xABC...", "alt": "0xDEF..."}
      - list: [{"address": "0xABC...", "label": "main"}, ...]
    Falls back to truncated address.
    """
    import os

    accounts_json = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "")
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
            if isinstance(accounts, dict):
                # Format: {label: address}
                for label, address in accounts.items():
                    if isinstance(address, str) and address.lower() == account_id.lower():
                        return label
            elif isinstance(accounts, list):
                # Format: [{address, label}, ...]
                for acct in accounts:
                    if isinstance(acct, dict) and acct.get("address", "").lower() == account_id.lower():
                        return acct.get("label", account_id[:10])
        except (json.JSONDecodeError, TypeError):
            pass
    return account_id[:10]
