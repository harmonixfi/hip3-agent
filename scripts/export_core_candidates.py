#!/usr/bin/env python3
"""Export all Core candidates ranked by quality for review."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core_tier_portfolio_construction import (
    CoreCandidate,
    load_core_candidates,
)

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export all Core candidates ranked by quality.",
    )
    parser.add_argument("--loris-csv", type=Path, default=ROOT / "data" / "loris_funding_history.csv")
    parser.add_argument("--felix-cache", type=Path, default=ROOT / "data" / "felix_equities_cache.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--portfolio-capital", type=float, default=1_000_000)
    parser.add_argument("--core-capital", type=float, default=600_000)
    parser.add_argument("--csv", type=Path, default=None, help="Export to CSV file")
    return parser.parse_args(argv)


def _load_hyperliquid_spot_symbols(db_path: Path) -> set[str] | None:
    if not db_path.exists():
        return None
    try:
        con = sqlite3.connect(str(db_path))
        rows = con.execute(
            "SELECT DISTINCT symbol_base FROM instruments_v3 "
            "WHERE venue='hyperliquid' AND contract_type='SPOT'"
        ).fetchall()
        con.close()
        if not rows:
            return None
        return {row[0] for row in rows}
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Table formatting
# ---------------------------------------------------------------------------

COLUMNS = [
    ("symbol",      10),
    ("venue",       12),
    ("quality",      8),
    ("stab",         7),
    ("eff_apr",      8),
    ("oi_rank",      7),
    ("be_days",      7),
    ("APR_lat",      8),
    ("APR1d",        8),
    ("APR3d",        8),
    ("APR7",         8),
    ("APR14",        8),
    ("flags",        45),
]


def _fmt(value: str, width: int) -> str:
    return value[:width].ljust(width)


def _header_line() -> str:
    return "  ".join(_fmt(name, width) for name, width in COLUMNS)


def _separator_line() -> str:
    return "  ".join("-" * width for _, width in COLUMNS)


def _format_float(val: float | None, fmt: str = ".1f") -> str:
    if val is None:
        return "-"
    return f"{val:{fmt}}"


def _candidate_row(c: CoreCandidate) -> str:
    cells = [
        _fmt(c.symbol, COLUMNS[0][1]),
        _fmt(c.funding_venue, COLUMNS[1][1]),
        _fmt(_format_float(c.pair_quality_score, ".1f"), COLUMNS[2][1]),
        _fmt(_format_float(c.stability_score, ".1f"), COLUMNS[3][1]),
        _fmt(_format_float(c.effective_apr_anchor, ".2f"), COLUMNS[4][1]),
        _fmt(str(c.oi_rank) if c.oi_rank is not None else "-", COLUMNS[5][1]),
        _fmt(_format_float(c.breakeven_estimate_days, ".1f"), COLUMNS[6][1]),
        _fmt(_format_float(c.apr_latest, ".1f"), COLUMNS[7][1]),
        _fmt(_format_float(c.apr_1d, ".1f"), COLUMNS[8][1]),
        _fmt(_format_float(c.apr_3d, ".1f"), COLUMNS[9][1]),
        _fmt(_format_float(c.apr_7d, ".1f"), COLUMNS[10][1]),
        _fmt(_format_float(c.apr_14d, ".1f"), COLUMNS[11][1]),
        _fmt("|".join(c.flags) if c.flags else "", COLUMNS[12][1]),
    ]
    return "  ".join(cells)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    hyperliquid_spot_symbols = _load_hyperliquid_spot_symbols(args.db)
    bundle = load_core_candidates(
        loris_csv=args.loris_csv,
        felix_cache=args.felix_cache,
        hyperliquid_spot_symbols=hyperliquid_spot_symbols,
    )

    if not bundle.candidates:
        print("No candidates loaded.")
        if bundle.warnings:
            print("Warnings:", " | ".join(bundle.warnings))
        return 1

    latest_ts = max((c.latest_ts for c in bundle.candidates), default=None)
    snapshot = latest_ts.isoformat().replace("+00:00", "Z") if latest_ts else "n/a"

    print("# Core Candidate Export — All Ranked by Quality")
    print(f"Snapshot: {snapshot}")
    print(f"Input State: {bundle.input_state}")
    if bundle.warnings:
        print(f"Warnings: {' | '.join(bundle.warnings)}")

    all_sorted = sorted(
        bundle.candidates,
        key=lambda c: c.pair_quality_score or float("-inf"),
        reverse=True,
    )

    print(f"Total candidates: {len(all_sorted)}")

    if args.csv:
        _export_csv(args.csv, all_sorted, snapshot)
        print(f"\nExported {len(all_sorted)} candidates to {args.csv}")
        return 0

    print(f"\n## All Candidates ({len(all_sorted)})")
    print(_header_line())
    print(_separator_line())
    for c in all_sorted:
        print(_candidate_row(c))

    return 0


CSV_FIELDS = [
    "symbol", "funding_venue", "tradeability_status",
    "pair_quality_score", "stability_score", "effective_apr_anchor",
    "oi_rank", "breakeven_estimate_days",
    "apr_latest", "apr_1d", "apr_3d", "apr_7d", "apr_14d",
    "positive_share",
    "spot_on_hyperliquid", "spot_on_felix",
    "freshness_hours", "flags",
]


def _export_csv(path: Path, candidates: list[CoreCandidate], snapshot: str) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "symbol": c.symbol,
                "funding_venue": c.funding_venue,
                "tradeability_status": c.tradeability_status,
                "pair_quality_score": _format_float(c.pair_quality_score, ".2f"),
                "stability_score": _format_float(c.stability_score, ".2f"),
                "effective_apr_anchor": _format_float(c.effective_apr_anchor, ".2f"),
                "oi_rank": c.oi_rank if c.oi_rank is not None else "",
                "breakeven_estimate_days": _format_float(c.breakeven_estimate_days, ".1f"),
                "apr_latest": _format_float(c.apr_latest, ".2f"),
                "apr_1d": _format_float(c.apr_1d, ".2f"),
                "apr_3d": _format_float(c.apr_3d, ".2f"),
                "apr_7d": _format_float(c.apr_7d, ".2f"),
                "apr_14d": _format_float(c.apr_14d, ".2f"),
                "positive_share": _format_float(c.positive_share, ".1f"),
                "spot_on_hyperliquid": c.spot_on_hyperliquid,
                "spot_on_felix": c.spot_on_felix,
                "freshness_hours": _format_float(c.freshness_hours, ".1f") if hasattr(c, "freshness_hours") and c.freshness_hours is not None else "",
                "flags": "|".join(c.flags) if c.flags else "",
            })


if __name__ == "__main__":
    raise SystemExit(main())
