#!/usr/bin/env python3
"""Hyperlend CLI — fetch lending/borrowing rates and market data.

Usage:
    python scripts/hyperlend.py rates [--tokens USDC,HYPE] [--raw]
    python scripts/hyperlend.py markets [--tokens USDC,HYPE]
    python scripts/hyperlend.py history --token USDC [--hours 168]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional

import httpx

BASE_URL = "https://api.hyperlend.finance"
CHAIN = "hyperEvm"

TOKEN_ADDRESSES: Dict[str, str] = {
    "HYPE": "0x5555555555555555555555555555555555555555",
    "wstHYPE": "0x94e8396e0869c9F2200760aF0621aFd240E1CF38",
    "kHYPE": "0xfD739d4e423301CE9385c1fb8850539D657C296D",
    "beHYPE": "0xd8FC8F0b03eBA61F64D08B0bef69d80916E5DdA9",
    "USDC": "0xb88339CB7199b77E23DB6E890353E22632Ba630f",
    "USDT": "0xB8CE59FC3717ada4C02eaDF9682A9e934F625ebb",
    "USDH": "0x111111a1a0667d36bD57c0A9f569b98057111111",
    "USDHL": "0xb50A96253aBDF803D85efcDce07Ad8becBc52BD5",
    "USDe": "0x5d3a1Ff2b6BAb83b63cd9AD0787074081a52ef34",
    "sUSDe": "0x211Cc4DD073734dA055fbF44a2b4667d5E5fE5d2",
    "USR": "0x0aD339d66BF4AeD5ce31c64Bc37B3244b6394A77",
    "UBTC": "0x9FDBdA0A5e284c32744D2f17Ee5c74B284993463",
    "UETH": "0xBe6727B535545C67d5cAa73dEa54865B92CF7907",
    "USOL": "0x068f321Fa8Fb9f0D135f290Ef6a3e2813e1c8A29",
}

SYMBOL_ALIASES: Dict[str, str] = {
    "WHYPE": "HYPE",
    "USD₮0": "USDT",
}

SYMBOL_BY_ADDRESS: Dict[str, str] = {v.lower(): k for k, v in TOKEN_ADDRESSES.items()}

RAY = 10**27


def _get(path: str, params: Optional[Dict[str, str]] = None) -> Any:
    with httpx.Client(timeout=15) as client:
        resp = client.get(f"{BASE_URL}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


TOKENS_LOWER: Dict[str, str] = {k.lower(): k for k in TOKEN_ADDRESSES}


def _filter_tokens(requested: Optional[str]) -> Optional[List[str]]:
    if not requested:
        return None
    raw = [s.strip() for s in requested.split(",")]
    resolved = []
    unknown = []
    for s in raw:
        canonical = TOKENS_LOWER.get(s.lower())
        if canonical:
            resolved.append(canonical)
        else:
            unknown.append(s)
    if unknown:
        print(
            json.dumps(
                {
                    "error": f"Unknown tokens: {unknown}",
                    "known_tokens": list(TOKEN_ADDRESSES.keys()),
                }
            )
        )
        sys.exit(1)
    return resolved


def _normalize_symbol(sym: str) -> str:
    return SYMBOL_ALIASES.get(sym, sym)


def _resolve_symbol(addr: str, reserves: Optional[List[Dict]] = None) -> str:
    sym = SYMBOL_BY_ADDRESS.get(addr.lower())
    if sym:
        return sym
    if reserves:
        for r in reserves:
            if r.get("underlyingAsset", "").lower() == addr.lower():
                return _normalize_symbol(r.get("symbol", addr[:10]))
    return addr[:10]


def cmd_rates(args: argparse.Namespace) -> None:
    tokens = _filter_tokens(args.tokens)
    rates_data = _get("/data/markets/rates", {"chain": CHAIN})
    reserves = _get("/data/markets", {"chain": CHAIN}).get("reserves", []) if not args.raw else []

    results = []
    for addr, info in rates_data.items():
        if not isinstance(info, dict):
            continue
        symbol = _resolve_symbol(addr, reserves)
        if tokens and symbol not in tokens:
            addr_match = any(
                TOKEN_ADDRESSES.get(t, "").lower() == addr.lower() for t in tokens
            )
            if not addr_match:
                continue

        is_isolated = bool(info.get("underlying"))
        if is_isolated:
            underlying_sym = _resolve_symbol(info["underlying"], reserves)
            collateral_sym = _resolve_symbol(info.get("collateral", ""), reserves) if info.get("collateral") else "?"
            symbol = f"{underlying_sym}/{collateral_sym}"

        entry: Dict[str, Any] = {
            "symbol": symbol,
            "address": addr,
            "supply_apr": round(info.get("supplyAPR", 0), 4),
            "supply_apy": round(info.get("supplyAPY", 0), 4),
        }
        if "borrowAPR" in info:
            entry["borrow_apr"] = round(info["borrowAPR"], 4)
            entry["borrow_apy"] = round(info.get("borrowAPY", 0), 4)

        if is_isolated:
            entry["type"] = "isolated"
            entry["underlying"] = info["underlying"]
            entry["collateral"] = info.get("collateral")
        else:
            entry["type"] = "core"

        results.append(entry)

    results.sort(key=lambda x: x.get("supply_apr", 0), reverse=True)
    print(json.dumps({"timestamp": int(time.time()), "chain": CHAIN, "rates": results}, indent=2))


def cmd_markets(args: argparse.Namespace) -> None:
    tokens = _filter_tokens(args.tokens)
    data = _get("/data/markets", {"chain": CHAIN})
    reserves = data.get("reserves", [])

    results = []
    for info in reserves:
        addr = info.get("underlyingAsset", "")
        raw_symbol = info.get("symbol", addr[:10])
        symbol = _normalize_symbol(raw_symbol)

        if tokens and symbol not in tokens:
            addr_match = any(
                TOKEN_ADDRESSES.get(t, "").lower() == addr.lower() for t in tokens
            )
            if not addr_match:
                continue

        liq_rate_raw = int(info.get("liquidityRate", 0))
        borrow_rate_raw = int(info.get("variableBorrowRate", 0))

        entry: Dict[str, Any] = {
            "symbol": symbol,
            "address": addr,
            "decimals": info.get("decimals"),
            "supply_rate_pct": round(liq_rate_raw / RAY * 100, 4) if liq_rate_raw else 0,
            "borrow_rate_pct": round(borrow_rate_raw / RAY * 100, 4) if borrow_rate_raw else 0,
            "ltv_bps": info.get("baseLTVasCollateral"),
            "liquidation_threshold_bps": info.get("reserveLiquidationThreshold"),
            "reserve_factor_bps": info.get("reserveFactor"),
            "is_active": info.get("isActive"),
            "is_frozen": info.get("isFrozen"),
            "borrowing_enabled": info.get("borrowingEnabled"),
            "supply_cap": info.get("supplyCap"),
            "borrow_cap": info.get("borrowCap"),
        }

        results.append(entry)

    results.sort(key=lambda x: x.get("supply_rate_pct", 0), reverse=True)
    print(json.dumps({"timestamp": int(time.time()), "chain": CHAIN, "markets": results}, indent=2))


def cmd_history(args: argparse.Namespace) -> None:
    raw = args.token.strip()
    symbol = TOKENS_LOWER.get(raw.lower())
    if not symbol:
        print(
            json.dumps(
                {
                    "error": f"Unknown token: {symbol}",
                    "known_tokens": list(TOKEN_ADDRESSES.keys()),
                }
            )
        )
        sys.exit(1)

    token_addr = TOKEN_ADDRESSES[symbol]
    data = _get("/data/interestRateHistory", {"chain": CHAIN, "token": token_addr})

    if not isinstance(data, list):
        print(json.dumps({"error": "Unexpected response format", "raw": data}))
        sys.exit(1)

    cutoff = None
    if args.hours:
        cutoff = (time.time() - args.hours * 3600) * 1000

    records = []
    for entry in data:
        ts = entry.get("timestamp", 0)
        if cutoff and ts < cutoff:
            continue

        rate_data = entry.get(token_addr, {})
        liq_raw = int(rate_data.get("currentLiquidityRate", 0))
        borrow_raw = int(rate_data.get("currentVariableBorrowRate", 0))

        records.append(
            {
                "timestamp": ts,
                "timestamp_s": int(ts / 1000) if ts else 0,
                "supply_rate_pct": round(liq_raw / RAY * 100, 6),
                "borrow_rate_pct": round(borrow_raw / RAY * 100, 6),
            }
        )

    records.sort(key=lambda x: x["timestamp"])

    summary: Dict[str, Any] = {"count": len(records)}
    if records:
        supply_rates = [r["supply_rate_pct"] for r in records]
        borrow_rates = [r["borrow_rate_pct"] for r in records]
        summary["supply_rate_min"] = round(min(supply_rates), 6)
        summary["supply_rate_max"] = round(max(supply_rates), 6)
        summary["supply_rate_avg"] = round(sum(supply_rates) / len(supply_rates), 6)
        summary["supply_rate_latest"] = supply_rates[-1]
        summary["borrow_rate_min"] = round(min(borrow_rates), 6)
        summary["borrow_rate_max"] = round(max(borrow_rates), 6)
        summary["borrow_rate_avg"] = round(sum(borrow_rates) / len(borrow_rates), 6)
        summary["borrow_rate_latest"] = borrow_rates[-1]
        summary["hours_covered"] = round(
            (records[-1]["timestamp"] - records[0]["timestamp"]) / 3_600_000, 1
        )

    print(
        json.dumps(
            {
                "timestamp": int(time.time()),
                "chain": CHAIN,
                "token": symbol,
                "address": token_addr,
                "summary": summary,
                "history": records if not args.summary_only else [],
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Hyperlend rate data CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_rates = sub.add_parser("rates", help="Current supply/borrow APR/APY for all pools")
    p_rates.add_argument("--tokens", help="Comma-separated token symbols to filter (e.g. USDC,HYPE)")
    p_rates.add_argument("--raw", action="store_true", help="Skip market data lookup for symbol resolution")

    p_markets = sub.add_parser("markets", help="Full market data (risk params, caps, rates)")
    p_markets.add_argument("--tokens", help="Comma-separated token symbols to filter")

    p_history = sub.add_parser("history", help="Historical hourly rates for a token")
    p_history.add_argument("--token", required=True, help="Token symbol (e.g. USDC)")
    p_history.add_argument("--hours", type=int, help="Limit to last N hours")
    p_history.add_argument("--summary-only", action="store_true", help="Only output summary stats, skip per-hour data")

    args = parser.parse_args()
    {"rates": cmd_rates, "markets": cmd_markets, "history": cmd_history}[args.command](args)


if __name__ == "__main__":
    main()
