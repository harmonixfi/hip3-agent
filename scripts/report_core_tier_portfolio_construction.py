#!/usr/bin/env python3
"""CLI report for Core-tier portfolio construction analysis."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.core_tier_portfolio_construction import (
    CoreCandidate,
    StrategyBasket,
    StrategyVerdict,
    build_strategy_2_basket,
    build_strategy_3_basket,
    compare_strategy_baskets,
    load_core_candidates,
)


@dataclass
class AnalysisResult:
    snapshot_ts: str
    input_state: str
    warnings: list[str]
    candidates: list[CoreCandidate]
    strategy_3_basket: StrategyBasket
    strategy_2_basket: StrategyBasket
    excluded_candidates: list[CoreCandidate]
    verdict: StrategyVerdict


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loris-csv", type=Path, default=ROOT / "data" / "loris_funding_history.csv")
    parser.add_argument("--felix-cache", type=Path, default=ROOT / "data" / "felix_equities_cache.json")
    parser.add_argument("--portfolio-capital", type=float, default=1_000_000)
    parser.add_argument("--core-capital", type=float, default=600_000)
    return parser.parse_args(argv)


def _format_basket(basket: StrategyBasket, *, core_capital_usd: float) -> str:
    deployed_capital = sum(position.capital_usd for position in basket.positions)
    lines = []
    if not basket.positions:
        lines.append("  (empty basket)")
    for position in basket.positions:
        lines.append(
            f"  - {position.symbol} @ {position.funding_venue}: "
            f"${position.capital_usd:,.0f} ({position.weight * 100:.1f}%)"
        )
    lines.append(f"  Deployed Capital: ${deployed_capital:,.0f}")
    lines.append(f"  Idle Capital: ${basket.idle_capital_usd:,.0f}")
    if basket.idle_capital_usd > 0:
        lines.append(f"  - Residual idle capital remains unallocated by basket rules")
    if basket.weighted_pair_quality_score is not None:
        lines.append(f"  Weighted Pair Quality: {basket.weighted_pair_quality_score:.1f}")
    if basket.weighted_stability_score is not None:
        lines.append(f"  Weighted Stability: {basket.weighted_stability_score:.1f}")
    if basket.weighted_effective_apr is not None:
        lines.append(f"  Weighted Effective APR: {basket.weighted_effective_apr:.2f}%")
    deploy_ratio = 1.0 - (basket.idle_capital_usd / max(core_capital_usd, 1.0))
    lines.append(f"  Deploy Ratio: {deploy_ratio:.0%}")
    lines.append(f"  Execution Uncertainty Count: {basket.execution_uncertainty_count}")
    lines.append(f"  Decay Concern Count: {basket.decay_concern_count}")
    return "\n".join(lines)


def _format_candidate(candidate: CoreCandidate) -> str:
    flags = ",".join(candidate.flags) if candidate.flags else "none"
    quality = "n/a" if candidate.pair_quality_score is None else f"{candidate.pair_quality_score:.1f}"
    effective = "n/a" if candidate.effective_apr_anchor is None else f"{candidate.effective_apr_anchor:.2f}%"
    return (
        f"  - {candidate.symbol} @ {candidate.funding_venue}: "
        f"tradeability={candidate.tradeability_status}, "
        f"quality={quality}, effective_apr={effective}, flags={flags}"
    )


def _candidate_lookup(candidates: list[CoreCandidate]) -> dict[tuple[str, str], CoreCandidate]:
    return {(candidate.symbol, candidate.funding_venue): candidate for candidate in candidates}


def _position_rationale(candidate: CoreCandidate) -> str:
    reasons: list[str] = []
    if candidate.tradeability_status == "EXECUTABLE":
        reasons.append("executable spot-plus-perp path")
    if candidate.pair_quality_score is not None:
        reasons.append(f"pair quality {candidate.pair_quality_score:.1f}")
    if candidate.stability_score is not None:
        reasons.append(f"stability {candidate.stability_score:.1f}")
    if candidate.effective_apr_anchor is not None:
        reasons.append(f"effective APR {candidate.effective_apr_anchor:.2f}%")
    if "SHORT_HISTORY" in candidate.flags:
        reasons.append("shorter history evidence")
    if "DECAYING_REGIME" in candidate.flags:
        reasons.append("decay risk flagged")
    return ", ".join(reasons) if reasons else "included by basket ranking"


def _format_basket_rationales(basket: StrategyBasket, candidates: list[CoreCandidate]) -> str:
    if not basket.positions:
        return "  (no included names)"
    by_key = _candidate_lookup(candidates)
    lines: list[str] = []
    for position in basket.positions:
        candidate = by_key.get((position.symbol, position.funding_venue))
        rationale = _position_rationale(candidate) if candidate is not None else "included by basket ranking"
        lines.append(f"  - {position.symbol}: {rationale}")
    return "\n".join(lines)


def _winner_basket(verdict: StrategyVerdict, strategy_3_basket: StrategyBasket, strategy_2_basket: StrategyBasket) -> StrategyBasket | None:
    if verdict.method_verdict == "STRATEGY_3":
        return strategy_3_basket
    if verdict.method_verdict == "STRATEGY_2":
        return strategy_2_basket
    return None


def render_core_tier_report(result: AnalysisResult, *, portfolio_capital: float, core_capital: float) -> str:
    shortlist_lines = ["  (no deployable shortlist)"]
    winner = _winner_basket(result.verdict, result.strategy_3_basket, result.strategy_2_basket)
    if winner and winner.positions:
        shortlist_lines = [
            f"  - {position.symbol} @ {position.funding_venue}: ${position.capital_usd:,.0f} ({position.weight * 100:.1f}%)"
            for position in winner.positions
        ]
        if winner.idle_capital_usd > 0:
            shortlist_lines.append(f"  - IDLE: ${winner.idle_capital_usd:,.0f}")

    excluded = result.excluded_candidates or []
    excluded_block = "\n".join(_format_candidate(candidate) for candidate in excluded[:25]) if excluded else "  (none)"
    warning_line = "none" if not result.warnings else " | ".join(result.warnings)
    rationale = " ".join(result.verdict.rationale) if result.verdict.rationale else "n/a"
    lines = [
        "# Core Tier Portfolio Construction Test",
        f"Snapshot: {result.snapshot_ts}",
        "Timezone: UTC",
        f"Input State: {result.input_state}",
        f"Warnings: {warning_line}",
        f"Portfolio Capital: ${portfolio_capital:,.0f}",
        f"Core Capital: ${core_capital:,.0f}",
        "",
        "## Core Shortlist Recommendation",
        *shortlist_lines,
        "",
        "## Strategy 3 Basket",
        _format_basket(result.strategy_3_basket, core_capital_usd=core_capital),
        "### Inclusion Rationale",
        _format_basket_rationales(result.strategy_3_basket, result.candidates),
        "",
        "## Strategy 2 Basket",
        _format_basket(result.strategy_2_basket, core_capital_usd=core_capital),
        "### Inclusion Rationale",
        _format_basket_rationales(result.strategy_2_basket, result.candidates),
        "",
        "## Near-Miss And Excluded Candidates",
        excluded_block,
        "",
        f"Method Verdict: {result.verdict.method_verdict}",
        f"Deployment Verdict: {result.verdict.deployment_verdict}",
        f"Rationale: {rationale}",
    ]
    return "\n".join(lines)


def run_analysis(
    *,
    loris_csv: Path,
    felix_cache: Path,
    portfolio_capital: float,
    core_capital: float,
) -> AnalysisResult:
    del portfolio_capital
    bundle = load_core_candidates(loris_csv=loris_csv, felix_cache=felix_cache)
    strategy_2_basket = build_strategy_2_basket(bundle.candidates, core_capital_usd=core_capital)
    strategy_3_basket = build_strategy_3_basket(bundle.candidates, core_capital_usd=core_capital)
    selected = {
        (position.symbol, position.funding_venue)
        for position in strategy_2_basket.positions + strategy_3_basket.positions
    }
    excluded_candidates = [
        candidate
        for candidate in bundle.candidates
        if (candidate.symbol, candidate.funding_venue) not in selected
    ]
    latest_ts = max((candidate.latest_ts for candidate in bundle.candidates), default=None)
    snapshot_ts = latest_ts.isoformat().replace("+00:00", "Z") if latest_ts else "n/a"
    verdict = compare_strategy_baskets(strategy_3_basket, strategy_2_basket)
    return AnalysisResult(
        snapshot_ts=snapshot_ts,
        input_state=bundle.input_state,
        warnings=bundle.warnings,
        candidates=bundle.candidates,
        strategy_3_basket=strategy_3_basket,
        strategy_2_basket=strategy_2_basket,
        excluded_candidates=excluded_candidates,
        verdict=verdict,
    )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    result = run_analysis(
        loris_csv=args.loris_csv,
        felix_cache=args.felix_cache,
        portfolio_capital=args.portfolio_capital,
        core_capital=args.core_capital,
    )
    print(
        render_core_tier_report(
            result,
            portfolio_capital=args.portfolio_capital,
            core_capital=args.core_capital,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
