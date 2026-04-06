"""Retroactive snapshot recalculation — APR fields only; equity unchanged."""

from __future__ import annotations

import logging
import sqlite3

from .apr import cashflow_adjusted_apr
from .snapshot import net_cashflow_adjustments_strategy

log = logging.getLogger(__name__)


def _recompute_strategy_apr(
    con: sqlite3.Connection,
    strategy_id: str,
    current_equity: float,
    snapshot_ts: int,
    window_days: int | None,
) -> float:
    if window_days is None:
        row = con.execute(
            """
            SELECT equity_usd, ts FROM vault_strategy_snapshots
            WHERE strategy_id = ? ORDER BY ts ASC LIMIT 1
            """,
            (strategy_id,),
        ).fetchone()
    else:
        cutoff_ms = snapshot_ts - (window_days * 86400 * 1000)
        row = con.execute(
            """
            SELECT equity_usd, ts FROM vault_strategy_snapshots
            WHERE strategy_id = ? AND ts <= ? ORDER BY ts DESC LIMIT 1
            """,
            (strategy_id, cutoff_ms),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (snapshot_ts - prior_ts) / 86400000.0
    if period_days <= 0:
        return 0.0

    net_cashflows = net_cashflow_adjustments_strategy(
        con, strategy_id, prior_ts, snapshot_ts
    )

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _recompute_vault_apr(
    con: sqlite3.Connection,
    current_equity: float,
    snapshot_ts: int,
    window_days: int | None,
) -> float:
    if window_days is None:
        row = con.execute(
            "SELECT total_equity_usd, ts FROM vault_snapshots ORDER BY ts ASC LIMIT 1"
        ).fetchone()
    else:
        cutoff_ms = snapshot_ts - (window_days * 86400 * 1000)
        row = con.execute(
            """
            SELECT total_equity_usd, ts FROM vault_snapshots
            WHERE ts <= ? ORDER BY ts DESC LIMIT 1
            """,
            (cutoff_ms,),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (snapshot_ts - prior_ts) / 86400000.0
    if period_days <= 0:
        return 0.0

    cf_row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows
        WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ? AND ts <= ?
        """,
        (prior_ts, snapshot_ts),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row and cf_row[0] is not None else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def recalc_snapshots(con: sqlite3.Connection, since_ms: int) -> int:
    """Recalculate APR for all snapshots from since_ms forward.

    Returns:
        Number of strategy snapshots updated (vault snapshots updated separately).
    """
    rows = con.execute(
        """
        SELECT snapshot_id, strategy_id, ts, equity_usd
        FROM vault_strategy_snapshots
        WHERE ts >= ?
        ORDER BY ts ASC
        """,
        (since_ms,),
    ).fetchall()

    count = 0
    for snapshot_id, strategy_id, ts, equity_usd in rows:
        apr_inception = _recompute_strategy_apr(con, strategy_id, float(equity_usd), int(ts), None)
        apr_30d = _recompute_strategy_apr(con, strategy_id, float(equity_usd), int(ts), 30)
        apr_7d = _recompute_strategy_apr(con, strategy_id, float(equity_usd), int(ts), 7)

        con.execute(
            """
            UPDATE vault_strategy_snapshots
            SET apr_since_inception = ?, apr_30d = ?, apr_7d = ?
            WHERE snapshot_id = ?
            """,
            (apr_inception, apr_30d, apr_7d, snapshot_id),
        )
        count += 1

    vault_rows = con.execute(
        """
        SELECT snapshot_id, ts, total_equity_usd FROM vault_snapshots
        WHERE ts >= ? ORDER BY ts ASC
        """,
        (since_ms,),
    ).fetchall()

    for snapshot_id, ts, total_equity in vault_rows:
        v_apr = _recompute_vault_apr(con, float(total_equity), int(ts), None)
        v_30 = _recompute_vault_apr(con, float(total_equity), int(ts), 30)
        v_7 = _recompute_vault_apr(con, float(total_equity), int(ts), 7)

        con.execute(
            """
            UPDATE vault_snapshots SET total_apr = ?, apr_30d = ?, apr_7d = ?
            WHERE snapshot_id = ?
            """,
            (v_apr, v_30, v_7, snapshot_id),
        )

    con.commit()
    log.info(
        "Recalculated %d strategy snapshots and %d vault snapshots from ts=%s",
        count,
        len(vault_rows),
        since_ms,
    )
    return count
