#!/usr/bin/env python3
"""Vault Strategy Manager CLI."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def cmd_sync_registry(con: sqlite3.Connection, registry_path: Path) -> int:
    from tracking.vault.db_sync import sync_registry
    from tracking.vault.registry import load_registry

    vault_name, strategies = load_registry(registry_path)
    count = sync_registry(con, vault_name, strategies)
    print(f"OK: synced {count} strategies from {registry_path}")
    return 0


def cmd_list(con: sqlite3.Connection, as_json: bool) -> int:
    from tracking.vault.db_sync import list_strategies

    rows = list_strategies(con)
    if as_json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no strategies)")
        return 0
    for r in rows:
        equity = f"${r['equity_usd']:,.2f}" if r.get("equity_usd") is not None else "no data"
        apr = (
            f"{r['apr_since_inception']:.4f}"
            if r.get("apr_since_inception") is not None
            else "n/a"
        )
        print(
            f"{r['strategy_id']}: {r['name']} | {r['type']} | {r['status']} | "
            f"{equity} | APR={apr} | target={r['target_weight_pct']}%"
        )
    return 0


def cmd_cashflow(con: sqlite3.Connection, args) -> int:
    from tracking.vault.recalc import recalc_snapshots

    ts = int(args.ts) if args.ts else int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    if args.type == "TRANSFER":
        if not args.from_strategy or not args.to_strategy:
            print("ERROR: TRANSFER requires --from and --to")
            return 1
        con.execute(
            """
            INSERT INTO vault_cashflows(
                ts, cf_type, amount, from_strategy_id, to_strategy_id, description, created_at_ms
            ) VALUES (?,?,?,?,?,?,?)
            """,
            (ts, "TRANSFER", args.amount, args.from_strategy, args.to_strategy, args.description, now_ms),
        )
    else:
        if not args.strategy:
            print("ERROR: DEPOSIT/WITHDRAW requires --strategy")
            return 1
        signed = args.amount if args.type == "DEPOSIT" else -args.amount
        con.execute(
            """
            INSERT INTO vault_cashflows(
                ts, cf_type, amount, strategy_id, description, created_at_ms
            ) VALUES (?,?,?,?,?,?)
            """,
            (ts, args.type, signed, args.strategy, args.description, now_ms),
        )

    con.commit()
    print(f"OK: {args.type} of {args.amount} USDC recorded")

    latest_snap_ts = con.execute("SELECT MAX(ts) FROM vault_strategy_snapshots").fetchone()[0]
    if latest_snap_ts and ts < latest_snap_ts:
        count = recalc_snapshots(con, ts)
        print(f"  -> Recalculated {count} strategy snapshots (backdated cashflow)")

    return 0


def cmd_recalc(con: sqlite3.Connection, args) -> int:
    from tracking.vault.recalc import recalc_snapshots

    if args.all:
        since_ms = 0
    elif args.since:
        dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        since_ms = int(dt.timestamp() * 1000)
    else:
        print("ERROR: provide --since DATE or --all")
        return 1

    count = recalc_snapshots(con, since_ms)
    print(f"OK: recalculated {count} strategy snapshots")
    return 0


def cmd_snapshot(con: sqlite3.Connection) -> int:
    from tracking.vault.snapshot import run_daily_snapshot

    result = run_daily_snapshot(con)
    print("OK: snapshot complete")
    print(f"  Strategies: {result['strategies_processed']}")
    print(f"  Vault equity: ${result['vault_equity']:,.2f}")
    print(f"  Vault APR: {result['vault_apr']:.6f}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="vault")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)

    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_sync = sub.add_parser("sync-registry", help="Sync strategies.json to DB")
    sp_sync.add_argument("--registry", type=Path, default=ROOT / "config" / "strategies.json")

    sp_list = sub.add_parser("list", help="List strategies with latest data")
    sp_list.add_argument("--json", action="store_true")

    sp_cf = sub.add_parser("cashflow", help="Record a cashflow event")
    sp_cf.add_argument("--type", required=True, choices=["DEPOSIT", "WITHDRAW", "TRANSFER"])
    sp_cf.add_argument("--amount", required=True, type=float)
    sp_cf.add_argument("--strategy", help="Target strategy (for DEPOSIT/WITHDRAW)")
    sp_cf.add_argument("--from", dest="from_strategy", help="Source strategy (for TRANSFER)")
    sp_cf.add_argument("--to", dest="to_strategy", help="Destination strategy (for TRANSFER)")
    sp_cf.add_argument("--ts", help="Epoch ms (defaults to now)")
    sp_cf.add_argument("--description", default="")

    sp_recalc = sub.add_parser("recalc", help="Recalculate APR for snapshots")
    sp_recalc.add_argument("--since", help="YYYY-MM-DD date to recalc from")
    sp_recalc.add_argument("--all", action="store_true", help="Recalculate all snapshots")

    sub.add_parser("snapshot", help="Run daily snapshot now")

    args = ap.parse_args()
    con = connect(args.db)

    try:
        if args.cmd == "sync-registry":
            return cmd_sync_registry(con, args.registry)
        if args.cmd == "list":
            return cmd_list(con, getattr(args, "json", False))
        if args.cmd == "cashflow":
            return cmd_cashflow(con, args)
        if args.cmd == "recalc":
            return cmd_recalc(con, args)
        if args.cmd == "snapshot":
            return cmd_snapshot(con)
        print(f"Unknown command: {args.cmd}")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
