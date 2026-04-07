"""Portfolio-level aggregation and snapshot writer.

Computes:
- Total equity from latest pm_account_snapshots (across all wallets)
- Funding today: SUM(FUNDING cashflows WHERE ts >= today_start_utc)
- Funding all-time: SUM(FUNDING cashflows WHERE ts >= tracking_start_date)
- Fees all-time: SUM(FEE cashflows WHERE ts >= tracking_start_date)
- Total unrealized PnL from pm_legs
- Cashflow-adjusted APR: (equity_change - net_deposits) / prior_equity / days * 365

Writes hourly snapshot to pm_portfolio_snapshots.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


DEFAULT_TRACKING_START = os.environ.get("TRACKING_START_DATE", "2026-03-27")


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_start_ms() -> int:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)


def _date_to_ms(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _get_total_equity(con: sqlite3.Connection) -> Dict[str, Any]:
    """Return Delta Neutral portfolio equity only.

    Filters pm_account_snapshots to addresses owned by the delta_neutral strategy.
    Other strategy wallets (depeg, lending) are tracked separately via vault providers.
    """
    from tracking.position_manager.accounts import get_strategy_wallets

    try:
        dn_wallets = get_strategy_wallets("delta_neutral")
    except KeyError:
        dn_wallets = []

    dn_addresses = [w["address"] for w in dn_wallets if w.get("address")]
    if not dn_addresses:
        return {"total_equity_usd": 0.0, "equity_by_account": {}}

    placeholders = ",".join(["?"] * len(dn_addresses))
    sql = f"""
        SELECT a.account_id, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) as max_ts
            FROM pm_account_snapshots
            WHERE account_id IN ({placeholders})
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
    """
    rows = con.execute(sql, dn_addresses).fetchall()

    equity_by_account: Dict[str, float] = {}
    total = 0.0
    for account_id, balance in rows:
        if balance is not None:
            equity_by_account[account_id] = float(balance)
            total += float(balance)
    return {"total_equity_usd": total, "equity_by_account": equity_by_account}


def _get_funding_sum(con, *, since_ms):
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0.0) FROM pm_cashflows WHERE cf_type = 'FUNDING' AND ts >= ?",
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_fees_sum(con, *, since_ms):
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0.0) FROM pm_cashflows WHERE cf_type = 'FEE' AND ts >= ?",
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_total_unrealized_pnl(con):
    row = con.execute("""
        SELECT COALESCE(SUM(l.unrealized_pnl), 0.0)
        FROM pm_legs l JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.status != 'CLOSED' AND l.unrealized_pnl IS NOT NULL
    """).fetchone()
    return float(row[0])


def _get_net_deposits(con, *, since_ms):
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0.0) FROM pm_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ?",
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_prior_equity(con, *, hours_ago=24, tolerance_hours=4):
    """Get equity from ~hours_ago.  Returns None if no snapshot within tolerance."""
    now = _now_ms()
    target_ms = now - hours_ago * 3600 * 1000
    min_allowed_ms = target_ms - tolerance_hours * 3600 * 1000
    row = con.execute(
        "SELECT total_equity_usd FROM pm_portfolio_snapshots "
        "WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
        (target_ms, min_allowed_ms),
    ).fetchone()
    if row is None or row[0] is None: return None
    return float(row[0])


def compute_position_net_funding(con, position_id):
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
        (position_id,),
    ).fetchone()
    return float(row[0])


def compute_portfolio_snapshot(con, *, tracking_start_date=DEFAULT_TRACKING_START):
    now = _now_ms()
    today_start = _today_start_ms()
    tracking_start_ms = _date_to_ms(tracking_start_date)

    equity_data = _get_total_equity(con)
    total_equity = equity_data["total_equity_usd"]
    equity_by_account = equity_data["equity_by_account"]
    total_upnl = _get_total_unrealized_pnl(con)
    funding_today = _get_funding_sum(con, since_ms=today_start)
    funding_alltime = _get_funding_sum(con, since_ms=tracking_start_ms)
    fees_alltime = _get_fees_sum(con, since_ms=tracking_start_ms)

    prior_equity = _get_prior_equity(con, hours_ago=24)
    daily_change = None
    cashflow_adjusted_change = None
    apr_daily = None

    if prior_equity is not None and prior_equity > 0:
        daily_change = total_equity - prior_equity
        net_deposits_24h = _get_net_deposits(con, since_ms=now - 24 * 3600 * 1000)
        cashflow_adjusted_change = daily_change - net_deposits_24h
        apr_daily = (cashflow_adjusted_change / prior_equity) * 365.0 * 100.0

        # Circuit-breaker: if equity moved >50% with no recorded deposits,
        # the change is likely an unrecorded deposit/withdrawal — suppress.
        if abs(daily_change) / prior_equity > 0.50 and net_deposits_24h == 0:
            daily_change = None
            cashflow_adjusted_change = None
            apr_daily = None

    snapshot = {
        "ts": now, "total_equity_usd": total_equity,
        "equity_by_account_json": json.dumps(equity_by_account),
        "total_unrealized_pnl": total_upnl, "total_funding_today": funding_today,
        "total_funding_alltime": funding_alltime, "total_fees_alltime": fees_alltime,
        "daily_change_usd": daily_change, "cashflow_adjusted_change": cashflow_adjusted_change,
        "apr_daily": apr_daily, "tracking_start_date": tracking_start_date,
    }

    hour_bucket = now // 3600000
    con.execute("DELETE FROM pm_portfolio_snapshots WHERE CAST(ts / 3600000 AS INTEGER) = ?", (hour_bucket,))
    con.execute("""
        INSERT INTO pm_portfolio_snapshots
          (ts, total_equity_usd, equity_by_account_json,
           total_unrealized_pnl, total_funding_today, total_funding_alltime,
           total_fees_alltime, daily_change_usd, cashflow_adjusted_change,
           apr_daily, tracking_start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (now, total_equity, json.dumps(equity_by_account),
         total_upnl, funding_today, funding_alltime,
         fees_alltime, daily_change, cashflow_adjusted_change,
         apr_daily, tracking_start_date),
    )
    con.commit()
    return snapshot
