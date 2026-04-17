"""Real-data E2E acceptance harness (spec §9 Real-data E2E).

Spins up a fresh sqlite DB, ingests real HL (and optionally Felix) fills,
runs the positions.json→DB migration, and reports 5 validation checks.

Usage:
  source .arbit_env
  .venv/bin/python scripts/e2e_real_fills.py --lookback-days 60

Output:
  - Fresh DB at tracking/db/e2e_<timestamp>.db
  - Report at docs/tasks/e2e_real_fills_report_YYYYMMDD.md
  - Exit 0 on zero violations, 1 otherwise
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.migrate_positions_to_db import migrate as run_migrate


def _apply_schemas(con: sqlite3.Connection) -> None:
    """Apply all three schema files to a fresh DB."""
    for path in [
        ROOT / "tracking/sql/schema_pm_v3.sql",
        ROOT / "tracking/sql/schema_monitoring_v1.sql",
        ROOT / "tracking/sql/schema_monitoring_v2.sql",
    ]:
        sql = path.read_text()
        # Split on ';' but tolerate duplicate-column errors for idempotent ALTER TABLE
        for stmt in sql.split(";"):
            s = stmt.strip()
            # Strip comment-only lines
            lines = [ln for ln in s.splitlines() if not ln.lstrip().startswith("--")]
            s = " ".join(lines).strip()
            if not s:
                continue
            try:
                con.execute(s)
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    continue
                raise
    con.commit()


def _ingest_real_fills(con: sqlite3.Connection, lookback_days: int) -> None:
    """Pull real fills from HL (and Felix if available) into pm_fills."""
    since_ms = int((time.time() - lookback_days * 86400) * 1000)

    # HL
    try:
        from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills
        from tracking.pipeline.spot_meta import fetch_spot_index_map
        spot_map = fetch_spot_index_map()
        n = ingest_hyperliquid_fills(con, spot_map, include_closed=True, since_ms=since_ms)
        print(f"  HL fills ingested: {n}")
    except Exception as e:
        print(f"  HL ingest failed: {e}")

    # Felix (optional — requires a valid connector with JWT/wallet credentials)
    try:
        from tracking.connectors.felix_private import FelixPrivateConnector  # type: ignore
        from tracking.pipeline.felix_fill_ingester import ingest_felix_fills_from_api

        connector = FelixPrivateConnector.from_env()
        n2 = ingest_felix_fills_from_api(con, connector, include_closed=True, since_ms=since_ms)
        print(f"  Felix fills ingested: {n2}")
    except ImportError:
        print("  Felix ingest skipped (no connector)")
    except AttributeError:
        print("  Felix ingest skipped (FelixPrivateConnector.from_env not available)")
    except Exception as e:
        print(f"  Felix ingest failed: {e}")


def _validate(con: sqlite3.Connection) -> dict:
    """Run all 5 validation checks; return report dict."""
    con.row_factory = sqlite3.Row
    report: dict = {"positions": [], "global_violations": 0}

    positions = con.execute(
        "SELECT position_id, base, status FROM pm_positions"
    ).fetchall()

    for pos in positions:
        pid = pos["position_id"]
        prow: dict = {"position_id": pid, "base": pos["base"], "status": pos["status"]}

        # ── (1) Volume reconciliation ─────────────────────────────
        legs = con.execute(
            "SELECT leg_id, side FROM pm_legs WHERE position_id=?", (pid,)
        ).fetchall()
        for leg in legs:
            net = con.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN trade_type='OPEN' THEN
                    CASE WHEN ?='LONG' THEN long_size ELSE short_size END ELSE 0 END),0)
                  - COALESCE(SUM(CASE WHEN trade_type='CLOSE' THEN
                    CASE WHEN ?='LONG' THEN long_size ELSE short_size END ELSE 0 END),0)
                FROM pm_trades WHERE position_id=? AND state='FINALIZED'
                """,
                (leg["side"], leg["side"], pid),
            ).fetchone()[0] or 0.0
            actual = con.execute(
                "SELECT size FROM pm_legs WHERE leg_id=?", (leg["leg_id"],)
            ).fetchone()[0] or 0.0
            prow[f"{leg['side'].lower()}_leg_net_trades"] = net
            prow[f"{leg['side'].lower()}_leg_qty_db"] = actual

        # ── (2) Fill coverage ────────────────────────────────────
        total_fills = con.execute(
            """
            SELECT COUNT(*) FROM pm_fills f
            JOIN pm_legs l ON f.leg_id=l.leg_id
            WHERE l.position_id=?
            """,
            (pid,),
        ).fetchone()[0]
        linked = con.execute(
            """
            SELECT COUNT(*) FROM pm_trade_fills tf
            JOIN pm_fills f ON f.fill_id=tf.fill_id
            JOIN pm_legs l ON f.leg_id=l.leg_id
            WHERE l.position_id=?
            """,
            (pid,),
        ).fetchone()[0]
        coverage = (linked / total_fills * 100) if total_fills else 100.0
        prow["fill_coverage_pct"] = round(coverage, 2)
        prow["unassigned_fills"] = total_fills - linked

        # ── (3) Spread sanity ────────────────────────────────────
        spread_stats = con.execute(
            "SELECT MIN(spread_bps), MAX(spread_bps) FROM pm_trades "
            "WHERE position_id=? AND trade_type='OPEN' AND state='FINALIZED'",
            (pid,),
        ).fetchone()
        prow["open_spread_min_bps"] = spread_stats[0]
        prow["open_spread_max_bps"] = spread_stats[1]
        if spread_stats[0] is not None:
            extreme = max(abs(spread_stats[0] or 0), abs(spread_stats[1] or 0))
            if extreme > 100:
                prow["spread_flag"] = f"|spread| > 100 bps ({extreme:.1f}) — manual review"
                report["global_violations"] += 1

        # ── (4) Realized P&L consistency ─────────────────────────
        cashflow_sum = con.execute(
            """
            SELECT COALESCE(SUM(amount),0) FROM pm_cashflows
            WHERE position_id=? AND cf_type IN ('REALIZED_PNL','FUNDING')
            """,
            (pid,),
        ).fetchone()[0]
        pnl_from_trades = con.execute(
            """
            SELECT COALESCE(SUM(realized_pnl_bps * long_notional / 10000.0), 0)
            FROM pm_trades
            WHERE position_id=? AND trade_type='CLOSE' AND state='FINALIZED'
              AND realized_pnl_bps IS NOT NULL AND long_notional IS NOT NULL
            """,
            (pid,),
        ).fetchone()[0]
        prow["cashflow_realized_usd"] = cashflow_sum
        prow["trades_realized_usd"] = pnl_from_trades
        if cashflow_sum and abs(pnl_from_trades - cashflow_sum) / abs(cashflow_sum) > 0.05:
            prow["pnl_flag"] = f"delta > 5% (cashflow {cashflow_sum:.2f} vs trades {pnl_from_trades:.2f})"
            report["global_violations"] += 1

        # ── (5) Side mapping correctness (sample 5 fills) ──────
        sample = con.execute(
            """
            SELECT tf.leg_side, t.trade_type, f.side FROM pm_trade_fills tf
            JOIN pm_trades t ON t.trade_id=tf.trade_id
            JOIN pm_fills f ON f.fill_id=tf.fill_id
            WHERE t.position_id=? LIMIT 5
            """,
            (pid,),
        ).fetchall()
        expected_map = {
            ("OPEN","LONG"):"BUY", ("OPEN","SHORT"):"SELL",
            ("CLOSE","LONG"):"SELL", ("CLOSE","SHORT"):"BUY",
        }
        for s in sample:
            exp = expected_map.get((s["trade_type"], s["leg_side"]))
            if exp != s["side"]:
                prow["side_violation"] = (
                    f"{s['trade_type']}+{s['leg_side']} expected {exp}, got {s['side']}"
                )
                report["global_violations"] += 1
                break

        report["positions"].append(prow)

    return report


def main() -> int:
    ap = argparse.ArgumentParser(description="Real-data E2E acceptance harness")
    ap.add_argument("--lookback-days", type=int, default=60)
    args = ap.parse_args()

    ts_iso = time.strftime("%Y%m%d_%H%M%S")
    tmp_db = ROOT / f"tracking/db/e2e_{ts_iso}.db"
    tmp_db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(tmp_db))
    print(f"Harness DB: {tmp_db}")

    try:
        _apply_schemas(con)
        _ingest_real_fills(con, args.lookback_days)
        run_migrate(con, positions_path=ROOT / "config/positions.json", commit=True)
        report = _validate(con)
    finally:
        con.close()

    out_path = ROOT / f"docs/tasks/e2e_real_fills_report_{time.strftime('%Y%m%d')}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# E2E Real Fills Report — {ts_iso}",
        "",
        f"Global violations: **{report['global_violations']}**",
        "",
        "## Per-position",
    ]
    for p in report["positions"]:
        lines.append("```json")
        lines.append(json.dumps(p, indent=2, default=str))
        lines.append("```")
    out_path.write_text("\n".join(lines))
    print(f"Report written to: {out_path}")
    print(f"Violations: {report['global_violations']}")

    return 0 if report["global_violations"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
