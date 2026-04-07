#!/usr/bin/env python3
"""Idempotent migration script for strategy wallet ownership refactor.

Validates config/strategies.json, runs sync-registry, pulls fresh snapshots,
and recomputes portfolio/vault snapshots. Safe to re-run.

Usage:
    .venv/bin/python scripts/migrate_strategy_wallets.py [--dry-run] [--skip-recompute]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STRATEGIES_PATH = ROOT / "config" / "strategies.json"
POSITIONS_PATH = ROOT / "config" / "positions.json"
DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"

_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def validate_strategies() -> Optional[dict]:
    """Step 1: Validate config/strategies.json structure.

    Returns parsed dict on success, None on failure.
    """
    _print_section("STEP 1: VALIDATE strategies.json")

    if not STRATEGIES_PATH.exists():
        print(f"FAIL: {STRATEGIES_PATH} not found")
        return None

    try:
        data = json.loads(STRATEGIES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON in {STRATEGIES_PATH}: {e}")
        return None

    if not isinstance(data, dict):
        print("FAIL: strategies.json must be a JSON object")
        return None

    strategies = data.get("strategies", [])
    if not isinstance(strategies, list) or not strategies:
        print("FAIL: 'strategies' must be a non-empty list")
        return None

    seen_labels: dict = {}  # label -> strategy_id
    errors: List[str] = []

    for i, s in enumerate(strategies):
        sid = s.get("strategy_id", f"<index {i}>")
        wallets = s.get("wallets", [])
        if not isinstance(wallets, list):
            errors.append(f"{sid}: 'wallets' must be a list")
            continue
        for j, w in enumerate(wallets):
            if not isinstance(w, dict):
                errors.append(f"{sid}/wallet[{j}]: must be a dict")
                continue
            label = w.get("label")
            venue = w.get("venue")
            address = w.get("address")
            if not label:
                errors.append(f"{sid}/wallet[{j}]: missing 'label'")
            if not venue:
                errors.append(f"{sid}/wallet[{j}]: missing 'venue'")
            if not address:
                errors.append(f"{sid}/wallet[{j}]: missing 'address'")
            elif not _ADDRESS_RE.match(address):
                errors.append(f"{sid}/wallet[{j}]: invalid address format '{address}' (expected 0x + 40 hex chars)")
            if label:
                if label in seen_labels and seen_labels[label] != sid:
                    errors.append(f"duplicate label '{label}' in strategies '{seen_labels[label]}' and '{sid}'")
                seen_labels[label] = sid

    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        return None

    print(f"  OK: {len(strategies)} strategies, {len(seen_labels)} unique labels")
    return data


def validate_env() -> None:
    """Step 2: Warn if HYPERLIQUID_ACCOUNTS_JSON is still set in env."""
    _print_section("STEP 2: VALIDATE env")

    legacy = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "").strip()
    if legacy:
        print("  WARNING: HYPERLIQUID_ACCOUNTS_JSON is still set in env but IS NO LONGER USED.")
        print("  Remove this line from .arbit_env after verifying strategies.json is correct.")
    else:
        print("  OK: HYPERLIQUID_ACCOUNTS_JSON not set (correct)")


def validate_positions(strategies_data: dict) -> bool:
    """Step 3: Validate positions.json wallet_labels resolve.

    FAIL on any OPEN/PAUSED/EXITING position with unknown wallet_label.
    INFO only for CLOSED positions.
    """
    _print_section("STEP 3: VALIDATE positions.json wallet_labels")

    if not POSITIONS_PATH.exists():
        print(f"  INFO: {POSITIONS_PATH} not found — skipping position validation")
        return True

    try:
        positions = json.loads(POSITIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON in {POSITIONS_PATH}: {e}")
        return False

    # Build label set from strategies
    known_labels = set()
    for s in strategies_data.get("strategies", []):
        for w in s.get("wallets", []):
            if isinstance(w, dict) and w.get("label"):
                known_labels.add(w["label"])

    blocking_errors: List[str] = []
    info_messages: List[str] = []

    for p in positions:
        pid = p.get("position_id", "?")
        status = p.get("status", "OPEN")
        for leg in p.get("legs", []):
            label = leg.get("wallet_label", "main")
            leg_id = leg.get("leg_id", "?")
            if label not in known_labels:
                msg = f"{pid}/{leg_id}: wallet_label='{label}' not in any strategy (known: {sorted(known_labels)})"
                if status in ("OPEN", "PAUSED", "EXITING"):
                    blocking_errors.append(msg)
                else:
                    info_messages.append(f"[CLOSED] {msg}")

    for m in info_messages:
        print(f"  INFO: {m}")
    for e in blocking_errors:
        print(f"  FAIL: {e}")

    if blocking_errors:
        return False

    print(f"  OK: all OPEN/PAUSED/EXITING positions have valid wallet_labels")
    return True


def run_sync_registry() -> bool:
    """Step 4: Run pm.py sync_registry to update pm_legs.meta_json."""
    _print_section("STEP 4: SYNC registry")
    try:
        import scripts.pm as pm_mod
        con = sqlite3.connect(str(DB_PATH))
        con.execute("PRAGMA foreign_keys = ON")
        try:
            result = pm_mod.sync_registry(con, POSITIONS_PATH)
            con.commit()
        finally:
            con.close()
        print(f"  OK: synced {result}")
        return True
    except Exception as e:
        print(f"  FAIL: sync_registry error: {e}")
        return False


def run_pull() -> bool:
    """Step 5: Pull fresh account snapshots."""
    _print_section("STEP 5: REFRESH account snapshots")
    try:
        from tracking.position_manager.puller import run_pull as pull_fn
        summary = pull_fn(
            db_path=DB_PATH,
            registry_path=None,
            venues_filter={"hyperliquid"},
            verbose=False,
        )
        print(f"  OK: snapshots_written={summary.get('snapshots_written', 0)}")
        return True
    except Exception as e:
        print(f"  FAIL: pull error: {e}")
        return False


def recompute_portfolio() -> bool:
    """Step 6: Recompute pm_portfolio_snapshots with DN-only filter."""
    _print_section("STEP 6: RECOMPUTE portfolio snapshot")
    try:
        from tracking.pipeline.portfolio import compute_portfolio_snapshot
        con = sqlite3.connect(str(DB_PATH))
        try:
            result = compute_portfolio_snapshot(con)
            con.commit()
        finally:
            con.close()
        total = result.get("total_equity_usd", 0) if isinstance(result, dict) else 0
        print(f"  OK: total_equity_usd=${total:,.2f}")
        return True
    except Exception as e:
        print(f"  FAIL: portfolio recompute error: {e}")
        return False


def recompute_vault() -> bool:
    """Step 7: Recompute vault_strategy_snapshots (non-fatal)."""
    _print_section("STEP 7: RECOMPUTE vault snapshots")
    try:
        from tracking.vault.snapshot import compute_vault_snapshot
        con = sqlite3.connect(str(DB_PATH))
        try:
            compute_vault_snapshot(con)
            con.commit()
        finally:
            con.close()
        print(f"  OK: vault snapshot computed")
        return True
    except Exception as e:
        print(f"  WARNING: vault recompute skipped or failed: {e}")
        print("  (Non-fatal — vault snapshots are recomputed by the hourly cron)")
        return True  # non-fatal


def report_final_state() -> None:
    """Step 8: Print final per-strategy equity report."""
    _print_section("STEP 8: REPORT")
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT total_equity_usd, equity_by_account_json FROM pm_portfolio_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        con.close()
        if rows:
            total = rows["total_equity_usd"] or 0
            breakdown = json.loads(rows["equity_by_account_json"] or "{}")
            print(f"  Dashboard total_equity_usd (DN only): ${total:,.2f}")
            print(f"  Wallet breakdown:")
            for addr, eq in breakdown.items():
                print(f"    {addr[:20]}...  ${eq:,.2f}")
    except Exception as e:
        print(f"  (skipped: {e})")


def main(dry_run: bool = False, skip_recompute: bool = False) -> int:
    """Run migration. Returns exit code."""
    print(f"Strategy Wallet Ownership Migration")
    print(f"  dry_run={dry_run}, skip_recompute={skip_recompute}")

    strategies_data = validate_strategies()
    if strategies_data is None:
        return 1

    validate_env()

    if not validate_positions(strategies_data):
        return 1

    if dry_run:
        print("\n(dry-run — stopping before write operations)")
        return 0

    if not run_sync_registry():
        return 1

    if not run_pull():
        return 1

    if not skip_recompute:
        if not recompute_portfolio():
            return 1
        recompute_vault()  # non-fatal

    report_final_state()
    print("\n=== MIGRATION COMPLETE ===")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy wallet ownership migration")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no writes")
    parser.add_argument("--skip-recompute", action="store_true", help="Skip portfolio/vault recompute")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run, skip_recompute=args.skip_recompute))
