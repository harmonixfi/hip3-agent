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
from api.models.schemas import AccountEquity, AccountUtilization, FundUtilization, PortfolioOverview

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


def _compute_fund_utilization(
    db: sqlite3.Connection,
    total_equity: float,
) -> FundUtilization:
    """Compute leverage, deployed/available capital from live DB data.

    Filters to delta_neutral strategy wallets only — lending/depeg tracked separately.
    """
    from tracking.position_manager.accounts import get_delta_neutral_equity_account_ids

    dn_addresses = {a.lower() for a in get_delta_neutral_equity_account_ids()}

    # 1. Per-account available/margin from latest snapshots (already fetched in caller
    #    but we need extra columns, so re-query with full columns)
    acct_detail_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance,
               a.available_balance, a.margin_balance, a.position_value
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    # Filter to DN wallets only (other strategies tracked separately in vault page)
    if dn_addresses:
        acct_detail_rows = [r for r in acct_detail_rows if (r["account_id"] or "").lower() in dn_addresses]

    # 2. Per-account notional from OPEN/PAUSED/EXITING legs
    leg_notional_rows = db.execute(
        """
        SELECT l.account_id,
               SUM(ABS(l.size * COALESCE(l.current_price, ep.avg_entry_price, l.entry_price))) AS notional
        FROM pm_legs l
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        INNER JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.status IN ('OPEN', 'PAUSED', 'EXITING')
          AND l.size IS NOT NULL
        GROUP BY l.account_id
        """
    ).fetchall()

    acct_notional_map: dict[str, float] = {}
    for row in leg_notional_rows:
        aid = row["account_id"] or "__unknown__"
        acct_notional_map[aid] = row["notional"] or 0.0

    # 3. Build per-account utilization
    accounts: list[AccountUtilization] = []
    total_notional = 0.0
    total_available = 0.0

    for arow in acct_detail_rows:
        aid = arow["account_id"]
        label = _account_label(aid)
        equity = arow["total_balance"] or 0.0
        available = arow["available_balance"] or 0.0
        margin_used = arow["margin_balance"] or 0.0
        pos_value = acct_notional_map.get(aid, 0.0)

        acct_leverage = pos_value / equity if equity > 0 else 0.0
        total_notional += pos_value
        total_available += available

        accounts.append(AccountUtilization(
            label=label,
            venue=arow["venue"],
            equity_usd=round(equity, 2),
            margin_used_usd=round(margin_used, 2),
            available_usd=round(available, 2),
            position_value_usd=round(pos_value, 2),
            leverage=round(acct_leverage, 2),
        ))

    # 4. Aggregate
    leverage = total_notional / total_equity if total_equity > 0 else 0.0
    deployed_pct = (total_notional / total_equity * 100) if total_equity > 0 else 0.0

    return FundUtilization(
        total_equity_usd=round(total_equity, 2),
        total_notional_usd=round(total_notional, 2),
        total_deployed_usd=round(total_notional, 2),
        total_available_usd=round(total_available, 2),
        leverage=round(leverage, 2),
        deployed_pct=round(deployed_pct, 1),
        accounts=accounts,
    )


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

    # 2. Latest account snapshots (equity per wallet), filtered to DN wallets only
    from tracking.position_manager.accounts import get_delta_neutral_equity_account_ids

    _dn_addresses = {a.lower() for a in get_delta_neutral_equity_account_ids()}

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

    if _dn_addresses:
        account_rows = [r for r in account_rows if (r["account_id"] or "").lower() in _dn_addresses]

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

    # Gate 24h metrics: verify an actual snapshot exists in the 20-28h-ago window.
    # Without a valid prior snapshot, daily_change is meaningless.
    import time as _time
    now_ms = int(_time.time() * 1000)
    target_ms = now_ms - 24 * 3600 * 1000
    min_ms = target_ms - 4 * 3600 * 1000  # 28h ago (4h tolerance)
    has_valid_prior = db.execute(
        "SELECT 1 FROM pm_portfolio_snapshots WHERE ts <= ? AND ts >= ? LIMIT 1",
        (target_ms, min_ms),
    ).fetchone() is not None

    # Use snapshot values if available, else compute from components
    # Snapshot REAL columns may be NULL — treat as None when insufficient history
    daily_change: Optional[float] = (
        float(snap["daily_change_usd"])
        if snap and snap["daily_change_usd"] is not None and has_valid_prior
        else None
    )
    apr: Optional[float] = (
        float(snap["apr_daily"])
        if snap and snap["apr_daily"] is not None and has_valid_prior
        else None
    )
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
    fund_util = _compute_fund_utilization(db, total_equity)
    daily_change_pct: Optional[float] = (
        (daily_change / (total_equity - daily_change) * 100)
        if daily_change is not None and total_equity and total_equity != daily_change
        else None
    )

    return PortfolioOverview(
        total_equity_usd=round(total_equity, 2),
        equity_by_account=equity_by_account,
        daily_change_usd=round(daily_change, 2) if daily_change is not None else None,
        daily_change_pct=round(daily_change_pct, 2) if daily_change_pct is not None else None,
        cashflow_adjusted_apr=round(apr, 2) if apr is not None else None,
        funding_today_usd=round(funding_today, 2),
        funding_alltime_usd=round(funding_alltime, 2),
        fees_alltime_usd=round(fees_alltime, 2),
        net_pnl_alltime_usd=round(net_pnl, 2),
        tracking_start_date=tracking_date,
        open_positions_count=open_count,
        total_unrealized_pnl=round(total_upnl, 2) if total_upnl else 0.0,
        as_of=_ts_to_iso(snap_ts),
        fund_utilization=fund_util,
    )


def _account_label(account_id: str) -> str:
    """Derive a human-friendly label from account_id.

    Reads from config/strategies.json via _load_strategies_cached. Falls back to
    truncated address if no match found.
    """
    from tracking.position_manager.accounts import _load_strategies_cached

    try:
        strategies = _load_strategies_cached()
    except Exception:
        strategies = []

    for s in strategies:
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            addr = w.get("address", "")
            if isinstance(addr, str) and addr.lower() == account_id.lower():
                return str(w.get("label", account_id[:10]))

    return account_id[:10]
