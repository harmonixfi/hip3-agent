# Simplify Core Tier Portfolio Construction to Data-First CSV Export

**Date:** 2026-03-16
**Status:** Draft
**Owner:** Harmonix

## Goal

Simplify the Core-tier portfolio construction system from a rule-based basket builder (Strategy 2/3 comparison) to a data-first scoring and export pipeline. The system should load candidates, compute all metrics, and export a flat CSV for human-driven pair selection.

This reflects a strategy shift: Core layer now targets lending pool deployment (Hypurrfi USDC + USDH Felix Frontier) with a smaller HIP-3 pairs overlay (25% allocation, 3 pairs), rather than full $600K funding-arb basket construction.

## Scope

In scope:
- Remove Strategy 2/3 basket construction logic and comparison framework
- Remove hard disqualifiers from scoring (DECAYING_REGIME and NON_EXECUTABLE no longer zero out scores)
- Remove the CLI report script (`report_core_tier_portfolio_construction.py`)
- Simplify the export script to produce a flat ranked CSV
- Update tests to match simplified behavior
- Update workspace docs (TOOLS.md, WORKFLOW.md)

Out of scope:
- Lending pool allocation logic (manual/advisory)
- New metrics or scoring formula changes
- Changes to data ingestion (Loris, Hyperliquid, Felix)

## Architecture

```
loris_funding_history.csv  ─┐
felix_equities_cache.json  ─┤──▶ load_core_candidates() ──▶ score_candidate() ──▶ CSV export
arbit_v3.db (HL spot)      ─┘
```

Single pipeline: load → score → export. No basket construction, no strategy comparison, no deployment verdict.

## Changes

### 1. Simplify `scripts/core_tier_portfolio_construction.py`

#### Remove

- `BasketPosition` dataclass
- `StrategyBasket` dataclass
- `StrategyVerdict` dataclass
- `build_strategy_2_basket()` function
- `build_strategy_3_basket()` function
- `compare_strategy_baskets()` function
- `_strategy_2_weight_template()` helper
- `_materialize_basket()` helper
- `_materialize_strategy_3_combo()` helper
- `_strategy_3_sort_key()` helper
- `PAIR_QUALITY_FLOOR` constant (no longer used as gate)
- Any helper functions used exclusively by the above

#### Modify

- `compute_pair_quality_score()`: Remove the early return that sets `pair_quality_score = 0.0` when `tradeability_status == "NON_EXECUTABLE"` (line 313-314). Always compute the full 5-component score for every candidate regardless of tradeability.
- `score_candidate()`: Remove the `eligible_for_basket` assignment logic (line 366-370) that gates on `DECAYING_REGIME` and `passes_shared_data_gate()`. Remove the `eligible_for_basket` field from `CoreCandidate` dataclass entirely — no remaining consumer.
- `_trend_alignment_score()`: Keep existing logic and flag assignment unchanged. Only the downstream consumer changes.
- Remove `from itertools import combinations` import (only used by `build_strategy_3_basket`).

#### Keep unchanged

- `CoreCandidate` dataclass (remove `eligible_for_basket` field, keep all others)
- `CandidateBundle` dataclass
- `load_core_candidates()` function
- `resolve_tradeability()` function
- `passes_shared_data_gate()` function
- `compute_stability_score()` function
- `estimate_breakeven_days()` function
- All 5 scoring component functions (`_funding_consistency_score`, `_trend_alignment_score`, `_oi_rank_to_score`, `_effective_apr_score`, `_breakeven_score`)
- `annualize_apr()` and `average_rate()` helpers
- Flag vocabulary (all flags remain informational)
- `APPROVED_FUNDING_VENUES` constant
- `NORMALIZED_BREAKEVEN_NOTIONAL_USD` constant

### 2. Simplify `scripts/export_core_candidates.py`

#### Remove

- Inline pool classification logic in `main()` that splits candidates into executable vs non-executable sections
- `_rejection_reason()` function
- `PAIR_QUALITY_FLOOR` import from `core_tier_portfolio_construction` (being removed from source)
- `passes_shared_data_gate` import (no longer needed for classification)
- Separate table sections for executable vs non-executable

#### Modify

- Output a single flat list of all candidates sorted by `pair_quality_score` descending
- Both console table and CSV export show the same data
- CSV columns:

```
symbol, funding_venue, tradeability_status, pair_quality_score, stability_score,
effective_apr_anchor, oi_rank, breakeven_estimate_days, apr_latest, apr_7d, apr_14d,
spot_on_hyperliquid, spot_on_felix, freshness_hours, flags
```

- Remove `rejection_reason` column from CSV (no longer applicable)
- Console table columns match CSV for consistency

### 3. Delete `scripts/report_core_tier_portfolio_construction.py`

This script depends on Strategy 2/3 functions being removed. Delete entirely.

### 4. Update `scripts/test_core_tier_portfolio_construction.py`

#### Remove tests

- `test_strategy_2_ranks_executable_names_by_stability_with_quality_floor`
- `test_strategy_3_chooses_the_best_valid_combination`
- `test_strategy_3_extends_pool_with_cross_check_names_when_breadth_is_thin`
- `test_strategy_3_redistributes_weight_after_cap_before_leaving_idle`
- `test_compare_baskets_uses_the_spec_order`
- `test_cli_report_contains_required_sections`

#### Modify tests

- Scoring tests: update assertions to verify NON_EXECUTABLE candidates now receive non-zero `pair_quality_score`
- Scoring tests: update assertions to verify DECAYING_REGIME candidates still get full scores

#### Keep tests

- `test_load_core_candidates_verifies_required_inputs`
- `test_load_core_candidates_handles_missing_loris_csv`
- `test_load_core_candidates_degrades_when_hyperliquid_spot_lookup_is_unresolved`
- `test_load_core_candidates_computes_historical_apr_windows`
- `test_load_core_candidates_flags_stale_and_short_history_and_missing_windows`
- `test_resolve_tradeability_variants`
- `test_tradeability_status_and_flags_are_resolved_from_spot_inputs`
- `test_scores_follow_the_spec_formulas`
- `test_breakeven_uses_the_150k_normalized_lot`
- `test_compute_stability_score_returns_none_when_any_apr_is_missing`
- `test_estimate_breakeven_days_returns_none_when_apr_is_zero_or_negative`
- `test_annualize_and_average_helpers`

### 5. Update workspace docs

#### `TOOLS.md`

- Remove `scripts/report_core_tier_portfolio_construction.py` entry
- Update `scripts/export_core_candidates.py` description to reflect flat CSV export purpose

#### `WORKFLOW.md`

- Remove "On-demand Core Tier Construction Test" runbook section referencing Strategy 2/3
- Add updated section for CSV candidate export workflow

## Scoring Behavior Change Summary

| Scenario | Before | After |
|----------|--------|-------|
| NON_EXECUTABLE candidate | `pair_quality_score = 0.0` | Full score computed, flag `MISSING_SPOT` remains |
| DECAYING_REGIME candidate | `eligible_for_basket = False`, excluded from baskets | Full score computed, flag `DECAYING_REGIME` remains |
| STALE_DATA candidate | Fails shared data gate → `eligible_for_basket = False`, excluded from baskets (scoring itself was never gated) | Same scoring, flag `STALE_DATA` remains. No basket eligibility check anymore |

## Non-Negotiables

- All scoring formulas remain unchanged (weights, normalization, components)
- Flags are always computed and surfaced — they become informational rather than gatekeeping
- CSV export must include all candidates, not just "passing" ones
- No new metrics or formula changes in this iteration
