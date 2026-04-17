"""Migrate config/positions.json → pm_positions / pm_legs / pm_trades.

Usage:
  .venv/bin/python scripts/migrate_positions_to_db.py --dry-run
  .venv/bin/python scripts/migrate_positions_to_db.py --commit

Idempotent: re-runs are no-ops for positions/legs/trades that already exist.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict

from tracking.pipeline.trades import (
    create_draft_trade, finalize_trade, TradeCreateError,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = ROOT / "config" / "positions.json"
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _wallet_to_account(wallet_label: str | None) -> str | None:
    """Resolve wallet_label → account_id via HYPERLIQUID_ACCOUNTS_JSON env var."""
    raw = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "{}")
    try:
        accts = json.loads(raw)
    except Exception:
        return None
    if wallet_label in accts:
        entry = accts[wallet_label]
        if isinstance(entry, dict):
            return entry.get("address") or entry.get("account_id")
    return None


def migrate(
    con: sqlite3.Connection,
    positions_path: Path = DEFAULT_POSITIONS,
    commit: bool = False,
) -> Dict[str, Any]:
    """Run the migration. Returns a report dict.

    commit=False: performs all operations inside the connection but rolls back
    at the end (dry run). commit=True: commits on success.

    Key design choices:
    - Positions are always inserted with status="OPEN" so that create_draft_trade
      does not raise (it rejects CLOSED positions). After finalize_trade runs,
      _update_leg_sizes_and_position_status derives the correct status (CLOSED
      when all net sizes reach zero via OPEN+CLOSE trades).
    - When commit=False (dry run), finalize_trade is skipped entirely because it
      calls con.commit() internally, which would leak writes even in dry-run mode.
      Only create_draft_trade is called (it does not commit), and the final
      con.rollback() cleans everything up.
    """
    positions = json.loads(Path(positions_path).read_text())
    now = _now_ms()

    report: Dict[str, Any] = {
        "positions_created": 0,
        "legs_created": 0,
        "trades_created": 0,
        "qty_diffs": [],
        "errors": [],
    }

    for pos in positions:
        pid = pos["position_id"]
        existing = con.execute(
            "SELECT 1 FROM pm_positions WHERE position_id=?", (pid,)
        ).fetchone()
        if not existing:
            # Always insert as OPEN — finalize_trade will derive CLOSED automatically
            # via _update_leg_sizes_and_position_status after CLOSE trade is finalized.
            con.execute(
                "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    pos["legs"][0]["venue"],
                    "OPEN",
                    now, now,
                    pos.get("base"),
                    pos.get("strategy_type"),
                ),
            )
            report["positions_created"] += 1

            for leg in pos["legs"]:
                account_id = _wallet_to_account(leg.get("wallet_label")) or ""
                con.execute(
                    "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, meta_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        leg["leg_id"], pid, leg["venue"], leg["inst_id"], leg["side"],
                        0.0, "OPEN", now, account_id,
                        json.dumps({"wallet_label": leg.get("wallet_label")}),
                    ),
                )
                report["legs_created"] += 1

        # Derive OPEN trade window from earliest opening-side fills
        legs_by_side = {l["side"]: l for l in pos["legs"]}
        long_leg_id = legs_by_side["LONG"]["leg_id"]
        short_leg_id = legs_by_side["SHORT"]["leg_id"]

        open_bounds = con.execute(
            """
            SELECT MIN(ts), MAX(ts) FROM pm_fills
            WHERE (leg_id = ? AND side = 'BUY') OR (leg_id = ? AND side = 'SELL')
            """,
            (long_leg_id, short_leg_id),
        ).fetchone()

        if open_bounds and open_bounds[0] is not None:
            start_ts, end_ts = open_bounds[0], open_bounds[1] + 1
            existing_open = con.execute(
                "SELECT 1 FROM pm_trades WHERE position_id=? AND trade_type='OPEN'", (pid,)
            ).fetchone()
            if not existing_open:
                try:
                    t = create_draft_trade(con, pid, "OPEN", start_ts, end_ts, note="migrated")
                    if commit:
                        finalize_trade(con, t["trade_id"])
                    report["trades_created"] += 1
                except TradeCreateError as e:
                    report["errors"].append(f"{pid} OPEN: {e}")

        # If CLOSED, synthesize a CLOSE trade from the post-open fill window
        if pos.get("status") == "CLOSED":
            close_bounds = con.execute(
                """
                SELECT MIN(ts), MAX(ts) FROM pm_fills
                WHERE (leg_id = ? AND side = 'SELL') OR (leg_id = ? AND side = 'BUY')
                """,
                (long_leg_id, short_leg_id),
            ).fetchone()
            if (
                close_bounds and close_bounds[1] is not None
                and open_bounds and open_bounds[1] is not None
                and close_bounds[1] > open_bounds[1]
            ):
                c_start, c_end = (open_bounds[1] + 1), close_bounds[1] + 1
                existing_close = con.execute(
                    "SELECT 1 FROM pm_trades WHERE position_id=? AND trade_type='CLOSE'", (pid,)
                ).fetchone()
                if not existing_close:
                    try:
                        t = create_draft_trade(con, pid, "CLOSE", c_start, c_end, note="migrated")
                        if commit:
                            finalize_trade(con, t["trade_id"])
                        report["trades_created"] += 1
                    except TradeCreateError as e:
                        report["errors"].append(f"{pid} CLOSE: {e}")

        # Report qty diff for each declared leg (expected qty from JSON vs current derived leg.size)
        for leg in pos["legs"]:
            expected = float(leg.get("qty", 0))
            actual_row = con.execute(
                "SELECT size FROM pm_legs WHERE leg_id=?", (leg["leg_id"],)
            ).fetchone()
            actual = actual_row[0] if actual_row else 0.0
            abs_exp = abs(expected) if expected else 1e-9
            delta_pct = abs(abs(actual or 0.0) - abs(expected)) / abs_exp * 100
            report["qty_diffs"].append({
                "leg_id": leg["leg_id"],
                "expected": expected,
                "actual": actual,
                "delta_pct": delta_pct,
            })

    if commit:
        con.commit()
    else:
        con.rollback()
    return report


def main():
    ap = argparse.ArgumentParser(description="Migrate config/positions.json → DB (Trade layer)")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    ap.add_argument("--commit", action="store_true", help="Apply changes (default is dry-run)")
    args = ap.parse_args()

    con = sqlite3.connect(str(args.db))
    try:
        report = migrate(con, positions_path=args.positions, commit=args.commit)
        print(json.dumps(report, indent=2, default=str))
    finally:
        con.close()


if __name__ == "__main__":
    main()
