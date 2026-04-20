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


def log(msg: str) -> None:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def main() -> int:
    log(f"pull_loris_funding START url={URL} out={OUT_PATH}")
    try:
        cfg = load_cfg()
        target_exchanges = normalize_target_exchanges(cfg.get("target_exchanges", []))
        oi_rank_max = int(cfg.get("oi_rank_max", 200))
        log(f"config target_exchanges={sorted(target_exchanges)} oi_rank_max={oi_rank_max}")

        payload = http_get_json(URL)
        ts = utc_now_iso()

        oi_map = payload.get("oi_rankings", {}) or {}
        funding = payload.get("funding_rates", {}) or {}
        venues_in_payload = list(funding.keys())
        log(f"api_response venues={venues_in_payload} oi_symbols={len(oi_map)}")

        ensure_header(OUT_PATH)

        rows = 0
        skipped_exchange = 0
        skipped_rank = 0
        with open(OUT_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for ex, ex_map in funding.items():
                ex_norm = normalize_exchange_name(ex)
                if target_exchanges and ex_norm not in target_exchanges:
                    skipped_exchange += len(ex_map) if isinstance(ex_map, dict) else 0
                    continue
                if not isinstance(ex_map, dict):
                    continue
                for sym, scaled in ex_map.items():
                    rank = oi_rank_to_int(oi_map.get(sym))
                    if rank != 9999 and rank > oi_rank_max:
                        skipped_rank += 1
                        continue
                    try:
                        scaled_f = float(scaled)
                    except Exception:
                        log(f"WARN bad scaled value ex={ex_norm} sym={sym} val={scaled!r}")
                        continue
                    rate = scaled_f / 10000.0
                    w.writerow([ts, ex_norm, sym, rank, scaled_f, rate])
                    rows += 1

        log(f"pull_loris_funding DONE appended_rows={rows} skipped_exchange={skipped_exchange} skipped_rank={skipped_rank} out={OUT_PATH}")
        return 0

    except Exception as exc:
        import traceback
        log(f"pull_loris_funding FAILED error={exc!r}")
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
