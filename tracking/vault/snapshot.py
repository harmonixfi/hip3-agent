"""Daily vault snapshot pipeline."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Dict

from .apr import cashflow_adjusted_apr
from .providers import PROVIDER_REGISTRY

log = logging.getLogger(__name__)


def _net_external_cashflows_strategy(
    con: sqlite3.Connection,
    strategy_id: str,
    start_ts: int,
    end_ts: int,
) -> float:
    """DEPOSIT + WITHDRAW amounts for strategy_id (WITHDRAW stored negative)."""
    row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows
        WHERE strategy_id = ? AND cf_type IN ('DEPOSIT', 'WITHDRAW')
          AND ts >= ? AND ts <= ?
        """,
        (strategy_id, start_ts, end_ts),
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _compute_apr_for_strategy(
    con: sqlite3.Connection,
    strategy_id: str,
    current_equity: float,
    now_ms: int,
    window_days: int | None,
) -> float:
    """Compute APR for a strategy over a given window."""
    if window_days is None:
        row = con.execute(
            """
            SELECT equity_usd, ts FROM vault_strategy_snapshots
            WHERE strategy_id = ? ORDER BY ts ASC LIMIT 1
            """,
            (strategy_id,),
        ).fetchone()
    else:
        cutoff_ms = now_ms - (window_days * 86400 * 1000)
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
    period_days = (now_ms - prior_ts) / 86400000.0
    if period_days <= 0:
        return 0.0

    net_cashflows = _net_external_cashflows_strategy(con, strategy_id, prior_ts, now_ms)
    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _compute_vault_apr(
    con: sqlite3.Connection,
    current_equity: float,
    now_ms: int,
    window_days: int | None,
) -> float:
    """Compute vault-level APR from vault_snapshots + external cashflows only."""
    if window_days is None:
        row = con.execute(
            "SELECT total_equity_usd, ts FROM vault_snapshots ORDER BY ts ASC LIMIT 1"
        ).fetchone()
    else:
        cutoff_ms = now_ms - (window_days * 86400 * 1000)
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
    period_days = (now_ms - prior_ts) / 86400000.0
    if period_days <= 0:
        return 0.0

    cf_row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows
        WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ? AND ts <= ?
        """,
        (prior_ts, now_ms),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row and cf_row[0] is not None else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _get_net_deposits(con: sqlite3.Connection) -> float:
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW')"
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def _upsert_strategy_snapshot(
    con: sqlite3.Connection,
    strategy_id: str,
    ts: int,
    equity: Any,
    apr_inception: float,
    apr_30d: float,
    apr_7d: float,
) -> None:
    day_bucket = ts // 86400000
    con.execute(
        """
        DELETE FROM vault_strategy_snapshots
        WHERE strategy_id = ? AND CAST(ts / 86400000 AS INTEGER) = ?
        """,
        (strategy_id, day_bucket),
    )

    meta_json = json.dumps(equity.meta, separators=(",", ":")) if equity.meta else None
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, equity_breakdown_json,
            apr_since_inception, apr_30d, apr_7d, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy_id,
            ts,
            equity.equity_usd,
            json.dumps(equity.breakdown, separators=(",", ":")),
            apr_inception,
            apr_30d,
            apr_7d,
            meta_json,
        ),
    )


def _upsert_vault_snapshot(
    con: sqlite3.Connection,
    ts: int,
    total_equity: float,
    weights: dict,
    total_apr: float,
    apr_30d: float,
    apr_7d: float,
    net_deposits: float,
) -> None:
    day_bucket = ts // 86400000
    con.execute(
        "DELETE FROM vault_snapshots WHERE CAST(ts / 86400000 AS INTEGER) = ?",
        (day_bucket,),
    )

    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json,
            total_apr, apr_30d, apr_7d, net_deposits_alltime, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            total_equity,
            json.dumps(weights, separators=(",", ":")),
            total_apr,
            apr_30d,
            apr_7d,
            net_deposits,
            None,
        ),
    )


def run_daily_snapshot(con: sqlite3.Connection) -> Dict[str, Any]:
    """Run the daily vault snapshot pipeline."""
    now_ms = int(time.time() * 1000)

    rows = con.execute(
        """
        SELECT strategy_id, name, type, status, wallets_json, target_weight_pct, config_json
        FROM vault_strategies WHERE status = 'ACTIVE'
        """
    ).fetchall()

    strategy_equities: Dict[str, Any] = {}
    strategies_processed = 0

    for row in rows:
        strategy = {
            "strategy_id": row[0],
            "name": row[1],
            "type": row[2],
            "status": row[3],
            "wallets_json": row[4],
            "target_weight_pct": row[5],
            "config_json": row[6],
        }
        sid = strategy["strategy_id"]
        stype = strategy["type"]

        provider_cls = PROVIDER_REGISTRY.get(stype)
        if not provider_cls:
            log.warning("No provider for strategy type '%s', skipping %s", stype, sid)
            continue

        try:
            provider = provider_cls()
            equity = provider.get_equity(strategy, con)
            strategy_equities[sid] = equity

            apr_inception = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, None)
            apr_30d = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, 30)
            apr_7d = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, 7)

            _upsert_strategy_snapshot(con, sid, now_ms, equity, apr_inception, apr_30d, apr_7d)
            strategies_processed += 1
            log.info(
                "  %s: equity=$%.2f, APR(inception)=%.2f%%",
                sid,
                equity.equity_usd,
                apr_inception,
            )
        except Exception:
            log.exception("Failed to snapshot strategy %s", sid)

    vault_equity = sum(e.equity_usd for e in strategy_equities.values())
    weights: Dict[str, float] = {}
    if vault_equity > 0:
        weights = {sid: e.equity_usd / vault_equity * 100 for sid, e in strategy_equities.items()}

    vault_apr = _compute_vault_apr(con, vault_equity, now_ms, None)
    vault_apr_30d = _compute_vault_apr(con, vault_equity, now_ms, 30)
    vault_apr_7d = _compute_vault_apr(con, vault_equity, now_ms, 7)

    net_deposits = _get_net_deposits(con)

    _upsert_vault_snapshot(
        con, now_ms, vault_equity, weights, vault_apr, vault_apr_30d, vault_apr_7d, net_deposits
    )
    con.commit()

    log.info(
        "Vault snapshot: equity=$%.2f, APR=%.2f%%, strategies=%d",
        vault_equity,
        vault_apr,
        strategies_processed,
    )

    return {
        "strategies_processed": strategies_processed,
        "vault_equity": vault_equity,
        "vault_apr": vault_apr,
        "weights": weights,
    }
