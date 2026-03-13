#!/usr/bin/env python3
"""Pull live funding data from Loris Tools and append to a local CSV history.

Design goals:
- minimal deps (stdlib only)
- append-only history so we can compute 14D averages/stability ourselves

Source:
- https://api.loris.tools/funding
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "config", "strategy.json")
OUT_PATH = os.path.join(ROOT, "data", "loris_funding_history.csv")
URL = "https://api.loris.tools/funding"
EXCHANGE_ALIASES = {
    "hyperliquid": "hyperliquid",
    "hl": "hyperliquid",
    "tradexyz": "tradexyz",
    "xyz": "tradexyz",
    "tradexyz_perp": "tradexyz",
    "felix": "felix",
    "kinetiq": "kinetiq",
    "hyena": "hyena",
}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_cfg() -> dict:
    with open(CFG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def http_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "arbit-tracker/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def normalize_exchange_name(name: str | None) -> str:
    key = str(name or "").strip().lower()
    return EXCHANGE_ALIASES.get(key, key)


def normalize_target_exchanges(values: list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    normalized = {normalize_exchange_name(v) for v in (values or []) if str(v).strip()}
    return {v for v in normalized if v}


def oi_rank_to_int(x: str | None) -> int:
    if not x:
        return 9999
    x = str(x).strip()
    if x.endswith("+"):
        x = x[:-1]
    try:
        return int(x)
    except ValueError:
        return 9999


def ensure_header(path: str) -> None:
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc", "exchange", "symbol", "oi_rank", "funding_8h_scaled", "funding_8h_rate"])


def main() -> int:
    cfg = load_cfg()
    target_exchanges = normalize_target_exchanges(cfg.get("target_exchanges", []))
    oi_rank_max = int(cfg.get("oi_rank_max", 200))

    payload = http_get_json(URL)
    ts = utc_now_iso()

    oi_map = payload.get("oi_rankings", {}) or {}
    funding = payload.get("funding_rates", {}) or {}

    ensure_header(OUT_PATH)

    rows = 0
    with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for ex, ex_map in funding.items():
            ex_norm = normalize_exchange_name(ex)
            if target_exchanges and ex_norm not in target_exchanges:
                continue
            if not isinstance(ex_map, dict):
                continue
            for sym, scaled in ex_map.items():
                rank = oi_rank_to_int(oi_map.get(sym))
                # If OI rank is missing (mapped to 9999), keep the row so we can
                # still track new/permissionless listings (e.g., HIP-3) that may not
                # be ranked yet.
                if rank != 9999 and rank > oi_rank_max:
                    continue
                # Loris "scaled" is typically an integer, but some venues (e.g. HIP-3)
                # return fractional scaled values. Preserve precision.
                try:
                    scaled_f = float(scaled)
                except Exception:
                    continue
                rate = scaled_f / 10000.0  # 8h-equivalent funding rate as fraction
                w.writerow([ts, ex_norm, sym, rank, scaled_f, rate])
                rows += 1

    print(f"appended_rows={rows} out={OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
