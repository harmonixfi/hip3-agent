#!/usr/bin/env python3
"""Print why LendingProvider equity is zero: SQLite config vs Harmonix row coverage.

Usage:
  source .arbit_env
  .venv/bin/python scripts/diagnose_lending_equity.py
  .venv/bin/python scripts/diagnose_lending_equity.py --db /path/to/arbit_v3.db
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_SQLITE = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_SQLITE)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"SQLite not found: {args.db}")
        return 1

    con = sqlite3.connect(str(args.db))
    row = con.execute(
        """
        SELECT strategy_id, config_json FROM vault_strategies
        WHERE strategy_id = 'lending'
        """
    ).fetchone()
    con.close()

    if not row:
        print("No vault_strategies row for lending — run: vault.py sync-registry")
        return 1

    _, config_json = row
    strategy = {"strategy_id": "lending", "config_json": config_json}
    print("=== SQLite vault_strategies.config_json (lending) ===")
    try:
        cfg = json.loads(config_json) if config_json else {}
        print(json.dumps(cfg, indent=2))
    except json.JSONDecodeError as e:
        print("Invalid JSON:", e)
        return 1

    from tracking.vault.providers.lending import LendingProvider

    p = LendingProvider()
    chain_id, vaults = p._chain_and_vaults(strategy)
    accounts = p._lending_account_addresses(strategy)
    usdc = p._usdc_address(strategy)

    print("\n=== Resolved by LendingProvider ===")
    print("chain_id:", chain_id)
    print("lending_accounts:", accounts)
    print("erc4626 vault_addresses (%d):" % len(vaults), vaults)
    print("usdc (Aave leg):", usdc)

    url = os.environ.get("HARMONIX_NAV_DB_URL", "").strip()
    if not url:
        print("\nHARMONIX_NAV_DB_URL not set.")
        return 1

    import psycopg2

    pg = psycopg2.connect(url, connect_timeout=15)
    cur = pg.cursor()

    for acct in accounts:
        cur.execute(
            """
            SELECT COUNT(DISTINCT chain_id) FROM raw.vault_erc4626_account_snapshot_hourly
            WHERE lower(account_address) = lower(%s)
            """,
            (acct,),
        )
        nchains = cur.fetchone()[0]
        cur.execute(
            """
            SELECT chain_id, COUNT(*) FROM raw.vault_erc4626_account_snapshot_hourly
            WHERE lower(account_address) = lower(%s)
            GROUP BY chain_id ORDER BY COUNT(*) DESC LIMIT 8
            """,
            (acct,),
        )
        rows = cur.fetchall()
        print(f"\n=== ERC4626 rows for account {acct} ===")
        print("distinct chain_ids (any):", nchains)
        print("top chain_id counts:", rows)

    acct0 = accounts[0].lower()
    print("\n=== Row counts matching LendingProvider filters ===")
    ph = ",".join(["%s"] * len(vaults))
    cur.execute(
        f"""
        SELECT COUNT(*) FROM raw.vault_erc4626_account_snapshot_hourly a
        WHERE a.chain_id = %s
          AND lower(a.account_address) = %s
          AND lower(a.vault_address) IN ({ph})
        """,
        (chain_id, acct0, *[v.lower() for v in vaults]),
    )
    erc_match = cur.fetchone()[0]
    print(
        f"raw.vault_erc4626_account_snapshot_hourly "
        f"(chain_id={chain_id}, account, vault IN list): {erc_match}"
    )

    cur.execute(
        """
        SELECT COUNT(*) FROM raw.aave_user_reserve_snapshot_hourly ur
        JOIN raw.aave_reserve r ON r.reserve_id = ur.reserve_id
        JOIN raw.aave_pool p ON p.pool_id = r.pool_id
        WHERE p.chain_id = %s AND ur.chain_id = %s
          AND lower(ur.account_address) = %s
          AND lower(r.underlying_token_address) = lower(%s)
          AND p.protocol_code IN ('HYPERLEND', 'HYPURRFI')
        """,
        (chain_id, chain_id, acct0, usdc),
    )
    aave_match = cur.fetchone()[0]
    print(
        "raw.aave_* (HYPERLEND/HYPURRFI, same chain, account, USDC):",
        aave_match,
    )

    se = p.get_equity(strategy, None)
    print("\n=== get_equity() ===")
    print("equity_usd:", se.equity_usd)
    print("breakdown keys:", list(se.breakdown.keys()) if se.breakdown else [])
    if se.meta:
        err = se.meta.get("error")
        if err:
            print("meta.error:", err)
        else:
            print("meta (no error key): chain_id", se.meta.get("chain_id"))

    cur.close()
    pg.close()

    if erc_match == 0 and aave_match == 0:
        print(
            "\n→ No rows match chain_id + account + vault/USDC filters. "
            "Usually chain_id in Harmonix ≠ resolved chain_id, or accounts/vaults differ."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
