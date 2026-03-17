# Simplify Core Tier to Data-First CSV Export — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Strategy 2/3 basket construction logic and hard disqualifiers from the Core-tier scoring system, leaving a clean load → score → CSV export pipeline.

**Architecture:** Simplify `core_tier_portfolio_construction.py` to candidate loading + scoring only. Remove basket construction dataclasses and functions. Update export script to flat CSV output. Delete the report CLI script.

**Tech Stack:** Python 3, `csv`, `dataclasses`, `pathlib`, existing `CostModelV3`, existing Loris/Felix/Hyperliquid data sources.

---

## File Structure

### Files to modify

- `scripts/core_tier_portfolio_construction.py`
  - Remove basket construction functions and dataclasses. Remove hard disqualifiers from scoring.
- `scripts/export_core_candidates.py`
  - Simplify to flat ranked CSV export.
- `scripts/test_core_tier_portfolio_construction.py`
  - Remove basket/strategy tests. Update scoring tests.
- `TOOLS.md`
  - Remove report script entry.
- `WORKFLOW.md`
  - Remove Strategy 2/3 runbook section.

### Files to delete

- `scripts/report_core_tier_portfolio_construction.py`

### Files unchanged

- `scripts/core_tier_portfolio_construction.py` — scoring functions, loading, tradeability, flags
- `tracking/analytics/cost_model_v3.py`
- `config/fees.json`
- `data/loris_funding_history.csv`
- `data/felix_equities_cache.json`
- `tracking/connectors/hyperliquid_public.py`
- `tracking/writers/hyperliquid_v3_writer.py`
- `scripts/pull_hyperliquid_v3.py`

## Chunk 1: Strip Basket Construction from Domain Module

### Task 1: Remove basket dataclasses and strategy functions

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`

- [ ] **Step 1: Remove the `from itertools import combinations` import (line 9)**

- [ ] **Step 2: Remove the `PAIR_QUALITY_FLOOR` constant (line 22)**

- [ ] **Step 3: Remove the `eligible_for_basket` field from `CoreCandidate` dataclass (line 64)**

- [ ] **Step 4: Remove the three basket/verdict dataclasses**

Remove `BasketPosition` (lines 76-80), `StrategyBasket` (lines 84-92), and `StrategyVerdict` (lines 96-99).

- [ ] **Step 5: Remove the NON_EXECUTABLE early return in scoring**

In the function that computes `pair_quality_score`, remove the early return at lines 313-314 that sets score to `0.0` when `tradeability_status == "NON_EXECUTABLE"`. The full 5-component score should always be computed.

- [ ] **Step 6: Remove the `eligible_for_basket` assignment in `score_candidate()` (lines 366-370)**

Remove this block entirely:
```python
candidate.eligible_for_basket = (
    passes_shared_data_gate(candidate)
    and candidate.tradeability_status == "EXECUTABLE"
    and "DECAYING_REGIME" not in candidate.flags
)
```

- [ ] **Step 7: Remove all basket construction functions**

Remove these functions entirely:
- `_strategy_2_weight_template()` (lines 458-466)
- `_materialize_basket()` (lines 469-506)
- `build_strategy_2_basket()` (lines 509-529)
- `_strategy_3_sort_key()` (lines 532-542)
- `_materialize_strategy_3_combo()` (lines 545-586)
- `build_strategy_3_basket()` (lines 589-617)
- `compare_strategy_baskets()` (lines 620-655)

- [ ] **Step 8: Verify the module still loads**

Run:

```bash
source .arbit_env && python3 -c "from scripts.core_tier_portfolio_construction import load_core_candidates, CoreCandidate; print('OK')"
```

Expected: `OK` with no import errors.

- [ ] **Step 9: Commit**

```bash
git add scripts/core_tier_portfolio_construction.py
git commit -m "refactor: remove basket construction logic from core tier module"
```

### Task 2: Update tests for simplified scoring behavior

**Files:**
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Remove imports of deleted items (lines 15-22)**

Remove imports of: `BasketPosition`, `StrategyBasket`, `build_strategy_2_basket`, `build_strategy_3_basket`, `compare_strategy_baskets`. Also remove `PAIR_QUALITY_FLOOR` if imported.

- [ ] **Step 2: Remove the 6 basket/strategy test functions**

Remove:
- `test_strategy_2_ranks_executable_names_by_stability_with_quality_floor` (lines 321-331)
- `test_strategy_3_chooses_the_best_valid_combination` (lines 334-346)
- `test_strategy_3_extends_pool_with_cross_check_names_when_breadth_is_thin` (lines 349-364)
- `test_strategy_3_redistributes_weight_after_cap_before_leaving_idle` (lines 367-382)
- `test_compare_baskets_uses_the_spec_order` (lines 385-407)
- `test_cli_report_contains_required_sections` (lines 446-469)

- [ ] **Step 3: Remove `make_scored_candidate` helper if it only served removed tests**

Check if `make_scored_candidate` (lines 98-116) is used by any remaining test. If not, remove it.

- [ ] **Step 4: Update `test_scores_follow_the_spec_formulas` to verify NON_EXECUTABLE gets full score**

Add or modify assertion:
```python
def test_non_executable_candidates_still_get_full_score(tmp_path: Path) -> None:
    candidate = make_candidate(
        symbol="XYZ",
        apr_latest=18.0,
        apr_7d=20.0,
        apr_14d=22.0,
        oi_rank=8,
        tradeability_status="NON_EXECUTABLE",
    )
    scored = score_candidate(candidate)
    assert scored.pair_quality_score is not None
    assert scored.pair_quality_score > 0
```

- [ ] **Step 5: Run all remaining tests**

Run:

```bash
source .arbit_env && python3 scripts/test_core_tier_portfolio_construction.py
```

Expected: all remaining tests pass.

- [ ] **Step 6: Commit**

```bash
git add scripts/test_core_tier_portfolio_construction.py
git commit -m "test: update core tier tests for simplified scoring"
```

## Chunk 2: Simplify Export Script and Clean Up

### Task 3: Simplify export script to flat CSV

**Files:**
- Modify: `scripts/export_core_candidates.py`

- [ ] **Step 1: Clean up imports**

Remove `PAIR_QUALITY_FLOOR` and `passes_shared_data_gate` imports. Keep only `CoreCandidate` and `load_core_candidates`.

- [ ] **Step 2: Remove `_rejection_reason()` function (lines 59-73)**

- [ ] **Step 3: Update CSV_FIELDS — remove `rejection_reason`**

Update `CSV_FIELDS` (lines 187-194) to remove `rejection_reason`:

```python
CSV_FIELDS = [
    "symbol", "funding_venue", "tradeability_status",
    "pair_quality_score", "stability_score", "effective_apr_anchor",
    "oi_rank", "breakeven_estimate_days",
    "apr_latest", "apr_7d", "apr_14d",
    "spot_on_hyperliquid", "spot_on_felix",
    "freshness_hours", "flags",
]
```

- [ ] **Step 4: Update `_export_csv()` — remove `rejection_reason` from row dict**

- [ ] **Step 5: Simplify `main()` — single sorted list, no pool splitting**

Replace the executable/non-executable split in `main()` with a single flat list:

```python
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
```

- [ ] **Step 6: Update console table COLUMNS — remove rejection_reason, keep flags**

Update `COLUMNS` list to match CSV fields. Remove `rejection_reason` column.

- [ ] **Step 7: Update `_candidate_row()` to match new COLUMNS**

- [ ] **Step 8: Test the export**

Run:

```bash
source .arbit_env && python3 scripts/export_core_candidates.py --csv data/core_candidates_export.csv
```

Expected: CSV exported with all candidates, no `rejection_reason` column, scores computed for all including NON_EXECUTABLE.

- [ ] **Step 9: Commit**

```bash
git add scripts/export_core_candidates.py
git commit -m "refactor: simplify export to flat ranked CSV"
```

### Task 4: Delete report script

**Files:**
- Delete: `scripts/report_core_tier_portfolio_construction.py`

- [ ] **Step 1: Delete the file**

```bash
rm scripts/report_core_tier_portfolio_construction.py
```

- [ ] **Step 2: Verify no other script imports from it**

```bash
grep -r "report_core_tier_portfolio_construction" scripts/ tracking/ --include="*.py"
```

Expected: no results (only docs may reference it).

- [ ] **Step 3: Commit**

```bash
git add -u scripts/report_core_tier_portfolio_construction.py
git commit -m "refactor: remove core tier report CLI script"
```

### Task 5: Update workspace docs

**Files:**
- Modify: `TOOLS.md`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Remove report script entry from `TOOLS.md` (lines 145-157)**

- [ ] **Step 2: Update export script entry in `TOOLS.md`**

Replace or add:
```markdown
### `scripts/export_core_candidates.py`
- Purpose: export all Core-tier candidates with scoring metrics as flat CSV for human review
- Inputs: `data/loris_funding_history.csv`, `data/felix_equities_cache.json`, `tracking/db/arbit_v3.db`
- Output: ranked CSV file or console table with all candidates and flags
- Safe for routine runs: **yes**

```bash
.venv/bin/python scripts/export_core_candidates.py --csv data/core_candidates_export.csv
```

- [ ] **Step 3: Remove "On-demand Core Tier Construction Test" section from `WORKFLOW.md` (lines 121-125)**

- [ ] **Step 4: Add updated candidate export section to `WORKFLOW.md`**

```markdown
### On-demand Core Candidate Export
Use `scripts/export_core_candidates.py` to export all scored candidates as CSV.
Scores are informational — flags (DECAYING_REGIME, STALE_DATA, etc.) are surfaced but do not gate scores.
Human picks pairs from the exported data.
```

- [ ] **Step 5: Commit**

```bash
git add TOOLS.md WORKFLOW.md
git commit -m "docs: update workspace docs for simplified candidate export"
```

### Task 6: Final verification

- [ ] **Step 1: Run the full test suite**

Run:

```bash
source .arbit_env && python3 scripts/test_core_tier_portfolio_construction.py
```

Expected: all tests pass.

- [ ] **Step 2: Run the export with live data**

Run:

```bash
source .arbit_env && python3 scripts/export_core_candidates.py --csv data/core_candidates_export.csv
```

Expected: CSV exported. NON_EXECUTABLE candidates now have non-zero quality scores. DECAYING_REGIME candidates have full scores with flag.

- [ ] **Step 3: Spot-check the CSV**

```bash
head -5 data/core_candidates_export.csv
```

Expected: no `rejection_reason` column. All candidates have scores.

- [ ] **Step 4: Verify deleted file is gone**

```bash
ls scripts/report_core_tier_portfolio_construction.py 2>&1
```

Expected: `No such file or directory`.
