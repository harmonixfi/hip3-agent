#!/usr/bin/env python3
"""Daily report: Top stable PERP↔PERP funding-carry pairs (playbook baseline).

Data source:
- Local append-only CSV pulled from Loris Tools: data/loris_funding_history.csv
- Pull helper: scripts/pull_loris_funding.py

Output:
- Plain text bullet list (Discord-friendly; no markdown tables)

This script is intentionally conservative:
- Uses trimmed mean (5%) over 14D + 7D windows.
- Requires current net APR >= threshold.
- Uses conservative round-trip cost floor (normal regime).

"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data" / "loris_funding_history.csv"
FEES_PATH = ROOT / "config" / "fees.json"
PLAYBOOK_PATH = ROOT / "docs" / "PLAYBOOK_baseline_funding_arbit.md"
PULL_LORIS = ROOT / "scripts" / "pull_loris_funding.py"


def tmean(x: np.ndarray, p: float = 0.05) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    x.sort()
    k = int(x.size * p)
    if x.size - 2 * k <= 0:
        return float(x.mean())
    return float(x[k : x.size - k].mean())


@dataclass
class PairRow:
    symbol: str
    oi_rank: int
    long_ex: str
    short_ex: str
    apr14: float
    apr7: float
    apr_cur: float
    pos_long: float
    pos_short: float
    be_days: float
    stability: float
    net14_8h: float

    def to_dict(self) -> dict:
        d = asdict(self)
        # add convenience fields
        d["net14_8h_pct"] = self.net14_8h * 100
        d["daily_pct"] = self.net14_8h * 3 * 100
        return d


def load_fees() -> dict:
    return json.loads(FEES_PATH.read_text(encoding="utf-8"))


def roundtrip_cost_pct_perp_perp(fees: dict, ex_long: str, ex_short: str, *, floor_pct: float) -> float:
    """Conservative round-trip cost estimate (entry+exit).

    Uses taker fees (if known) + proxy slippage. If a venue fee schedule is
    missing in config/fees.json, we fall back to a conservative default taker fee.
    """

    slip_bps = float(fees.get("default_assumptions", {}).get("proxy_slippage_bps", 10))
    venues = fees.get("venues", {})

    def taker_bps(ex: str) -> float:
        v = venues.get(ex) or {}
        perp = v.get("perp") or {}
        if "taker_bps" in perp:
            return float(perp["taker_bps"])
        # Conservative default for unknown venues until we confirm fee tiers
        return 10.0

    taker_long = taker_bps(ex_long)
    taker_short = taker_bps(ex_short)
    bps = 2 * (taker_long + taker_short) + 4 * slip_bps
    return max(bps / 10000.0, floor_pct)


def compute_top_pairs(
    df: pd.DataFrame,
    *,
    venues: list[str],
    oi_max: int,
    min_apr14: float,
    min_apr7: float,
    min_apr_cur: float,
    pos_long_max: float,
    pos_short_min: float,
    be_days_max: float,
    cost_floor_pct: float,
) -> tuple[list[PairRow], list[PairRow]]:
    fees = load_fees()

    # current snapshot per exchange+symbol
    idx = df.groupby(["exchange", "symbol"])["timestamp_utc"].idxmax()
    cur = df.loc[idx, ["exchange", "symbol", "funding_8h_rate", "oi_rank"]].rename(
        columns={"funding_8h_rate": "cur", "oi_rank": "oi_rank_cur"}
    )

    # 14D aggregate per exchange+symbol
    g14 = (
        df.groupby(["exchange", "symbol"])
        .agg(
            n=("funding_8h_rate", "size"),
            tmean14=("funding_8h_rate", lambda x: tmean(np.asarray(x), 0.05)),
            std14=("funding_8h_rate", "std"),
            pos14=("funding_8h_rate", lambda x: float((np.asarray(x) > 0).mean())),
            oi_rank=("oi_rank", "min"),
        )
        .reset_index()
    )

    # 7D aggregate
    last_ts = df["timestamp_utc"].max()
    cut7 = last_ts - pd.Timedelta(days=7)
    df7 = df[df["timestamp_utc"] >= cut7]
    g7 = (
        df7.groupby(["exchange", "symbol"])
        .agg(
            n7=("funding_8h_rate", "size"),
            tmean7=("funding_8h_rate", lambda x: tmean(np.asarray(x), 0.05)),
        )
        .reset_index()
    )

    m = g14.merge(g7, on=["exchange", "symbol"], how="left").merge(cur, on=["exchange", "symbol"], how="left")
    m = m[(m["n"] >= 50) & (m["exchange"].isin(venues))]

    rows: list[PairRow] = []
    watch: list[PairRow] = []

    for sym, gg in m.groupby("symbol"):
        if len(gg) < 2:
            continue
        oi = int(gg["oi_rank"].min()) if math.isfinite(float(gg["oi_rank"].min())) else 9999
        if oi > oi_max:
            continue

        # evaluate ordered pairs
        for i in range(len(gg)):
            for j in range(len(gg)):
                if i == j:
                    continue
                L = gg.iloc[i]
                S = gg.iloc[j]

                # net funding pnl per 8h: (short receives S_rate, long pays/receives -L_rate)
                net14 = float(S["tmean14"] - L["tmean14"])
                net7 = float((S.get("tmean7") or 0.0) - (L.get("tmean7") or 0.0))
                net_cur = float((S.get("cur") or 0.0) - (L.get("cur") or 0.0))

                apr14 = net14 * 3 * 365 * 100
                apr7 = net7 * 3 * 365 * 100
                apr_cur = net_cur * 3 * 365 * 100

                pos_long = float(L["pos14"])
                pos_short = float(S["pos14"])

                # stability score: abs(mean)/std (proxy)
                stdL = float(L["std14"]) if float(L["std14"]) and float(L["std14"]) > 0 else float("nan")
                stdS = float(S["std14"]) if float(S["std14"]) and float(S["std14"]) > 0 else float("nan")
                stab = 0.0
                if math.isfinite(stdL):
                    stab += abs(float(L["tmean14"])) / stdL
                if math.isfinite(stdS):
                    stab += abs(float(S["tmean14"])) / stdS

                cost_pct = roundtrip_cost_pct_perp_perp(fees, str(L["exchange"]), str(S["exchange"]), floor_pct=cost_floor_pct)
                daily = net14 * 3  # fraction/day
                be_days = (cost_pct / daily) if daily > 0 else float("inf")

                pr = PairRow(
                    symbol=sym,
                    oi_rank=oi,
                    long_ex=str(L["exchange"]),
                    short_ex=str(S["exchange"]),
                    apr14=apr14,
                    apr7=apr7,
                    apr_cur=apr_cur,
                    pos_long=pos_long,
                    pos_short=pos_short,
                    be_days=be_days,
                    stability=stab,
                    net14_8h=net14,
                )

                # strict filter (Tier A)
                strict_ok = (
                    (apr_cur >= min_apr_cur)
                    and (be_days <= be_days_max)
                    and (pos_long <= pos_long_max)
                    and (pos_short >= pos_short_min)
                    and ((apr14 >= min_apr14) or (apr7 >= min_apr7))
                )

                if strict_ok:
                    rows.append(pr)
                else:
                    # Watchlist: near-miss
                    near = (
                        (apr_cur >= min_apr_cur * 0.75)
                        and (be_days <= be_days_max * 1.5)
                        and ((apr14 >= min_apr14 * 0.75) or (apr7 >= min_apr7 * 0.75))
                    )
                    if near:
                        watch.append(pr)

    # Sort + pick best unique symbols
    def rank_key(x: PairRow):
        return (x.stability, x.apr14, x.apr_cur)

    rows.sort(key=rank_key, reverse=True)
    watch.sort(key=rank_key, reverse=True)

    # de-duplicate by symbol
    def dedup(items: list[PairRow]) -> list[PairRow]:
        out: list[PairRow] = []
        seen: set[str] = set()
        for it in items:
            if it.symbol in seen:
                continue
            out.append(it)
            seen.add(it.symbol)
        return out

    return dedup(rows), dedup(watch)


def fmt_pct(x: float) -> str:
    return f"{x:+.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true", help="Run pull_loris_funding.py before computing")
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--watch", type=int, default=3)
    ap.add_argument("--oi-max", type=int, default=200)
    ap.add_argument("--be-max", type=float, default=7.0)
    ap.add_argument("--cost-floor", type=float, default=0.006, help="Conservative round-trip cost floor (pct, e.g. 0.006=0.6%%)")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    ap.add_argument("--no-explain", action="store_true", help="(text mode) omit the metric explanation block")
    ap.add_argument(
        "--venues",
        type=str,
        default="okx,paradex,lighter,ethereal,hyperliquid,hyena,kinetiq,tradexyz,felix",
        help="Comma-separated venue list (Loris exchange keys).",
    )
    args = ap.parse_args()

    if args.pull:
        # Keep downstream output machine-readable (esp. --format json)
        subprocess.run(
            ["python3", str(PULL_LORIS)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    if not CSV_PATH.exists():
        print("No data yet: data/loris_funding_history.csv missing")
        return 1

    df = pd.read_csv(CSV_PATH)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)

    last_ts = df["timestamp_utc"].max()
    cut14 = last_ts - pd.Timedelta(days=14)
    df = df[df["timestamp_utc"] >= cut14]

    venues = [v.strip() for v in args.venues.split(",") if v.strip()]

    top, watch = compute_top_pairs(
        df,
        venues=venues,
        oi_max=args.oi_max,
        min_apr14=20.0,
        min_apr7=25.0,
        min_apr_cur=20.0,
        pos_long_max=0.35,
        pos_short_min=0.65,
        be_days_max=float(args.be_max),
        cost_floor_pct=float(args.cost_floor),
    )

    if args.format == "json":
        payload = {
            "kind": "perp_perp_playbook_report",
            "snapshot_ts": last_ts.isoformat(),
            "window": "last14d",
            "playbook_path": str(PLAYBOOK_PATH),
            "assumptions": {
                "round_trip_cost_floor_pct": float(args.cost_floor),
                "be_days_max": float(args.be_max),
                "oi_max": int(args.oi_max),
                "venues": venues,
            },
            "top": [r.to_dict() for r in top[: args.top]],
            "watchlist": [r.to_dict() for r in watch[: args.watch]],
        }
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    # text mode
    print(f"Daily funding report — Top stable PERP↔PERP (Tier A baseline)")
    print(f"Data window: last14d | snapshot: {last_ts.isoformat()}")
    print(f"Playbook: {PLAYBOOK_PATH}")
    print(f"Assumption: round-trip cost floor ~{float(args.cost_floor)*100:.2f}% (normal regime)")
    print("Note: CHECK BASIS + DEPTH before entry. Avoid extreme mean-reversion unless requested.")
    print("")

    if not args.no_explain:
        print("How to read metrics:")
        print("- LONG/SHORT: bạn LONG perp ở venue_long và SHORT perp ở venue_short (delta-neutral).")
        print("- APR14 / APR7: net funding carry annualized, tính từ 14D/7D trimmed-mean (5%) của (funding_short - funding_long).")
        print("- APRcur: net funding carry annualized tại snapshot mới nhất (funding_short_current - funding_long_current).")
        print("- pos_long / pos_short: % số mẫu trong 14D mà funding_rate > 0 trên từng venue.")
        print("    • pos_long thấp ⇒ funding thường âm ở venue LONG ⇒ LONG thường *nhận* funding.")
        print("    • pos_short cao ⇒ funding thường dương ở venue SHORT ⇒ SHORT thường *nhận* funding.")
        print("- BE~Xd: số ngày hòa vốn = (round-trip cost assumption) / (expected daily funding from net14).")
        print("")

    if not top:
        print("Top candidates: (none meeting strict Tier-A filters right now)")
    else:
        print(f"Top {min(args.top, len(top))} candidates:")
        for i, r in enumerate(top[: args.top], 1):
            daily_pct = r.net14_8h * 3 * 100
            net14_8h_pct = r.net14_8h * 100
            print(
                f"- #{i} {r.symbol} (OI#{r.oi_rank}) | LONG {r.long_ex} / SHORT {r.short_ex}"
                f" | APR14 {fmt_pct(r.apr14)} (net {net14_8h_pct:+.3f}%/8h ~{daily_pct:+.3f}%/day)"
                f" | APR7 {fmt_pct(r.apr7)} | APRcur {fmt_pct(r.apr_cur)}"
                f" | BE~{r.be_days:.1f}d | pos_long {r.pos_long*100:.0f}% / pos_short {r.pos_short*100:.0f}%"
            )

    if watch:
        print("")
        print(f"Watchlist (near-miss) {min(args.watch, len(watch))}:")
        for i, r in enumerate(watch[: args.watch], 1):
            daily_pct = r.net14_8h * 3 * 100
            net14_8h_pct = r.net14_8h * 100
            print(
                f"- (W{i}) {r.symbol} | LONG {r.long_ex} / SHORT {r.short_ex}"
                f" | APR14 {fmt_pct(r.apr14)} (net {net14_8h_pct:+.3f}%/8h ~{daily_pct:+.3f}%/day)"
                f" | APR7 {fmt_pct(r.apr7)} | APRcur {fmt_pct(r.apr_cur)} | BE~{r.be_days:.1f}d"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
