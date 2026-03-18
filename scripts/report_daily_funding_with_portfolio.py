#!/usr/bin/env python3
"""Harmonix daily funding report + portfolio review.

What it does
- Reviews tracked SPOT_PERP positions with funding/cost/breakeven fields.
- Ranks the top Hyperliquid rotation candidates not currently held.
- Supports explicit rotation-cost analysis via --rotate-from / --rotate-to.

Deterministic: yes (no LLM). Prints no secrets.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from scripts.report_daily_funding_sections import (
    APR14_MIN_THRESHOLD,
    SECTION_PORTFOLIO,
    SECTION_ROTATION_EQUITIES,
    SECTION_ROTATION_GENERAL,
    VALID_SECTIONS,
    build_candidate_pool,
    candidate_identity,
    SectionStatus,
    build_flagged_positions,
    emit_status,
    load_felix_membership,
    normalize_symbol,
    render_portfolio_summary_section,
    render_rotation_section,
)
from tracking.analytics.cost_model_v3 import CostModelV3
from tracking.position_manager.carry import compute_all_carries

DB_DEFAULT = ROOT / "tracking" / "db" / "arbit_v3.db"
LORIS_CSV = ROOT / "data" / "loris_funding_history.csv"
FELIX_EQUITIES_CACHE = ROOT / "data" / "felix_equities_cache.json"
EQUITY_CSV = ROOT / "tracking" / "equity" / "equity_daily.csv"
STABLE_CCY = {"USD", "USDC", "USDT"}
SUPPORTED_REPORT_EXCHANGES = ("hyperliquid", "tradexyz", "felix", "kinetiq", "hyena")
HYPERLIQUID_DEX_TO_VENUE = {
    "xyz": "tradexyz",
    "flx": "felix",
    "km": "kinetiq",
    "hyna": "hyena",
}


@dataclass
class CandidateRow:
    symbol: str
    exchange: str
    oi_rank: Optional[int]
    latest_ts: datetime
    apr_latest: Optional[float]
    apr_1d: Optional[float]
    apr_2d: Optional[float]
    apr_3d: Optional[float]
    apr_7d: Optional[float]
    apr_14d: Optional[float]
    avg_15d_rate_8h: Optional[float]
    stability_score: Optional[float]
    flags: List[str]


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _effective_leg_venue(leg: Dict[str, Any]) -> str:
    venue = str(leg.get("venue") or "").strip().lower()
    inst_id = str(leg.get("inst_id") or "").strip()
    if venue == "hyperliquid" and ":" in inst_id:
        dex, _coin = inst_id.split(":", 1)
        return HYPERLIQUID_DEX_TO_VENUE.get(dex.strip().lower(), venue)
    return venue


def _position_perp_venue(position: Dict[str, Any]) -> str:
    if str(position.get("strategy") or "").upper() == "SPOT_PERP":
        for leg in position.get("legs") or []:
            if str(leg.get("side") or "").upper() == "SHORT":
                return _effective_leg_venue(leg)
    for leg in position.get("legs") or []:
        if "/" not in str(leg.get("inst_id") or ""):
            return _effective_leg_venue(leg)
    return str(position.get("venue") or "").strip().lower() or "n/a"


def _fmt_money(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"${x:,.2f}"


def _fmt_pct(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    return f"{x:+.1f}%"


def _fmt_days(x: Optional[float]) -> str:
    if x is None:
        return "n/a"
    if x >= 1:
        return f"{x:.1f}d"
    return f"{x * 24:.1f}h"


def _ms_to_utc(ms: Optional[int]) -> str:
    if not ms:
        return "n/a"
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    except Exception:
        return "n/a"


def _rate_to_apr(rate_8h: Optional[float]) -> Optional[float]:
    if rate_8h is None:
        return None
    return float(rate_8h) * 3.0 * 365.0 * 100.0


def _avg_rate(samples: List[Tuple[datetime, float]], since_dt: datetime) -> Tuple[Optional[float], int]:
    vals = [rate for ts, rate in samples if ts >= since_dt]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def load_latest_equity_snapshot() -> Tuple[Optional[str], Dict[str, float], Dict[str, str]]:
    if not EQUITY_CSV.exists() or EQUITY_CSV.stat().st_size == 0:
        return None, {}, {}

    rows: List[Dict[str, str]] = []
    with EQUITY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if isinstance(row, dict):
                rows.append(row)

    if not rows:
        return None, {}, {}

    latest_date = max((row.get("date_local") or "") for row in rows if row.get("date_local"))
    eq: Dict[str, float] = {}
    note: Dict[str, str] = {}
    for row in rows:
        if (row.get("date_local") or "") != latest_date:
            continue
        venue = (row.get("venue") or "").strip()
        if not venue:
            continue
        val = _safe_float(row.get("equity_usd"))
        if val is not None:
            eq[venue] = val
        note[venue] = (row.get("note") or "").strip()

    return latest_date, eq, note


def _parse_json(raw: Any) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _position_rows(con: sqlite3.Connection) -> List[Dict[str, Any]]:
    rows = con.execute(
        """
        SELECT
          p.position_id,
          p.venue,
          p.strategy,
          p.status,
          p.created_at_ms,
          p.meta_json,
          l.leg_id,
          l.venue,
          l.inst_id,
          l.side,
          l.size,
          l.entry_price,
          l.current_price,
          l.unrealized_pnl,
          l.opened_at_ms,
          l.meta_json
        FROM pm_positions p
        LEFT JOIN pm_legs l
          ON p.position_id = l.position_id
         AND l.status = 'OPEN'
        WHERE p.status = 'OPEN'
        ORDER BY p.created_at_ms ASC, l.leg_id ASC
        """
    ).fetchall()

    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        (
            pid,
            venue,
            strategy,
            status,
            created_at_ms,
            pos_meta_json,
            leg_id,
            leg_venue,
            inst_id,
            side,
            size,
            entry_price,
            current_price,
            unrealized_pnl,
            opened_at_ms,
            leg_meta_json,
        ) = row

        if pid not in out:
            meta = _parse_json(pos_meta_json)
            out[pid] = {
                "position_id": str(pid),
                "venue": str(venue or ""),
                "strategy": str(strategy or meta.get("strategy_type") or ""),
                "status": str(status or ""),
                "created_at_ms": int(created_at_ms or 0),
                "meta": meta,
                "base": str(meta.get("base") or str(pid).split("_", 1)[0]).upper(),
                "legs": [],
            }

        if leg_id:
            out[pid]["legs"].append(
                {
                    "leg_id": str(leg_id),
                    "venue": str(leg_venue or ""),
                    "inst_id": str(inst_id or ""),
                    "side": str(side or "").upper(),
                    "size": float(size or 0.0),
                    "entry_price": _safe_float(entry_price),
                    "current_price": _safe_float(current_price),
                    "unrealized_pnl": _safe_float(unrealized_pnl),
                    "opened_at_ms": int(opened_at_ms or 0),
                    "meta": _parse_json(leg_meta_json),
                }
            )

    return list(out.values())


def _table_exists(con: sqlite3.Connection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(con: sqlite3.Connection, table_name: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(row[1]) for row in rows}


def _validate_required_schema(con: sqlite3.Connection) -> None:
    required_columns = {
        "pm_positions": {
            "position_id",
            "venue",
            "strategy",
            "status",
            "created_at_ms",
            "updated_at_ms",
            "closed_at_ms",
            "meta_json",
        },
        "pm_legs": {
            "leg_id",
            "position_id",
            "venue",
            "inst_id",
            "side",
            "size",
            "entry_price",
            "current_price",
            "unrealized_pnl",
            "realized_pnl",
            "status",
            "opened_at_ms",
            "closed_at_ms",
            "meta_json",
        },
        "pm_cashflows": {
            "position_id",
            "leg_id",
            "ts",
            "cf_type",
            "amount",
            "currency",
        },
    }
    for table_name, required in required_columns.items():
        existing = _table_columns(con, table_name)
        missing = sorted(required - existing)
        if missing:
            raise sqlite3.OperationalError(f"{table_name} missing columns: {', '.join(missing)}")


def _load_open_position_bases(con: sqlite3.Connection) -> List[str]:
    rows = con.execute(
        """
        SELECT position_id, meta_json
        FROM pm_positions
        WHERE status = 'OPEN'
        ORDER BY created_at_ms ASC
        """
    ).fetchall()
    bases: List[str] = []
    for position_id, meta_json in rows:
        meta = _parse_json(meta_json)
        base = normalize_symbol(meta.get("base") or str(position_id).split("_", 1)[0])
        if base:
            bases.append(base)
    return bases


def _is_required_schema_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    required_markers = (
        "pm_positions",
        "pm_legs",
        "pm_cashflows",
        "updated_at_ms",
        "closed_at_ms",
        "realized_pnl",
    )
    return any(marker in message for marker in required_markers)


def _first_cashflow_ts(con: sqlite3.Connection, position_id: str) -> Optional[int]:
    row = con.execute(
        "SELECT MIN(ts) FROM pm_cashflows WHERE position_id=?",
        (position_id,),
    ).fetchone()
    if not row or row[0] is None:
        return None
    return int(row[0])


def _position_start_ms(con: sqlite3.Connection, position: Dict[str, Any]) -> Optional[int]:
    created = int(position.get("created_at_ms") or 0)
    if created > 0:
        return created
    leg_opened = min((int(leg.get("opened_at_ms") or 0) for leg in position["legs"] if leg.get("opened_at_ms")), default=0)
    if leg_opened > 0:
        return leg_opened
    return _first_cashflow_ts(con, position["position_id"])


def _position_amount_usd(position: Dict[str, Any]) -> Optional[float]:
    meta = position.get("meta") or {}
    amt = _safe_float(meta.get("amount_usd"))
    if amt is not None and amt > 0:
        return amt

    gross = 0.0
    for leg in position.get("legs") or []:
        px = _safe_float(leg.get("current_price")) or _safe_float(leg.get("entry_price"))
        qty = _safe_float(leg.get("size"))
        if px is None or qty is None:
            continue
        gross += abs(px * qty)
    return gross or None


def _infer_product_types(position: Dict[str, Any]) -> Dict[str, str]:
    legs = position.get("legs") or []
    out: Dict[str, str] = {}

    if str(position.get("strategy") or "").upper() == "SPOT_PERP" and len(legs) == 2:
        for leg in legs:
            if leg.get("side") == "LONG":
                out[leg["leg_id"]] = "spot"
            elif leg.get("side") == "SHORT":
                out[leg["leg_id"]] = "perp"

    for leg in legs:
        if leg["leg_id"] in out:
            continue
        inst_id = str(leg.get("inst_id") or "")
        out[leg["leg_id"]] = "spot" if "/" in inst_id else "perp"

    return out


def _estimate_fees_from_notional(position: Dict[str, Any], amount_usd: float, *, is_open: bool) -> Optional[float]:
    legs = position.get("legs") or []
    if not legs or amount_usd <= 0:
        return None

    product_types = _infer_product_types(position)
    fee_model = CostModelV3()
    one_leg_notional = amount_usd / max(len(legs), 1)
    total = 0.0

    for leg in legs:
        venue = _effective_leg_venue(leg)
        product_type = product_types.get(leg["leg_id"], "perp")
        try:
            bps = fee_model.get_fee_bps(venue, product_type, is_maker=False)
        except KeyError:
            fallback_type = "perp" if product_type == "spot" else product_type
            bps = fee_model.get_fee_bps(venue, fallback_type, is_maker=False)
        total += one_leg_notional * bps / 10000.0

    return total


def _ledger_open_fees_usd(con: sqlite3.Connection, position_id: str, start_ms: Optional[int]) -> Optional[float]:
    if not start_ms:
        return None
    window_start = int(start_ms - 15 * 60 * 1000)
    window_end = int(start_ms + 12 * 3600 * 1000)
    row = con.execute(
        """
        SELECT SUM(ABS(amount))
        FROM pm_cashflows
        WHERE position_id = ?
          AND cf_type = 'FEE'
          AND ts >= ? AND ts <= ?
          AND UPPER(currency) IN ('USD','USDC','USDT')
        """,
        (position_id, window_start, window_end),
    ).fetchone()
    if not row or row[0] is None:
        return None
    val = float(row[0])
    return val if val > 0 else None


def resolve_open_fees_usd(con: sqlite3.Connection, position: Dict[str, Any], start_ms: Optional[int], amount_usd: Optional[float]) -> Optional[float]:
    ledger = _ledger_open_fees_usd(con, position["position_id"], start_ms)
    if ledger is not None:
        return ledger

    meta = position.get("meta") or {}
    explicit = _safe_float(meta.get("open_fees_usd"))
    if explicit is not None and explicit >= 0:
        return explicit

    if amount_usd is not None:
        return _estimate_fees_from_notional(position, amount_usd, is_open=True)
    return None


def _stable_sum(con: sqlite3.Connection, position_id: str, cf_type: str, since_ms: int, until_ms: int) -> float:
    row = con.execute(
        """
        SELECT SUM(amount)
        FROM pm_cashflows
        WHERE position_id = ?
          AND cf_type = ?
          AND ts >= ? AND ts <= ?
          AND UPPER(currency) IN ('USD','USDC','USDT')
        """,
        (position_id, cf_type, int(since_ms), int(until_ms)),
    ).fetchone()
    return float(row[0] or 0.0) if row else 0.0


def _window_funding_metrics(con: sqlite3.Connection, position_id: str, now_ms: int, start_ms: Optional[int] = None) -> Dict[str, float]:
    one_day = 24 * 3600 * 1000
    funding_1d = _stable_sum(con, position_id, "FUNDING", now_ms - one_day, now_ms)
    funding_2d = _stable_sum(con, position_id, "FUNDING", now_ms - 2 * one_day, now_ms)
    funding_3d = _stable_sum(con, position_id, "FUNDING", now_ms - 3 * one_day, now_ms)
    funding_15d = _stable_sum(con, position_id, "FUNDING", now_ms - 15 * one_day, now_ms)
    # Use min(days_open, 15) as denominator so new positions aren't diluted
    days_open = 15.0
    if start_ms is not None and start_ms > 0:
        days_open = max((now_ms - start_ms) / one_day, 0.1)  # floor at 0.1 to avoid div-by-zero
        days_open = min(days_open, 15.0)
    return {
        "funding_1d_usd": funding_1d,
        "funding_2d_usd": funding_2d,
        "funding_3d_usd": funding_3d,
        "avg_15d_funding_usd_per_day": funding_15d / days_open,
    }


def _breakeven_days(open_fees_usd: Optional[float], avg_daily_funding_usd: Optional[float]) -> Optional[float]:
    if open_fees_usd is None or avg_daily_funding_usd is None or avg_daily_funding_usd <= 0:
        return None
    return open_fees_usd / avg_daily_funding_usd


def _position_advisory(carry: Dict[str, Any], avg_15d_daily: Optional[float], funding_1d_usd: Optional[float]) -> Tuple[str, str]:
    apr_cur = _safe_float(carry.get("apr_cur"))
    apr14 = _safe_float(carry.get("apr_14d"))
    if carry.get("missing_funding_data"):
        return "INVESTIGATE", "missing funding data"
    if funding_1d_usd is not None and funding_1d_usd <= 0:
        return "EXIT", "last 1d funding <= 0"
    if avg_15d_daily is not None and avg_15d_daily <= 0:
        return "MONITOR", "15d funding avg not positive"
    if apr_cur is not None and apr_cur <= 0:
        return "EXIT", "APR latest <= 0"
    if apr14 is not None and apr14 <= APR14_MIN_THRESHOLD:
        return "MONITOR", "APR14 below threshold"
    if apr_cur is not None and apr14 is not None and apr_cur >= 30 and apr14 >= 30:
        return "INCREASE SIZE", "current and regime APR are strong"
    return "HOLD", "carry regime acceptable"


def build_position_rows(con: sqlite3.Connection, positions: List[Dict[str, Any]], carry_by: Dict[str, Dict[str, Any]], now_ms: int) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for position in positions:
        pid = position["position_id"]
        start_ms = _position_start_ms(con, position)
        amount_usd = _position_amount_usd(position)
        funding = _window_funding_metrics(con, pid, now_ms, start_ms)
        open_fees_usd = resolve_open_fees_usd(con, position, start_ms, amount_usd)
        carry = carry_by.get(pid) or {}
        advisory, reason = _position_advisory(
            carry,
            funding.get("avg_15d_funding_usd_per_day"),
            funding.get("funding_1d_usd"),
        )

        rows.append(
            {
                "position_id": pid,
                "ticker": position["base"],
                "perp_venue": _position_perp_venue(position),
                "amount_usd": amount_usd,
                "start_ms": start_ms,
                "start_time": _ms_to_utc(start_ms),
                "avg_15d_funding_usd_per_day": funding["avg_15d_funding_usd_per_day"],
                "funding_1d_usd": funding["funding_1d_usd"],
                "funding_2d_usd": funding["funding_2d_usd"],
                "funding_3d_usd": funding["funding_3d_usd"],
                "open_fees_usd": open_fees_usd,
                "breakeven_days": _breakeven_days(open_fees_usd, funding["avg_15d_funding_usd_per_day"]),
                "advisory": advisory,
                "reason": reason,
                "apr_latest": _safe_float(carry.get("apr_cur")),
                "apr_14d": _safe_float(carry.get("apr_14d")),
                "position": position,
            }
        )
    return rows


def load_rotation_candidates(
    csv_path: Path,
    *,
    held_symbols: List[str],
    top: int,
    oi_max: int,
    stale_warn_hours: float = 12.0,
) -> Tuple[List[CandidateRow], Dict[str, Any]]:
    now = _now_utc()
    cutoff_15d = now - timedelta(days=15)
    by_symbol: Dict[str, Dict[str, Any]] = {}
    latest_global: Optional[datetime] = None

    if not csv_path.exists():
        return [], {"latest_ts": None, "degraded": True, "reason": "missing loris csv"}

    with csv_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            exchange = str(row.get("exchange") or "").lower()
            if exchange not in SUPPORTED_REPORT_EXCHANGES:
                continue
            try:
                ts = datetime.fromisoformat(str(row.get("timestamp_utc") or "").replace("Z", "+00:00"))
            except Exception:
                continue
            if ts < cutoff_15d:
                continue
            symbol = normalize_symbol(row.get("symbol") or "")
            if not symbol:
                continue
            try:
                rate_8h = float(row.get("funding_8h_rate") or 0.0)
            except Exception:
                continue
            oi_rank = None
            try:
                raw_oi = row.get("oi_rank")
                oi_rank = int(raw_oi) if raw_oi not in ("", None) else None
            except Exception:
                oi_rank = None

            slot_key = candidate_identity(symbol, exchange)
            slot = by_symbol.setdefault(
                slot_key,
                {"symbol": symbol, "exchange": exchange, "samples": [], "latest_ts": ts, "latest_rate": rate_8h, "oi_rank": oi_rank},
            )
            slot["samples"].append((ts, rate_8h))
            if ts >= slot["latest_ts"]:
                slot["latest_ts"] = ts
                slot["latest_rate"] = rate_8h
                slot["oi_rank"] = oi_rank
            if latest_global is None or ts > latest_global:
                latest_global = ts

    ranked: List[CandidateRow] = []
    for (_symbol, _exchange), item in by_symbol.items():
        symbol = str(item["symbol"])
        exchange = str(item["exchange"])
        oi_rank = item.get("oi_rank")
        samples = sorted(item["samples"], key=lambda x: x[0])
        apr_latest = _rate_to_apr(item["latest_rate"])
        avg_1d, n1 = _avg_rate(samples, now - timedelta(days=1))
        avg_2d, n2 = _avg_rate(samples, now - timedelta(days=2))
        avg_3d, n3 = _avg_rate(samples, now - timedelta(days=3))
        avg_7d, n7 = _avg_rate(samples, now - timedelta(days=7))
        avg_14d, n14 = _avg_rate(samples, now - timedelta(days=14))
        avg_15d, _ = _avg_rate(samples, now - timedelta(days=15))

        apr_14d = _rate_to_apr(avg_14d)
        apr_7d = _rate_to_apr(avg_7d)
        apr_1d = _rate_to_apr(avg_1d)
        apr_2d = _rate_to_apr(avg_2d)
        apr_3d = _rate_to_apr(avg_3d)
        stability = None
        if apr_latest is not None and apr_7d is not None and apr_14d is not None:
            stability = 0.55 * apr_14d + 0.30 * apr_7d + 0.15 * apr_latest

        stale_hours = (now - item["latest_ts"]).total_seconds() / 3600.0
        flags: List[str] = []
        if stale_hours >= stale_warn_hours:
            flags.append(f"STALE_{stale_hours:.1f}H")
        if n14 < 16:
            flags.append("LOW_14D_SAMPLE")
        if n3 < 3:
            flags.append("LOW_3D_SAMPLE")
        if oi_rank is None:
            flags.append("NO_OI_RANK")

        ranked.append(
            CandidateRow(
                symbol=symbol,
                exchange=exchange,
                oi_rank=oi_rank,
                latest_ts=item["latest_ts"],
                apr_latest=apr_latest,
                apr_1d=apr_1d,
                apr_2d=apr_2d,
                apr_3d=apr_3d,
                apr_7d=apr_7d,
                apr_14d=apr_14d,
                avg_15d_rate_8h=avg_15d,
                stability_score=stability,
                flags=flags,
            )
        )

    ranked.sort(
        key=lambda row: (
            row.stability_score if row.stability_score is not None else float("-inf"),
            row.apr_14d if row.apr_14d is not None else float("-inf"),
            row.apr_7d if row.apr_7d is not None else float("-inf"),
            row.apr_latest if row.apr_latest is not None else float("-inf"),
            row.latest_ts,
        ),
        reverse=True,
    )

    held_symbol_set = {normalize_symbol(symbol) for symbol in held_symbols}
    best_by_candidate: Dict[tuple[str, str], CandidateRow] = {}
    for row in ranked:
        if normalize_symbol(row.symbol) in held_symbol_set:
            continue
        identity = candidate_identity(row.symbol, row.exchange)
        if identity not in best_by_candidate:
            best_by_candidate[identity] = row

    out = list(best_by_candidate.values())

    degraded = latest_global is None or ((now - latest_global).total_seconds() / 3600.0) >= stale_warn_hours
    meta = {
        "latest_ts": latest_global.isoformat() if latest_global else None,
        "degraded": degraded,
        "reason": "stale candidate funding" if degraded else None,
    }
    return out[:top], meta


def _candidate_daily_funding_usd(candidate: CandidateRow, amount_usd: float) -> Optional[float]:
    if candidate.avg_15d_rate_8h is None or amount_usd <= 0:
        return None
    perp_notional = amount_usd / 2.0
    return perp_notional * candidate.avg_15d_rate_8h * 3.0


def _find_position(position_rows: List[Dict[str, Any]], key: str) -> Optional[Dict[str, Any]]:
    key_up = key.upper()
    for row in position_rows:
        if row["position_id"].upper() == key_up or row["ticker"].upper() == key_up:
            return row
    return None


def build_rotation_analysis(position_rows: List[Dict[str, Any]], candidates: List[CandidateRow], rotate_from: str, rotate_to: str) -> Dict[str, Any]:
    current = _find_position(position_rows, rotate_from)
    if current is None:
        raise ValueError(f"rotation source not found: {rotate_from}")
    target = next((cand for cand in candidates if cand.symbol.upper() == rotate_to.upper()), None)
    if target is None:
        raise ValueError(f"rotation target not found in current candidate set: {rotate_to}")

    amount_usd = _safe_float(current.get("amount_usd"))
    if amount_usd is None or amount_usd <= 0:
        raise ValueError(f"amount_usd missing for position {current['position_id']}")

    close_fees = _estimate_fees_from_notional(current["position"], amount_usd, is_open=False)
    open_fees = _estimate_fees_from_notional(
        {
            "strategy": "SPOT_PERP",
            "legs": [
                {"leg_id": f"{target.symbol}_SPOT", "venue": "hyperliquid", "inst_id": target.symbol, "side": "LONG"},
                {"leg_id": f"{target.symbol}_PERP", "venue": target.exchange, "inst_id": target.symbol, "side": "SHORT"},
            ],
        },
        amount_usd,
        is_open=True,
    )
    expected_daily_funding = _candidate_daily_funding_usd(target, amount_usd)
    total_cost = (close_fees or 0.0) + (open_fees or 0.0)
    breakeven_days = None if expected_daily_funding is None or expected_daily_funding <= 0 else total_cost / expected_daily_funding

    return {
        "current_position_id": current["position_id"],
        "current_ticker": current["ticker"],
        "candidate_symbol": target.symbol,
        "amount_usd": amount_usd,
        "close_fees_usd": close_fees,
        "open_fees_usd": open_fees,
        "total_switch_cost_usd": total_cost,
        "expected_daily_funding_usd": expected_daily_funding,
        "switch_breakeven_days": breakeven_days,
        "candidate_apr_14d": target.apr_14d,
        "candidate_apr_7d": target.apr_7d,
        "candidate_apr_1d": target.apr_1d,
        "candidate_apr_2d": target.apr_2d,
        "candidate_apr_3d": target.apr_3d,
        "candidate_stability_score": target.stability_score,
    }


def format_rotation_analysis(analysis: Dict[str, Any]) -> str:
    lines = [
        "# Rotation Cost Analysis",
        f"From: {analysis['current_position_id']} ({analysis['current_ticker']})",
        f"To: {analysis['candidate_symbol']}",
        f"Amount ($): {_fmt_money(analysis['amount_usd'])}",
        f"Close Fees ($): {_fmt_money(analysis['close_fees_usd'])}",
        f"Open Fees ($): {_fmt_money(analysis['open_fees_usd'])}",
        f"Total Switch Cost ($): {_fmt_money(analysis['total_switch_cost_usd'])}",
        f"Expected Daily Funding ($): {_fmt_money(analysis['expected_daily_funding_usd'])}",
        f"Breakeven Time: {_fmt_days(analysis['switch_breakeven_days'])}",
        (
            f"Candidate Metrics: APR14 {_fmt_pct(analysis['candidate_apr_14d'])}"
            f" | APR7 {_fmt_pct(analysis['candidate_apr_7d'])}"
            f" | APR1d {_fmt_pct(analysis['candidate_apr_1d'])}"
            f" | APR2d {_fmt_pct(analysis['candidate_apr_2d'])}"
            f" | APR3d {_fmt_pct(analysis['candidate_apr_3d'])}"
            f" | Score {analysis['candidate_stability_score']:.2f}"
        ),
    ]
    return "\n".join(lines)


def render_daily_report(
    *,
    position_rows: List[Dict[str, Any]],
    candidates: List[CandidateRow],
    candidate_meta: Dict[str, Any],
    date_local: Optional[str],
    eq: Dict[str, float],
    eq_note: Dict[str, str],
) -> str:
    lines: List[str] = []
    workflow_state = "DEGRADED" if candidate_meta.get("degraded") else "NORMAL"
    lines.append("# 📊 Harmonix Daily Funding Report")
    lines.append(
        f"Snapshot: {_now_utc().strftime('%Y-%m-%d %H:%MZ')} | "
        f"Funding latest: {candidate_meta.get('latest_ts') or 'n/a'} | "
        f"State: {workflow_state}"
    )
    if candidate_meta.get("reason"):
        lines.append(f"Warning: {candidate_meta['reason']}")

    if date_local and eq:
        total = sum(eq.values())
        lines.append("")
        lines.append(f"## Account Equity (latest {date_local} local)")
        lines.append(f"Total tracked: {_fmt_money(total)}")
        for venue in sorted(eq.keys()):
            note = eq_note.get(venue) or ""
            tail = f" ({note})" if (note and note != "ok") else ""
            lines.append(f"- {venue}: {_fmt_money(eq.get(venue))}{tail}")

    lines.append("")
    lines.append("## Current Positions")
    if not position_rows:
        lines.append("- (no open positions tracked)")
    for row in position_rows:
        lines.append(
            f"- {row['ticker']} | venue {row['perp_venue']} | amount {_fmt_money(row['amount_usd'])} | start {row['start_time']} | "
            f"avg15d/day {_fmt_money(row['avg_15d_funding_usd_per_day'])} | "
            f"1d {_fmt_money(row['funding_1d_usd'])} | 2d {_fmt_money(row['funding_2d_usd'])} | 3d {_fmt_money(row['funding_3d_usd'])} | "
            f"open fees {_fmt_money(row['open_fees_usd'])} | BE {_fmt_days(row['breakeven_days'])} | "
            f"**{row['advisory']}** ({row['reason']})"
        )

    lines.append("")
    lines.append("## Top 5 Rotation Candidates")
    if not candidates:
        lines.append("- (none)")
    for idx, cand in enumerate(candidates, 1):
        note = ", ".join(cand.flags) if cand.flags else "ok"
        score = f"{cand.stability_score:.2f}" if cand.stability_score is not None else "n/a"
        lines.append(
            f"- #{idx} {cand.symbol} | venue {cand.exchange} | APR14 {_fmt_pct(cand.apr_14d)} | APR7 {_fmt_pct(cand.apr_7d)} | "
            f"APR1d {_fmt_pct(cand.apr_1d)} | APR2d {_fmt_pct(cand.apr_2d)} | APR3d {_fmt_pct(cand.apr_3d)} | "
            f"score {score} | {note}"
        )

    lines.append("")
    lines.append("## Rotation Cost Analysis")
    lines.append("- On demand only. Use `--rotate-from <position_id|ticker> --rotate-to <symbol>` to compute close/open/switch cost and breakeven.")

    return "\n".join(lines)


def _normalized_argv(argv: Optional[List[str]]) -> List[str]:
    return list(sys.argv[1:] if argv is None else argv)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    argv_list = _normalized_argv(argv)
    if "--equities" in argv_list:
        print("--equities is deprecated and unsupported", file=sys.stderr)
        raise SystemExit(1)
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)
    ap.add_argument("--section", choices=VALID_SECTIONS, default=None)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--oi-max", type=int, default=9999)
    ap.add_argument("--rotate-from", type=str, default=None)
    ap.add_argument("--rotate-to", type=str, default=None)
    args = ap.parse_args(argv_list)
    validate_args(args)
    return args


def validate_args(args: argparse.Namespace) -> None:
    if args.top < 1:
        raise SystemExit(1)
    if bool(args.rotate_from) != bool(args.rotate_to):
        raise SystemExit(1)
    if args.section and (args.rotate_from or args.rotate_to):
        raise SystemExit(1)
    if not args.section and not (args.rotate_from and args.rotate_to):
        raise SystemExit(1)


def _emit_portfolio_hard_fail(*, snapshot_ts: str | None, warning: str) -> int:
    emit_status(
        SectionStatus(
            section=SECTION_PORTFOLIO,
            state="HARD_FAIL",
            snapshot_ts=snapshot_ts,
            warnings=[warning],
            hard_fail=True,
        )
    )
    return 1


def run(args: argparse.Namespace) -> int:
    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")

    try:
        if args.section == SECTION_PORTFOLIO or not args.section:
            required_tables = ("pm_positions", "pm_legs", "pm_cashflows")
        else:
            required_tables = ("pm_positions",)
        missing_tables = [name for name in required_tables if not _table_exists(con, name)]
        if missing_tables:
            if args.section:
                emit_status(
                    SectionStatus(
                        section=args.section,
                        state="HARD_FAIL",
                        snapshot_ts=None,
                        warnings=[f"missing required tables: {', '.join(missing_tables)}"],
                        hard_fail=True,
                    )
                )
                return 1
            else:
                print(
                    "Missing required tables in DB: "
                    + ", ".join(missing_tables)
                    + f" | db={args.db}",
                    file=sys.stderr,
                )
                return 1

        if args.section == SECTION_PORTFOLIO:
            snapshot_ts = _now_utc().isoformat()
            try:
                _validate_required_schema(con)
                positions = _position_rows(con)
            except sqlite3.OperationalError as exc:
                return _emit_portfolio_hard_fail(
                    snapshot_ts=snapshot_ts,
                    warning=f"malformed required schema: {exc}",
                )
            warnings: List[str] = []
            try:
                carries = compute_all_carries(con, LORIS_CSV)
                carry_by = {row.get("position_id"): row for row in carries if row.get("position_id")}
            except sqlite3.OperationalError as exc:
                if _is_required_schema_error(exc):
                    return _emit_portfolio_hard_fail(
                        snapshot_ts=snapshot_ts,
                        warning=f"malformed required schema: {exc}",
                    )
                carry_by = {}
                warnings.append(f"carry inputs degraded: {exc}")
            except Exception as exc:
                carry_by = {}
                warnings.append(f"carry inputs degraded: {exc}")
            try:
                now_ms = int(_now_utc().timestamp() * 1000)
                position_rows = build_position_rows(con, positions, carry_by, now_ms)
            except sqlite3.OperationalError as exc:
                return _emit_portfolio_hard_fail(
                    snapshot_ts=snapshot_ts,
                    warning=f"malformed required schema: {exc}",
                )
            flagged_positions = build_flagged_positions(position_rows, warnings)
            section_text, status = render_portfolio_summary_section(
                position_rows=position_rows,
                flagged_positions=flagged_positions,
                snapshot_ts=snapshot_ts,
                warnings=warnings,
                fmt_money=_fmt_money,
                fmt_days=_fmt_days,
            )
            print(section_text)
            emit_status(status)
            return 0

        if args.section in {SECTION_ROTATION_GENERAL, SECTION_ROTATION_EQUITIES}:
            snapshot_ts = _now_utc().isoformat()
            try:
                held_symbols = _load_open_position_bases(con)
            except sqlite3.OperationalError as exc:
                emit_status(
                    SectionStatus(
                        section=args.section,
                        state="HARD_FAIL",
                        snapshot_ts=snapshot_ts,
                        warnings=[f"malformed required schema: {exc}"],
                        hard_fail=True,
                    )
                )
                return 1
            candidate_limit = max(args.top, 200)
            candidates, candidate_meta = load_rotation_candidates(
                LORIS_CSV,
                held_symbols=[],
                top=candidate_limit,
                oi_max=args.oi_max,
            )
            membership = load_felix_membership(FELIX_EQUITIES_CACHE, now=_now_utc())
            pool = build_candidate_pool(
                section=args.section,
                candidates=candidates,
                held_symbols=held_symbols,
                top=args.top,
                candidate_meta=candidate_meta,
                membership=membership,
            )
            section_text, status = render_rotation_section(
                section=args.section,
                ranked_rows=pool.ranked_rows,
                flagged_rows=pool.flagged_rows,
                top=args.top,
                status=pool.status,
                fmt_pct=_fmt_pct,
            )
            print(section_text)
            emit_status(status)
            return 0

        date_local, eq, eq_note = load_latest_equity_snapshot()
        positions = _position_rows(con)
        carries = compute_all_carries(con, LORIS_CSV)
        carry_by = {row.get("position_id"): row for row in carries if row.get("position_id")}
        now_ms = int(_now_utc().timestamp() * 1000)
        position_rows = build_position_rows(con, positions, carry_by, now_ms)
        held_symbols = [row["ticker"] for row in position_rows]

        candidate_limit = max(args.top, 200) if args.rotate_from and args.rotate_to else args.top
        candidates, candidate_meta = load_rotation_candidates(
            LORIS_CSV,
            held_symbols=held_symbols,
            top=candidate_limit,
            oi_max=args.oi_max,
        )

        if args.rotate_from and args.rotate_to:
            print(format_rotation_analysis(build_rotation_analysis(position_rows, candidates, args.rotate_from, args.rotate_to)))
            return 0

        print(
            render_daily_report(
                position_rows=position_rows,
                candidates=candidates[: args.top],
                candidate_meta=candidate_meta,
                date_local=date_local,
                eq=eq,
                eq_note=eq_note,
            )
        )
        return 0
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        con.close()


def main_for_test(argv: List[str]) -> int:
    return run(parse_args(argv))


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
