#!/usr/bin/env python3
"""Dump Lighter perp positions + spot balances.

Usage:
  ETHEREAL_ACCOUNT_ADDRESS=0x... python3 scripts/lighter_dump.py
  LIGHTER_L1_ADDRESS=0x... python3 scripts/lighter_dump.py

This is a helper to build `config/positions.json` correctly, especially for
spot legs like `LIT/USDC`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.lighter_private import LighterPrivateConnector


def main() -> int:
    if not (os.environ.get("LIGHTER_L1_ADDRESS") or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")):
        print("Missing ETHEREAL_ACCOUNT_ADDRESS (or LIGHTER_L1_ADDRESS)", file=sys.stderr)
        return 1

    c = LighterPrivateConnector()
    acct = c.fetch_account_snapshot()
    pos = c.fetch_open_positions()

    print("== ACCOUNT ==")
    print(json.dumps({k: acct.get(k) for k in ("account_id", "total_balance", "available_balance", "unrealized_pnl")}, indent=2))

    print("\n== OPEN (perp + spot) ==")
    if not pos:
        print("(none)")
        return 0

    for p in pos:
        print(
            f"{p.get('inst_id')} | {p.get('side')} | size={p.get('size')} | entry={p.get('entry_price')} | px={p.get('current_price')} | leg_id={p.get('leg_id')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
