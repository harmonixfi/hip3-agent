#!/usr/bin/env python3
"""Position Manager healthcheck.

Design:
- Deterministic.
- Silent when healthy.
- Emits ONE Discord-ready message when something looks broken/stale.

Checks (heuristics):
- pm_leg_snapshots freshness (should update every 5m)
- funding_v3 freshness per venue (hourly pulls)
- Loris CSV freshness (30m cadence)
- pm_cashflows freshness (hourly ingest)

Exit codes:
- 0 always (so cron doesn't spam). Prints message only on issues.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"
LORIS_CSV = ROOT / "data" / "loris_funding_history.csv"


def now_ms() -> int:
    return int(time.time() * 1000)


def fmt_age(ms: Optional[int], now: int) -> str:
    if not ms:
        return "N/A"
    dt_s = max(0.0, (now - int(ms)) / 1000.0)
    if dt_s < 60:
        return f"{dt_s:.0f}s"
    if dt_s < 3600:
        return f"{dt_s/60:.0f}m"
    return f"{dt_s/3600:.1f}h"


def utc_ts_str(ms: Optional[int]) -> str:
    if not ms:
        return "N/A"
    return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


@dataclass
class Finding:
    severity: str  # WARN|CRITICAL
    check: str
    detail: str


def q1(con: sqlite3.Connection, sql: str, params: Tuple = ()) -> Optional[Tuple]:
    cur = con.execute(sql, params)
    return cur.fetchone()


def latest_leg_snapshots(con: sqlite3.Connection) -> Dict[str, int]:
    out: Dict[str, int] = {}
    cur = con.execute("SELECT venue, MAX(ts) FROM pm_leg_snapshots GROUP BY venue")
    for venue, ts in cur.fetchall():
        if venue and ts:
            out[str(venue)] = int(ts)
    return out


def latest_funding(con: sqlite3.Connection) -> Dict[str, int]:
    out: Dict[str, int] = {}
    cur = con.execute("SELECT venue, MAX(ts) FROM funding_v3 GROUP BY venue")
    for venue, ts in cur.fetchall():
        if venue and ts:
            out[str(venue)] = int(ts)
    return out


def mtime_ms(path: Path) -> Optional[int]:
    try:
        return int(path.stat().st_mtime * 1000)
    except Exception:
        return None


def latest_loris_csv_ts(path: Path) -> Optional[int]:
    if not path.exists() or path.stat().st_size == 0:
        return None

    # Read last ~200 lines quickly (CSV grows)
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - 64_000), os.SEEK_SET)
            chunk = f.read().decode("utf-8", errors="ignore")
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        if len(lines) < 2:
            return None
        # Find the last data line (not header)
        for ln in reversed(lines):
            if ln.lower().startswith("timestamp_utc,"):
                continue
            parts = ln.split(",")
            if not parts:
                continue
            ts_iso = parts[0].strip()
            try:
                dtv = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
                return int(dtv.timestamp() * 1000)
            except Exception:
                continue
    except Exception:
        return None

    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    now = now_ms()
    findings: List[Finding] = []

    if not args.db.exists():
        findings.append(Finding("CRITICAL", "db_missing", f"DB not found: {args.db}"))
    else:
        con = sqlite3.connect(str(args.db))
        con.execute("PRAGMA foreign_keys = ON")
        try:
            # 1) Position snapshots freshness (should be 5m cadence)
            # Only relevant when we have ACTIVE managed positions.
            row_ap = q1(con, "SELECT COUNT(*) FROM pm_positions WHERE status IN ('OPEN','PAUSED','EXITING')")
            active_pos = int(row_ap[0]) if (row_ap and row_ap[0] is not None) else 0
            if active_pos > 0:
                # Only check venues that currently have OPEN managed legs.
                curv = con.execute("SELECT DISTINCT venue FROM pm_legs WHERE status='OPEN'")
                open_leg_venues = {str(r[0]) for r in curv.fetchall() if r and r[0]}

                snap = latest_leg_snapshots(con)
                snap = {v: ts for v, ts in snap.items() if (not open_leg_venues or v in open_leg_venues)}

                if not snap and open_leg_venues:
                    findings.append(Finding("CRITICAL", "pm_leg_snapshots", "No leg snapshots found for OPEN legs (pull_positions_v3 may be failing)"))
                else:
                    for venue, ts in sorted(snap.items()):
                        age_m = (now - ts) / 60_000.0
                        if age_m >= 30:
                            findings.append(Finding("CRITICAL", "pm_leg_snapshots_stale", f"{venue}: last={utc_ts_str(ts)} age={fmt_age(ts, now)}"))
                        elif age_m >= 15:
                            findings.append(Finding("WARN", "pm_leg_snapshots_stale", f"{venue}: last={utc_ts_str(ts)} age={fmt_age(ts, now)}"))
            else:
                # No active managed positions -> stale snapshots are expected; stay silent.
                pass

            # 2) Funding v3 freshness (hourly)
            fund = latest_funding(con)
            if not fund:
                findings.append(Finding("WARN", "funding_v3", "No funding_v3 rows found yet"))
            else:
                for venue, ts in sorted(fund.items()):
                    age_h = (now - ts) / 3_600_000.0
                    if age_h >= 6:
                        findings.append(Finding("CRITICAL", "funding_v3_stale", f"{venue}: last={utc_ts_str(ts)} age={fmt_age(ts, now)}"))
                    elif age_h >= 3:
                        findings.append(Finding("WARN", "funding_v3_stale", f"{venue}: last={utc_ts_str(ts)} age={fmt_age(ts, now)}"))

            # 3) Cashflows ingest freshness (hourly cron)
            # Do NOT use MAX(ts) from pm_cashflows: funding events can be sparse.
            ingest_log = ROOT / "logs" / "pm_cashflows_ingest.log"
            ing_m = mtime_ms(ingest_log)
            if ing_m is None:
                findings.append(Finding("WARN", "pm_cashflows_ingest", f"Missing ingest log: {ingest_log}"))
            else:
                age_h = (now - ing_m) / 3_600_000.0
                if age_h >= 6:
                    findings.append(Finding("CRITICAL", "pm_cashflows_ingest_stale", f"last_run≈{utc_ts_str(ing_m)} age={fmt_age(ing_m, now)}"))
                elif age_h >= 2:
                    findings.append(Finding("WARN", "pm_cashflows_ingest_stale", f"last_run≈{utc_ts_str(ing_m)} age={fmt_age(ing_m, now)}"))
        finally:
            con.close()

    # 4) Loris CSV freshness (30m cadence)
    loris_ts = latest_loris_csv_ts(LORIS_CSV)
    if loris_ts is None:
        findings.append(Finding("WARN", "loris_csv", f"No recent loris CSV rows found: {LORIS_CSV}"))
    else:
        age_h = (now - loris_ts) / 3_600_000.0
        if age_h >= 6:
            findings.append(Finding("CRITICAL", "loris_csv_stale", f"last={utc_ts_str(loris_ts)} age={fmt_age(loris_ts, now)}"))
        elif age_h >= 2:
            findings.append(Finding("WARN", "loris_csv_stale", f"last={utc_ts_str(loris_ts)} age={fmt_age(loris_ts, now)}"))

    # 5) Wallet/account mismatch checks (common footgun)
    # If you change wallet addresses but keep old auth tokens, monitoring silently points to the old account.
    try:
        expected_pdx = (os.environ.get("PARADEX_ACCOUNT_ADDRESS") or "").strip().lower()
        if expected_pdx and (os.environ.get("PARADEX_JWT") or os.environ.get("PARADEX_READONLY_TOKEN")):
            from tracking.connectors.paradex_private import ParadexPrivateConnector

            pdx = ParadexPrivateConnector()
            acct = (pdx.fetch_account_snapshot() or {}).get("account_id")
            acct_l = str(acct or "").strip().lower()
            if acct_l and acct_l != expected_pdx:
                findings.append(
                    Finding(
                        "WARN",
                        "paradex_wallet_mismatch",
                        f"token_account={acct} != env PARADEX_ACCOUNT_ADDRESS={expected_pdx} (update PARADEX_JWT for new wallet)",
                    )
                )
    except Exception:
        pass

    if args.json:
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "findings": [f.__dict__ for f in findings],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    if not findings:
        return 0

    # Compose ONE Discord message
    crit = [f for f in findings if f.severity == "CRITICAL"]
    warn = [f for f in findings if f.severity == "WARN"]

    lines: List[str] = []
    lines.append(f"# 🩺 System Healthcheck ({len(findings)} issue(s))")
    lines.append("")

    if crit:
        lines.append("## 🚨 CRITICAL")
        lines.append("")
        for f in crit:
            lines.append(f"- **{f.check}**: {f.detail}")
        lines.append("")

    if warn:
        lines.append("## ⚠️ WARN")
        lines.append("")
        for f in warn:
            lines.append(f"- **{f.check}**: {f.detail}")
        lines.append("")

    lines.append("**Action:** check cron logs in `/mnt/data/agents/arbit/logs/` and rerun the failing script manually.")
    lines.append("---")
    lines.append(f"*Generated at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}*")

    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
