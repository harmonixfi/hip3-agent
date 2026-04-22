"""
Audit data/loris_funding_history.csv for quality issues:
- Per-venue coverage summary
- Gaps > 2 days within a symbol series
- Stale symbols (latest row > 12h ago)
- Low sample count (< 16 rows in last 14 days)
- Felix equity coverage
"""

import csv
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

CSV_PATH = Path("data/loris_funding_history.csv")
FELIX_CACHE = Path("data/felix_equities_cache.json")
REPORT_OUT = Path("docs/reports/loris_data_quality.md")

STALE_HOURS = 12.0
GAP_DAYS = 2.0
SAMPLE_14D_MIN = 16

# Legacy mislabeled data: these symbols appear under venue=hyperliquid but were
# actually tradexyz/felix/kinetiq. They stopped ~2026-01-14. Ignore them.
LEGACY_HL_CUTOFF = datetime(2026, 2, 1, tzinfo=timezone.utc)

now = datetime.now(timezone.utc)
cutoff_14d = now - timedelta(days=14)


def load_series() -> dict[tuple[str, str], list[datetime]]:
    series: dict[tuple[str, str], list[datetime]] = defaultdict(list)
    with open(CSV_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp_utc"].replace("Z", "+00:00"))
            series[(row["exchange"], row["symbol"])].append(ts)
    for key in series:
        series[key].sort()
    # Drop legacy mislabeled hyperliquid stock rows
    legacy = {k for k, tss in series.items() if k[0] == "hyperliquid" and max(tss) < LEGACY_HL_CUTOFF}
    for k in legacy:
        del series[k]
    return series


def find_gaps(timestamps: list[datetime], threshold_days: float) -> list[tuple[datetime, datetime, float]]:
    gaps = []
    for i in range(1, len(timestamps)):
        delta_h = (timestamps[i] - timestamps[i - 1]).total_seconds() / 3600
        if delta_h > threshold_days * 24:
            gaps.append((timestamps[i - 1], timestamps[i], delta_h))
    return gaps


def hours_stale(timestamps: list[datetime]) -> float:
    return (now - timestamps[-1]).total_seconds() / 3600


def sample_count_14d(timestamps: list[datetime]) -> int:
    return sum(1 for ts in timestamps if ts >= cutoff_14d)


def fmt_ts(ts: datetime) -> str:
    return ts.strftime("%Y-%m-%d %H:%M UTC")


def main():
    print(f"Loading {CSV_PATH} ...")
    series = load_series()
    print(f"Loaded {sum(len(v) for v in series.values()):,} rows, {len(series):,} (exchange, symbol) pairs")

    felix_equities: list[str] = []
    if FELIX_CACHE.exists():
        felix_equities = json.loads(FELIX_CACHE.read_text())["symbols"]

    # ── per-venue aggregation ──────────────────────────────────────────────
    venues = sorted({k[0] for k in series})
    venue_stats: dict[str, dict] = {}
    for venue in venues:
        keys = [(v, s) for (v, s) in series if v == venue]
        all_ts = [ts for k in keys for ts in series[k]]
        all_ts.sort()
        stale_count = sum(1 for k in keys if hours_stale(series[k]) >= STALE_HOURS)
        gap_count = sum(1 for k in keys if find_gaps(series[k], GAP_DAYS))
        venue_stats[venue] = {
            "symbols": len(keys),
            "rows": len(all_ts),
            "first": all_ts[0],
            "last": all_ts[-1],
            "stale": stale_count,
            "with_gaps": gap_count,
        }

    # ── per-symbol issues ──────────────────────────────────────────────────
    stale_rows: list[tuple] = []
    gap_rows: list[tuple] = []
    low_sample_rows: list[tuple] = []

    for (venue, symbol), timestamps in sorted(series.items()):
        h = hours_stale(timestamps)
        if h >= STALE_HOURS:
            stale_rows.append((venue, symbol, timestamps[-1], h))

        for gap_start, gap_end, gap_h in find_gaps(timestamps, GAP_DAYS):
            gap_rows.append((venue, symbol, gap_start, gap_end, gap_h))

        n14 = sample_count_14d(timestamps)
        if n14 < SAMPLE_14D_MIN:
            low_sample_rows.append((venue, symbol, n14))

    # sort for readability
    stale_rows.sort(key=lambda x: -x[3])
    gap_rows.sort(key=lambda x: -x[4])
    low_sample_rows.sort(key=lambda x: x[2])

    # ── Felix equity coverage ──────────────────────────────────────────────
    # Felix equities are spot equity tokens — a symbol counts as covered if it
    # appears in ANY venue (tradexyz, felix, kinetiq, hyena, hyperliquid)
    all_symbols_in_csv = {s for (v, s) in series}
    felix_in_csv = all_symbols_in_csv  # coverage is cross-venue
    felix_missing = [s for s in felix_equities if s not in all_symbols_in_csv]
    felix_missing.sort()

    # ── write report ───────────────────────────────────────────────────────
    lines: list[str] = []

    def h(text: str):
        lines.append(text)

    h(f"# Loris Funding Data Quality Report")
    h(f"")
    h(f"**Generated:** {fmt_ts(now)}  ")
    h(f"**CSV path:** `{CSV_PATH}`  ")
    h(f"**CSV latest row:** {fmt_ts(max(ts for tss in series.values() for ts in tss))}  ")
    h(f"**Staleness threshold:** {STALE_HOURS:.0f}h  ")
    h(f"**Gap threshold:** {GAP_DAYS:.0f} days  ")
    h(f"")

    # overall health banner
    total_issues = len(stale_rows) + len(gap_rows) + len(low_sample_rows)
    if total_issues == 0:
        h(f"> **STATUS: CLEAN** — no staleness, gaps, or low-sample issues detected.")
    else:
        h(f"> **STATUS: ISSUES FOUND** — {len(stale_rows)} stale symbols, {len(gap_rows)} gap events, {len(low_sample_rows)} low-sample symbols.")
    h(f"")

    # ── venue summary ──────────────────────────────────────────────────────
    h(f"## Venue Summary")
    h(f"")
    h(f"| Venue | Symbols | Total Rows | Date Range | Stale (>{STALE_HOURS:.0f}h) | With Gaps (>{GAP_DAYS:.0f}d) |")
    h(f"|-------|---------|------------|------------|--------|-----------|")
    for venue in venues:
        s = venue_stats[venue]
        date_range = f"{s['first'].strftime('%Y-%m-%d')} → {s['last'].strftime('%Y-%m-%d')}"
        h(f"| {venue} | {s['symbols']:,} | {s['rows']:,} | {date_range} | {s['stale']} | {s['with_gaps']} |")
    h(f"")

    # ── Felix equity coverage ──────────────────────────────────────────────
    h(f"## Felix Equity Coverage")
    h(f"")
    h(f"- **Total Felix equities defined:** {len(felix_equities)}")
    h(f"- **Symbols with data in CSV (any venue):** {len([s for s in felix_equities if s in all_symbols_in_csv])}")
    h(f"- **Symbols MISSING from CSV (all venues):** {len(felix_missing)}")
    h(f"")
    if felix_missing:
        h(f"Missing symbols (no rows in any venue):")
        h(f"")
        # group in rows of 10 for readability
        for i in range(0, len(felix_missing), 10):
            h(f"`{'`, `'.join(felix_missing[i:i+10])}`")
        h(f"")
    else:
        h(f"All Felix equities have data in CSV.")
        h(f"")

    # ── stale symbols ──────────────────────────────────────────────────────
    h(f"## Stale Symbols (latest row > {STALE_HOURS:.0f}h ago)")
    h(f"")
    if stale_rows:
        h(f"| Venue | Symbol | Last Row | Hours Stale |")
        h(f"|-------|--------|----------|-------------|")
        for venue, symbol, last_ts, h_stale in stale_rows:
            h(f"| {venue} | {symbol} | {fmt_ts(last_ts)} | {h_stale:.1f}h |")
    else:
        h(f"No stale symbols.")
    h(f"")

    # ── gap report ─────────────────────────────────────────────────────────
    h(f"## Gap Report (gaps > {GAP_DAYS:.0f} days within a series)")
    h(f"")
    if gap_rows:
        h(f"| Venue | Symbol | Gap Start | Gap End | Gap (hours) |")
        h(f"|-------|--------|-----------|---------|-------------|")
        for venue, symbol, g_start, g_end, g_h in gap_rows:
            h(f"| {venue} | {symbol} | {fmt_ts(g_start)} | {fmt_ts(g_end)} | {g_h:.1f}h |")
    else:
        h(f"No gaps > {GAP_DAYS:.0f} days found.")
    h(f"")

    # ── low sample ─────────────────────────────────────────────────────────
    h(f"## Low Sample (< {SAMPLE_14D_MIN} rows in last 14 days)")
    h(f"")
    if low_sample_rows:
        h(f"| Venue | Symbol | Rows (14d) |")
        h(f"|-------|--------|------------|")
        for venue, symbol, n in low_sample_rows:
            h(f"| {venue} | {symbol} | {n} |")
    else:
        h(f"All symbols have ≥ {SAMPLE_14D_MIN} rows in the last 14 days.")
    h(f"")

    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text("\n".join(lines))
    print(f"Report written to {REPORT_OUT}")

    # console summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    for venue in venues:
        s = venue_stats[venue]
        print(f"  {venue:15s}  {s['symbols']:3d} symbols  {s['rows']:7,} rows  "
              f"last: {s['last'].strftime('%Y-%m-%d %H:%M')}")
    covered = len([s for s in felix_equities if s in all_symbols_in_csv])
    print(f"\nFélix equities: {covered}/{len(felix_equities)} covered across all venues "
          f"({len(felix_missing)} missing)")
    print(f"Stale:     {len(stale_rows)}")
    print(f"Gaps:      {len(gap_rows)}")
    print(f"Low sample:{len(low_sample_rows)}")


if __name__ == "__main__":
    main()
