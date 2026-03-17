"""Core-tier portfolio construction domain logic."""

from __future__ import annotations

import csv
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_daily_funding_sections import load_felix_membership, normalize_symbol
from tracking.analytics.cost_model_v3 import CostModelV3

APPROVED_FUNDING_VENUES = ("hyperliquid", "tradexyz", "hyena", "kinetiq")
FRESHNESS_MAX_HOURS = 12.0
NORMALIZED_BREAKEVEN_NOTIONAL_USD = 150_000.0
SUPPORTED_FLAGS = {
    "STALE_DATA",
    "MISSING_APR_WINDOW",
    "MISSING_SPOT",
    "CROSS_CHECK_NEEDED",
    "SHORT_HISTORY",
    "DECAYING_REGIME",
    "HIGH_BREAKEVEN",
    "LOW_LIQUIDITY_CONFIDENCE",
    "VENUE_DATA_MISSING",
}


@dataclass
class CoreCandidate:
    symbol: str
    funding_venue: str
    latest_ts: datetime
    apr_latest: float | None
    apr_1d: float | None
    apr_3d: float | None
    apr_7d: float | None
    apr_14d: float | None
    apr_30d: float | None
    oi_rank: int | None
    spot_on_hyperliquid: bool
    spot_on_felix: bool
    tradeability_status: str
    flags: list[str]
    freshness_hours: float | None = None
    history_days: float = 0.0
    funding_observation_count: int = 0
    funding_consistency_score: float | None = None
    trend_alignment_score: float | None = None
    liquidity_score: float | None = None
    effective_apr_score: float | None = None
    breakeven_score: float | None = None
    stability_score: float | None = None
    pair_quality_score: float | None = None
    effective_apr_anchor: float | None = None
    breakeven_estimate_days: float | None = None
    breakeven_notional_usd: float | None = None
    funding_samples: list[tuple[datetime, float, int | None]] = field(default_factory=list)


@dataclass
class CandidateBundle:
    input_state: str
    warnings: list[str]
    candidates: list[CoreCandidate]


def passes_shared_data_gate(candidate: CoreCandidate) -> bool:
    return (
        candidate.freshness_hours is not None
        and candidate.freshness_hours < FRESHNESS_MAX_HOURS
        and None not in (candidate.apr_latest, candidate.apr_7d, candidate.apr_14d)
        and "STALE_DATA" not in candidate.flags
        and "MISSING_APR_WINDOW" not in candidate.flags
    )


def _now_utc(now: datetime | None = None) -> datetime:
    return now if now is not None else datetime.now(timezone.utc)


def _parse_timestamp(raw: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def annualize_apr(rate_8h: float | None) -> float | None:
    if rate_8h is None:
        return None
    return rate_8h * 3.0 * 365.0 * 100.0


def average_rate(samples: list[tuple[datetime, float]], since_dt: datetime) -> float | None:
    values = [rate for ts, rate in samples if ts >= since_dt]
    return (sum(values) / len(values)) if values else None


def _dedupe_flags(flags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for flag in flags:
        if not flag or flag in seen:
            continue
        seen.add(flag)
        ordered.append(flag)
    return ordered


def _load_funding_groups(
    loris_csv: Path,
) -> tuple[dict[tuple[str, str], list[tuple[datetime, float, int | None]]], set[str]]:
    grouped: dict[tuple[str, str], list[tuple[datetime, float, int | None]]] = {}
    seen_venues: set[str] = set()
    if not loris_csv.exists():
        return grouped, seen_venues

    with loris_csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            venue = str(row.get("exchange") or "").strip().lower()
            if venue not in APPROVED_FUNDING_VENUES:
                continue
            seen_venues.add(venue)
            symbol = normalize_symbol(row.get("symbol") or "")
            ts = _parse_timestamp(row.get("timestamp_utc") or "")
            if not symbol or ts is None:
                continue
            try:
                rate = float(row.get("funding_8h_rate") or "")
            except (TypeError, ValueError):
                continue
            oi_rank_raw = row.get("oi_rank")
            try:
                oi_rank = int(oi_rank_raw) if oi_rank_raw and int(oi_rank_raw) != 9999 else None
            except (TypeError, ValueError):
                oi_rank = None
            grouped.setdefault((venue, symbol), []).append((ts, rate, oi_rank))

    for samples in grouped.values():
        samples.sort(key=lambda item: item[0])
    return grouped, seen_venues


def resolve_tradeability(
    symbol: str,
    *,
    spot_on_hyperliquid: bool,
    spot_on_felix: bool,
    hyperliquid_spot_known: bool,
) -> tuple[str, list[str]]:
    del symbol
    if spot_on_hyperliquid or spot_on_felix:
        return "EXECUTABLE", []
    if hyperliquid_spot_known:
        return "NON_EXECUTABLE", ["MISSING_SPOT"]
    return "CROSS_CHECK_NEEDED", ["MISSING_SPOT", "CROSS_CHECK_NEEDED"]


def _oi_rank_to_score(oi_rank: int | None) -> tuple[float, list[str]]:
    if oi_rank is None:
        return 25.0, ["LOW_LIQUIDITY_CONFIDENCE"]
    if oi_rank <= 10:
        return 100.0, []
    if oi_rank <= 25:
        return 85.0, []
    if oi_rank <= 50:
        return 70.0, []
    if oi_rank <= 100:
        return 50.0, []
    if oi_rank <= 150:
        return 35.0, []
    return 20.0, []


def _trend_alignment_score(candidate: CoreCandidate) -> tuple[float, list[str]]:
    if None in (candidate.apr_latest, candidate.apr_7d, candidate.apr_14d):
        return 0.0, ["MISSING_APR_WINDOW"]
    latest = candidate.apr_latest or 0.0
    apr_7d = candidate.apr_7d or 0.0
    apr_14d = candidate.apr_14d or 0.0
    if latest <= 0 or apr_7d <= 0 or apr_14d <= 0:
        return 0.0, ["DECAYING_REGIME"] if latest <= 0 else []
    if latest < apr_7d < apr_14d:
        return 30.0, ["DECAYING_REGIME"]
    if latest >= apr_7d >= apr_14d:
        return 100.0, []
    if latest >= 0.85 * apr_7d and apr_7d >= 0.85 * apr_14d:
        return 80.0, []
    if latest >= 0.6 * apr_7d and apr_7d >= 0.6 * apr_14d:
        return 55.0, []
    return 40.0, ["DECAYING_REGIME"]


def _funding_consistency_score(
    samples: list[tuple[datetime, float, int | None]],
    latest_ts: datetime,
) -> tuple[float, list[str]]:
    if not samples:
        return 0.0, ["SHORT_HISTORY", "MISSING_APR_WINDOW"]
    lookback_days = 30 if (latest_ts - samples[0][0]).days >= 30 else 14
    since_dt = latest_ts - timedelta(days=lookback_days)
    relevant = [rate for ts, rate, _ in samples if ts >= since_dt]
    if not relevant:
        return 0.0, ["SHORT_HISTORY"]
    positive_share = sum(1 for rate in relevant if rate > 0) / len(relevant)
    sign_flips = sum(
        1
        for idx in range(1, len(relevant))
        if (relevant[idx - 1] > 0) != (relevant[idx] > 0)
    )
    flip_penalty = min(30.0, sign_flips * 5.0)
    short_history_flag = ["SHORT_HISTORY"] if lookback_days == 14 else []
    return max(0.0, positive_share * 100.0 - flip_penalty), short_history_flag


def compute_stability_score(candidate: CoreCandidate) -> float | None:
    if None in (candidate.apr_latest, candidate.apr_7d, candidate.apr_14d):
        return None
    return 0.55 * candidate.apr_14d + 0.30 * candidate.apr_7d + 0.15 * candidate.apr_latest


def estimate_breakeven_days(
    candidate: CoreCandidate,
    *,
    normalized_lot_usd: float = NORMALIZED_BREAKEVEN_NOTIONAL_USD,
) -> float | None:
    effective_apr_anchor = (candidate.apr_14d / 2.0) if candidate.apr_14d is not None else None
    if effective_apr_anchor is None or effective_apr_anchor <= 0:
        return None

    spot_venue = "hyperliquid" if candidate.spot_on_hyperliquid else "felix"
    model = CostModelV3()
    try:
        total_cost = model.calculate_entry_exit_cost(
            venue_1=spot_venue,
            product_type_1="spot",
            venue_2=candidate.funding_venue,
            product_type_2="perp",
        )["total_bps"]
        total_roundtrip_cost_usd = normalized_lot_usd * total_cost / 10_000.0
    except KeyError:
        try:
            total_roundtrip_cost_usd = (
                normalized_lot_usd * model.get_fee_bps(spot_venue, "spot", is_maker=False) / 10_000.0
                + normalized_lot_usd * model.get_fee_bps(candidate.funding_venue, "perp", is_maker=False) / 10_000.0
            ) * 2.0
        except KeyError:
            return None

    daily_net_funding = normalized_lot_usd * (effective_apr_anchor / 100.0) / 365.0
    if daily_net_funding <= 0:
        return None
    return total_roundtrip_cost_usd / daily_net_funding


def _effective_apr_score(effective_apr_anchor: float | None) -> float:
    if effective_apr_anchor is None or effective_apr_anchor <= 0:
        return 0.0
    return min(100.0, (effective_apr_anchor / 20.0) * 100.0)


def _breakeven_score(days: float | None) -> tuple[float, list[str]]:
    if days is None:
        return 0.0, ["HIGH_BREAKEVEN"]
    if days <= 3:
        return 100.0, []
    if days <= 7:
        return 80.0, []
    if days <= 10:
        return 60.0, ["HIGH_BREAKEVEN"]
    if days <= 14:
        return 40.0, ["HIGH_BREAKEVEN"]
    return 15.0, ["HIGH_BREAKEVEN"]


def compute_pair_quality_score(candidate: CoreCandidate) -> float | None:
    if None in (candidate.apr_latest, candidate.apr_7d, candidate.apr_14d):
        return None
    if candidate.funding_consistency_score is None:
        return None
    if candidate.trend_alignment_score is None:
        return None
    if candidate.liquidity_score is None:
        return None
    if candidate.effective_apr_score is None:
        return None
    if candidate.breakeven_score is None:
        return None
    return (
        0.30 * candidate.funding_consistency_score
        + 0.25 * candidate.trend_alignment_score
        + 0.20 * candidate.liquidity_score
        + 0.15 * candidate.effective_apr_score
        + 0.10 * candidate.breakeven_score
    )


def score_candidate(candidate: CoreCandidate) -> CoreCandidate:
    candidate.stability_score = compute_stability_score(candidate)
    candidate.effective_apr_anchor = (
        (candidate.apr_14d / 2.0) if candidate.apr_14d is not None else None
    )

    consistency_score, consistency_flags = _funding_consistency_score([], candidate.latest_ts)
    if candidate.funding_observation_count > 0 and candidate.funding_samples:
        consistency_score, consistency_flags = _funding_consistency_score(
            candidate.funding_samples,
            candidate.latest_ts,
        )
    candidate.funding_consistency_score = consistency_score

    trend_score, trend_flags = _trend_alignment_score(candidate)
    candidate.trend_alignment_score = trend_score

    liquidity_score, liquidity_flags = _oi_rank_to_score(candidate.oi_rank)
    candidate.liquidity_score = liquidity_score

    candidate.effective_apr_score = _effective_apr_score(candidate.effective_apr_anchor)
    candidate.breakeven_estimate_days = estimate_breakeven_days(candidate)
    candidate.breakeven_notional_usd = NORMALIZED_BREAKEVEN_NOTIONAL_USD
    breakeven_score, breakeven_flags = _breakeven_score(candidate.breakeven_estimate_days)
    candidate.breakeven_score = breakeven_score

    candidate.flags = _dedupe_flags(
        list(candidate.flags) + consistency_flags + trend_flags + liquidity_flags + breakeven_flags
    )
    candidate.pair_quality_score = compute_pair_quality_score(candidate)
    return candidate


def load_core_candidates(
    *,
    loris_csv: Path,
    felix_cache: Path,
    now: datetime | None = None,
    hyperliquid_spot_symbols: set[str] | None = None,
) -> CandidateBundle:
    now_utc = _now_utc(now)
    if not loris_csv.exists():
        return CandidateBundle("DEGRADED", ["missing loris csv"], [])

    grouped, seen_venues = _load_funding_groups(loris_csv)
    if not grouped:
        return CandidateBundle("DEGRADED", ["no valid funding rows in csv"], [])

    warnings: list[str] = []
    for venue in APPROVED_FUNDING_VENUES:
        if venue not in seen_venues:
            warnings.append(f"VENUE_DATA_MISSING:{venue}")

    felix_membership = load_felix_membership(felix_cache, now=now_utc)
    felix_symbols = felix_membership.symbols
    if felix_membership.warning:
        warnings.append(felix_membership.warning)
    if hyperliquid_spot_symbols is None:
        warnings.append("Hyperliquid spot availability unresolved; executable spot checks are partial")

    spot_symbols = {normalize_symbol(symbol) for symbol in (hyperliquid_spot_symbols or set())}
    hyperliquid_spot_known = hyperliquid_spot_symbols is not None
    candidates: list[CoreCandidate] = []

    for (venue, symbol), samples in sorted(grouped.items()):
        latest_ts, latest_rate, oi_rank = samples[-1]
        latest_hours = (now_utc - latest_ts).total_seconds() / 3600.0
        apr_latest = annualize_apr(latest_rate)
        avg_7d = average_rate([(ts, rate) for ts, rate, _ in samples], latest_ts - timedelta(days=7))
        avg_14d = average_rate([(ts, rate) for ts, rate, _ in samples], latest_ts - timedelta(days=14))
        avg_30d = average_rate([(ts, rate) for ts, rate, _ in samples], latest_ts - timedelta(days=30))
        apr_7d = annualize_apr(avg_7d) if avg_7d is not None and len(samples) >= 2 else None
        apr_14d = annualize_apr(avg_14d) if avg_14d is not None and (latest_ts - samples[0][0]).total_seconds() >= 14 * 86400 else None
        apr_30d = annualize_apr(avg_30d) if avg_30d is not None and (latest_ts - samples[0][0]).total_seconds() >= 30 * 86400 else None
        avg_1d = average_rate([(ts, rate) for ts, rate, _ in samples], latest_ts - timedelta(days=1))
        avg_3d = average_rate([(ts, rate) for ts, rate, _ in samples], latest_ts - timedelta(days=3))
        apr_1d = annualize_apr(avg_1d) if avg_1d is not None and len(samples) >= 2 else None
        apr_3d = annualize_apr(avg_3d) if avg_3d is not None and len(samples) >= 2 else None

        spot_on_hyperliquid = symbol in spot_symbols
        spot_on_felix = symbol in felix_symbols
        tradeability_status, tradeability_flags = resolve_tradeability(
            symbol,
            spot_on_hyperliquid=spot_on_hyperliquid,
            spot_on_felix=spot_on_felix,
            hyperliquid_spot_known=hyperliquid_spot_known,
        )

        flags = list(tradeability_flags)
        if latest_hours >= FRESHNESS_MAX_HOURS:
            flags.append("STALE_DATA")
        if None in (apr_latest, apr_7d, apr_14d):
            flags.append("MISSING_APR_WINDOW")
        history_days = max(0.0, (latest_ts - samples[0][0]).total_seconds() / 86400.0)
        if history_days < 14:
            flags.append("SHORT_HISTORY")

        candidate = CoreCandidate(
            symbol=symbol,
            funding_venue=venue,
            latest_ts=latest_ts,
            apr_latest=apr_latest,
            apr_1d=apr_1d,
            apr_3d=apr_3d,
            apr_7d=apr_7d,
            apr_14d=apr_14d,
            apr_30d=apr_30d,
            oi_rank=oi_rank,
            spot_on_hyperliquid=spot_on_hyperliquid,
            spot_on_felix=spot_on_felix,
            tradeability_status=tradeability_status,
            flags=_dedupe_flags(flags),
            freshness_hours=latest_hours,
            history_days=history_days,
            funding_observation_count=len(samples),
            funding_samples=list(samples),
        )
        candidates.append(score_candidate(candidate))

    input_state = "NORMAL" if not warnings else "DEGRADED"
    return CandidateBundle(input_state=input_state, warnings=warnings, candidates=candidates)


