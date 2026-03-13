#!/usr/bin/env python3
"""Dump Paradex account + open positions.

Usage:
  PARADEX_JWT=... python3 scripts/paradex_dump.py

(Uses read-only JWT.)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.paradex_private import ParadexPrivateConnector


def main() -> int:
    if not (os.environ.get("PARADEX_JWT") or os.environ.get("PARADEX_READONLY_TOKEN")):
        print("Missing PARADEX_JWT (or PARADEX_READONLY_TOKEN)", file=sys.stderr)
        return 1

    c = ParadexPrivateConnector()
    acct = c.fetch_account_snapshot()
    pos = c.fetch_open_positions()

    print("== ACCOUNT ==")
    print(json.dumps({k: acct.get(k) for k in ("account_id", "total_balance", "available_balance", "margin_balance")}, indent=2))

    print("\n== OPEN POSITIONS ==")
    if not pos:
        print("(none)")
        return 0

    for p in pos:
        print(
            f"{p.get('inst_id')} | {p.get('side')} | size={p.get('size')} | entry={p.get('entry_price')} | uPnL={p.get('unrealized_pnl')} | leg_id={p.get('leg_id')}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
