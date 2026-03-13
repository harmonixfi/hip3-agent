#!/usr/bin/env python3
"""Dump Hyperliquid open perp positions.

Usage:
  ETHEREAL_ACCOUNT_ADDRESS=0x... python3 scripts/hyperliquid_dump.py
  HYPERLIQUID_ADDRESS=0x... python3 scripts/hyperliquid_dump.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector


def main() -> int:
    if not (os.environ.get("HYPERLIQUID_ADDRESS") or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")):
        print("Missing ETHEREAL_ACCOUNT_ADDRESS (or HYPERLIQUID_ADDRESS)", file=sys.stderr)
        return 1

    c = HyperliquidPrivateConnector()
    acct = c.fetch_account_snapshot()
    pos = c.fetch_open_positions()

    print("== ACCOUNT ==")
    print(json.dumps({k: acct.get(k) for k in ("account_id", "total_balance", "available_balance", "position_value")}, indent=2))

    print("\n== OPEN POSITIONS ==")
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
