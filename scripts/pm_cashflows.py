#!/usr/bin/env python3
"""Cashflow ledger CLI (pm_cashflows).

Commands:
- ingest: fetch funding/fees events and write into pm_cashflows
- report: rollup last 24h / 7d per position

This is deterministic (no LLM) and prints no secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
DB_DEFAULT = ROOT / "tracking" / "db" / "arbit_v3.db"
STATE_PATH = ROOT / "tracking" / "pm_cashflow_state.json"
HYPERLIQUID_WINDOW_MS = 12 * 3600 * 1000
HYPERLIQUID_DEFAULT_SINCE_HOURS = 24 * 21

import sys
sys.path.insert(0, str(ROOT))

from tracking.position_manager.cashflows import CashflowEvent, insert_cashflow_events, load_managed_leg_index, rollup, now_ms
from tracking.connectors.paradex_private import ParadexPrivateConnector
from tracking.connectors.ethereal_private import EtherealPrivateConnector
from tracking.connectors.hyperliquid_private import (
    DEFAULT_DEX as HYPERLIQUID_DEFAULT_DEX,
    HyperliquidPrivateConnector,
    namespaced_inst_id,
    post_info as hyperliquid_post_info,
    split_inst_id as split_hyperliquid_inst_id,
    strip_coin_namespace,
)
from tracking.connectors.lighter_private import LighterPrivateConnector
from tracking.pipeline.hl_cashflow_attribution import (
    hl_norm_dex as _hl_norm_dex,
    hl_resolve_fee_fill_target,
    hl_row_dex_from_coin as _hl_row_dex_from_coin,
)
from tracking.pipeline.spot_meta import fetch_spot_index_map

try:
    from tracking.connectors.okx_private import OKXPrivateConnector
except Exception:  # OKX creds may be absent
    OKXPrivateConnector = None  # type: ignore


def _load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"ethereal": {}}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"ethereal": {}}


def _save_state(st: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, indent=2, sort_keys=True), encoding="utf-8")


def ingest_paradex(con: sqlite3.Connection) -> int:
    """Ingest Paradex funding accrual using position fields.

    Important: Paradex "funding payments" history is tied to fills and can be sparse.
    For carry monitoring we instead track the delta of:
      total_funding_pnl = unrealized_funding_pnl + realized_positional_funding_pnl

    We store deltas as cf_type=FUNDING (USD).
    First observation of a position sets baseline (no event).
    """

    idx = load_managed_leg_index(con)

    # If no managed paradex legs, no-op
    cur = con.execute("SELECT 1 FROM pm_legs WHERE venue='paradex' AND status='OPEN' LIMIT 1")
    if cur.fetchone() is None:
        return 0

    st = _load_state()
    st.setdefault("paradex", {})

    c = ParadexPrivateConnector()
    acct = c.fetch_account_snapshot()
    account_id = acct.get("account_id") or ""

    positions = c.fetch_open_positions()

    events: List[CashflowEvent] = []

    for p in positions:
        raw = p.get("raw_json") or {}
        pos_id = str(raw.get("id") or "")
        market = str(raw.get("market") or p.get("inst_id") or "")
        side = str(raw.get("side") or p.get("side") or "").upper()

        if not pos_id or not market or side not in ("LONG", "SHORT"):
            continue

        try:
            uf = float(raw.get("unrealized_funding_pnl") or 0.0)
        except Exception:
            uf = 0.0
        try:
            rf = float(raw.get("realized_positional_funding_pnl") or 0.0)
        except Exception:
            rf = 0.0

        total = float(uf + rf)

        key = f"{account_id}:{pos_id}:{market}:{side}"
        last = st["paradex"].get(key)
        ts_ms = int(raw.get("last_updated_at") or raw.get("created_at") or now_ms())

        if last is None:
            st["paradex"][key] = {"total_funding_pnl": total, "ts": ts_ms}
            continue

        last_total = float((last or {}).get("total_funding_pnl") or 0.0)
        delta = total - last_total
        st["paradex"][key] = {"total_funding_pnl": total, "ts": ts_ms}

        if abs(delta) < 1e-12:
            continue

        position_id = None
        leg_id = None
        k = ("paradex", str(account_id), market, side)
        if k in idx:
            position_id, leg_id = idx[k]

        events.append(
            CashflowEvent(
                venue="paradex",
                account_id=str(account_id),
                ts=ts_ms,
                cf_type="FUNDING",
                amount=float(delta),
                currency="USD",
                description=f"funding_pnl_delta {market} ({side})",
                position_id=position_id,
                leg_id=leg_id,
                raw_json=raw,
                meta={"market": market, "side": side, "proxy": "funding_pnl_delta"},
            )
        )

    n = insert_cashflow_events(con, events)
    _save_state(st)
    return n


def ingest_ethereal(con: sqlite3.Connection) -> int:
    """Ethereal does not expose a clean funding payments feed in the current openapi.

    We approximate realized funding/fees as deltas of cumulative fields from /v1/position:
    - fundingUsd (cumulative)
    - feesAccruedUsd (cumulative)

    We store the deltas as FUNDING and FEE cashflow events.
    """
    idx = load_managed_leg_index(con)
    st = _load_state()
    st.setdefault("ethereal", {})

    c = EtherealPrivateConnector()
    account_id = c.sender

    positions = c.fetch_open_positions()

    events: List[CashflowEvent] = []

    for p in positions:
        raw = p.get("raw_json") or {}
        pos_id = str(raw.get("id") or "")
        sub = str(raw.get("subaccountId") or "")
        key = f"{sub}:{pos_id}" if (sub and pos_id) else p.get("leg_id")
        if not key:
            continue

        # cumulative fields
        fund_cum = raw.get("fundingUsd")
        fee_cum = raw.get("feesAccruedUsd")

        try:
            fund_cum_f = float(fund_cum) if fund_cum is not None else 0.0
        except Exception:
            fund_cum_f = 0.0

        try:
            fee_cum_f = float(fee_cum) if fee_cum is not None else 0.0
        except Exception:
            fee_cum_f = 0.0

        last = st["ethereal"].get(key) or {}
        last_fund = float(last.get("fundingUsd") or 0.0)
        last_fee = float(last.get("feesAccruedUsd") or 0.0)

        dfund = fund_cum_f - last_fund
        dfee = fee_cum_f - last_fee

        # Map to managed leg
        inst_id = str(p.get("inst_id") or "")
        side = str(p.get("side") or "").upper()
        position_id = None
        leg_id = None
        k = ("ethereal", str(account_id), inst_id, side)
        if k in idx:
            position_id, leg_id = idx[k]

        ts_ms = int(raw.get("updatedAt") or raw.get("updated_at") or now_ms())

        if abs(dfund) > 1e-12:
            # Ethereal UI shows Funding as negative of `fundingUsd` field.
            # Normalize to PnL-style cashflow: positive = credit, negative = cost.
            events.append(
                CashflowEvent(
                    venue="ethereal",
                    account_id=str(account_id),
                    ts=ts_ms,
                    cf_type="FUNDING",
                    amount=float(-dfund),
                    currency="USD",
                    description=f"fundingUsd delta (pnl_sign=-1) ({key})",
                    position_id=position_id,
                    leg_id=leg_id,
                    raw_json=raw,
                    meta={"inst_id": inst_id, "side": side, "pnl_sign": -1},
                )
            )

        if abs(dfee) > 1e-12:
            # fees are costs => store as negative
            events.append(
                CashflowEvent(
                    venue="ethereal",
                    account_id=str(account_id),
                    ts=ts_ms,
                    cf_type="FEE",
                    amount=float(-abs(dfee)),
                    currency="USD",
                    description=f"feesAccruedUsd delta ({key})",
                    position_id=position_id,
                    leg_id=leg_id,
                    raw_json=raw,
                    meta={"inst_id": inst_id, "side": side},
                )
            )

        # update state
        st["ethereal"][key] = {"fundingUsd": fund_cum_f, "feesAccruedUsd": fee_cum_f, "ts": ts_ms}

    n = insert_cashflow_events(con, events)
    _save_state(st)
    return n


def _hl_post(payload: Dict[str, Any], *, dex: str = HYPERLIQUID_DEFAULT_DEX, timeout: int = 30) -> Any:
    return hyperliquid_post_info(payload, dex=dex, timeout=timeout)


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


def _load_hyperliquid_targets(con: sqlite3.Connection) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    """Return account_id -> dex -> lookup_key -> target metadata for OPEN Hyperliquid legs.

    Funding ingests only perp keys (SHORT for SPOT_PERP). Fee ingests also spot keys for SPOT_PERP
    (LONG leg): lookup_key is the full spot ``inst_id`` (e.g. ``HYPE/USDC``) under native dex ``""``.
    """

    cur = con.execute(
        """
        SELECT p.strategy, l.position_id, l.leg_id, l.inst_id, l.side, l.account_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE l.venue='hyperliquid' AND l.status='OPEN' AND p.status='OPEN'
        """
    )
    targets: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
    for strategy, position_id, leg_id, inst_id, side, account_id in cur.fetchall():
        inst = str(inst_id or "")
        side_u = str(side or "").upper()
        acct = str(account_id or "")
        strat = str(strategy or "").upper()

        if strat == "SPOT_PERP":
            if _is_spot_inst_id(inst) and side_u == "LONG":
                targets.setdefault(acct, {}).setdefault("", {})[inst] = {
                    "position_id": str(position_id),
                    "leg_id": str(leg_id),
                    "inst_id": inst,
                    "side": side_u,
                }
            elif not _is_spot_inst_id(inst) and side_u == "SHORT":
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
            continue

        if _is_spot_inst_id(inst):
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


def ingest_hyperliquid(
    con: sqlite3.Connection,
    *,
    since_hours: int = HYPERLIQUID_DEFAULT_SINCE_HOURS,
    spot_index_map: Optional[Dict[int, str]] = None,
) -> int:
    """Ingest Hyperliquid realized funding + fees for OPEN managed legs.

    Funding attaches to perp legs only. Fees attach to perp legs and, for SPOT_PERP, to the spot leg
    (resolved via ``spotMeta`` index map, same as fill ingester).

    See ``scripts/hl_reset_backfill.py`` for one-time backfill including CLOSED instruments.
    """
    targets_by_account = _load_hyperliquid_targets(con)
    if not targets_by_account:
        return 0

    spot_map: Dict[int, str] = spot_index_map if spot_index_map is not None else fetch_spot_index_map()

    end_ms = now_ms()
    start_ms = end_ms - int(since_hours) * 3600 * 1000

    events: List[CashflowEvent] = []
    windows = _iter_time_windows(start_ms, end_ms)

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
                            ts = r.get("time") or r.get("ts") or r.get("timestamp")
                            try:
                                ts_ms = int(ts)
                            except Exception:
                                continue

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
                                continue
                            target = coin_targets.get(coin)
                            if target is None:
                                continue

                            try:
                                amount = float(amt)
                            except Exception:
                                continue

                            events.append(
                                CashflowEvent(
                                    venue="hyperliquid",
                                    account_id=str(account_id),
                                    ts=ts_ms,
                                    cf_type="FUNDING",
                                    amount=float(amount),
                                    currency="USDC",
                                    description=f"funding {target['inst_id']}",
                                    position_id=target["position_id"],
                                    leg_id=target["leg_id"],
                                    raw_json=r,
                                    meta={
                                        "coin": coin,
                                        "dex": dex or "",
                                        "inst_id": target["inst_id"],
                                        "pnl_sign": 1,
                                    },
                                )
                            )
                except Exception:
                    pass

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
                            target = hl_resolve_fee_fill_target(raw_coin, dex, coin_targets, spot_map)
                            if target is None:
                                continue

                            events.append(
                                CashflowEvent(
                                    venue="hyperliquid",
                                    account_id=str(account_id),
                                    ts=ts_ms,
                                    cf_type="FEE",
                                    amount=float(-abs(fee_f)),
                                    currency="USDC",
                                    description=f"trade_fee {target['inst_id']}",
                                    position_id=target["position_id"],
                                    leg_id=target["leg_id"],
                                    raw_json=r,
                                    meta={"coin": raw_coin, "dex": dex or "", "inst_id": target["inst_id"]},
                                )
                            )
                except Exception:
                    pass

    return insert_cashflow_events(con, events)


def ingest_lighter(con: sqlite3.Connection) -> int:
    """Ingest Lighter realized PnL deltas as a proxy cashflow.

    Lighter's public account payload includes `realized_pnl` per perp position,
    but does not break out funding vs fees. We ingest deltas as cf_type=OTHER.

    Important: on first observation of a leg, we only set the baseline (no event)
    to avoid a huge 'catch-up' delta.
    """

    idx = load_managed_leg_index(con)
    st = _load_state()
    st.setdefault("lighter", {})

    c = LighterPrivateConnector()
    account_id = c.l1_address

    positions = c.fetch_open_positions()

    events: List[CashflowEvent] = []
    for p in positions:
        inst_id = str(p.get("inst_id") or "")
        if not inst_id or "/" in inst_id:
            continue  # spot legs ignored

        side = str(p.get("side") or "").upper()
        raw = p.get("raw_json") or {}
        rp = raw.get("realized_pnl")
        try:
            rp_f = float(rp)
        except Exception:
            continue

        leg_key = str(p.get("leg_id") or f"{account_id}:{inst_id}:{side}")
        last = st["lighter"].get(leg_key)
        ts_ms = int(time.time() * 1000)

        if last is None:
            st["lighter"][leg_key] = {"realized_pnl": rp_f, "ts": ts_ms}
            continue

        last_rp = float((last or {}).get("realized_pnl") or 0.0)
        delta = rp_f - last_rp
        st["lighter"][leg_key] = {"realized_pnl": rp_f, "ts": ts_ms}

        if abs(delta) < 1e-12:
            continue

        position_id = None
        leg_id = None
        k = ("lighter", str(account_id), inst_id, side)
        if k in idx:
            position_id, leg_id = idx[k]

        events.append(
            CashflowEvent(
                venue="lighter",
                account_id=str(account_id),
                ts=ts_ms,
                cf_type="OTHER",
                amount=float(delta),
                currency="USDC",
                description=f"realized_pnl delta (proxy, includes funding/fees?) {inst_id}",
                position_id=position_id,
                leg_id=leg_id,
                raw_json=raw,
                meta={"inst_id": inst_id, "side": side, "proxy": True},
            )
        )

    n = insert_cashflow_events(con, events)
    _save_state(st)
    return n


def ingest_okx(con: sqlite3.Connection, *, since_hours: int = 24 * 7) -> int:
    """Ingest OKX realized funding (and optionally fees) from account bills.

    Requires OKX_API_KEY/SECRET/PASSPHRASE. If not configured, we skip silently.
    """

    if OKXPrivateConnector is None:
        return 0

    # Check env without printing secrets
    import os

    if not (os.environ.get("OKX_API_KEY") and os.environ.get("OKX_API_SECRET") and os.environ.get("OKX_API_PASSPHRASE")):
        return 0

    idx = load_managed_leg_index(con)

    cur = con.execute("SELECT 1 FROM pm_legs WHERE venue='okx' AND status='OPEN' LIMIT 1")
    if cur.fetchone() is None:
        return 0

    c = OKXPrivateConnector()
    account_id = "okx"

    end_ms = now_ms()
    start_ms = end_ms - int(since_hours) * 3600 * 1000

    events: List[CashflowEvent] = []

    # Funding fee bills (type=8)
    try:
        bills = c.fetch_bills(bill_type="8", begin_ms=start_ms, end_ms=end_ms, limit=100)
    except Exception:
        bills = []

    for r in bills:
        ts = r.get("ts")
        try:
            ts_ms = int(ts)
        except Exception:
            continue

        inst_id = str(r.get("instId") or "")
        ccy = str(r.get("ccy") or "USDT")

        # For funding fee, OKX suggests using `pnl`.
        amt = r.get("pnl")
        if amt is None:
            amt = r.get("balChg")
        try:
            amount = float(amt)
        except Exception:
            continue

        sub_type = str(r.get("subType") or "")
        desc = f"okx funding bill inst={inst_id} subType={sub_type}".strip()

        position_id = None
        leg_id = None
        for side in ("LONG", "SHORT"):
            k = ("okx", str(account_id), inst_id, side)
            if k in idx:
                position_id, leg_id = idx[k]
                break

        events.append(
            CashflowEvent(
                venue="okx",
                account_id=account_id,
                ts=ts_ms,
                cf_type="FUNDING",
                amount=float(amount),
                currency=ccy,
                description=desc,
                position_id=position_id,
                leg_id=leg_id,
                raw_json=r,
                meta={"inst_id": inst_id, "subType": sub_type, "type": "8"},
            )
        )

    return insert_cashflow_events(con, events)


def _ingest_try(label: str, fn, *args, **kwargs) -> int:
    """Run one venue ingest; on failure log to stderr and return 0 so other venues still run."""
    try:
        return int(fn(*args, **kwargs) or 0)
    except Exception as e:
        print(f"[pm_cashflows] WARN: {label} ingest failed ({type(e).__name__}): {e}", file=sys.stderr)
        return 0


def cmd_ingest(args) -> int:
    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        n = 0
        venues = [v.strip().lower() for v in args.venues.split(",") if v.strip()]
        if "paradex" in venues:
            n += _ingest_try("paradex", ingest_paradex, con)
        if "ethereal" in venues:
            n += _ingest_try("ethereal", ingest_ethereal, con)
        if "hyperliquid" in venues:
            n += _ingest_try("hyperliquid", ingest_hyperliquid, con, since_hours=int(args.since_hours))
        if "lighter" in venues:
            n += _ingest_try("lighter", ingest_lighter, con)
        if "okx" in venues:
            n += _ingest_try("okx", ingest_okx, con, since_hours=int(args.since_hours))
        print(f"OK: inserted {n} cashflow events")
        return 0
    finally:
        con.close()


def _fmt_usd(x: float) -> str:
    return f"{x:+.2f}"


def cmd_report(args) -> int:
    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        now = now_ms()
        r24 = rollup(con, now - 24 * 3600 * 1000)
        r7d = rollup(con, now - 7 * 24 * 3600 * 1000)

        if args.json:
            print(json.dumps({"last_24h": r24, "last_7d": r7d}, indent=2, sort_keys=True))
            return 0

        print("== Cashflow rollup (last 24h) ==")
        if not r24:
            print("(none)")
        for row in r24:
            print(f"{row['position_id']:45s} {row['cf_type']:8s} {row['currency']:4s} total={_fmt_usd(row['total'])} n={row['n']}")

        print("\n== Cashflow rollup (last 7d) ==")
        if not r7d:
            print("(none)")
        for row in r7d:
            print(f"{row['position_id']:45s} {row['cf_type']:8s} {row['currency']:4s} total={_fmt_usd(row['total'])} n={row['n']}")

        return 0
    finally:
        con.close()


def _parse_ts_to_ms(s: str) -> int:
    s = (s or "").strip()
    if not s:
        return now_ms()
    # accept ms epoch
    if s.isdigit():
        return int(s)
    # accept ISO like 2026-02-11T10:00:00Z
    import datetime as _dt

    iso = s.replace("Z", "+00:00")
    d = _dt.datetime.fromisoformat(iso)
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return int(d.timestamp() * 1000)


def _default_account_id_for(venue: str) -> str:
    v = (venue or "").lower().strip()
    if v == "paradex":
        return (os.environ.get("PARADEX_ACCOUNT_ADDRESS") or os.environ.get("PARADEX_ACCOUNT_ID") or "paradex").strip()
    if v == "hyperliquid":
        return (os.environ.get("HYPERLIQUID_ADDRESS") or "hyperliquid").strip()
    if v == "hyena":
        return (os.environ.get("HYENA_ADDRESS") or "hyena").strip()
    if v == "lighter":
        return (os.environ.get("LIGHTER_L1_ADDRESS") or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS") or "lighter").strip()
    if v == "ethereal":
        return (os.environ.get("ETHEREAL_ACCOUNT_ADDRESS") or "ethereal").strip()
    if v == "okx":
        return "okx"
    return v or "unknown"


def cmd_manual(args) -> int:
    """Insert a manual DEPOSIT/WITHDRAW/TRANSFER cashflow row."""
    venue = args.venue.lower().strip()
    cf_type = args.type.upper().strip()
    amount = float(args.amount)

    # enforce sign convention: amount positive input
    if cf_type == "DEPOSIT":
        signed = abs(amount)
    elif cf_type == "WITHDRAW":
        signed = -abs(amount)
    elif cf_type == "TRANSFER":
        # TRANSFER can be either direction; require signed amount
        signed = float(amount)
    else:
        raise SystemExit("type must be DEPOSIT|WITHDRAW|TRANSFER")

    ts_ms = _parse_ts_to_ms(args.ts) if args.ts else now_ms()
    account_id = (args.account_id or _default_account_id_for(venue)).strip() or "unknown"

    ev = CashflowEvent(
        venue=venue,
        account_id=account_id,
        ts=int(ts_ms),
        cf_type=cf_type,
        amount=float(signed),
        currency=str(args.currency).upper(),
        description=str(args.desc or "manual cashflow").strip(),
        position_id=None,
        leg_id=None,
        raw_json=None,
        meta={"manual": True},
    )

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")
    try:
        n = insert_cashflow_events(con, [ev])
        print(f"OK: inserted {n} manual cashflow event ({cf_type} {signed:+.2f} {ev.currency}) venue={venue}")
        return 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)

    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_i = sub.add_parser("ingest")
    sp_i.add_argument(
        "--venues",
        type=str,
        default="paradex,ethereal,hyperliquid",
        help="Comma-separated: paradex, ethereal, hyperliquid, lighter, okx. "
        "Failures in one venue are logged and skipped so others still run.",
    )
    sp_i.add_argument("--since-hours", type=int, default=HYPERLIQUID_DEFAULT_SINCE_HOURS)

    sp_r = sub.add_parser("report")
    sp_r.add_argument("--json", action="store_true")

    sp_m = sub.add_parser("manual", help="Insert manual deposit/withdraw/transfer cashflow")
    sp_m.add_argument("--venue", required=True, type=str)
    sp_m.add_argument("--type", required=True, type=str, choices=["DEPOSIT", "WITHDRAW", "TRANSFER"])
    sp_m.add_argument("--amount", required=True, type=float, help="Positive amount; sign will be applied by type (TRANSFER can be signed)")
    sp_m.add_argument("--currency", type=str, default="USDC")
    sp_m.add_argument("--ts", type=str, default=None, help="UTC ISO (2026-02-11T10:00:00Z) or epoch ms")
    sp_m.add_argument("--account-id", type=str, default=None)
    sp_m.add_argument("--desc", type=str, default="")

    args = ap.parse_args()

    if args.cmd == "ingest":
        return cmd_ingest(args)
    if args.cmd == "report":
        return cmd_report(args)
    if args.cmd == "manual":
        return cmd_manual(args)

    raise SystemExit("unknown cmd")


if __name__ == "__main__":
    raise SystemExit(main())
