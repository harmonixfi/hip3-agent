#!/usr/bin/env python3
"""Export Felix Equities candidates with weekday-only data (tradexyz, kinetiq, felix venues)."""

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
from scripts.export_core_candidates import _format_float, CSV_FIELDS

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"

EQUITIES_APPROVED_VENUES = ("tradexyz", "kinetiq", "felix")
EQUITIES_WEEKEND_FILTER_VENUES = frozenset({"tradexyz", "kinetiq", "felix"})


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Export Felix Equities candidates (weekday-only, tradexyz/kinetiq/felix venues).",
    )
    parser.add_argument("--loris-csv", type=Path, default=ROOT / "data" / "loris_funding_history.csv")
    parser.add_argument("--felix-cache", type=Path, default=ROOT / "data" / "felix_equities_cache.json")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--csv", type=Path, default=ROOT / "data" / "equities_candidates_20260420.csv")
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
        return {row[0] for row in rows} if rows else None
    except Exception:
        return None


def main(argv=None) -> int:
    args = parse_args(argv)
    hyperliquid_spot_symbols = _load_hyperliquid_spot_symbols(args.db)

    bundle = load_core_candidates(
        loris_csv=args.loris_csv,
        felix_cache=args.felix_cache,
        hyperliquid_spot_symbols=hyperliquid_spot_symbols,
        approved_venues=EQUITIES_APPROVED_VENUES,
        equity_venues=EQUITIES_WEEKEND_FILTER_VENUES,
        felix_only=True,
    )

    if not bundle.candidates:
        print("No equities candidates loaded.")
        if bundle.warnings:
            print("Warnings:", " | ".join(bundle.warnings))
        return 1

    latest_ts = max((c.latest_ts for c in bundle.candidates), default=None)
    snapshot = latest_ts.isoformat().replace("+00:00", "Z") if latest_ts else "n/a"

    print(f"# Equities Candidate Export")
    print(f"Snapshot: {snapshot}")
    print(f"Venues: {', '.join(EQUITIES_APPROVED_VENUES)} (weekends excluded)")
    print(f"Felix-only: True")
    if bundle.warnings:
        print(f"Warnings: {' | '.join(bundle.warnings)}")

    all_sorted = sorted(
        bundle.candidates,
        key=lambda c: c.pair_quality_score or float("-inf"),
        reverse=True,
    )
    print(f"Total equities candidates: {len(all_sorted)}")

    args.csv.parent.mkdir(parents=True, exist_ok=True)
    with open(args.csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for c in all_sorted:
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
                "freshness_hours": _format_float(c.freshness_hours, ".1f") if c.freshness_hours is not None else "",
                "flags": "|".join(c.flags) if c.flags else "",
            })

    print(f"Exported {len(all_sorted)} equities candidates to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
