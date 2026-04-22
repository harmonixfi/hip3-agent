#!/usr/bin/env python3
"""Query exported candidates CSV and produce ranked reports."""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "data" / "candidates_20260420.csv"

APR_STABLE_THRESHOLD = 11.0       # % — both apr_7d and apr_14d must exceed this
POSITIVE_SHARE_THRESHOLD = 60.0   # % of funding samples that must be positive


REPORT_COLS = [
    ("rank",      5),
    ("symbol",   10),
    ("venue",    12),
    ("stable",    7),
    ("quality",   8),
    ("pos%",      6),
    ("eff_apr",   8),
    ("apr_1d",    8),
    ("apr_3d",    8),
    ("apr_7d",    8),
    ("apr_14d",   8),
    ("oi_rank",   7),
    ("be_days",   8),
    ("status",   18),
    ("flags",    50),
]

MD_HEADERS = [
    "#", "Symbol", "Venue", "Stable", "Quality",
    "Pos%", "Eff APR", "APR 1d", "APR 3d", "APR 7d", "APR 14d",
    "OI Rank", "BE Days", "Status", "Flags",
]


def _fmt(val: str, width: int) -> str:
    return val[:width].ljust(width)


def _header() -> str:
    return "  ".join(_fmt(name, w) for name, w in REPORT_COLS)


def _sep() -> str:
    return "  ".join("-" * w for _, w in REPORT_COLS)


def _safe_float(val: str) -> float:
    try:
        return float(val)
    except (ValueError, TypeError):
        return float("-inf")


def _has_flag(r: dict, flag: str) -> bool:
    return flag in r.get("flags", "")


def _stable_label(r: dict) -> str:
    if r["_is_stable"]:
        return "YES"
    reasons = []
    apr7 = _safe_float(r.get("apr_7d", ""))
    apr14 = _safe_float(r.get("apr_14d", ""))
    ps = _safe_float(r.get("positive_share", ""))
    if apr7 <= APR_STABLE_THRESHOLD or apr14 <= APR_STABLE_THRESHOLD:
        reasons.append("low_apr")
    if ps != float("-inf") and ps < POSITIVE_SHARE_THRESHOLD:
        reasons.append("low_pos%")
    if _has_flag(r, "DECAYING_REGIME"):
        reasons.append("decay")
    return ",".join(reasons) if reasons else "no"


def _is_stable(r: dict) -> bool:
    apr7 = _safe_float(r.get("apr_7d", ""))
    apr14 = _safe_float(r.get("apr_14d", ""))
    if apr7 <= APR_STABLE_THRESHOLD or apr14 <= APR_STABLE_THRESHOLD:
        return False
    ps = _safe_float(r.get("positive_share", ""))
    if ps == float("-inf") or ps < POSITIVE_SHARE_THRESHOLD:
        return False
    # Exclude decaying regime: 7d/14d averages may be positive but trend is falling
    if _has_flag(r, "DECAYING_REGIME"):
        return False
    return True


def _sort_key(r: dict):
    stable = r["_is_stable"]
    quality = _safe_float(r.get("pair_quality_score", ""))
    return (not stable, -quality)


def _cells(rank: int, r: dict) -> list[str]:
    return [
        str(rank),
        r["symbol"],
        r["funding_venue"],
        _stable_label(r),
        r["pair_quality_score"],
        r.get("positive_share", "-"),
        r["effective_apr_anchor"],
        r.get("apr_1d", "-"),
        r.get("apr_3d", "-"),
        r["apr_7d"],
        r["apr_14d"],
        r["oi_rank"] or "—",
        r["breakeven_estimate_days"] or "—",
        r["tradeability_status"],
        r["flags"].replace("|", " · ") if r["flags"] else "",
    ]


def _plain_row(rank: int, r: dict) -> str:
    cells = _cells(rank, r)
    return "  ".join(_fmt(c, REPORT_COLS[i][1]) for i, c in enumerate(cells))


def _md_row(rank: int, r: dict) -> str:
    return "| " + " | ".join(_cells(rank, r)) + " |"


def load_and_sort(csv_path: Path) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["_is_stable"] = _is_stable(r)
    rows.sort(key=_sort_key)
    return rows


def print_report(title: str, rows: list[dict], top_n: int = 20, md: bool = False) -> None:
    stable_count = sum(1 for r in rows if r["_is_stable"])
    print(f"\n## {title}")
    print(
        f"Total in group: {len(rows)} | "
        f"stable (apr≥{APR_STABLE_THRESHOLD}%, pos≥{POSITIVE_SHARE_THRESHOLD}%, no DECAY): {stable_count}"
    )
    if md:
        print("| " + " | ".join(MD_HEADERS) + " |")
        print("| " + " | ".join("---" for _ in MD_HEADERS) + " |")
        for i, r in enumerate(rows[:top_n], start=1):
            print(_md_row(i, r))
    else:
        print(_header())
        print(_sep())
        for i, r in enumerate(rows[:top_n], start=1):
            print(_plain_row(i, r))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Query candidates CSV for ranked reports.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--threshold", type=float, default=APR_STABLE_THRESHOLD,
                        help="APR threshold for 7d and 14d")
    parser.add_argument("--pos-threshold", type=float, default=POSITIVE_SHARE_THRESHOLD,
                        help="Min %% of positive funding samples to be considered stable")
    parser.add_argument("--md", type=Path, default=None, help="Export markdown report to this path")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    global APR_STABLE_THRESHOLD, POSITIVE_SHARE_THRESHOLD
    APR_STABLE_THRESHOLD = args.threshold
    POSITIVE_SHARE_THRESHOLD = args.pos_threshold

    rows = load_and_sort(args.csv)
    non_felix = [r for r in rows if r.get("spot_on_felix", "").lower() != "true"]
    felix = [r for r in rows if r.get("spot_on_felix", "").lower() == "true"]

    use_md = args.md is not None
    header_lines = [
        f"# Candidate Analysis — {args.csv.name}",
        f"Date: 2026-04-20",
        f"Total: {len(rows)} | Non-Felix: {len(non_felix)} | Felix: {len(felix)}",
        f"Stable criteria: apr_7d > {APR_STABLE_THRESHOLD}% AND apr_14d > {APR_STABLE_THRESHOLD}%"
        f" AND positive_share > {POSITIVE_SHARE_THRESHOLD}% AND no DECAYING_REGIME",
        f"Sort: stable first (YES), then pair_quality_score DESC",
        "",
        "> **pair_quality_score** = 30% funding_consistency + 25% trend_alignment + 20% liquidity + 15% effective_apr + 10% breakeven",
        "> **Stable** column: YES = passes all criteria; otherwise shows failing reason(s): low_apr / low_pos% / decay",
    ]

    if use_md:
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf

    for line in header_lines:
        print(line)

    if non_felix:
        print_report("Top 20 Non-Felix Candidates", non_felix, args.top, md=use_md)
    if felix:
        print_report("Top 20 Felix Equities Candidates", felix, args.top, md=use_md)

    if use_md:
        sys.stdout = old_stdout
        content = buf.getvalue()
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(content, encoding="utf-8")
        print(content)
        print(f"\n---\nExported to {args.md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
