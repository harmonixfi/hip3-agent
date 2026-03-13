#!/usr/bin/env python3
"""Position Manager CLI (v3).

MVP commands:
- sync-registry: load config/positions.json and upsert into pm_positions/pm_legs
- list: show managed positions rollup

No private APIs yet.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).parent.parent
# Ensure repo root is on sys.path so `import tracking...` works.
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _q1(con: sqlite3.Connection, sql: str, params=()):
    cur = con.execute(sql, params)
    row = cur.fetchone()
    return row[0] if row else None


def load_registry_json(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"registry must be a list, got {type(data).__name__}")
    return data


def sync_registry(con: sqlite3.Connection, registry_path: Path) -> Dict[str, Any]:
    # Use the validator
    import sys
    sys.path.insert(0, str(ROOT))
    from tracking.position_manager.registry import load_registry  # type: ignore

    positions = load_registry(registry_path)
    now_ms = int(time.time() * 1000)

    n_pos = 0
    n_legs = 0

    for p in positions:
        # venue field in pm_positions is required by schema, but many positions are multi-venue.
        venues = sorted({leg.venue for leg in p.legs})
        venue = venues[0] if len(venues) == 1 else "multi"

        raw_obj = {
            "position_id": p.position_id,
            "strategy_type": p.strategy_type,
            "base": p.base,
            "status": p.status,
            "thresholds": p.thresholds,
            "legs": [leg.__dict__ for leg in p.legs],
        }

        created_at = _q1(con, "SELECT created_at_ms FROM pm_positions WHERE position_id=?", (p.position_id,))
        created_at_ms = int(created_at) if created_at is not None else now_ms

        con.execute(
            """
            INSERT INTO pm_positions(
              position_id, venue, strategy, status, created_at_ms, updated_at_ms, raw_json, meta_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(position_id) DO UPDATE SET
              venue=excluded.venue,
              strategy=excluded.strategy,
              status=excluded.status,
              updated_at_ms=excluded.updated_at_ms,
              raw_json=excluded.raw_json,
              meta_json=excluded.meta_json
            """,
            (
                p.position_id,
                venue,
                p.strategy_type,
                p.status,
                created_at_ms,
                now_ms,
                json.dumps(raw_obj, separators=(",", ":"), sort_keys=True),
                json.dumps({"base": p.base, "thresholds": p.thresholds or {}}, separators=(",", ":"), sort_keys=True),
            ),
        )
        n_pos += 1

        # legs
        for leg in p.legs:
            opened_at = _q1(con, "SELECT opened_at_ms FROM pm_legs WHERE leg_id=?", (leg.leg_id,))
            opened_at_ms = int(opened_at) if opened_at is not None else now_ms

            leg_status = "CLOSED" if p.status == "CLOSED" else "OPEN"

            con.execute(
                """
                INSERT INTO pm_legs(
                  leg_id, position_id, venue, inst_id, side, size,
                  entry_price, current_price, unrealized_pnl, realized_pnl,
                  status, opened_at_ms, closed_at_ms,
                  raw_json, meta_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(leg_id) DO UPDATE SET
                  position_id=excluded.position_id,
                  venue=excluded.venue,
                  inst_id=excluded.inst_id,
                  side=excluded.side,
                  size=excluded.size,
                  status=excluded.status,
                  raw_json=excluded.raw_json,
                  meta_json=excluded.meta_json
                """,
                (
                    leg.leg_id,
                    p.position_id,
                    leg.venue,
                    leg.inst_id,
                    leg.side,
                    float(leg.qty),
                    None,
                    None,
                    None,
                    None,
                    leg_status,
                    opened_at_ms,
                    None,
                    json.dumps(leg.__dict__, separators=(",", ":"), sort_keys=True),
                    json.dumps(
                        {
                            "qty": leg.qty,
                            "qty_type": leg.qty_type,
                            "leverage": leg.leverage,
                            "margin_mode": leg.margin_mode,
                            "collateral": leg.collateral,
                        },
                        separators=(",", ":"),
                        sort_keys=True,
                    ),
                ),
            )
            n_legs += 1

    con.commit()
    return {"positions": n_pos, "legs": n_legs, "registry": str(registry_path)}


def list_positions(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    cur = con.execute(
        """
        SELECT p.position_id, p.venue, p.strategy, p.status, p.updated_at_ms, p.raw_json,
               COUNT(l.leg_id) as n_legs
        FROM pm_positions p
        LEFT JOIN pm_legs l ON l.position_id = p.position_id
        GROUP BY p.position_id
        ORDER BY p.updated_at_ms DESC
        """
    )

    out: List[Dict[str, Any]] = []
    for position_id, venue, strategy, status, updated_at_ms, raw_json, n_legs in cur.fetchall():
        base = None
        try:
            if raw_json:
                base = json.loads(raw_json).get("base")
        except Exception:
            base = None

        out.append(
            {
                "position_id": position_id,
                "base": base,
                "venue": venue,
                "strategy": strategy,
                "status": status,
                "n_legs": int(n_legs),
                "updated_at_ms": int(updated_at_ms) if updated_at_ms is not None else None,
            }
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(prog="pm")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)

    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_sync = sub.add_parser("sync-registry", help="Load registry JSON and upsert into DB")
    sp_sync.add_argument("--registry", type=Path, default=ROOT / "config" / "positions.json")

    sp_list = sub.add_parser("list", help="List managed positions")
    sp_list.add_argument("--json", action="store_true")

    args = ap.parse_args()

    con = connect(args.db)
    try:
        if args.cmd == "sync-registry":
            res = sync_registry(con, args.registry)
            print(f"OK: synced registry -> {res['positions']} positions, {res['legs']} legs")
            return 0

        if args.cmd == "list":
            rows = list_positions(con)
            if args.json:
                print(json.dumps(rows, indent=2, sort_keys=True))
                return 0
            if not rows:
                print("(no positions)")
                return 0

            # Pretty-ish plain output
            for r in rows:
                base = r.get("base") or "?"
                print(
                    f"{r['position_id']}: {base} | {r['strategy']} | {r['status']} | legs={r['n_legs']} | venue={r['venue']}"
                )
            return 0

        raise SystemExit("unknown command")
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
