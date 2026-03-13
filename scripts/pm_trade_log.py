#!/usr/bin/env python3
"""Generate a markdown trade log from pm_* tables.

Use-case
- When a position underperforms (or when closing), generate a consistent log entry
  so Bean can review later and we can improve pair selection.

Output
- Writes to /mnt/data/agents/arbit/trades/<YYYY-MM-DD>_<POSITION_ID>.md by default.

This script is deterministic and prints no secrets.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.position_manager.carry import compute_all_carries


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_date_utc() -> str:
    return utc_now().date().isoformat()


def fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def ms_to_utc_str(ms: Optional[int]) -> str:
    if not ms:
        return "n/a"
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    except Exception:
        return "n/a"


def load_position(con: sqlite3.Connection, position_id: str) -> Dict[str, Any]:
    row = con.execute(
        "SELECT position_id, venue, strategy, status, created_at_ms, updated_at_ms, closed_at_ms, meta_json FROM pm_positions WHERE position_id=?",
        (position_id,),
    ).fetchone()
    if not row:
        raise SystemExit(f"Position not found: {position_id}")

    meta = {}
    try:
        meta = json.loads(row[7]) if row[7] else {}
    except Exception:
        meta = {}

    legs = con.execute(
        """
        SELECT leg_id, venue, inst_id, side, size, opened_at_ms, closed_at_ms
        FROM pm_legs
        WHERE position_id=?
        ORDER BY leg_id
        """,
        (position_id,),
    ).fetchall()

    leg_list = []
    for leg_id, venue, inst_id, side, size, opened_at_ms, closed_at_ms in legs:
        leg_list.append(
            {
                "leg_id": leg_id,
                "venue": venue,
                "inst_id": inst_id,
                "side": side,
                "size": float(size or 0.0),
                "opened_at_ms": opened_at_ms,
                "closed_at_ms": closed_at_ms,
            }
        )

    return {
        "position_id": row[0],
        "venue": row[1],
        "strategy": row[2],
        "status": row[3],
        "created_at_ms": row[4],
        "updated_at_ms": row[5],
        "closed_at_ms": row[6],
        "meta": meta,
        "legs": leg_list,
    }


def cashflows_since(con: sqlite3.Connection, position_id: str, since_ms: int) -> Dict[str, float]:
    cur = con.execute(
        """
        SELECT cf_type, UPPER(currency) as ccy, SUM(amount)
        FROM pm_cashflows
        WHERE position_id=? AND ts>=? AND UPPER(currency) IN ('USD','USDC','USDT')
        GROUP BY cf_type, UPPER(currency)
        """,
        (position_id, int(since_ms)),
    )
    out = {"funding": 0.0, "fee": 0.0, "other": 0.0}
    for cf_type, ccy, s in cur.fetchall():
        amt = float(s or 0.0)
        if cf_type == "FUNDING":
            out["funding"] += amt
        elif cf_type == "FEE":
            out["fee"] += amt
        else:
            out["other"] += amt
    out["net"] = out["funding"] + out["fee"] + out["other"]
    return out


def carry_for(con: sqlite3.Connection, position_id: str) -> Optional[Dict[str, Any]]:
    carries = compute_all_carries(con, ROOT / "data" / "loris_funding_history.csv")
    for c in carries:
        if c.get("position_id") == position_id:
            return c
    return None


def default_since_ms(pos: Dict[str, Any]) -> int:
    # Use earliest leg open time if present; else position created_at.
    ts = [int(l.get("opened_at_ms") or 0) for l in pos.get("legs") or [] if l.get("opened_at_ms")]
    if ts:
        return min(ts)
    return int(pos.get("created_at_ms") or 0) or int(utc_now().timestamp() * 1000)


def write_log(*, out_path: Path, pos: Dict[str, Any], tag: str, note: str) -> None:
    strategy = str(pos.get("strategy") or "")
    status = str(pos.get("status") or "")

    # derive pair string
    pair = ""
    try:
        l = pos.get("legs") or []
        long_ex = next((x["venue"] for x in l if str(x.get("side")).upper() == "LONG"), None)
        short_ex = next((x["venue"] for x in l if str(x.get("side")).upper() == "SHORT"), None)
        if long_ex and short_ex:
            pair = f"LONG {long_ex} / SHORT {short_ex}"
    except Exception:
        pair = ""

    since_ms = default_since_ms(pos)

    con = sqlite3.connect(str(ROOT / "tracking" / "db" / "arbit_v3.db"))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        cf = cashflows_since(con, pos["position_id"], since_ms)
        c = carry_for(con, pos["position_id"]) or {}
    finally:
        con.close()

    apr_cur = safe_float(c.get("apr_cur"))
    apr14 = safe_float(c.get("apr_14d"))

    lines: List[str] = []
    lines.append(f"# Trade Log — {pos['position_id']}")
    lines.append("")
    lines.append(f"Date: {iso_date_utc()} (UTC)")
    lines.append(f"Status: {status}")
    lines.append(f"Tag: {tag}")
    lines.append("")

    lines.append("## Setup")
    lines.append(f"- Strategy: {strategy}")
    if pair:
        lines.append(f"- Pair: {pair}")
    lines.append(f"- OpenedAt: {ms_to_utc_str(since_ms)}")
    lines.append("- Legs:")
    for leg in pos.get("legs") or []:
        lines.append(
            f"  - {leg['venue']} {leg['inst_id']} {leg['side']} size={leg['size']} (leg_id={leg['leg_id']})"
        )

    lines.append("")
    lines.append("## Performance")
    if apr_cur is not None or apr14 is not None:
        lines.append(f"- Carry snapshot: APRcur={('n/a' if apr_cur is None else f'{apr_cur:+.1f}%')} | APR14={('n/a' if apr14 is None else f'{apr14:+.1f}%')}")
    lines.append(f"- Realized cashflows since entry (stable): funding={fmt_money(cf.get('funding'))} fee={fmt_money(cf.get('fee'))} other={fmt_money(cf.get('other'))} net={fmt_money(cf.get('net'))}")

    if note:
        lines.append("")
        lines.append("## Notes")
        lines.append(note.strip())

    lines.append("")
    lines.append("---")
    lines.append("GeneratedBy: pm_trade_log.py")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=ROOT / "tracking" / "db" / "arbit_v3.db")
    ap.add_argument("--position-id", required=True)
    ap.add_argument("--tag", default="INEFFECTIVE", help="OK|INEFFECTIVE|UNKNOWN")
    ap.add_argument("--note", default="")
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        pos = load_position(con, args.position_id)
    finally:
        con.close()

    out = args.out
    if out is None:
        out = ROOT / "trades" / f"{iso_date_utc()}_{args.position_id}.md"

    write_log(out_path=out, pos=pos, tag=str(args.tag).upper(), note=str(args.note))
    print(f"OK wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
