#!/usr/bin/env python3
"""Backup any existing v3 DB then create a fresh one.

- If db exists: copy to *.bak.<epoch_ms>
- Remove original
- Re-init schema

Default DB: tracking/db/arbit_v3.db
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def main() -> int:
    sys.path.insert(0, str(ROOT))

    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    db = args.db
    if db.exists():
        ts = int(time.time() * 1000)
        bak = db.with_suffix(db.suffix + f".bak.{ts}")
        shutil.copy2(db, bak)
        db.unlink()
        print(f"Backed up old db -> {bak}")

    # init
    from scripts.db_v3_init import main as init_main  # type: ignore

    # Reuse the init script but preserve --db argument.
    import sys as _sys
    old_argv = list(_sys.argv)
    try:
        _sys.argv = [old_argv[0], "--db", str(db)]
        return init_main()
    finally:
        _sys.argv = old_argv


if __name__ == "__main__":
    raise SystemExit(main())
