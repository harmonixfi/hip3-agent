"""Recompute daily_change_usd, cashflow_adjusted_change, apr_daily for
existing pm_portfolio_snapshots rows using current pm_cashflows.

Equity values stay untouched — only APR-related fields are updated.
Matches the logic in tracking/pipeline/portfolio.py::compute_portfolio_snapshot.
"""

from __future__ import annotations

import argparse
import sqlite3


def _prior_equity(con, snapshot_ts, hours_ago=24, tolerance_hours=4):
    target_ms = snapshot_ts - hours_ago * 3600 * 1000
    min_allowed = target_ms - tolerance_hours * 3600 * 1000
    row = con.execute(
        "SELECT total_equity_usd FROM pm_portfolio_snapshots "
        "WHERE ts <= ? AND ts >= ? ORDER BY ts DESC LIMIT 1",
        (target_ms, min_allowed),
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def _net_deposits(con, end_ts, window_hours=24):
    start_ts = end_ts - window_hours * 3600 * 1000
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0.0) FROM pm_cashflows "
        "WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts > ? AND ts <= ?",
        (start_ts, end_ts),
    ).fetchone()
    return float(row[0])


def recompute(db_path: str, since_ms: int | None) -> None:
    con = sqlite3.connect(db_path)
    try:
        where = "WHERE ts >= ?" if since_ms else ""
        args = (since_ms,) if since_ms else ()
        rows = con.execute(
            f"SELECT snapshot_id, ts, total_equity_usd FROM pm_portfolio_snapshots {where} ORDER BY ts ASC",
            args,
        ).fetchall()

        updated = 0
        suppressed = 0
        nulled = 0
        for snap_id, ts, equity in rows:
            prior = _prior_equity(con, ts)
            daily_change = None
            adjusted = None
            apr = None

            if prior is not None and prior > 0:
                daily_change = equity - prior
                net_dep = _net_deposits(con, ts)
                adjusted = daily_change - net_dep
                apr = (adjusted / prior) * 365.0 * 100.0
                # circuit breaker (same as portfolio.py)
                if abs(daily_change) / prior > 0.50 and net_dep == 0:
                    daily_change = adjusted = apr = None
                    suppressed += 1

            if prior is None:
                nulled += 1

            con.execute(
                "UPDATE pm_portfolio_snapshots "
                "SET daily_change_usd=?, cashflow_adjusted_change=?, apr_daily=? "
                "WHERE snapshot_id=?",
                (daily_change, adjusted, apr, snap_id),
            )
            updated += 1

        con.commit()
        print(f"Updated {updated} snapshots | suppressed by circuit breaker: {suppressed} | no prior equity: {nulled}")
    finally:
        con.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="tracking/db/arbit_v3.db")
    p.add_argument("--since", help="ISO date, e.g. 2026-04-02", default=None)
    args = p.parse_args()

    since_ms = None
    if args.since:
        import datetime as _dt
        since_ms = int(_dt.datetime.fromisoformat(args.since).timestamp() * 1000)

    recompute(args.db, since_ms)
