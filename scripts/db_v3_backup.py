#!/usr/bin/env python3
"""Backup SQLite DB v3 (non-destructive).

- Copies tracking/db/arbit_v3.db into tracking/db/backups/ with timestamp.
- Optional retention prune.

Safe for cron.
"""

from __future__ import annotations

import argparse
import os
import shutil
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"
DEFAULT_DIR = ROOT / "tracking" / "db" / "backups"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_DIR)
    ap.add_argument("--keep-days", type=int, default=14)
    args = ap.parse_args()

    db = args.db
    if not db.exists():
        print(f"missing_db={db}")
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    out = args.out_dir / f"{db.name}.bak.{ts}"
    shutil.copy2(db, out)
    print(f"backup_ok={out}")

    # prune old backups
    keep_s = max(0, int(args.keep_days)) * 24 * 3600
    if keep_s > 0:
        cutoff = time.time() - keep_s
        for p in sorted(args.out_dir.glob(f"{db.name}.bak.*")):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
