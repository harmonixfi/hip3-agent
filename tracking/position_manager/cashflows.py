"""Cashflow ledger utilities (pm_cashflows).

Purpose:
- Ingest realized funding payments + fees into `pm_cashflows` (append-only).
- Provide rollups (24h/7d) per managed position.

Conventions:
- amount: positive = credit, negative = debit
- currency: prefer USD/USDC when known

We intentionally keep this deterministic (no LLM).
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass
class CashflowEvent:
    venue: str
    account_id: str
    ts: int
    cf_type: str  # FUNDING | FEE | ... (see schema)
    amount: float
    currency: str
    description: str = ""
    position_id: Optional[str] = None
    leg_id: Optional[str] = None
    raw_json: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None

    def to_row(self) -> Tuple:
        return (
            self.position_id,
            self.leg_id,
            self.venue,
            self.account_id,
            int(self.ts),
            self.cf_type,
            float(self.amount),
            self.currency,
            self.description,
            json.dumps(self.raw_json or {}, separators=(",", ":"), sort_keys=True),
            json.dumps(self.meta or {}, separators=(",", ":"), sort_keys=True),
        )


def now_ms() -> int:
    return int(time.time() * 1000)


def _exists_event(con: sqlite3.Connection, ev: CashflowEvent) -> bool:
    """Best-effort de-dup (since schema doesn't enforce uniqueness)."""
    sql = """
    SELECT 1 FROM pm_cashflows
    WHERE venue=? AND account_id=? AND ts=? AND cf_type=? AND amount=? AND currency=? AND COALESCE(description,'')=COALESCE(?, '')
    LIMIT 1
    """
    cur = con.execute(
        sql,
        (
            ev.venue,
            ev.account_id,
            int(ev.ts),
            ev.cf_type,
            float(ev.amount),
            ev.currency,
            ev.description,
        ),
    )
    return cur.fetchone() is not None


def insert_cashflow_events(con: sqlite3.Connection, events: Iterable[CashflowEvent]) -> int:
    """Insert events append-only, with best-effort de-dup."""
    sql = """
    INSERT INTO pm_cashflows(
      position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, raw_json, meta_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    n = 0
    for ev in events:
        if _exists_event(con, ev):
            continue
        con.execute(sql, ev.to_row())
        n += 1
    con.commit()
    return n


def load_managed_leg_index(con: sqlite3.Connection) -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    """Map (venue, inst_id, side) -> (position_id, leg_id)."""
    cur = con.execute(
        """
        SELECT leg_id, position_id, venue, inst_id, side
        FROM pm_legs
        WHERE status='OPEN'
        """
    )
    idx: Dict[Tuple[str, str, str], Tuple[str, str]] = {}
    for leg_id, position_id, venue, inst_id, side in cur.fetchall():
        key = (str(venue), str(inst_id), str(side).upper())
        idx[key] = (str(position_id), str(leg_id))
    return idx


def rollup(con: sqlite3.Connection, since_ms: int, until_ms: Optional[int] = None) -> List[Dict[str, Any]]:
    """Roll up cashflows per position (all types) within a window."""
    until_ms = int(until_ms) if until_ms is not None else now_ms()

    cur = con.execute(
        """
        SELECT COALESCE(position_id,'(unmapped)') as position_id,
               cf_type,
               SUM(amount) as total_amount,
               currency,
               COUNT(*) as n
        FROM pm_cashflows
        WHERE ts >= ? AND ts <= ?
        GROUP BY COALESCE(position_id,'(unmapped)'), cf_type, currency
        ORDER BY position_id, cf_type
        """,
        (int(since_ms), int(until_ms)),
    )

    out: List[Dict[str, Any]] = []
    for position_id, cf_type, total_amount, currency, n in cur.fetchall():
        out.append(
            {
                "position_id": position_id,
                "cf_type": cf_type,
                "total": float(total_amount or 0.0),
                "currency": currency,
                "n": int(n or 0),
                "since_ms": int(since_ms),
                "until_ms": int(until_ms),
            }
        )
    return out


STABLE_CCY = {"USD", "USDC", "USDT"}


def rollup_stable_by_position(
    con: sqlite3.Connection,
    since_ms: int,
    until_ms: Optional[int] = None,
    *,
    cf_types: Tuple[str, ...] = ("FUNDING", "FEE"),
) -> Dict[str, Dict[str, Any]]:
    """Return stablecoin rollup per position for FUNDING/FEE.

    Output shape:
    {
      position_id: {
        "funding": float,
        "fee": float,
        "net": float,
        "n_funding": int,
        "n_fee": int,
        "since_ms": int,
        "until_ms": int,
      },
      ...
    }

    Notes:
    - Only counts rows where currency in STABLE_CCY.
    - Ignores unmapped (NULL position_id) rows.
    """

    until_ms = int(until_ms) if until_ms is not None else now_ms()

    placeholders = ",".join("?" for _ in cf_types)
    sql = f"""
    SELECT position_id, cf_type, currency,
           SUM(amount) as total,
           COUNT(*) as n,
           MIN(ts) as min_ts,
           MAX(ts) as max_ts
    FROM pm_cashflows
    WHERE position_id IS NOT NULL
      AND ts >= ? AND ts <= ?
      AND cf_type IN ({placeholders})
    GROUP BY position_id, cf_type, currency
    """

    cur = con.execute(sql, (int(since_ms), int(until_ms), *cf_types))

    out: Dict[str, Dict[str, Any]] = {}
    for position_id, cf_type, currency, total, n, min_ts, max_ts in cur.fetchall():
        if str(currency).upper() not in STABLE_CCY:
            continue
        pid = str(position_id)
        out.setdefault(
            pid,
            {
                "funding": 0.0,
                "fee": 0.0,
                "net": 0.0,
                "n_funding": 0,
                "n_fee": 0,
                "min_ts": None,
                "max_ts": None,
                "since_ms": int(since_ms),
                "until_ms": int(until_ms),
            },
        )

        # update observation window
        try:
            mi = int(min_ts) if min_ts is not None else None
            ma = int(max_ts) if max_ts is not None else None
        except Exception:
            mi = None
            ma = None

        if mi is not None:
            if out[pid]["min_ts"] is None or mi < int(out[pid]["min_ts"]):
                out[pid]["min_ts"] = mi
        if ma is not None:
            if out[pid]["max_ts"] is None or ma > int(out[pid]["max_ts"]):
                out[pid]["max_ts"] = ma

        total_f = float(total or 0.0)
        n_i = int(n or 0)
        if cf_type == "FUNDING":
            out[pid]["funding"] += total_f
            out[pid]["n_funding"] += n_i
        elif cf_type == "FEE":
            out[pid]["fee"] += total_f
            out[pid]["n_fee"] += n_i

    for pid, d in out.items():
        d["net"] = float(d.get("funding", 0.0)) + float(d.get("fee", 0.0))

    return out
