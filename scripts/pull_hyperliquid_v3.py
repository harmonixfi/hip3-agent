#!/usr/bin/env python3
"""Pull Hyperliquid public data and write into DB v3.

Writes:
- instruments_v3 (perps)
- prices_v3 (mid/mark/last)
- funding_v3 (funding rates)

Minimal ingestion runner for V3-032.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors import hyperliquid_public
from tracking.writers.hyperliquid_v3_writer import connect, upsert_instruments, upsert_spot_instruments, insert_prices, insert_funding

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"
FELIX_HL_MARK_SOURCES = ROOT / "config" / "felix_hl_mark_sources.json"


def _felix_hyperliquid_inst_ids() -> set[str]:
    """inst_id values we must always have in instruments_v3/prices_v3 for Felix DN marks."""
    try:
        with open(FELIX_HL_MARK_SOURCES, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return set()
    out: set[str] = set()
    for v in data.values():
        if isinstance(v, dict) and v.get("venue") == "hyperliquid":
            iid = v.get("inst_id")
            if iid:
                out.add(str(iid))
    return out


def _log_felix_marks(
    felix_ids: set[str],
    price_rows: list[dict],
    mark_prices: dict,
    by_sym: dict[str, dict],
    ts_ms: int,
) -> None:
    """Stdout lines so you can confirm Felix hedge symbols got a sane HL mid."""
    if not felix_ids:
        return
    by_inst = {r["instId"]: r for r in price_rows}
    print(f"Felix HL marks (felix_hl_mark_sources.json)  ts_ms={ts_ms}")
    for iid in sorted(felix_ids):
        row = by_inst.get(iid)
        if row is not None and row.get("mid") is not None:
            print(f"  OK   {iid}  mid={row['mid']:.6g}  -> prices_v3")
        elif iid not in mark_prices:
            print(f"  WARN {iid}  not in allMids response — cannot price")
        elif iid not in by_sym:
            print(f"  WARN {iid}  not in perp meta universe — check symbol vs HL")
        else:
            print(f"  WARN {iid}  in meta+allMids but no price row (bug?)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument(
        "--inst-limit",
        type=int,
        default=50,
        help="Max perp instruments to upsert (0 = all). Felix-mapped HL symbols are always merged in.",
    )
    ap.add_argument("--funding-limit", type=int, default=50)
    args = ap.parse_args()

    ts = int(time.time() * 1000)
    felix_inst_ids = _felix_hyperliquid_inst_ids()

    # Get perp instruments
    all_insts = hyperliquid_public.get_instruments()
    # Limit to avoid timeout; 0 means no cap
    insts = all_insts[: args.inst_limit] if args.inst_limit > 0 else all_insts

    # HIP-3 perps (xyz:*) are merged via get_instruments(); still merge felix map in case of cap order
    # but Felix mark enrichment needs prices_v3 rows. Merge mapped symbols from full universe.
    by_sym = {i["symbol"]: i for i in all_insts}
    seen_syms = {i["symbol"] for i in insts}
    for sym in sorted(felix_inst_ids):
        if sym in seen_syms:
            continue
        extra = by_sym.get(sym)
        if extra:
            insts.append(extra)
            seen_syms.add(sym)

    # Get spot instruments
    spot_insts = hyperliquid_public.get_spot_instruments()

    # Get mark prices
    mark_prices = hyperliquid_public.get_mark_prices()

    # Get funding rates
    funding = hyperliquid_public.get_funding()

    # Prepare instrument rows
    inst_rows = []
    for inst in insts:
        inst_rows.append({
            "symbol": inst["symbol"],
            "szDecimals": inst.get("szDecimals", 3),
            "status": "OPEN",
        })

    # Prepare price rows
    price_rows = []
    for inst in insts:
        inst_id = inst["symbol"]
        if inst_id not in mark_prices:
            continue

        price_data = mark_prices[inst_id]
        mid = float(price_data.get("midPrice", 0.0)) if price_data.get("midPrice") else None

        price_rows.append({
            "instId": inst_id,
            "ts": ts,
            "mid": mid,
            "source": "hyperliquid:mark_price",
            "quality_flags": {"no_bid_ask": True},
        })

    # Prepare funding rows
    # Filter to only include instruments we're actually inserting
    inst_symbols = set(inst["symbol"] for inst in insts)

    funding_rows = []
    for inst_id, funding_rate in funding.items():
        if inst_id not in inst_symbols:
            continue

        funding_rows.append({
            "instId": inst_id,
            "ts": ts,
            "fundingRate": float(funding_rate),
            "interval_hours": 1,  # Hyperliquid funding is hourly
            "source": "hyperliquid:funding_rate",
            "quality_flags": {},
        })

    # Limit funding
    funding_rows = funding_rows[:args.funding_limit] if args.funding_limit > 0 else funding_rows

    # Prepare spot instrument rows
    spot_inst_rows = []
    for inst in spot_insts:
        spot_inst_rows.append({
            "symbol": inst["symbol"],
            "pair_name": inst.get("pair_name", ""),
            "quote": inst.get("quote", "USDC"),
            "szDecimals": inst.get("szDecimals", 0),
            "isCanonical": inst.get("isCanonical", False),
        })

    # Write to DB
    con = connect(args.db)
    try:
        n_inst = upsert_instruments(con, inst_rows)
        n_spot = upsert_spot_instruments(con, spot_inst_rows)
        n_price = insert_prices(con, price_rows)
        n_funding = insert_funding(con, funding_rows)
        con.commit()

        print(
            f"Hyperliquid v3: {n_inst} perp instruments, {n_spot} spot instruments, "
            f"{n_price} prices, {n_funding} funding records",
            flush=True,
        )
        _log_felix_marks(felix_inst_ids, price_rows, mark_prices, by_sym, ts)
        return 0
    except Exception as e:
        con.rollback()
        print(f"Error writing to DB: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
