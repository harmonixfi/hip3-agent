"""Trade reconcile hook — called after fill_ingester cron run.

DRAFT trades auto-pick up newly-ingested fills in their window.
FINALIZED trades count unassigned fills and raise warnings (no auto-merge).
"""
from __future__ import annotations

import sqlite3
import time
from typing import Dict

from tracking.pipeline.trades import recompute_trade, side_for


def _now_ms() -> int:
    return int(time.time() * 1000)


def _count_unassigned_fills_in_window(
    con: sqlite3.Connection,
    long_leg_id: str,
    short_leg_id: str,
    long_side: str,
    short_side: str,
    start_ts: int,
    end_ts: int,
) -> int:
    row = con.execute(
        """
        SELECT COUNT(*) FROM pm_fills f
        WHERE f.ts >= ? AND f.ts < ?
          AND (
            (f.leg_id = ? AND f.side = ?) OR
            (f.leg_id = ? AND f.side = ?)
          )
          AND NOT EXISTS (SELECT 1 FROM pm_trade_fills tf WHERE tf.fill_id = f.fill_id)
        """,
        (start_ts, end_ts, long_leg_id, long_side, short_leg_id, short_side),
    ).fetchone()
    return int(row[0] or 0)


def run_reconcile(con: sqlite3.Connection) -> Dict[str, int]:
    """Refresh DRAFT trades and raise warnings for FINALIZED with late fills.

    Returns summary: {'drafts_recomputed', 'warnings_raised', 'warnings_cleared'}.
    """
    con.row_factory = sqlite3.Row
    drafts_recomputed = 0
    warnings_raised = 0
    warnings_cleared = 0

    # Every DRAFT gets recomputed; INSERT OR IGNORE within recompute_trade handles idempotency
    draft_ids = [
        r["trade_id"]
        for r in con.execute("SELECT trade_id FROM pm_trades WHERE state = 'DRAFT'").fetchall()
    ]
    for tid in draft_ids:
        recompute_trade(con, tid)
        drafts_recomputed += 1

    finalized = con.execute(
        "SELECT trade_id, trade_type, start_ts, end_ts, long_leg_id, short_leg_id "
        "FROM pm_trades WHERE state = 'FINALIZED'"
    ).fetchall()

    now = _now_ms()
    for t in finalized:
        long_side = side_for(t["trade_type"], "LONG")
        short_side = side_for(t["trade_type"], "SHORT")
        n = _count_unassigned_fills_in_window(
            con,
            t["long_leg_id"], t["short_leg_id"],
            long_side, short_side,
            t["start_ts"], t["end_ts"],
        )

        existing = con.execute(
            "SELECT unassigned_count, first_seen_ms FROM pm_trade_reconcile_warnings WHERE trade_id=?",
            (t["trade_id"],),
        ).fetchone()

        if n > 0:
            if existing is None:
                con.execute(
                    "INSERT INTO pm_trade_reconcile_warnings (trade_id, unassigned_count, first_seen_ms, last_checked_ms) "
                    "VALUES (?,?,?,?)",
                    (t["trade_id"], n, now, now),
                )
                warnings_raised += 1
            else:
                con.execute(
                    "UPDATE pm_trade_reconcile_warnings SET unassigned_count=?, last_checked_ms=? WHERE trade_id=?",
                    (n, now, t["trade_id"]),
                )
        else:
            if existing is not None:
                con.execute(
                    "DELETE FROM pm_trade_reconcile_warnings WHERE trade_id=?",
                    (t["trade_id"],),
                )
                warnings_cleared += 1

    con.commit()
    return {
        "drafts_recomputed": drafts_recomputed,
        "warnings_raised": warnings_raised,
        "warnings_cleared": warnings_cleared,
    }
