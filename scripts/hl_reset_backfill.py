#!/usr/bin/env python3
"""Standalone Hyperliquid FUNDING/FEE backfill for one-time DB reset.

This is NOT imported by pm_cashflows.py (cron). Only scripts/reset_hyperliquid_cashflows.py uses it.

Adds OPEN perp targets from pm_legs plus optional CLOSED legs listed in
config/hl_cashflow_backfill_extra_targets.json so historical funding (e.g. xyz:CRCL) can be
attributed when those positions are no longer open.
"""

from __future__ import annotations

import json
import os
import random
import sqlite3
import sys
import time
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent.parent

HYPERLIQUID_WINDOW_MS = 12 * 3600 * 1000
HYPERLIQUID_DEFAULT_SINCE_HOURS = 24 * 21
DEFAULT_CONFIG = ROOT / "config" / "hl_cashflow_backfill_extra_targets.json"

sys.path.insert(0, str(ROOT))

from tracking.connectors.hyperliquid_private import (  # noqa: E402
    DEFAULT_DEX as HYPERLIQUID_DEFAULT_DEX,
    namespaced_inst_id,
    post_info as hyperliquid_post_info,
    split_inst_id as split_hyperliquid_inst_id,
    strip_coin_namespace,
)
from tracking.position_manager.cashflows import CashflowEvent, insert_cashflow_events, now_ms  # noqa: E402

# Space out /info calls; HL returns 429 if we hammer many windows × dexes in a row.
_POST_MIN_INTERVAL_S = float(os.environ.get("HL_RESET_BACKFILL_MIN_INTERVAL_S", "0.35"))
_HL_POST_MAX_RETRIES = int(os.environ.get("HL_RESET_BACKFILL_MAX_RETRIES", "12"))
_last_hl_post_mono = 0.0


def _hl_throttle() -> None:
    global _last_hl_post_mono
    gap = time.monotonic() - _last_hl_post_mono
    if gap < _POST_MIN_INTERVAL_S:
        time.sleep(_POST_MIN_INTERVAL_S - gap)
    _last_hl_post_mono = time.monotonic()


def _hl_post(payload: Dict[str, Any], *, dex: str = HYPERLIQUID_DEFAULT_DEX, timeout: int = 30) -> Any:
    """POST /info with spacing + retry on HTTP 429 (rate limit)."""
    for attempt in range(_HL_POST_MAX_RETRIES):
        _hl_throttle()
        try:
            return hyperliquid_post_info(payload, dex=dex, timeout=timeout)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < _HL_POST_MAX_RETRIES - 1:
                ra = None
                try:
                    if e.headers:
                        ra = e.headers.get("Retry-After")
                except Exception:
                    pass
                if ra is not None:
                    try:
                        wait_s = float(ra) + random.uniform(0.2, 1.5)
                    except ValueError:
                        wait_s = min(120.0, (2**attempt) * 0.85 + random.uniform(0, 1.5))
                else:
                    wait_s = min(120.0, (2**attempt) * 0.85 + random.uniform(0, 1.5))
                time.sleep(wait_s)
                continue
            raise


def _iter_time_windows(start_ms: int, end_ms: int, *, window_ms: int = HYPERLIQUID_WINDOW_MS) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    cursor = int(start_ms)
    end_ms = int(end_ms)
    while cursor < end_ms:
        nxt = min(cursor + int(window_ms), end_ms)
        out.append((cursor, nxt))
        cursor = nxt
    return out


def _is_spot_inst_id(inst_id: str) -> bool:
    return "/" in str(inst_id or "")


def _hl_norm_dex(d: str) -> str:
    return str(d or "").strip().lower()


def _fmt_ms_utc(ms: int) -> str:
    import datetime as _dt

    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _hl_row_dex_from_coin(raw_coin: str) -> str:
    raw = str(raw_coin or "").strip()
    if ":" in raw:
        return raw.split(":", 1)[0].strip().lower()
    return ""


def _rows_to_targets(rows: List[Tuple[Any, ...]]) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    targets: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
    for strategy, position_id, leg_id, inst_id, side, account_id in rows:
        inst = str(inst_id or "")
        side_u = str(side or "").upper()
        acct = str(account_id or "")
        if _is_spot_inst_id(inst):
            continue
        if str(strategy or "").upper() == "SPOT_PERP" and side_u != "SHORT":
            continue
        dex, coin = split_hyperliquid_inst_id(inst)
        coin = strip_coin_namespace(coin)
        if not coin:
            continue
        targets.setdefault(acct, {}).setdefault(dex, {})[coin] = {
            "position_id": str(position_id),
            "leg_id": str(leg_id),
            "inst_id": namespaced_inst_id(dex=dex, coin=coin),
            "side": side_u,
        }
    return targets


def _load_open_targets(con: sqlite3.Connection) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    cur = con.execute(
        """
        SELECT p.strategy, l.position_id, l.leg_id, l.inst_id, l.side, l.account_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE l.venue='hyperliquid' AND l.status='OPEN' AND p.status='OPEN'
        """
    )
    return _rows_to_targets(cur.fetchall())


def _load_closed_targets_for_inst_ids(
    con: sqlite3.Connection, inst_ids: List[str]
) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    if not inst_ids:
        return {}
    ph = ",".join("?" for _ in inst_ids)
    cur = con.execute(
        f"""
        SELECT p.strategy, l.position_id, l.leg_id, l.inst_id, l.side, l.account_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE l.venue='hyperliquid' AND l.status='CLOSED' AND l.inst_id IN ({ph})
        ORDER BY l.leg_id DESC
        """,
        inst_ids,
    )
    return _rows_to_targets(cur.fetchall())


def _all_target_keys(t: Dict[str, Dict[str, Dict[str, Dict[str, str]]]]) -> Set[Tuple[str, str, str]]:
    keys: Set[Tuple[str, str, str]] = set()
    for acct, d1 in t.items():
        for dex, d2 in d1.items():
            for coin in d2:
                keys.add((acct, dex, coin))
    return keys


def _merge_targets(
    base: Dict[str, Dict[str, Dict[str, Dict[str, str]]]],
    extra: Dict[str, Dict[str, Dict[str, Dict[str, str]]]],
) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    out: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
    for acct, d1 in base.items():
        out[acct] = {}
        for dex, d2 in d1.items():
            out[acct][dex] = dict(d2)
    for acct, d1 in extra.items():
        for dex, d2 in d1.items():
            for coin, meta in d2.items():
                out.setdefault(acct, {}).setdefault(dex, {})
                if coin not in out[acct][dex]:
                    out[acct][dex][coin] = meta
    return out


def _optional_id(val: Any) -> str:
    if val is None or val == "":
        return ""
    return str(val)


def _manual_targets_from_config(entries: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    out: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
    for m in entries or []:
        inst = str(m.get("inst_id") or "").strip()
        acct = str(m.get("account_id") or "").strip()
        if not inst or not acct:
            continue
        if _is_spot_inst_id(inst):
            continue
        dex, coin = split_hyperliquid_inst_id(inst)
        coin = strip_coin_namespace(coin)
        if not coin:
            continue
        out.setdefault(acct, {}).setdefault(dex, {})[coin] = {
            "position_id": _optional_id(m.get("position_id")),
            "leg_id": _optional_id(m.get("leg_id")),
            "inst_id": namespaced_inst_id(dex=dex, coin=coin),
            "side": str(m.get("side") or "SHORT").upper(),
        }
    return out


def load_reset_targets_ex(
    con: sqlite3.Connection, *, config_path: Optional[Path] = None
) -> Tuple[Dict[str, Dict[str, Dict[str, Dict[str, str]]]], Dict[str, Any]]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG
    cfg: Dict[str, Any] = {}
    cfg_err: Optional[str] = None
    if path.exists():
        try:
            cfg = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            cfg = {}
            cfg_err = str(e)

    open_t = _load_open_targets(con)
    inst_ids = [str(x).strip() for x in (cfg.get("include_closed_inst_ids") or []) if str(x).strip()]
    closed_t = _load_closed_targets_for_inst_ids(con, inst_ids)
    merged_oc = _merge_targets(open_t, closed_t)
    manual = _manual_targets_from_config(list(cfg.get("manual_targets") or []))
    merged = _merge_targets(merged_oc, manual)

    open_keys = _all_target_keys(open_t)
    closed_keys = _all_target_keys(closed_t)
    manual_keys = _all_target_keys(manual)

    lines: List[str] = []
    for acct in sorted(merged.keys()):
        for dex in sorted(merged[acct].keys()):
            for coin in sorted(merged[acct][dex].keys()):
                key = (acct, dex, coin)
                if key in open_keys:
                    src = "OPEN"
                elif key in closed_keys:
                    src = "CLOSED"
                elif key in manual_keys:
                    src = "manual"
                else:
                    src = "?"
                meta = merged[acct][dex][coin]
                leg = meta.get("leg_id") or "(none)"
                lines.append(
                    f"  {src:6s}  account={acct}  dex={repr(dex):14s}  coin={coin:12s}  "
                    f"inst_id={meta.get('inst_id','')}  leg_id={leg}  pos={meta.get('position_id','')}"
                )

    report: Dict[str, Any] = {
        "config_path": str(path.resolve()),
        "config_exists": path.exists(),
        "config_parse_error": cfg_err,
        "include_closed_inst_ids": inst_ids,
        "manual_targets_count": len(cfg.get("manual_targets") or []),
        "n_keys_open": len(open_keys),
        "n_keys_closed_query": len(closed_keys),
        "n_keys_manual": len(manual_keys),
        "n_keys_merged": len(_all_target_keys(merged)),
        "target_lines": lines,
        "config_json_preview": {k: v for k, v in cfg.items() if k != "comment"},
    }
    return merged, report


def load_reset_targets(
    con: sqlite3.Connection, *, config_path: Optional[Path] = None
) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    t, _ = load_reset_targets_ex(con, config_path=config_path)
    return t


def parse_ts_to_ms(s: str) -> int:
    s = (s or "").strip()
    if not s:
        return now_ms()
    if s.isdigit():
        return int(s)
    import datetime as _dt

    iso = s.replace("Z", "+00:00")
    d = _dt.datetime.fromisoformat(iso)
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return int(d.timestamp() * 1000)


def run_backfill(
    con: sqlite3.Connection,
    *,
    since_hours: int = HYPERLIQUID_DEFAULT_SINCE_HOURS,
    start_ms: Optional[int] = None,
    end_ms: Optional[int] = None,
    verbose: bool = False,
    config_path: Optional[Path] = None,
) -> int:
    """Fetch HL userFunding + userFillsByTime and insert into pm_cashflows (deduped)."""
    targets_by_account, load_report = load_reset_targets_ex(con, config_path=config_path)
    if not targets_by_account:
        if verbose:
            print("[hl_reset_backfill] no targets (no OPEN legs and no extra config) — skipping.", file=sys.stderr)
        return 0

    if verbose:
        try:
            from tracking.connectors import hyperliquid_private as _hlp

            api_base = getattr(_hlp, "BASE_URL", "(unknown)")
        except Exception:
            api_base = "(unknown)"
        addr = (os.environ.get("HYPERLIQUID_ADDRESS") or "").strip()
        if len(addr) >= 14:
            addr_show = f"{addr[:10]}…{addr[-4:]}"
        else:
            addr_show = addr or "(HYPERLIQUID_ADDRESS unset — check .arbit_env)"
        print(
            "[hl_reset_backfill] — data sources —\n"
            f"  HL API: {api_base}\n"
            f"  Wallet (env): {addr_show}\n"
            f"  Config file: {load_report['config_path']} (exists={load_report['config_exists']})",
            file=sys.stderr,
        )
        if load_report.get("config_parse_error"):
            print(f"  Config JSON error: {load_report['config_parse_error']}", file=sys.stderr)
        print(
            f"  include_closed_inst_ids: {load_report['include_closed_inst_ids']}\n"
            f"  manual_targets entries: {load_report['manual_targets_count']}\n"
            f"  target key counts: OPEN={load_report['n_keys_open']}  "
            f"CLOSED(from DB)={load_report['n_keys_closed_query']}  "
            f"manual={load_report['n_keys_manual']}  merged={load_report['n_keys_merged']}\n"
            "  Per-slot attribution (what we map API rows onto):",
            file=sys.stderr,
        )
        for ln in load_report["target_lines"]:
            print(ln, file=sys.stderr)
        print("  — end target list —", file=sys.stderr)

    end = int(end_ms) if end_ms is not None else now_ms()
    if start_ms is not None:
        start = int(start_ms)
    else:
        start = end - int(since_hours) * 3600 * 1000
    if start >= end:
        if verbose:
            print(f"[hl_reset_backfill] empty window start={start} end={end}", file=sys.stderr)
        return 0

    events: List[CashflowEvent] = []
    windows = _iter_time_windows(start, end)

    st: Dict[str, Any] = {
        "fund_api_errors": 0,
        "fee_api_errors": 0,
        "fund_rows_raw": 0,
        "fund_rows_accepted": 0,
        "fund_skip_namespace": 0,
        "fund_skip_no_target": 0,
        "fund_skip_amount": 0,
        "fund_ts_raw_min": None,
        "fund_ts_raw_max": None,
        "fee_rows_raw": 0,
        "fee_rows_accepted": 0,
        "fee_skip_namespace": 0,
        "fee_skip_no_target": 0,
    }

    def _note_fund_ts(ts_ms: int) -> None:
        if st["fund_ts_raw_min"] is None or ts_ms < st["fund_ts_raw_min"]:
            st["fund_ts_raw_min"] = ts_ms
        if st["fund_ts_raw_max"] is None or ts_ms > st["fund_ts_raw_max"]:
            st["fund_ts_raw_max"] = ts_ms

    for account_id, targets_by_dex in targets_by_account.items():
        for dex, coin_targets in targets_by_dex.items():
            for win_start, win_end in windows:
                try:
                    rows = _hl_post(
                        {"type": "userFunding", "user": account_id, "startTime": int(win_start), "endTime": int(win_end)},
                        dex=dex,
                    )
                    if isinstance(rows, list):
                        for r in rows:
                            if not isinstance(r, dict):
                                continue
                            st["fund_rows_raw"] += 1
                            ts = r.get("time") or r.get("ts") or r.get("timestamp")
                            try:
                                ts_ms = int(ts)
                            except Exception:
                                continue
                            _note_fund_ts(ts_ms)

                            d = r.get("delta") if isinstance(r.get("delta"), dict) else None
                            raw_coin = ""
                            amt = None
                            if d is not None:
                                raw_coin = str(d.get("coin") or "")
                                amt = d.get("usdc")
                                if amt is None:
                                    amt = d.get("funding")
                            else:
                                raw_coin = str(r.get("coin") or "")
                                amt = r.get("funding") or r.get("usdc") or r.get("payment")

                            coin = strip_coin_namespace(raw_coin)
                            if _hl_norm_dex(dex) != _hl_row_dex_from_coin(raw_coin):
                                st["fund_skip_namespace"] += 1
                                continue
                            target = coin_targets.get(coin)
                            if target is None:
                                st["fund_skip_no_target"] += 1
                                continue
                            try:
                                amount = float(amt)
                            except Exception:
                                st["fund_skip_amount"] += 1
                                continue

                            st["fund_rows_accepted"] += 1
                            events.append(
                                CashflowEvent(
                                    venue="hyperliquid",
                                    account_id=str(account_id),
                                    ts=ts_ms,
                                    cf_type="FUNDING",
                                    amount=float(amount),
                                    currency="USDC",
                                    description=f"funding {target['inst_id']}",
                                    position_id=target["position_id"] or None,
                                    leg_id=target["leg_id"] or None,
                                    raw_json=r,
                                    meta={
                                        "coin": coin,
                                        "dex": dex or "",
                                        "inst_id": target["inst_id"],
                                        "pnl_sign": 1,
                                        "hl_reset_backfill": True,
                                    },
                                )
                            )
                except Exception as e:
                    st["fund_api_errors"] += 1
                    if verbose:
                        print(
                            f"[hl_reset_backfill] userFunding error dex={dex!r} acct={account_id[:12]}… "
                            f"win={win_start}-{win_end}: {e!r}",
                            file=sys.stderr,
                        )

                try:
                    fills = _hl_post(
                        {
                            "type": "userFillsByTime",
                            "user": account_id,
                            "startTime": int(win_start),
                            "endTime": int(win_end),
                            "aggregateByTime": False,
                        },
                        dex=dex,
                    )
                    if isinstance(fills, list):
                        for r in fills:
                            if not isinstance(r, dict):
                                continue
                            st["fee_rows_raw"] += 1
                            ts = r.get("time") or r.get("ts") or r.get("timestamp")
                            try:
                                ts_ms = int(ts)
                            except Exception:
                                continue
                            fee = r.get("fee")
                            try:
                                fee_f = float(fee)
                            except Exception:
                                continue
                            if fee_f == 0:
                                continue
                            raw_coin = str(r.get("coin") or r.get("asset") or "")
                            coin = strip_coin_namespace(raw_coin)
                            if _hl_norm_dex(dex) != _hl_row_dex_from_coin(raw_coin):
                                st["fee_skip_namespace"] += 1
                                continue
                            target = coin_targets.get(coin)
                            if target is None:
                                st["fee_skip_no_target"] += 1
                                continue
                            st["fee_rows_accepted"] += 1
                            events.append(
                                CashflowEvent(
                                    venue="hyperliquid",
                                    account_id=str(account_id),
                                    ts=ts_ms,
                                    cf_type="FEE",
                                    amount=float(-abs(fee_f)),
                                    currency="USDC",
                                    description=f"trade_fee {target['inst_id']}",
                                    position_id=target["position_id"] or None,
                                    leg_id=target["leg_id"] or None,
                                    raw_json=r,
                                    meta={"coin": coin, "dex": dex or "", "inst_id": target["inst_id"], "hl_reset_backfill": True},
                                )
                            )
                except Exception as e:
                    st["fee_api_errors"] += 1
                    if verbose:
                        print(
                            f"[hl_reset_backfill] userFillsByTime error dex={dex!r} acct={account_id[:12]}… "
                            f"win={win_start}-{win_end}: {e!r}",
                            file=sys.stderr,
                        )

    fund_sum = sum(e.amount for e in events if e.cf_type == "FUNDING")
    fee_sum = sum(e.amount for e in events if e.cf_type == "FEE")
    fund_ts_in = [e.ts for e in events if e.cf_type == "FUNDING"]

    if verbose:
        span_h = (end - start) / 3_600_000.0
        coins_by_acct = {a: sorted({c for _d, ct in td.items() for c in ct}) for a, td in targets_by_account.items()}
        print(
            "[hl_reset_backfill] — API pull summary —\n"
            f"  time window: start_ms={start} ({_fmt_ms_utc(start)})\n"
            f"               end_ms={end} ({_fmt_ms_utc(end)})\n"
            f"  span≈{span_h:.1f}h  12h windows={len(windows)}\n"
            f"  coins by account (for userFunding/userFills): {coins_by_acct}\n"
            f"  userFunding rows: raw_from_api={st['fund_rows_raw']}  accepted_to_events={st['fund_rows_accepted']}  "
            f"skip_namespace={st['fund_skip_namespace']}  skip_no_managed_coin={st['fund_skip_no_target']}  "
            f"skip_bad_amount={st['fund_skip_amount']}  api_errors={st['fund_api_errors']}\n"
            f"  earliest funding ts in API payloads: {st['fund_ts_raw_min']} "
            f"({_fmt_ms_utc(st['fund_ts_raw_min']) if st['fund_ts_raw_min'] else 'none'})\n"
            f"  userFills rows: raw_from_api={st['fee_rows_raw']}  accepted_to_events={st['fee_rows_accepted']}  "
            f"skip_namespace={st['fee_skip_namespace']}  skip_no_managed_coin={st['fee_skip_no_target']}  "
            f"api_errors={st['fee_api_errors']}\n"
            f"  events before insert: FUNDING={st['fund_rows_accepted']}  FEE={st['fee_rows_accepted']}  "
            f"sum(FUNDING usdc)={fund_sum:+.6f}  sum(FEE usdc)={fee_sum:+.6f}",
            file=sys.stderr,
        )
        if fund_ts_in:
            print(
                f"  min/max ts among FUNDING events queued: {min(fund_ts_in)} / {max(fund_ts_in)}  "
                f"({_fmt_ms_utc(min(fund_ts_in))} … {_fmt_ms_utc(max(fund_ts_in))})",
                file=sys.stderr,
            )

    n_ins = insert_cashflow_events(con, events)
    if verbose:
        print(
            f"[hl_reset_backfill] — sqlite —  insert new_rows={n_ins}  "
            f"events_built={len(events)}  (skipped by dedupe: {len(events) - n_ins})",
            file=sys.stderr,
        )
    return n_ins
