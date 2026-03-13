#!/usr/bin/env python3
"""Shared section-report helpers."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, TextIO

SECTION_PORTFOLIO = "portfolio-summary"
SECTION_ROTATION_GENERAL = "rotation-general"
SECTION_ROTATION_EQUITIES = "rotation-equities"

VALID_SECTIONS = (
    SECTION_PORTFOLIO,
    SECTION_ROTATION_GENERAL,
    SECTION_ROTATION_EQUITIES,
)

APR14_MIN_THRESHOLD = 1


@dataclass
class SectionStatus:
    section: str
    state: str
    snapshot_ts: str | None
    warnings: List[str]
    hard_fail: bool


@dataclass
class FlaggedCandidate:
    symbol: str
    exchange: str
    reason: str
    flags: List[str]


@dataclass
class FelixMembership:
    symbols: set[str]
    state: str
    warning: str | None
    snapshot_ts: str | None


@dataclass
class CandidatePoolResult:
    ranked_rows: List[Any]
    flagged_rows: List[FlaggedCandidate]
    status: SectionStatus


def emit_status(status: SectionStatus, stream: TextIO | None = None) -> None:
    if stream is None:
        stream = sys.stderr
    print(json.dumps(asdict(status), sort_keys=True), file=stream)


def _parse_snapshot_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_symbol(raw: Any) -> str:
    symbol = str(raw or "").strip().upper()
    if not symbol:
        return ""
    if ":" in symbol:
        symbol = symbol.split(":", 1)[1]
    if "/" in symbol:
        symbol = symbol.split("/", 1)[0]
    for delimiter in ("-", "_"):
        if delimiter not in symbol:
            continue
        base, suffix = symbol.split(delimiter, 1)
        if suffix in {"PERP", "USD", "USDT", "USDC"}:
            symbol = base
            break
    return symbol


def normalize_exchange(raw: Any) -> str:
    return str(raw or "").strip().lower()


def candidate_identity(symbol: Any, exchange: Any) -> tuple[str, str]:
    return normalize_symbol(symbol), normalize_exchange(exchange)


def build_global_header(statuses: Sequence[SectionStatus], failed_sections: Sequence[str]) -> str:
    all_warnings: List[str] = []
    latest_snapshot = None
    state = "NORMAL"
    for status in statuses:
        parsed_snapshot = _parse_snapshot_ts(status.snapshot_ts)
        if parsed_snapshot and (latest_snapshot is None or parsed_snapshot > latest_snapshot):
            latest_snapshot = parsed_snapshot
        if status.state != "NORMAL":
            state = "DEGRADED"
        all_warnings.extend(status.warnings)
    if failed_sections:
        state = "DEGRADED"
    snapshot_ts = latest_snapshot.isoformat().replace("+00:00", "Z") if latest_snapshot else "n/a"
    lines = [
        "# Daily Funding Report",
        f"State: {state}",
        f"Snapshot: {snapshot_ts}",
        "Timezone: UTC",
    ]
    if failed_sections:
        lines.append("Failed Sections: " + ", ".join(failed_sections))
    if all_warnings:
        lines.append("Warnings: " + " | ".join(all_warnings))
    return "\n".join(lines)


def load_felix_membership(cache_path: Path, *, now: datetime | None = None, max_age_hours: float = 24.0) -> FelixMembership:
    now = now or datetime.now(timezone.utc)
    if not cache_path.exists():
        return FelixMembership(
            symbols=set(),
            state="unavailable",
            warning="Felix classification unavailable; ranked split omitted",
            snapshot_ts=None,
        )

    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return FelixMembership(
            symbols=set(),
            state="unavailable",
            warning=f"Felix classification unavailable; ranked split omitted ({exc})",
            snapshot_ts=None,
        )

    symbols = {normalize_symbol(symbol) for symbol in payload.get("symbols") or [] if normalize_symbol(symbol)}
    snapshot_ts = payload.get("timestamp")
    ts = _parse_snapshot_ts(str(snapshot_ts))
    if ts is None:
        return FelixMembership(
            symbols=symbols,
            state="unavailable",
            warning="Felix classification unavailable; ranked split omitted",
            snapshot_ts=None,
        )

    age_hours = (now - ts).total_seconds() / 3600.0
    if age_hours >= max_age_hours:
        return FelixMembership(
            symbols=symbols,
            state="stale_cache",
            warning="Felix classification stale; split may be outdated",
            snapshot_ts=ts.isoformat(),
        )

    return FelixMembership(
        symbols=symbols,
        state="fresh_cache",
        warning=None,
        snapshot_ts=ts.isoformat(),
    )


def build_flagged_positions(position_rows: List[Dict[str, Any]], carry_warnings: List[str] | None = None) -> List[Dict[str, str]]:
    flagged: List[Dict[str, str]] = []
    if carry_warnings:
        for row in position_rows:
            flagged.append(
                {
                    "symbol": str(row.get("ticker") or "n/a"),
                    "issue": "carry inputs degraded",
                    "mode": "rendered with degraded advisory",
                }
            )
    for row in position_rows:
        if row.get("advisory") == "INVESTIGATE":
            flagged.append(
                {
                    "symbol": str(row.get("ticker") or "n/a"),
                    "issue": str(row.get("reason") or "needs investigation"),
                    "mode": "rendered with fallback values",
                }
            )
        elif row.get("open_fees_usd") is None:
            flagged.append(
                {
                    "symbol": str(row.get("ticker") or "n/a"),
                    "issue": "open fees unresolved",
                    "mode": "rendered with fallback values",
                }
            )
    return flagged


def format_portfolio_summary_row(
    row: Dict[str, Any],
    *,
    fmt_money,
    fmt_days,
    carry_degraded: bool = False,
) -> str:
    advisory = row["advisory"]
    reason = row["reason"]
    if carry_degraded:
        advisory = "INVESTIGATE"
        reason = "carry inputs degraded"
    return (
        f"- {row['ticker']} | venue {row['perp_venue']} | amount {fmt_money(row['amount_usd'])} | "
        f"start {row['start_time']} | avg15d/day {fmt_money(row['avg_15d_funding_usd_per_day'])} | "
        f"1d {fmt_money(row['funding_1d_usd'])} | 2d {fmt_money(row['funding_2d_usd'])} | "
        f"3d {fmt_money(row['funding_3d_usd'])} | open fees {fmt_money(row['open_fees_usd'])} | "
        f"BE {fmt_days(row['breakeven_days'])} | **{advisory}** ({reason})"
    )


def render_portfolio_summary_section(
    *,
    position_rows: List[Dict[str, Any]],
    flagged_positions: List[Dict[str, str]],
    snapshot_ts: str,
    warnings: List[str],
    fmt_money,
    fmt_days,
) -> tuple[str, SectionStatus]:
    lines = ["## Portfolio Summary"]

    if not position_rows:
        lines.append("(no open positions tracked)")
    else:
        carry_degraded = bool(warnings)
        for row in position_rows:
            lines.append(format_portfolio_summary_row(row, fmt_money=fmt_money, fmt_days=fmt_days, carry_degraded=carry_degraded))

    lines.append("")
    lines.append("### Flagged Positions")
    if not flagged_positions:
        lines.append("- (none)")
    else:
        for item in flagged_positions:
            lines.append(f"- {item['symbol']} | {item['issue']} | {item['mode']}")

    state = "DEGRADED" if warnings or flagged_positions else "NORMAL"
    status = SectionStatus(
        section=SECTION_PORTFOLIO,
        state=state,
        snapshot_ts=snapshot_ts,
        warnings=list(warnings),
        hard_fail=False,
    )
    return "\n".join(lines), status


def _candidate_flag_set(candidate: Any) -> set[str]:
    flags = {str(flag).strip().upper() for flag in getattr(candidate, "flags", []) if str(flag).strip()}
    for flag in list(flags):
        if flag.startswith("STALE_"):
            flags.add("STALE")
    return flags


def _candidate_reason(candidate: Any, flags: set[str]) -> str:
    apr_14d = getattr(candidate, "apr_14d", None)
    if apr_14d is None or apr_14d <= APR14_MIN_THRESHOLD:
        if apr_14d is None:
            return f"APR14 n/a <= {APR14_MIN_THRESHOLD:.1f}% threshold"
        return f"APR14 {apr_14d:.2f}% <= {APR14_MIN_THRESHOLD:.1f}% threshold"
    if "STALE" in flags:
        return "stale symbol funding"
    if "LOW_14D_SAMPLE" in flags:
        return "low 14d sample"
    if "LOW_3D_SAMPLE" in flags:
        return "low 3d sample"
    if "BROKEN_PERSISTENCE" in flags:
        return "broken persistence"
    if "SEVERE_STRUCTURE" in flags:
        return "severe structure"
    return "eligible"


def _is_candidate_eligible(candidate: Any) -> bool:
    flags = _candidate_flag_set(candidate)
    apr_14d = getattr(candidate, "apr_14d", None)
    return bool(
        apr_14d is not None
        and apr_14d > APR14_MIN_THRESHOLD
        and "STALE" not in flags
        and "LOW_14D_SAMPLE" not in flags
        and "LOW_3D_SAMPLE" not in flags
        and "BROKEN_PERSISTENCE" not in flags
        and "SEVERE_STRUCTURE" not in flags
    )


def _candidate_matches_section(symbol: str, section: str, membership_symbols: set[str]) -> bool:
    in_felix = symbol in membership_symbols
    if section == SECTION_ROTATION_GENERAL:
        return not in_felix
    if section == SECTION_ROTATION_EQUITIES:
        return in_felix
    return False


def build_candidate_pool(
    *,
    section: str,
    candidates: Sequence[Any],
    held_symbols: Sequence[str],
    top: int,
    candidate_meta: Dict[str, Any],
    membership: FelixMembership,
) -> CandidatePoolResult:
    warnings: List[str] = []
    if candidate_meta.get("reason"):
        warnings.append(str(candidate_meta["reason"]))
    if membership.warning:
        warnings.append(membership.warning)

    held = {normalize_symbol(symbol) for symbol in held_symbols if normalize_symbol(symbol)}
    latest_ts = candidate_meta.get("latest_ts") or membership.snapshot_ts

    flagged_rows: List[FlaggedCandidate] = []
    ranked_rows: List[Any] = []
    can_rank = membership.state in {"fresh_cache", "stale_cache"} and not candidate_meta.get("degraded")
    can_partition_flagged = membership.state in {"fresh_cache", "stale_cache"}

    for candidate in candidates:
        symbol = normalize_symbol(getattr(candidate, "symbol", ""))
        if not symbol or symbol in held:
            continue
        flags = _candidate_flag_set(candidate)
        relevant = can_partition_flagged and _candidate_matches_section(symbol, section, membership.symbols)
        if can_rank and _is_candidate_eligible(candidate) and _candidate_matches_section(symbol, section, membership.symbols):
            ranked_rows.append(candidate)
            continue
        reason = _candidate_reason(candidate, flags)
        if reason == "eligible" and candidate_meta.get("degraded") and relevant:
            reason = str(candidate_meta.get("reason") or "candidate funding degraded")
        if reason != "eligible" and relevant:
            flagged_rows.append(
                FlaggedCandidate(
                    symbol=symbol,
                    exchange=normalize_exchange(getattr(candidate, "exchange", "")),
                    reason=reason,
                    flags=sorted(flags),
                )
            )

    if not can_partition_flagged and any(not _is_candidate_eligible(candidate) for candidate in candidates):
        flagged_rows.append(
            FlaggedCandidate(
                symbol="n/a",
                exchange="n/a",
                reason="flagged candidates could not be partitioned reliably",
                flags=[],
            )
        )

    state = "DEGRADED" if warnings else "NORMAL"
    status = SectionStatus(
        section=section,
        state=state,
        snapshot_ts=latest_ts,
        warnings=warnings,
        hard_fail=False,
    )
    return CandidatePoolResult(ranked_rows=ranked_rows[:top], flagged_rows=flagged_rows, status=status)


def render_rotation_section(
    *,
    section: str,
    ranked_rows: Sequence[Any],
    flagged_rows: Sequence[FlaggedCandidate],
    top: int,
    status: SectionStatus,
    fmt_pct,
) -> tuple[str, SectionStatus]:
    if section == SECTION_ROTATION_GENERAL:
        title = f"## Top {top} Rotation Candidates - General"
        empty_text = "(no eligible general candidates)"
    else:
        title = f"## Top {top} Rotation Candidates - Equities"
        empty_text = "(no eligible equities candidates)"

    lines = [title]
    for warning in status.warnings:
        lines.append(f"Warning: {warning}")

    if not ranked_rows:
        lines.append(empty_text)
    else:
        for idx, candidate in enumerate(ranked_rows, start=1):
            score = getattr(candidate, "stability_score", None)
            score_text = f"{score:.2f}" if score is not None else "n/a"
            flags = getattr(candidate, "flags", [])
            note = ", ".join(flags) if flags else "ok"
            lines.append(
                f"- {idx}. {normalize_symbol(getattr(candidate, 'symbol', ''))} | "
                f"venue {normalize_exchange(getattr(candidate, 'exchange', ''))} | "
                f"APR14 {fmt_pct(getattr(candidate, 'apr_14d', None))} | "
                f"APR7 {fmt_pct(getattr(candidate, 'apr_7d', None))} | "
                f"APR1d {fmt_pct(getattr(candidate, 'apr_1d', None))} | "
                f"APR2d {fmt_pct(getattr(candidate, 'apr_2d', None))} | "
                f"APR3d {fmt_pct(getattr(candidate, 'apr_3d', None))} | "
                f"Score {score_text} | {note}"
            )

    lines.append("")
    lines.append("### Flagged Candidates")
    if not flagged_rows:
        lines.append("- (none)")
    else:
        for flagged in flagged_rows:
            flags_text = ", ".join(flagged.flags) if flagged.flags else "n/a"
            lines.append(f"- {flagged.symbol} | venue {flagged.exchange} | {flagged.reason} | {flags_text}")

    return "\n".join(lines), status
