#!/usr/bin/env python3
"""Hyperliquid API data fetcher — spot/perp metadata, L2 books, funding rates.

API: POST https://api.hyperliquid.xyz/info — no auth, stdlib only.

Commands:
    --spot-meta [--filter TEXT]             List spot pairs
    --perp-meta [--filter TEXT] [--min-vol N] [--top N]
                                            Perps with funding APR, OI, volume
    --book COIN [--levels N]                L2 order book analysis
    --funding SYMBOL                        Funding rate for one perp
    --spot-volume [--min-vol N] [--top N]   Top spot pairs by 24h volume
    --usdt0                                 USDT0/USDC swap analysis
    --open-orders ADDRESS [--filter SYM]    Open orders for a wallet

Notes:
    - Spot coin format for --book: @N (index from spotMeta)
    - Perp coin format for --book: symbol directly (BNB, HYPE, BTC…)
    - Funding rate from API is per-hour. APR = rate × 8760 × 100
    - USDT0/USDC spot index discovered at runtime from spotMeta
"""

import json
import sys
import argparse
import urllib.request
import urllib.error
from typing import Optional
from datetime import datetime, timezone

HL_URL = "https://api.hyperliquid.xyz/info"

# ── HTTP client ────────────────────────────────────────────────────────────────

def hl_post(payload: dict):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        HL_URL, data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    last_err = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as e:
            last_err = e
    raise RuntimeError(f"Hyperliquid API request failed: {last_err}") from last_err


# ── formatters ─────────────────────────────────────────────────────────────────

def fmt_usd(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{sign}${abs_v/1e9:.2f}B"
    if abs_v >= 1_000_000:
        return f"{sign}${abs_v/1e6:.2f}M"
    if abs_v >= 1_000:
        return f"{sign}${abs_v/1e3:.1f}K"
    return f"{sign}${abs_v:.2f}"

def fmt_num(v: Optional[float], decimals: int = 6) -> str:
    if v is None:
        return "N/A"
    abs_v = abs(v)
    sign = "-" if v < 0 else ""
    if abs_v >= 1_000_000_000:
        return f"{sign}{abs_v/1e9:.3f}B"
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v/1e6:.3f}M"
    if abs_v >= 1_000:
        return f"{sign}{abs_v/1e3:.2f}K"
    return f"{sign}{abs_v:.{decimals}g}"

def fmt_pct(v: Optional[float], plus: bool = True, decimals: int = 4) -> str:
    if v is None:
        return "N/A"
    sign = "+" if plus and v >= 0 else ""
    return f"{sign}{v:.{decimals}f}%"

def fmt_bps(v: Optional[float]) -> str:
    if v is None:
        return "N/A"
    return f"{v:.2f}bps"


# ── spotMeta helpers ───────────────────────────────────────────────────────────

def _build_spot_index(spot_meta: dict) -> tuple:
    """Return (tok_by_idx, pairs_by_name)."""
    tok_by_idx = {t["index"]: t for t in spot_meta["tokens"]}
    pairs_by_name = {u["name"]: u for u in spot_meta["universe"]}
    return tok_by_idx, pairs_by_name

def _pair_token_names(pair: dict, tok_by_idx: dict) -> tuple:
    base_idx = pair["tokens"][0]
    quote_idx = pair["tokens"][1]
    base = tok_by_idx.get(base_idx, {}).get("name", f"?{base_idx}")
    quote = tok_by_idx.get(quote_idx, {}).get("name", f"?{quote_idx}")
    return base, quote

def _find_pair_index(spot_meta: dict, base_name: str, quote_name: str) -> Optional[int]:
    tok_by_idx = {t["index"]: t["name"] for t in spot_meta["tokens"]}
    for u in spot_meta["universe"]:
        names = {tok_by_idx.get(t, "") for t in u["tokens"]}
        if names == {base_name, quote_name}:
            return u["index"]
    return None

def _pct_change(prev: float, curr: float) -> Optional[float]:
    if not prev:
        return None
    return (curr - prev) / prev * 100


# ── L2 book analysis ───────────────────────────────────────────────────────────

def _depth_usd(levels: list, n: int = 10) -> float:
    total = 0.0
    for lvl in levels[:n]:
        total += float(lvl["px"]) * float(lvl["sz"])
    return total

def _walk_book(levels: list, target_usd: float) -> dict:
    """Fill target_usd notional against the book. Returns avg_px, slippage_bps."""
    remaining = target_usd
    cost = 0.0
    base = 0.0
    for lvl in levels:
        px = float(lvl["px"])
        sz = float(lvl["sz"])
        level_usd = px * sz
        if remaining <= level_usd:
            fill = remaining / px
            cost += remaining
            base += fill
            remaining = 0.0
            break
        cost += level_usd
        base += sz
        remaining -= level_usd
    if base == 0 or remaining > 0:
        return {"avg_px": None, "slippage_bps": None, "filled_usd": target_usd - remaining}
    avg_px = cost / base
    best_px = float(levels[0]["px"])
    slippage = abs(avg_px - best_px) / best_px * 10_000
    return {"avg_px": avg_px, "slippage_bps": slippage, "filled_usd": target_usd}

def _divider(n: int) -> None:
    print("─" * n)


# ── commands ───────────────────────────────────────────────────────────────────

def cmd_spot_meta(filter_text: Optional[str] = None, json_out: bool = False) -> None:
    data = hl_post({"type": "spotMeta"})
    tok_by_idx, _ = _build_spot_index(data)

    rows = []
    for u in data["universe"]:
        base, quote = _pair_token_names(u, tok_by_idx)
        name = u["name"]
        if filter_text and filter_text.upper() not in f"{name} {base} {quote}".upper():
            continue
        rows.append({
            "index": u["index"],
            "coin": f"@{u['index']}",
            "name": name,
            "base": base,
            "quote": quote,
            "canonical": u["isCanonical"],
        })

    if json_out:
        print(json.dumps(rows, indent=2))
        return

    print(f"\n=== Spot Pairs ({len(rows)} shown) ===")
    hdr = f"{'Idx':>5}  {'Coin':<8}  {'Name':<16}  {'Base':<12}  {'Quote':<8}  Canon"
    print(hdr)
    _divider(len(hdr))
    for r in rows:
        print(f"{r['index']:>5}  {r['coin']:<8}  {r['name']:<16}  {r['base']:<12}  {r['quote']:<8}  {'✓' if r['canonical'] else ''}")


def cmd_perp_meta(filter_text: Optional[str] = None, min_vol: float = 0,
                  top: int = 50, json_out: bool = False) -> None:
    raw = hl_post({"type": "metaAndAssetCtxs"})
    universe = raw[0]["universe"]
    ctxs = raw[1]

    rows = []
    for u, ctx in zip(universe, ctxs):
        symbol = u["name"]
        if filter_text and filter_text.upper() not in symbol.upper():
            continue
        mark = float(ctx.get("markPx") or 0)
        oi_base = float(ctx.get("openInterest") or 0)
        vol = float(ctx.get("dayNtlVlm") or 0)
        if vol < min_vol:
            continue
        funding = float(ctx.get("funding") or 0)
        prev = float(ctx.get("prevDayPx") or mark)
        rows.append({
            "symbol": symbol,
            "mark_px": mark,
            "day_vol_usd": vol,
            "oi_usd": oi_base * mark,
            "funding_hr_pct": funding * 100,
            "funding_apr_pct": funding * 8760 * 100,
            "day_chg_pct": _pct_change(prev, mark),
        })

    rows.sort(key=lambda r: abs(r["funding_apr_pct"]), reverse=True)
    rows = rows[:top]

    if json_out:
        print(json.dumps(rows, indent=2))
        return

    sort_note = "sorted by |Funding APR|"
    if filter_text:
        sort_note += f", filter='{filter_text}'"
    print(f"\n=== Perp Markets ({len(rows)} shown, {sort_note}) ===")
    hdr = f"{'Symbol':<10} {'Mark Px':>12} {'24h Vol':>12} {'OI USD':>12} {'Fund/hr':>10} {'APR':>10} {'24h%':>8}"
    print(hdr)
    _divider(len(hdr))
    for r in rows:
        print(
            f"{r['symbol']:<10}"
            f" {fmt_num(r['mark_px']):>12}"
            f" {fmt_usd(r['day_vol_usd']):>12}"
            f" {fmt_usd(r['oi_usd']):>12}"
            f" {fmt_pct(r['funding_hr_pct'], decimals=6):>10}"
            f" {fmt_pct(r['funding_apr_pct'], decimals=2):>10}"
            f" {fmt_pct(r['day_chg_pct'], decimals=2):>8}"
        )


def cmd_book(coin: str, levels: int = 10, sizes: Optional[list] = None,
             json_out: bool = False) -> None:
    if sizes is None:
        sizes = [5_000, 10_000, 25_000]

    data = hl_post({"type": "l2Book", "coin": coin})
    bids = data["levels"][0]
    asks = data["levels"][1]

    if not bids or not asks:
        print(f"No order book data for {coin}")
        return

    best_bid = float(bids[0]["px"])
    best_ask = float(asks[0]["px"])
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10_000

    bid_depth = _depth_usd(bids, levels)
    ask_depth = _depth_usd(asks, levels)

    slippage_rows = []
    for size in sizes:
        buy = _walk_book(asks, size)
        sell = _walk_book(bids, size)
        slippage_rows.append({
            "size": size,
            "buy_bps": buy["slippage_bps"],
            "sell_bps": sell["slippage_bps"],
        })

    if json_out:
        out = {
            "coin": coin,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
            "spread_bps": spread_bps,
            "bid_depth_usd": bid_depth,
            "ask_depth_usd": ask_depth,
            "slippage": slippage_rows,
            "bids": bids[:levels],
            "asks": asks[:levels],
        }
        print(json.dumps(out, indent=2))
        return

    print(f"\n=== L2 Book: {coin} ===")
    print(f"Best Bid:  {best_bid:>14.8g}    Best Ask:  {best_ask:>14.8g}")
    print(f"Mid:       {mid:>14.8g}    Spread:    {spread_bps:.2f} bps")
    print(f"Bid Depth ({levels}L): {fmt_usd(bid_depth):>10}    Ask Depth ({levels}L): {fmt_usd(ask_depth):>10}")

    print(f"\n{'Bid Size':>14}  {'Bid Px':>12}  |  {'Ask Px':>12}  {'Ask Size':<14}")
    _divider(60)
    n = min(levels, len(bids), len(asks))
    for i in range(n):
        b, a = bids[i], asks[i]
        print(f"{float(b['sz']):>14.4f}  {float(b['px']):>12.8g}  |  {float(a['px']):>12.8g}  {float(a['sz']):<14.4f}")

    print(f"\n{'Size':>10}  {'Buy Slip':>12}  {'Sell Slip':>12}")
    _divider(38)
    for s in slippage_rows:
        buy_s = fmt_bps(s["buy_bps"]) if s["buy_bps"] is not None else "insuff depth"
        sell_s = fmt_bps(s["sell_bps"]) if s["sell_bps"] is not None else "insuff depth"
        print(f"{fmt_usd(s['size']):>10}  {buy_s:>12}  {sell_s:>12}")


def cmd_funding(symbol: str, json_out: bool = False) -> None:
    raw = hl_post({"type": "metaAndAssetCtxs"})
    universe = raw[0]["universe"]
    ctxs = raw[1]

    result = None
    for u, ctx in zip(universe, ctxs):
        if u["name"].upper() == symbol.upper():
            mark = float(ctx.get("markPx") or 0)
            oi_base = float(ctx.get("openInterest") or 0)
            funding = float(ctx.get("funding") or 0)
            result = {
                "symbol": u["name"],
                "mark_px": mark,
                "funding_hr_pct": funding * 100,
                "funding_8h_pct": funding * 8 * 100,
                "funding_apr_pct": funding * 8760 * 100,
                "oi_usd": oi_base * mark,
                "day_vol_usd": float(ctx.get("dayNtlVlm") or 0),
            }
            break

    if result is None:
        print(f"Symbol '{symbol}' not found. Use --perp-meta to list all symbols.")
        sys.exit(1)

    if json_out:
        print(json.dumps(result, indent=2))
        return

    print(f"\n=== Funding: {result['symbol']} ===")
    print(f"Mark Price:    {result['mark_px']:>16.8g}")
    print(f"Funding/hr:    {result['funding_hr_pct']:>+15.6f}%")
    print(f"Funding/8h:    {result['funding_8h_pct']:>+15.6f}%")
    print(f"Funding APR:   {result['funding_apr_pct']:>+15.4f}%")
    print(f"OI (USD):      {fmt_usd(result['oi_usd']):>16}")
    print(f"24h Volume:    {fmt_usd(result['day_vol_usd']):>16}")


def cmd_spot_volume(min_vol: float = 1000, top: int = 30,
                    json_out: bool = False) -> None:
    spot_raw = hl_post({"type": "spotMetaAndAssetCtxs"})
    meta, ctxs = spot_raw
    tok_by_idx, pairs_by_name = _build_spot_index(meta)

    # Build perp symbol set for cross-referencing
    perp_raw = hl_post({"type": "metaAndAssetCtxs"})
    perp_symbols = {u["name"].upper() for u in perp_raw[0]["universe"]}

    rows = []
    for ctx in ctxs:
        vol = float(ctx.get("dayNtlVlm") or 0)
        if vol < min_vol:
            continue
        coin = ctx["coin"]
        pair = pairs_by_name.get(coin)
        if pair is None:
            continue
        base, quote = _pair_token_names(pair, tok_by_idx)
        mark = float(ctx.get("markPx") or 0)
        prev = float(ctx.get("prevDayPx") or mark)
        rows.append({
            "coin": coin,
            "index": pair["index"],
            "base": base,
            "quote": quote,
            "day_vol_usd": vol,
            "mark_px": mark,
            "day_chg_pct": _pct_change(prev, mark),
            "has_perp": base.upper() in perp_symbols,
        })

    rows.sort(key=lambda r: r["day_vol_usd"], reverse=True)
    rows = rows[:top]

    if json_out:
        print(json.dumps(rows, indent=2))
        return

    print(f"\n=== Spot Volume (top {len(rows)}, min {fmt_usd(min_vol)}) ===")
    hdr = f"{'Pair':<18}  {'24h Vol':>12}  {'Price':>12}  {'24h%':>8}  {'Perp?'}"
    print(hdr)
    _divider(len(hdr))
    for r in rows:
        label = f"{r['base']}/{r['quote']}"
        chg = fmt_pct(r["day_chg_pct"], decimals=2) if r["day_chg_pct"] is not None else "N/A"
        perp_flag = "✓" if r["has_perp"] else ""
        print(
            f"{label:<18}"
            f"  {fmt_usd(r['day_vol_usd']):>12}"
            f"  {fmt_num(r['mark_px']):>12}"
            f"  {chg:>8}"
            f"  {perp_flag}"
        )


def cmd_usdt0(sizes: Optional[list] = None, json_out: bool = False) -> None:
    if sizes is None:
        sizes = [20_000, 100_000, 200_000]

    spot_meta = hl_post({"type": "spotMeta"})
    idx = _find_pair_index(spot_meta, "USDT0", "USDC")
    if idx is None:
        print("USDT0/USDC pair not found in spotMeta")
        sys.exit(1)

    coin = f"@{idx}"
    book = hl_post({"type": "l2Book", "coin": coin})
    bids = book["levels"][0]   # buyers of USDT0 (you sell USDT0 here → get USDC)
    asks = book["levels"][1]   # sellers of USDT0 (you buy USDT0 here → spend USDC)

    if not bids or not asks:
        print("No order book data for USDT0/USDC")
        return

    best_bid = float(bids[0]["px"])
    best_ask = float(asks[0]["px"])
    mid = (best_bid + best_ask) / 2
    spread_bps = (best_ask - best_bid) / mid * 10_000

    bid_depth = _depth_usd(bids, 20)
    ask_depth = _depth_usd(asks, 20)

    swap_rows = []
    for size in sizes:
        # Sell USDT0 → USDC: walk bids
        sell = _walk_book(bids, size)
        sell_vs_par = (sell["avg_px"] - 1.0) * 10_000 if sell["avg_px"] else None  # bps vs $1

        # Buy USDT0 ← USDC: walk asks
        buy = _walk_book(asks, size)
        buy_vs_par = (buy["avg_px"] - 1.0) * 10_000 if buy["avg_px"] else None

        rt = (buy_vs_par - sell_vs_par) if (buy_vs_par is not None and sell_vs_par is not None) else None
        swap_rows.append({
            "size_usd": size,
            "sell_avg_px": sell["avg_px"],
            "sell_vs_parity_bps": sell_vs_par,
            "buy_avg_px": buy["avg_px"],
            "buy_vs_parity_bps": buy_vs_par,
            "round_trip_bps": rt,
        })

    if json_out:
        out = {
            "coin": coin,
            "pair_index": idx,
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid": mid,
            "spread_bps": spread_bps,
            "bid_depth_usd": bid_depth,
            "ask_depth_usd": ask_depth,
            "swap_analysis": swap_rows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        print(json.dumps(out, indent=2))
        return

    print(f"\n=== USDT0/USDC Swap ({coin}) ===")
    print(f"Best Bid (sell USDT0): {best_bid:.6f} USDC/USDT0")
    print(f"Best Ask (buy USDT0):  {best_ask:.6f} USDC/USDT0")
    print(f"Mid:                   {mid:.6f}   Spread: {spread_bps:.2f} bps")
    print(f"Bid Depth (20L):       {fmt_usd(bid_depth):>10}    Ask Depth (20L): {fmt_usd(ask_depth):>10}")

    # Swap cost: positive sell_vs_par = above $1 (good for seller), positive buy_vs_par = above $1 (bad for buyer)
    print(f"\n{'Size':>10}  {'Sell→USDC (vs $1)':>18}  {'Buy←USDC (vs $1)':>18}  {'Round-trip':>12}")
    print("  positive sell = above $1 (good) | positive buy = above $1 (cost)")
    _divider(68)
    for s in swap_rows:
        sv = fmt_bps(s["sell_vs_parity_bps"]) if s["sell_vs_parity_bps"] is not None else "insuff depth"
        bv = fmt_bps(s["buy_vs_parity_bps"]) if s["buy_vs_parity_bps"] is not None else "insuff depth"
        rt = fmt_bps(s["round_trip_bps"]) if s["round_trip_bps"] is not None else "N/A"
        print(f"{fmt_usd(s['size_usd']):>10}  {sv:>18}  {bv:>18}  {rt:>12}")

    print(f"\n{'Bid Size':>14}  {'Bid Px':>10}  |  {'Ask Px':>10}  {'Ask Size':<14}")
    _divider(56)
    for i in range(min(10, len(bids), len(asks))):
        b, a = bids[i], asks[i]
        print(f"{float(b['sz']):>14.2f}  {float(b['px']):>10.6f}  |  {float(a['px']):>10.6f}  {float(a['sz']):<14.2f}")


def cmd_open_orders(address: str, filter_text: Optional[str] = None,
                    json_out: bool = False) -> None:
    orders = hl_post({"type": "frontendOpenOrders", "user": address.lower()})
    if not isinstance(orders, list):
        print(f"Unexpected response: {orders}")
        sys.exit(1)

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    rows = []
    for o in orders:
        coin = o.get("coin", "?")
        if filter_text and filter_text.upper() not in coin.upper():
            continue
        try:
            px = float(o.get("limitPx") or 0)
            sz = float(o.get("sz") or 0)
            orig_sz = float(o.get("origSz") or sz)
        except (TypeError, ValueError):
            px, sz, orig_sz = 0.0, 0.0, 0.0
        side = "Buy" if o.get("side") == "B" else "Sell"
        notional = px * sz
        filled_pct = ((orig_sz - sz) / orig_sz * 100) if orig_sz > 0 else 0.0
        age_ms = now_ms - int(o.get("timestamp") or now_ms)
        trigger_px = float(o.get("triggerPx") or 0)
        rows.append({
            "coin": coin,
            "side": side,
            "order_type": o.get("orderType", "?"),
            "tif": o.get("tif"),
            "limit_px": px,
            "sz": sz,
            "orig_sz": orig_sz,
            "filled_pct": filled_pct,
            "notional_usd": notional,
            "reduce_only": bool(o.get("reduceOnly")),
            "is_trigger": bool(o.get("isTrigger")),
            "trigger_px": trigger_px if o.get("isTrigger") else None,
            "trigger_condition": o.get("triggerCondition") if o.get("isTrigger") else None,
            "is_position_tpsl": bool(o.get("isPositionTpsl")),
            "age_hours": age_ms / 1000 / 3600,
            "oid": o.get("oid"),
            "cloid": o.get("cloid"),
            "timestamp": o.get("timestamp"),
        })

    rows.sort(key=lambda r: (r["coin"], -r["notional_usd"]))

    if json_out:
        out = {
            "user": address.lower(),
            "count": len(rows),
            "total_notional_usd": sum(r["notional_usd"] for r in rows),
            "orders": rows,
        }
        print(json.dumps(out, indent=2))
        return

    if not rows:
        note = f" matching '{filter_text}'" if filter_text else ""
        print(f"\nNo open orders for {address}{note}")
        return

    total_notional = sum(r["notional_usd"] for r in rows)
    coins = sorted({r["coin"] for r in rows})
    print(f"\n=== Open Orders: {address} ===")
    print(f"Count: {len(rows)} orders across {len(coins)} symbols    "
          f"Total notional: {fmt_usd(total_notional)}")

    hdr = (f"{'Coin':<10} {'Side':<5} {'Type':<10} {'TIF':<5} "
           f"{'Limit Px':>12} {'Size':>12} {'Notional':>12} "
           f"{'Filled%':>7} {'Age':>8} {'Flags':<12} {'OID'}")
    print(hdr)
    _divider(min(len(hdr), 140))
    for r in rows:
        age = r["age_hours"]
        if age < 1:
            age_str = f"{age * 60:.0f}m"
        elif age < 48:
            age_str = f"{age:.1f}h"
        else:
            age_str = f"{age / 24:.1f}d"
        flags = []
        if r["reduce_only"]:
            flags.append("RO")
        if r["is_trigger"]:
            flags.append(f"TRIG@{r['trigger_px']:g}")
        if r["is_position_tpsl"]:
            flags.append("TPSL")
        flag_str = ",".join(flags) if flags else "-"
        tif = r["tif"] or "-"
        print(
            f"{r['coin']:<10} "
            f"{r['side']:<5} "
            f"{r['order_type'][:10]:<10} "
            f"{tif:<5} "
            f"{fmt_num(r['limit_px']):>12} "
            f"{fmt_num(r['sz']):>12} "
            f"{fmt_usd(r['notional_usd']):>12} "
            f"{r['filled_pct']:>6.1f}% "
            f"{age_str:>8} "
            f"{flag_str[:12]:<12} "
            f"{r['oid']}"
        )


# ── main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hyperliquid API — spot/perp metadata, order books, funding",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--spot-meta", action="store_true",
                        help="List spot pairs (use --filter to search)")
    parser.add_argument("--perp-meta", action="store_true",
                        help="List perps sorted by |funding APR| (use --filter, --min-vol, --top)")
    parser.add_argument("--book", metavar="COIN",
                        help="L2 book: perp symbol (BNB) or spot index (@166). Use --levels.")
    parser.add_argument("--funding", metavar="SYMBOL",
                        help="Funding rate for one perp symbol")
    parser.add_argument("--spot-volume", action="store_true",
                        help="Top spot pairs by 24h volume (use --min-vol, --top)")
    parser.add_argument("--usdt0", action="store_true",
                        help="USDT0/USDC swap analysis")
    parser.add_argument("--open-orders", metavar="ADDRESS", dest="open_orders",
                        help="Open orders for a wallet (uses frontendOpenOrders)")
    parser.add_argument("--filter", metavar="TEXT",
                        help="Filter by name/symbol substring")
    parser.add_argument("--min-vol", type=float, default=1_000, metavar="USD",
                        help="Min 24h volume USD (default: $1,000)")
    parser.add_argument("--top", type=int, default=30,
                        help="Max rows to show (default: 30)")
    parser.add_argument("--levels", type=int, default=10,
                        help="Order book depth levels (default: 10)")
    parser.add_argument("--json", action="store_true", dest="json_out",
                        help="JSON output for agent parsing")
    args = parser.parse_args()

    ran = False

    if args.spot_meta:
        cmd_spot_meta(filter_text=args.filter, json_out=args.json_out)
        ran = True

    if args.perp_meta:
        cmd_perp_meta(filter_text=args.filter, min_vol=args.min_vol,
                      top=args.top, json_out=args.json_out)
        ran = True

    if args.book:
        cmd_book(coin=args.book, levels=args.levels, json_out=args.json_out)
        ran = True

    if args.funding:
        cmd_funding(symbol=args.funding, json_out=args.json_out)
        ran = True

    if args.spot_volume:
        cmd_spot_volume(min_vol=args.min_vol, top=args.top, json_out=args.json_out)
        ran = True

    if args.usdt0:
        cmd_usdt0(json_out=args.json_out)
        ran = True

    if args.open_orders:
        cmd_open_orders(address=args.open_orders, filter_text=args.filter,
                        json_out=args.json_out)
        ran = True

    if not ran:
        parser.print_help()


if __name__ == "__main__":
    main()
