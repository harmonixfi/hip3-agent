#!/usr/bin/env python3
"""Dump Ethereal subaccounts, balances, and open positions.

Usage:
  ETHEREAL_ACCOUNT_ADDRESS=0x... python3 scripts/ethereal_dump.py
  ETHEREAL_ACCOUNT_ADDRESS=0x... ETHEREAL_SUBACCOUNT_ID=<uuid> python3 scripts/ethereal_dump.py

This is a helper to build `config/positions.json` correctly.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.ethereal_private import EtherealPrivateConnector


def main() -> int:
    if not (os.environ.get("ETHEREAL_ACCOUNT_ADDRESS") or os.environ.get("ETHEREAL_SENDER")):
        print("Missing ETHEREAL_ACCOUNT_ADDRESS (or ETHEREAL_SENDER)", file=sys.stderr)
        return 1

    c = EtherealPrivateConnector()
    acct = c.fetch_account_snapshot()
    pos = c.fetch_open_positions()

    print("== ACCOUNT ROLLUP ==")
    print(json.dumps({k: acct.get(k) for k in ("account_id", "total_balance", "available_balance", "margin_balance")}, indent=2))

    print("\n== OPEN POSITIONS (normalized) ==")
    if not pos:
        print("(none)")
        return 0

    for p in pos:
        print(
            f"{p.get('inst_id')} | {p.get('side')} | size={p.get('size')} | entry={p.get('entry_price')} | mark={p.get('current_price')} | leg_id={p.get('leg_id')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
