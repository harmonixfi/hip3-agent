#!/usr/bin/env python3
"""Deterministic regression script for core-tier portfolio construction."""

from __future__ import annotations

import json
import math
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core_tier_portfolio_construction import (
    NORMALIZED_BREAKEVEN_NOTIONAL_USD,
    BasketPosition,
    CoreCandidate,
    StrategyBasket,
    annualize_apr,
    average_rate,
    build_strategy_2_basket,
    build_strategy_3_basket,
    compare_strategy_baskets,
    compute_stability_score,
    estimate_breakeven_days,
    load_core_candidates,
    resolve_tradeability,
    score_candidate,
)


def assert_close(actual: float, expected: float, *, rel: float = 1e-6) -> None:
    if not math.isclose(actual, expected, rel_tol=rel, abs_tol=rel):
        raise AssertionError(f"expected {expected}, got {actual}")


def build_loris_fixture(tmp_path: Path, rows: list[tuple[str, str, str, int | None, float]]) -> Path:
    loris_csv = tmp_path / "loris.csv"
    lines = ["timestamp_utc,exchange,symbol,oi_rank,funding_8h_scaled,funding_8h_rate\n"]
    for ts, exchange, symbol, oi_rank, rate in rows:
        scaled = rate * 10000.0
        oi_str = "9999" if oi_rank is None else str(oi_rank)
        lines.append(f"{ts},{exchange},{symbol},{oi_str},{scaled},{rate}\n")
    loris_csv.write_text("".join(lines), encoding="utf-8")
    return loris_csv


def build_felix_fixture(tmp_path: Path, symbols: list[str]) -> Path:
    felix_cache = tmp_path / "felix.json"
    felix_cache.write_text(
        json.dumps(
            {
                "timestamp": "2026-03-12T16:00:00+00:00",
                "symbols": symbols,
            }
        ),
        encoding="utf-8",
    )
    return felix_cache


def make_candidate(
    *,
    symbol: str = "HYPE",
    funding_venue: str = "hyperliquid",
    apr_latest: float | None = 18.0,
    apr_7d: float | None = 20.0,
    apr_14d: float | None = 22.0,
    oi_rank: int | None = 8,
    tradeability_status: str = "EXECUTABLE",
    spot_on_hyperliquid: bool = True,
    spot_on_felix: bool = False,
    flags: list[str] | None = None,
) -> CoreCandidate:
    candidate = CoreCandidate(
        symbol=symbol,
        funding_venue=funding_venue,
        latest_ts=datetime(2026, 3, 12, 16, 0, 0, tzinfo=timezone.utc),
        apr_latest=apr_latest,
        apr_7d=apr_7d,
        apr_14d=apr_14d,
        apr_30d=apr_14d,
        oi_rank=oi_rank,
        spot_on_hyperliquid=spot_on_hyperliquid,
        spot_on_felix=spot_on_felix,
        tradeability_status=tradeability_status,
        flags=list(flags or []),
        freshness_hours=1.0,
        history_days=30.0,
        funding_observation_count=90,
        funding_samples=[
            (datetime(2026, 3, 12, 16, 0, 0, tzinfo=timezone.utc) - timedelta(days=days), 0.0002, oi_rank)
            for days in (0, 3, 7, 14, 21, 28)
        ],
    )
    return candidate


def make_scored_candidate(
    symbol: str,
    *,
    stability_score: float = 25.0,
    pair_quality_score: float = 75.0,
    effective_apr_anchor: float = 12.0,
    tradeability_status: str = "EXECUTABLE",
    flags: list[str] | None = None,
) -> CoreCandidate:
    candidate = make_candidate(
        symbol=symbol,
        tradeability_status=tradeability_status,
        flags=flags,
    )
    candidate.stability_score = stability_score
    candidate.pair_quality_score = pair_quality_score
    candidate.effective_apr_anchor = effective_apr_anchor
    candidate.eligible_for_basket = tradeability_status == "EXECUTABLE"
    return candidate


def test_load_core_candidates_verifies_required_inputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        loris_csv = build_loris_fixture(
            tmp_path,
            [
                ("2026-03-12T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.0004),
                ("2026-03-10T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00035),
                ("2026-03-05T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00030),
                ("2026-02-26T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00028),
            ],
        )
        bundle = load_core_candidates(
            loris_csv=loris_csv,
            felix_cache=build_felix_fixture(tmp_path, ["HYPE"]),
            now=datetime(2026, 3, 12, 17, 0, 0, tzinfo=timezone.utc),
        )
        assert bundle.input_state == "DEGRADED"
        assert bundle.candidates
        assert bundle.candidates[0].symbol == "HYPE"
        assert bundle.candidates[0].funding_venue == "hyperliquid"


def test_load_core_candidates_handles_missing_loris_csv() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle = load_core_candidates(
            loris_csv=tmp_path / "missing.csv",
            felix_cache=build_felix_fixture(tmp_path, ["HYPE"]),
        )
        assert bundle.input_state == "DEGRADED"
        assert bundle.warnings == ["missing loris csv"]


def test_tradeability_status_and_flags_are_resolved_from_spot_inputs() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle = load_core_candidates(
            loris_csv=build_loris_fixture(
                tmp_path,
                [
                    ("2026-03-12T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00040),
                    ("2026-03-10T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00036),
                    ("2026-03-01T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00034),
                    ("2026-02-20T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00033),
                    ("2026-03-12T16:00:00+00:00", "tradexyz", "XYZ", 45, 0.00035),
                    ("2026-03-10T16:00:00+00:00", "tradexyz", "XYZ", 45, 0.00035),
                    ("2026-03-01T16:00:00+00:00", "tradexyz", "XYZ", 45, 0.00035),
                    ("2026-02-20T16:00:00+00:00", "tradexyz", "XYZ", 45, 0.00035),
                ],
            ),
            felix_cache=build_felix_fixture(tmp_path, ["XYZ"]),
            now=datetime(2026, 3, 12, 18, 0, 0, tzinfo=timezone.utc),
            hyperliquid_spot_symbols={"HYPE"},
        )
        by_symbol = {candidate.symbol: candidate for candidate in bundle.candidates}
        assert by_symbol["HYPE"].tradeability_status == "EXECUTABLE"
        assert "STALE_DATA" not in by_symbol["HYPE"].flags
        assert by_symbol["XYZ"].tradeability_status == "EXECUTABLE"


def test_resolve_tradeability_variants() -> None:
    status, flags = resolve_tradeability(
        "HYPE",
        spot_on_hyperliquid=True,
        spot_on_felix=False,
        hyperliquid_spot_known=True,
    )
    assert status == "EXECUTABLE"
    assert flags == []

    status, flags = resolve_tradeability(
        "XYZ",
        spot_on_hyperliquid=False,
        spot_on_felix=True,
        hyperliquid_spot_known=False,
    )
    assert status == "EXECUTABLE"
    assert flags == []

    status, flags = resolve_tradeability(
        "DOGE",
        spot_on_hyperliquid=False,
        spot_on_felix=False,
        hyperliquid_spot_known=False,
    )
    assert status == "CROSS_CHECK_NEEDED"
    assert "MISSING_SPOT" in flags

    status, flags = resolve_tradeability(
        "DOGE",
        spot_on_hyperliquid=False,
        spot_on_felix=False,
        hyperliquid_spot_known=True,
    )
    assert status == "NON_EXECUTABLE"
    assert flags == ["MISSING_SPOT"]


def test_annualize_and_average_helpers() -> None:
    assert_close(annualize_apr(0.0004), 43.8, rel=1e-5)
    assert annualize_apr(None) is None
    base_ts = datetime(2026, 3, 12, 16, 0, 0, tzinfo=timezone.utc)
    samples = [
        (base_ts, 0.0001),
        (base_ts + timedelta(days=1), 0.0002),
        (base_ts + timedelta(days=3), 0.0003),
    ]
    assert_close(average_rate(samples, base_ts), 0.0002)
    assert average_rate(samples, base_ts + timedelta(days=10)) is None


def test_scores_follow_the_spec_formulas() -> None:
    candidate = make_candidate()
    candidate = score_candidate(candidate)
    assert_close(candidate.stability_score or 0.0, 0.55 * 22.0 + 0.30 * 20.0 + 0.15 * 18.0)
    assert candidate.pair_quality_score is not None
    assert candidate.pair_quality_score >= 60.0
    assert_close(candidate.effective_apr_anchor or 0.0, 11.0)
    assert candidate.breakeven_estimate_days is not None


def test_breakeven_uses_the_150k_normalized_lot() -> None:
    candidate = score_candidate(make_candidate())
    assert candidate.breakeven_notional_usd == NORMALIZED_BREAKEVEN_NOTIONAL_USD


def test_compute_stability_score_returns_none_when_any_apr_is_missing() -> None:
    assert compute_stability_score(make_candidate(apr_latest=None)) is None
    assert compute_stability_score(make_candidate(apr_7d=None)) is None
    assert compute_stability_score(make_candidate(apr_14d=None)) is None


def test_estimate_breakeven_days_returns_none_when_apr_is_zero_or_negative() -> None:
    assert estimate_breakeven_days(make_candidate(apr_14d=0.0, apr_7d=0.0, apr_latest=0.0)) is None
    assert estimate_breakeven_days(make_candidate(apr_14d=-1.0, apr_7d=-1.0, apr_latest=-1.0)) is None


def test_load_core_candidates_flags_stale_and_short_history_and_missing_windows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        bundle = load_core_candidates(
            loris_csv=build_loris_fixture(
                tmp_path,
                [
                    ("2026-03-10T00:00:00+00:00", "hyena", "ALPHA", 90, 0.00015),
                    ("2026-03-11T00:00:00+00:00", "hyena", "ALPHA", 90, -0.00010),
                ],
            ),
            felix_cache=build_felix_fixture(tmp_path, []),
            now=datetime(2026, 3, 12, 16, 0, 0, tzinfo=timezone.utc),
            hyperliquid_spot_symbols=set(),
        )
        candidate = bundle.candidates[0]
        assert "SHORT_HISTORY" in candidate.flags
        assert "MISSING_APR_WINDOW" in candidate.flags
        assert candidate.tradeability_status == "NON_EXECUTABLE"


def test_load_core_candidates_computes_historical_apr_windows() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rows = [
            ("2026-03-12T16:00:00+00:00", "hyperliquid", "HYPE", 10, 0.00040),
            ("2026-03-09T16:00:00+00:00", "hyperliquid", "HYPE", 10, 0.00035),
            ("2026-03-07T16:00:00+00:00", "hyperliquid", "HYPE", 10, 0.00030),
            ("2026-03-02T16:00:00+00:00", "hyperliquid", "HYPE", 10, 0.00025),
            ("2026-02-25T16:00:00+00:00", "hyperliquid", "HYPE", 10, 0.00022),
        ]
        bundle = load_core_candidates(
            loris_csv=build_loris_fixture(tmp_path, rows),
            felix_cache=build_felix_fixture(tmp_path, ["HYPE"]),
            now=datetime(2026, 3, 12, 17, 0, 0, tzinfo=timezone.utc),
        )
        candidate = bundle.candidates[0]
        assert candidate.apr_7d is not None
        assert candidate.apr_14d is not None
        assert candidate.stability_score is not None


def test_load_core_candidates_degrades_when_hyperliquid_spot_lookup_is_unresolved() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        rows = []
        for venue in ("hyperliquid", "tradexyz", "hyena", "kinetiq"):
            rows.extend(
                [
                    ("2026-03-12T16:00:00+00:00", venue, venue[:2].upper(), 10, 0.00040),
                    ("2026-03-09T16:00:00+00:00", venue, venue[:2].upper(), 10, 0.00035),
                    ("2026-03-01T16:00:00+00:00", venue, venue[:2].upper(), 10, 0.00030),
                    ("2026-02-20T16:00:00+00:00", venue, venue[:2].upper(), 10, 0.00025),
                ]
            )
        bundle = load_core_candidates(
            loris_csv=build_loris_fixture(tmp_path, rows),
            felix_cache=build_felix_fixture(tmp_path, []),
            now=datetime(2026, 3, 12, 17, 0, 0, tzinfo=timezone.utc),
        )
        assert bundle.input_state == "DEGRADED"
        assert any("Hyperliquid spot availability unresolved" in warning for warning in bundle.warnings)


def test_strategy_2_ranks_executable_names_by_stability_with_quality_floor() -> None:
    basket = build_strategy_2_basket(
        [
            make_scored_candidate("A", stability_score=28, pair_quality_score=78),
            make_scored_candidate("B", stability_score=26, pair_quality_score=74),
            make_scored_candidate("C", stability_score=25, pair_quality_score=59),
        ],
        core_capital_usd=600000,
    )
    assert [row.symbol for row in basket.positions] == ["A", "B"]
    assert all(row.weight <= 0.40 for row in basket.positions)


def test_strategy_3_chooses_the_best_valid_combination() -> None:
    basket = build_strategy_3_basket(
        [
            make_scored_candidate("A", pair_quality_score=88, stability_score=30, effective_apr_anchor=14),
            make_scored_candidate("B", pair_quality_score=84, stability_score=28, effective_apr_anchor=13),
            make_scored_candidate("C", pair_quality_score=70, stability_score=21, effective_apr_anchor=11, flags=["DECAYING_REGIME"]),
            make_scored_candidate("D", pair_quality_score=68, stability_score=22, effective_apr_anchor=12, tradeability_status="CROSS_CHECK_NEEDED"),
        ],
        core_capital_usd=600000,
    )
    assert [row.symbol for row in basket.positions][:2] == ["A", "B"]
    assert basket.execution_uncertainty_count == 0
    assert all(row.weight <= 0.40 for row in basket.positions)


def test_strategy_3_extends_pool_with_cross_check_names_when_breadth_is_thin() -> None:
    basket = build_strategy_3_basket(
        [
            make_scored_candidate("A", pair_quality_score=88, stability_score=30, effective_apr_anchor=14),
            make_scored_candidate(
                "C",
                pair_quality_score=80,
                stability_score=24,
                effective_apr_anchor=12,
                tradeability_status="CROSS_CHECK_NEEDED",
            ),
        ],
        core_capital_usd=600000,
    )
    assert {row.symbol for row in basket.positions} == {"A", "C"}
    assert basket.execution_uncertainty_count == 1


def test_strategy_3_redistributes_weight_after_cap_before_leaving_idle() -> None:
    from core_tier_portfolio_construction import _materialize_strategy_3_combo

    basket = _materialize_strategy_3_combo(
        (
            make_scored_candidate("A", pair_quality_score=200, stability_score=30, effective_apr_anchor=14),
            make_scored_candidate("B", pair_quality_score=60, stability_score=24, effective_apr_anchor=12),
            make_scored_candidate("C", pair_quality_score=60, stability_score=24, effective_apr_anchor=12),
        ),
        core_capital_usd=600000,
    )
    weights = {row.symbol: row.weight for row in basket.positions}
    assert_close(weights["A"], 0.40)
    assert_close(weights["B"], 0.30)
    assert_close(weights["C"], 0.30)
    assert_close(basket.idle_capital_usd, 0.0)


def test_compare_baskets_uses_the_spec_order() -> None:
    better = StrategyBasket(
        strategy_label="STRATEGY_3",
        positions=[BasketPosition(symbol="A", funding_venue="hyperliquid", capital_usd=210000, weight=0.35)],
        idle_capital_usd=390000,
        weighted_effective_apr=10.0,
        weighted_pair_quality_score=84.0,
        weighted_stability_score=28.0,
        execution_uncertainty_count=0,
        decay_concern_count=0,
    )
    worse = StrategyBasket(
        strategy_label="STRATEGY_2",
        positions=[BasketPosition(symbol="B", funding_venue="hyperliquid", capital_usd=240000, weight=0.40)],
        idle_capital_usd=360000,
        weighted_effective_apr=12.0,
        weighted_pair_quality_score=85.0,
        weighted_stability_score=26.0,
        execution_uncertainty_count=1,
        decay_concern_count=0,
    )
    verdict = compare_strategy_baskets(better, worse)
    assert verdict.method_verdict == "STRATEGY_3"


def run_cli_capture(args: list[str]) -> str:
    result = subprocess.run(
        ["python3", "scripts/report_core_tier_portfolio_construction.py", *args],
        cwd=Path(__file__).resolve().parent.parent,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout


def build_realistic_loris_fixture(tmp_path: Path) -> Path:
    base_ts = datetime(2026, 3, 12, 16, 0, 0, tzinfo=timezone.utc)
    rows: list[tuple[str, str, str, int | None, float]] = []
    assets = [
        ("hyperliquid", "HYPE", 5, 0.00040),
        ("tradexyz", "DOGE", 15, 0.00025),
        ("hyena", "SOL", 10, 0.00018),
        ("kinetiq", "ETH", 8, 0.00016),
    ]
    for exchange, symbol, oi_rank, rate in assets:
        for days_ago in (0, 3, 7, 14, 21):
            rows.append(
                (
                    (base_ts - timedelta(days=days_ago)).isoformat(),
                    exchange,
                    symbol,
                    oi_rank,
                    rate,
                )
            )
    return build_loris_fixture(tmp_path, rows)


def test_cli_report_contains_required_sections() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        stdout = run_cli_capture(
            [
                "--loris-csv",
                str(build_realistic_loris_fixture(tmp_path)),
                "--felix-cache",
                str(build_felix_fixture(tmp_path, ["DOGE", "HYPE"])),
                "--portfolio-capital",
                "1000000",
                "--core-capital",
                "600000",
            ]
        )
        assert "# Core Tier Portfolio Construction Test" in stdout
        assert "## Strategy 3 Basket" in stdout
        assert "## Strategy 2 Basket" in stdout
        assert "## Near-Miss And Excluded Candidates" in stdout
        assert "Method Verdict:" in stdout
        assert "Deployment Verdict:" in stdout
        assert "### Inclusion Rationale" in stdout
        assert "Deployed Capital:" in stdout
        assert "Idle Capital:" in stdout


def main() -> int:
    test_functions = [
        obj
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    failures: list[str] = []
    for func in test_functions:
        try:
            func()
            print(f"PASS {func.__name__}")
        except Exception as exc:
            failures.append(f"{func.__name__}: {exc}")
            print(f"FAIL {func.__name__}: {exc}")
    if failures:
        raise SystemExit(1)
    print(f"PASS all ({len(test_functions)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
