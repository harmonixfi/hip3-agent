#!/usr/bin/env python3
"""Daily equity snapshot + report across tracked venues.

Goal
- Persist a daily rollup of total equity (USD-like) across venues Bean tracks.
- Provide a daily PnL delta and simple daily APR (= delta / prior_total * 365).

Storage
- CSV: tracking/equity/equity_daily.csv
  columns: date_local, ts_utc, venue, equity_usd, note

Notes / caveats
- This is *equity* as each venue reports it (margin/account_value/collateral).
- Daily APR is naive if you deposit/withdraw during the day. (We can adjust later using pm_cashflows.)
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to sys.path so `tracking.*` imports work when executed as a script.
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

OUT_PATH = ROOT / "tracking" / "equity" / "equity_daily.csv"

# Use Asia/Ho_Chi_Minh (canonical). Asia/Saigon is often an alias but not always present.
LOCAL_TZ_NAME = os.environ.get("ARBIT_LOCAL_TZ") or "Asia/Ho_Chi_Minh"


def local_today_str(now_utc: Optional[datetime] = None) -> str:
    now_utc = now_utc or datetime.now(timezone.utc)
    if ZoneInfo is None:
        return now_utc.date().isoformat()
    try:
        tz = ZoneInfo(LOCAL_TZ_NAME)
        return now_utc.astimezone(tz).date().isoformat()
    except Exception:
        return now_utc.date().isoformat()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_header(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["date_local", "ts_utc", "venue", "equity_usd", "note"])


def read_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return [row for row in r if isinstance(row, dict)]


def write_rows(path: Path, rows: List[Dict[str, str]]) -> None:
    ensure_header(path)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["date_local", "ts_utc", "venue", "equity_usd", "note"])
        w.writeheader()
        for row in rows:
            w.writerow(row)


def upsert_day(rows: List[Dict[str, str]], *, date_local: str, venue: str, equity_usd: Optional[float], note: str) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in rows:
        if (r.get("date_local") == date_local) and (r.get("venue") == venue):
            continue
        out.append(r)
    out.append(
        {
            "date_local": date_local,
            "ts_utc": utc_now_iso(),
            "venue": venue,
            "equity_usd": "" if equity_usd is None else f"{float(equity_usd):.8f}",
            "note": note,
        }
    )
    # stable sort
    out.sort(key=lambda r: (r.get("date_local") or "", r.get("venue") or ""))
    return out


def safe_float(x) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _err_note(e: Exception) -> str:
    msg = str(e).strip().replace("\n", " ")
    if len(msg) > 120:
        msg = msg[:120] + "…"
    return f"ERR {e.__class__.__name__}: {msg}" if msg else f"ERR {e.__class__.__name__}"


def fetch_equities() -> Tuple[Dict[str, Optional[float]], Dict[str, str]]:
    """Return (venue->equity, venue->note)."""
    equities: Dict[str, Optional[float]] = {}
    notes: Dict[str, str] = {}

    # Paradex
    try:
        from tracking.connectors.paradex_private import ParadexPrivateConnector

        c = ParadexPrivateConnector()
        s = c.fetch_account_snapshot() or {}
        equities["paradex"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
        notes["paradex"] = "ok"
    except Exception as e:
        equities["paradex"] = None
        notes["paradex"] = _err_note(e)

    # Hyperliquid
    try:
        from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector

        c = HyperliquidPrivateConnector()
        s = c.fetch_account_snapshot() or {}
        equities["hyperliquid"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
        notes["hyperliquid"] = "ok"
    except Exception as e:
        equities["hyperliquid"] = None
        notes["hyperliquid"] = _err_note(e)

    # Hyena
    # If we can't pull from an API (or Hyena isn't Hyperliquid-backed), allow manual override.
    try:
        ov = os.environ.get("HYENA_EQUITY_OVERRIDE")
        if ov is not None and str(ov).strip() != "":
            equities["hyena"] = float(str(ov).strip())
            notes["hyena"] = "manual_override"
        else:
            from tracking.connectors.hyena_private import HyenaPrivateConnector

            c = HyenaPrivateConnector()
            s = c.fetch_account_snapshot() or {}
            equities["hyena"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
            notes["hyena"] = "ok"
    except Exception as e:
        equities["hyena"] = None
        notes["hyena"] = _err_note(e)

    # Lighter
    try:
        from tracking.connectors.lighter_private import LighterPrivateConnector

        c = LighterPrivateConnector()
        s = c.fetch_account_snapshot() or {}
        equities["lighter"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
        notes["lighter"] = "ok"
    except Exception as e:
        equities["lighter"] = None
        notes["lighter"] = _err_note(e)

    # Ethereal
    try:
        from tracking.connectors.ethereal_private import EtherealPrivateConnector

        c = EtherealPrivateConnector()
        s = c.fetch_account_snapshot() or {}
        equities["ethereal"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
        notes["ethereal"] = "ok"
    except Exception as e:
        equities["ethereal"] = None
        notes["ethereal"] = _err_note(e)

    # OKX
    try:
        from tracking.connectors.okx_private import OKXPrivateConnector

        c = OKXPrivateConnector()
        s = c.fetch_account_snapshot() or {}
        equities["okx"] = safe_float(s.get("margin_balance") or s.get("total_balance"))
        notes["okx"] = "ok"
    except Exception as e:
        equities["okx"] = None
        notes["okx"] = _err_note(e)

    return equities, notes


def cmd_snapshot() -> int:
    date_local = local_today_str()
    rows = read_rows(OUT_PATH)
    equities, notes = fetch_equities()

    for venue in sorted(equities.keys()):
        rows = upsert_day(rows, date_local=date_local, venue=venue, equity_usd=equities[venue], note=notes.get(venue, ""))

    write_rows(OUT_PATH, rows)
    print(f"OK snapshot date_local={date_local} venues={len(equities)} out={OUT_PATH}")
    return 0


def totals_by_date(rows: List[Dict[str, str]]) -> Dict[str, float]:
    by: Dict[str, float] = {}
    for r in rows:
        d = (r.get("date_local") or "").strip()
        if not d:
            continue
        eq = safe_float(r.get("equity_usd"))
        if eq is None:
            continue
        by[d] = by.get(d, 0.0) + float(eq)
    return by


def venue_breakdown_for_date(rows: List[Dict[str, str]], date_local: str) -> List[Tuple[str, Optional[float], str]]:
    out = []
    for r in rows:
        if (r.get("date_local") or "") != date_local:
            continue
        v = (r.get("venue") or "").strip()
        eq = safe_float(r.get("equity_usd"))
        note = (r.get("note") or "").strip()
        out.append((v, eq, note))
    out.sort(key=lambda x: x[0])
    return out


def fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def _ts_ms_from_iso(s: str) -> Optional[int]:
    s = (s or "").strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return int(d.timestamp() * 1000)
    except Exception:
        return None


def _latest_ts_ms_for_day(rows: List[Dict[str, str]], date_local: str) -> Optional[int]:
    ts = []
    for r in rows:
        if (r.get("date_local") or "") != date_local:
            continue
        t = _ts_ms_from_iso(r.get("ts_utc") or "")
        if t is not None:
            ts.append(t)
    return max(ts) if ts else None


def _net_external_cashflow_usd(since_ms: int, until_ms: int, *, db_path: Optional[str] = None) -> Optional[float]:
    """Sum DEPOSIT/WITHDRAW stablecoin cashflows in the interval.

    Positive = net deposits, Negative = net withdrawals.
    """
    import sqlite3

    dbp = Path(db_path) if db_path else (ROOT / "tracking" / "db" / "arbit_v3.db")
    if not dbp.exists():
        return None

    con = sqlite3.connect(str(dbp))
    try:
        cur = con.execute(
            """
            SELECT SUM(amount) as s
            FROM pm_cashflows
            WHERE ts >= ? AND ts <= ?
              AND cf_type IN ('DEPOSIT','WITHDRAW')
              AND UPPER(currency) IN ('USD','USDC','USDT')
            """,
            (int(since_ms), int(until_ms)),
        )
        row = cur.fetchone()
        if not row:
            return 0.0
        s = row[0]
        return float(s or 0.0)
    except Exception:
        return None
    finally:
        con.close()


def cmd_report(limit_days: int = 7, *, db_path: Optional[str] = None) -> int:
    rows = read_rows(OUT_PATH)
    if not rows:
        print("No equity history yet. Run: python3 scripts/equity_daily.py snapshot")
        return 1

    totals = totals_by_date(rows)
    days = sorted(totals.keys())
    if not days:
        print("No valid equity totals yet (all venues missing?).")
        return 1

    d0 = days[-1]
    d1 = days[-2] if len(days) >= 2 else None

    t0 = totals.get(d0)
    msg = []
    msg.append(f"**Daily Equity Snapshot** ({d0} local)")
    msg.append(f"Total equity: {fmt_money(t0)}")

    if d1 is not None:
        t1 = totals.get(d1)
        if t1 and t1 > 0:
            raw_delta = t0 - t1

            ts1 = _latest_ts_ms_for_day(rows, d1)
            ts0 = _latest_ts_ms_for_day(rows, d0)
            net_flow = _net_external_cashflow_usd(ts1, ts0, db_path=db_path) if (ts1 and ts0) else None

            # Adjusted PnL = equity change - net deposits/withdrawals
            if net_flow is None:
                pnl = raw_delta
                msg.append(
                    f"Δ vs {d1}: {fmt_money(raw_delta)} | cashflow adj: n/a | PnL(adj): {fmt_money(pnl)} | implied APR: {(pnl / t1 * 365 * 100):+.1f}%"
                )
            else:
                pnl = raw_delta - net_flow
                msg.append(
                    f"Δ vs {d1}: {fmt_money(raw_delta)} | net deposits: {fmt_money(net_flow)} | PnL(adj): {fmt_money(pnl)} | implied APR: {(pnl / t1 * 365 * 100):+.1f}%"
                )
        else:
            msg.append(f"Δ vs {d1}: n/a (missing prior total)")

    bd = venue_breakdown_for_date(rows, d0)
    if bd:
        msg.append("\nBreakdown:")
        for v, eq, note in bd:
            tail = f" ({note})" if (note and note != "ok") else ""
            msg.append(f"- {v}: {fmt_money(eq)}{tail}")

    tail_days = days[-limit_days:]
    if len(tail_days) > 1:
        msg.append("\nLast totals:")
        for d in tail_days:
            msg.append(f"- {d}: {fmt_money(totals.get(d))}")

    print("\n".join(msg).strip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("snapshot", help="Fetch and store today's equity snapshot")

    rp = sub.add_parser("report", help="Print latest daily equity report")
    rp.add_argument("--days", type=int, default=7, help="Include last N totals (default: 7)")
    rp.add_argument("--db", type=str, default=str(ROOT / "tracking" / "db" / "arbit_v3.db"), help="Path to arbit_v3.db (for cashflow adjustment)")

    args = ap.parse_args()

    if args.cmd == "snapshot":
        return cmd_snapshot()
    if args.cmd == "report":
        return cmd_report(limit_days=int(args.days), db_path=str(args.db))

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
