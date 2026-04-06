#!/usr/bin/env python3
"""Vault daily snapshot cron job (02:05 UTC / 09:05 ICT)."""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vault_snapshot] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    log.info("Starting vault daily snapshot")
    t0 = time.time()

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys = ON")

    try:
        from tracking.vault.snapshot import run_daily_snapshot

        result = run_daily_snapshot(con)
        elapsed = time.time() - t0
        log.info(
            "Done in %.1fs: strategies=%s, equity=$%.2f, apr=%.6f",
            elapsed,
            result["strategies_processed"],
            result["vault_equity"],
            result["vault_apr"],
        )
        return 0
    except Exception:
        log.exception("Vault snapshot failed")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
