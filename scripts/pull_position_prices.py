#!/usr/bin/env python3
"""Pull prices for instruments with active position legs.

Fetches bid/ask/mid from Hyperliquid for all inst_ids in pm_legs
that belong to non-CLOSED positions. Handles three instrument types:

- Spot (HYPE/USDC): L2Book via @index from spotMeta
- Builder dex perp (xyz:GOLD): allMids with dex parameter (mid only)
- Native perp (HYPE): L2Book for bid/ask

Usage:
    source .arbit_env && .venv/bin/python scripts/pull_position_prices.py
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.hyperliquid_public import get_l2book
from tracking.connectors.hyperliquid_private import post_info, split_inst_id
from tracking.pipeline.spot_meta import fetch_spot_index_map
from tracking.writers.hyperliquid_v3_writer import (
    connect,
    ensure_position_instruments,
    insert_prices,
)

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def get_active_leg_inst_ids(con: sqlite3.Connection) -> List[str]:
    """Get distinct inst_ids from legs of non-CLOSED positions."""
    rows = con.execute("""
        SELECT DISTINCT l.inst_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.status != 'CLOSED'
    """).fetchall()
    return [r[0] for r in rows]


def classify_inst_id(inst_id: str) -> str:
    """Classify an inst_id: 'spot', 'builder_dex', or 'native_perp'."""
    if "/" in inst_id:
        return "spot"
    if ":" in inst_id:
        return "builder_dex"
    return "native_perp"


_API_DELAY = 0.3  # seconds between API calls to avoid 429


def fetch_spot_prices(
    spot_ids: List[str],
    spot_index_map: Dict[int, str],
) -> List[Dict]:
    """Fetch L2Book bid/ask for spot instruments using @index format."""
    # Build reverse map: pair_name -> universe_index
    reverse = {v: k for k, v in spot_index_map.items()}

    results = []
    for inst_id in spot_ids:
        idx = reverse.get(inst_id)
        if idx is None:
            print(f"  WARN: no spotMeta index for {inst_id}, skipping")
            continue

        time.sleep(_API_DELAY)
        book = get_l2book(f"@{idx}")
        if not book:
            print(f"  WARN: empty L2Book for {inst_id} (@{idx})")
            continue

        results.append({
            "inst_id": inst_id,
            "bid": book["bid"],
            "ask": book["ask"],
            "mid": book["mid"],
            "source": "l2book:spot",
        })
        print(f"  {inst_id}: bid={book['bid']:.4f} ask={book['ask']:.4f}")

    return results


def fetch_builder_dex_prices(dex_ids: List[str]) -> List[Dict]:
    """Fetch mid prices for builder dex perps via allMids with dex param."""
    # Group by dex name
    by_dex: Dict[str, List[str]] = {}
    for inst_id in dex_ids:
        dex, coin = split_inst_id(inst_id)
        by_dex.setdefault(dex, []).append((inst_id, coin))

    results = []
    for dex, pairs in by_dex.items():
        try:
            data = post_info({"type": "allMids"}, dex=dex)
        except Exception as e:
            print(f"  WARN: allMids failed for dex={dex}: {e}")
            continue

        if not isinstance(data, dict):
            continue

        time.sleep(_API_DELAY)

        for inst_id, coin in pairs:
            # allMids returns keys with dex prefix (e.g., "xyz:GOLD")
            # Try both prefixed and unprefixed
            mid_str = data.get(f"{dex}:{coin}") or data.get(coin)
            if mid_str is None:
                print(f"  WARN: no mid for {inst_id} in dex={dex}")
                continue

            mid = float(mid_str)
            results.append({
                "inst_id": inst_id,
                "mid": mid,
                "source": f"allMids:dex={dex}",
            })
            print(f"  {inst_id}: mid={mid:.4f}")

    return results


def fetch_native_perp_prices(perp_ids: List[str]) -> List[Dict]:
    """Fetch L2Book bid/ask for native perp instruments."""
    results = []
    for inst_id in perp_ids:
        time.sleep(_API_DELAY)
        book = get_l2book(inst_id)
        if not book:
            print(f"  WARN: empty L2Book for {inst_id}")
            continue

        results.append({
            "inst_id": inst_id,
            "bid": book["bid"],
            "ask": book["ask"],
            "mid": book["mid"],
            "source": "l2book:perp",
        })
        print(f"  {inst_id}: bid={book['bid']:.4f} ask={book['ask']:.4f}")

    return results


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Pull prices for position legs")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    if not args.db.exists():
        print(f"DB not found: {args.db}")
        return 1

    con = connect(args.db)
    ts = int(time.time() * 1000)

    # 1. Get active leg inst_ids
    inst_ids = get_active_leg_inst_ids(con)
    if not inst_ids:
        print("No active position legs found")
        con.close()
        return 0

    print(f"Active leg instruments: {len(inst_ids)}")

    # 2. Classify
    spot_ids = [i for i in inst_ids if classify_inst_id(i) == "spot"]
    dex_ids = [i for i in inst_ids if classify_inst_id(i) == "builder_dex"]
    perp_ids = [i for i in inst_ids if classify_inst_id(i) == "native_perp"]

    print(f"  Spot: {spot_ids}")
    print(f"  Builder dex: {dex_ids}")
    print(f"  Native perp: {perp_ids}")

    # 3. Fetch prices
    all_prices = []

    if spot_ids:
        print("\nFetching spot prices (L2Book)...")
        spot_cache = fetch_spot_index_map()
        all_prices.extend(fetch_spot_prices(spot_ids, spot_cache))

    if dex_ids:
        print("\nFetching builder dex prices (allMids)...")
        all_prices.extend(fetch_builder_dex_prices(dex_ids))

    if perp_ids:
        print("\nFetching native perp prices (L2Book)...")
        all_prices.extend(fetch_native_perp_prices(perp_ids))

    if not all_prices:
        print("\nNo prices fetched")
        con.close()
        return 0

    # 4. Ensure instrument rows exist (FK constraint)
    inst_rows = []
    for p in all_prices:
        iid = p["inst_id"]
        itype = classify_inst_id(iid)
        if itype == "spot":
            base = iid.split("/")[0]
            inst_rows.append({"inst_id": iid, "contract_type": "SPOT", "base": base, "quote": "USDC"})
        elif itype == "builder_dex":
            _, coin = split_inst_id(iid)
            inst_rows.append({"inst_id": iid, "contract_type": "PERP", "base": coin, "quote": "USD"})
        else:
            inst_rows.append({"inst_id": iid, "contract_type": "PERP", "base": iid, "quote": "USD"})

    ensure_position_instruments(con, inst_rows)

    # 5. Build price rows and insert
    price_rows = []
    for p in all_prices:
        price_rows.append({
            "instId": p["inst_id"],
            "ts": ts,
            "bid": p.get("bid"),
            "ask": p.get("ask"),
            "mid": p.get("mid"),
            "source": p.get("source", "position_prices"),
            "quality_flags": {} if p.get("bid") else {"no_bid_ask": True},
        })

    n = insert_prices(con, price_rows)
    con.commit()

    # Sync pm_legs.current_price from prices_v3 immediately so the API
    # reflects fresh prices without waiting for pipeline_hourly.py.
    from tracking.pipeline.price_utils import resolve_price
    legs = con.execute(
        "SELECT leg_id, venue, inst_id FROM pm_legs WHERE status = 'OPEN'"
    ).fetchall()
    synced = 0
    for leg_id, venue, inst_id in legs:
        row = resolve_price(con, venue, inst_id, leg_id=leg_id)
        if row is None:
            continue
        price = row.get("mid") or row.get("last") or row.get("bid") or row.get("ask")
        if price is None or row.get("ts", 0) == 0:
            continue
        con.execute("UPDATE pm_legs SET current_price = ? WHERE leg_id = ?", (price, leg_id))
        synced += 1
    con.commit()
    con.close()

    print(f"\nDone: {n} price rows inserted for {len(all_prices)} instruments, {synced} pm_legs prices synced")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
