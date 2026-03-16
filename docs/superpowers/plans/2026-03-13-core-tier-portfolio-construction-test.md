# Core Tier Portfolio Construction Test Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic Core-tier analysis path that loads current funding data, scores executable spot+perp candidates, compares Strategy 3 vs Strategy 2, and outputs a human-readable Core basket recommendation for the current market.

**Architecture:** Add one focused domain module for Core-tier candidate loading, scoring, sizing, and strategy comparison, then keep a thin CLI entrypoint for rendering the final analysis report. Reuse existing fee assumptions, symbol normalization, Loris funding history, and Felix cache rather than embedding duplicate data rules in the CLI.

**Tech Stack:** Python 3, `csv`, `json`, `argparse`, `dataclasses`, `pathlib`, existing `scripts/report_daily_funding_sections.py` normalization helpers, existing `tracking.analytics.cost_model_v3.CostModelV3`, markdown docs.

---

## File Structure

### New files

- `scripts/core_tier_portfolio_construction.py`
  - Single responsibility: domain logic for candidate loading, tradeability resolution, score calculation, basket sizing, Strategy 2 / Strategy 3 selection, and verdict comparison.
- `scripts/report_core_tier_portfolio_construction.py`
  - Thin CLI entrypoint that loads inputs, invokes the domain module, and prints the final human-readable analysis report.
- `scripts/test_core_tier_portfolio_construction.py`
  - Deterministic regression script with fixture-backed assertions for loading, scoring, strategy selection, degraded-input handling, and final report formatting.

### Existing files to modify

- `TOOLS.md`
  - Add the new on-demand analysis command and note that it is advisory-only.
- `WORKFLOW.md`
  - Add a short runbook entry for Core-tier construction testing so the analysis path is discoverable.

### Existing files to reuse without modification unless forced by implementation reality

- `scripts/report_daily_funding_sections.py`
  - Reuse `normalize_symbol()` and related helpers instead of reimplementing symbol cleanup.
- `config/fees.json`
  - Reuse current fee assumptions through `CostModelV3`.
- `data/loris_funding_history.csv`
  - Primary funding source.
- `data/felix_equities_cache.json`
  - Spot / Felix membership cross-check input.

### Execution note

This workspace is currently not a git repo. During execution here, replace each commit step with a timestamped checkpoint note in the worker log. If the work is moved into a git-backed runtime later, use the provided commit commands verbatim.

## Chunk 1: Candidate Loading And Pair Scoring

### Task 1: Create the Core candidate loader and prove input verification works

**Files:**
- Create: `scripts/core_tier_portfolio_construction.py`
- Create: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write the failing fixture-backed loader test**

```python
from pathlib import Path
from scripts.core_tier_portfolio_construction import load_core_candidates


def test_load_core_candidates_verifies_required_inputs(tmp_path: Path) -> None:
    loris_csv = tmp_path / "loris.csv"
    loris_csv.write_text(
        "timestamp_utc,exchange,symbol,oi_rank,funding_8h_scaled,funding_8h_rate\n"
        "2026-03-12T16:00:00+00:00,hyperliquid,HYPE,12,0.0,0.0004\n",
        encoding="utf-8",
    )
    felix_cache = tmp_path / "felix.json"
    felix_cache.write_text('{"timestamp":"2026-03-12T16:00:00+00:00","symbols":["HYPE"]}', encoding="utf-8")

    bundle = load_core_candidates(loris_csv=loris_csv, felix_cache=felix_cache)

    assert bundle.input_state == "NORMAL"
    assert bundle.candidates
    assert bundle.candidates[0].symbol == "HYPE"
    assert bundle.candidates[0].funding_venue == "hyperliquid"
```

- [ ] **Step 2: Run the new test script to verify it fails**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
ImportError or AttributeError because the core-tier module and loader do not exist yet
```

- [ ] **Step 3: Create the domain dataclasses and input bundle skeleton**

```python
@dataclass
class CoreCandidate:
    symbol: str
    funding_venue: str
    latest_ts: datetime
    apr_latest: float | None
    apr_7d: float | None
    apr_14d: float | None
    oi_rank: int | None
    spot_on_hyperliquid: bool
    spot_on_felix: bool
    tradeability_status: str
    flags: list[str]


@dataclass
class CandidateBundle:
    input_state: str
    warnings: list[str]
    candidates: list[CoreCandidate]
```

- [ ] **Step 4: Implement minimal input verification and candidate loading**

```python
def load_core_candidates(*, loris_csv: Path, felix_cache: Path) -> CandidateBundle:
    if not loris_csv.exists():
        return CandidateBundle(input_state="DEGRADED", warnings=["missing loris csv"], candidates=[])
    rows = _load_latest_rows_by_exchange_symbol(loris_csv)
    felix_symbols = _load_felix_symbols(felix_cache)
    candidates = [
        CoreCandidate(
            symbol=row.symbol,
            funding_venue=row.exchange,
            latest_ts=row.latest_ts,
            apr_latest=row.apr_latest,
            apr_7d=row.apr_7d,
            apr_14d=row.apr_14d,
            oi_rank=row.oi_rank,
            spot_on_hyperliquid=_spot_exists_on_hyperliquid(row.symbol),
            spot_on_felix=row.symbol in felix_symbols,
            tradeability_status="CROSS_CHECK_NEEDED",
            flags=[],
        )
        for row in rows
    ]
    return CandidateBundle(input_state="NORMAL", warnings=[], candidates=candidates)
```

- [ ] **Step 5: Re-run the test script to verify the loader now works**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
loader assertions pass; later scoring tests still fail or are not added yet
```

- [ ] **Step 6: Commit / checkpoint the loader milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add core tier candidate loader scaffold"
```

### Task 2: Add tradeability resolution, flagging, and funding-window calculations

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write failing tests for tradeability statuses and freshness flags**

```python
def test_tradeability_status_and_flags_are_resolved_from_spot_inputs(tmp_path: Path) -> None:
    bundle = load_core_candidates(
        loris_csv=build_loris_fixture(tmp_path, [
            ("2026-03-12T16:00:00+00:00", "hyperliquid", "HYPE", 12, 0.00040),
            ("2026-03-12T16:00:00+00:00", "tradexyz", "XYZ", 45, 0.00035),
        ]),
        felix_cache=build_felix_fixture(tmp_path, ["XYZ"]),
    )
    by_symbol = {row.symbol: row for row in bundle.candidates}
    assert by_symbol["HYPE"].tradeability_status == "EXECUTABLE"
    assert by_symbol["XYZ"].tradeability_status in {"EXECUTABLE", "CROSS_CHECK_NEEDED"}
    assert "STALE_DATA" not in by_symbol["HYPE"].flags
```

- [ ] **Step 2: Run the test script to confirm the new assertions fail**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
FAIL because tradeability resolution and flags are not implemented yet
```

- [ ] **Step 3: Implement the tradeability-status resolver and shared flag vocabulary**

```python
def resolve_tradeability(symbol: str, *, spot_on_hyperliquid: bool, spot_on_felix: bool) -> tuple[str, list[str]]:
    if spot_on_hyperliquid:
        return "EXECUTABLE", []
    if spot_on_felix:
        return "EXECUTABLE", []
    return "CROSS_CHECK_NEEDED", ["MISSING_SPOT", "CROSS_CHECK_NEEDED"]
```

- [ ] **Step 4: Add funding-window aggregation helpers for latest / 7d / 14d / 30d**

```python
def annualize_apr(rate_8h: float | None) -> float | None:
    if rate_8h is None:
        return None
    return rate_8h * 3.0 * 365.0 * 100.0


def average_rate(samples: list[tuple[datetime, float]], since_dt: datetime) -> float | None:
    values = [rate for ts, rate in samples if ts >= since_dt]
    return (sum(values) / len(values)) if values else None
```

- [ ] **Step 5: Re-run the test script**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
tradeability and funding-window tests pass; scoring tests are next
```

- [ ] **Step 6: Commit / checkpoint the tradeability milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add core tier tradeability and funding windows"
```

### Task 3: Implement `stability_score`, `pair_quality_score`, and breakeven math

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write failing tests for the two scores and normalized breakeven**

```python
def test_scores_follow_the_spec_formulas() -> None:
    candidate = make_candidate(
        symbol="HYPE",
        apr_latest=18.0,
        apr_7d=20.0,
        apr_14d=22.0,
        oi_rank=8,
        tradeability_status="EXECUTABLE",
    )
    scored = score_candidate(candidate)
    assert round(scored.stability_score, 2) == round(0.55 * 22.0 + 0.30 * 20.0 + 0.15 * 18.0, 2)
    assert scored.pair_quality_score >= 60.0
    assert scored.effective_apr_anchor == 11.0
    assert scored.breakeven_estimate_days is not None


def test_breakeven_uses_the_150k_normalized_lot() -> None:
    candidate = make_candidate(symbol="HYPE", apr_latest=18.0, apr_7d=20.0, apr_14d=22.0, oi_rank=8)
    scored = score_candidate(candidate)
    assert scored.breakeven_notional_usd == 150000
```

- [ ] **Step 2: Run the test script to verify the score assertions fail**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
FAIL because score_candidate() and breakeven fields are missing
```

- [ ] **Step 3: Implement the exact `stability_score` formula and normalized 0-100 scoring components**

```python
def compute_stability_score(candidate: CoreCandidate) -> float | None:
    if None in (candidate.apr_latest, candidate.apr_7d, candidate.apr_14d):
        return None
    return 0.55 * candidate.apr_14d + 0.30 * candidate.apr_7d + 0.15 * candidate.apr_latest
```

- [ ] **Step 4: Implement cost and breakeven estimation with `CostModelV3`**

```python
def estimate_breakeven_days(candidate: CoreCandidate, *, normalized_lot_usd: float = 150000) -> float | None:
    effective_apr_anchor = (candidate.apr_14d or 0.0) / 2.0
    model = CostModelV3()
    total_roundtrip_cost = (
        normalized_lot_usd * model.get_fee_bps("hyperliquid", "spot", is_maker=False) / 10000.0
        + normalized_lot_usd * model.get_fee_bps(candidate.funding_venue, "perp", is_maker=False) / 10000.0
    ) * 2.0
    daily_net_funding = normalized_lot_usd * (effective_apr_anchor / 100.0) / 365.0
    if daily_net_funding <= 0:
        return None
    return total_roundtrip_cost / daily_net_funding
```

- [ ] **Step 5: Implement `score_candidate()` so it writes all analysis fields onto the candidate model**

```python
@dataclass
class CoreCandidate:
    ...
    stability_score: float | None = None
    pair_quality_score: float | None = None
    effective_apr_anchor: float | None = None
    breakeven_estimate_days: float | None = None
    breakeven_notional_usd: float | None = None
```

- [ ] **Step 6: Re-run the test script**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
score and breakeven tests pass; strategy-selection tests still fail or are not added yet
```

- [ ] **Step 7: Commit / checkpoint the scoring milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add core tier scoring and breakeven logic"
```

## Chunk 2: Strategy Selection, Report Rendering, And CLI

### Task 4: Implement Strategy 2 basket construction

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write failing tests for Strategy 2 selection and sizing templates**

```python
def test_strategy_2_ranks_executable_names_by_stability_with_quality_floor() -> None:
    candidates = [
        make_scored_candidate("A", stability_score=28, pair_quality_score=78, tradeability_status="EXECUTABLE"),
        make_scored_candidate("B", stability_score=26, pair_quality_score=74, tradeability_status="EXECUTABLE"),
        make_scored_candidate("C", stability_score=25, pair_quality_score=59, tradeability_status="EXECUTABLE"),
    ]
    basket = build_strategy_2_basket(candidates, core_capital_usd=600000)
    assert [row.symbol for row in basket.positions] == ["A", "B"]
    assert basket.idle_capital_usd == 0 or basket.idle_capital_usd > 0
    assert all(row.weight <= 0.40 for row in basket.positions)
```

- [ ] **Step 2: Run the test script to verify Strategy 2 assertions fail**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
FAIL because Strategy 2 basket construction does not exist yet
```

- [ ] **Step 3: Add basket dataclasses**

```python
@dataclass
class BasketPosition:
    symbol: str
    funding_venue: str
    capital_usd: float
    weight: float


@dataclass
class StrategyBasket:
    strategy_label: str
    positions: list[BasketPosition]
    idle_capital_usd: float
    weighted_effective_apr: float | None
    weighted_pair_quality_score: float | None
    weighted_stability_score: float | None
    execution_uncertainty_count: int
    decay_concern_count: int
```

- [ ] **Step 4: Implement Strategy 2 filtering and sizing**

```python
def build_strategy_2_basket(candidates: list[CoreCandidate], *, core_capital_usd: float) -> StrategyBasket:
    ranked = [
        c for c in candidates
        if c.tradeability_status == "EXECUTABLE" and (c.pair_quality_score or 0) >= 60
    ]
    ranked.sort(key=lambda c: (c.stability_score or float("-inf"), c.pair_quality_score or float("-inf")), reverse=True)
    chosen = ranked[:4]
    weights = _strategy_2_weight_template(len(chosen))
    return _materialize_basket("STRATEGY_2", chosen, weights, core_capital_usd=core_capital_usd)
```

- [ ] **Step 5: Re-run the test script**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
Strategy 2 tests pass; Strategy 3 tests remain failing or absent
```

- [ ] **Step 6: Commit / checkpoint the Strategy 2 milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add strategy 2 core basket selection"
```

### Task 5: Implement Strategy 3 combination search and winner comparison

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write failing tests for Strategy 3 combination search**

```python
def test_strategy_3_chooses_the_best_valid_combination() -> None:
    candidates = [
        make_scored_candidate("A", pair_quality_score=88, stability_score=30, effective_apr_anchor=14, tradeability_status="EXECUTABLE"),
        make_scored_candidate("B", pair_quality_score=84, stability_score=28, effective_apr_anchor=13, tradeability_status="EXECUTABLE"),
        make_scored_candidate("C", pair_quality_score=70, stability_score=21, effective_apr_anchor=11, tradeability_status="EXECUTABLE", flags=["DECAYING_REGIME"]),
        make_scored_candidate("D", pair_quality_score=68, stability_score=22, effective_apr_anchor=12, tradeability_status="CROSS_CHECK_NEEDED"),
    ]
    basket = build_strategy_3_basket(candidates, core_capital_usd=600000)
    assert [row.symbol for row in basket.positions][:2] == ["A", "B"]
    assert basket.execution_uncertainty_count == 0
    assert all(row.weight <= 0.40 for row in basket.positions)
```

- [ ] **Step 2: Add failing comparison tests for Strategy 3 vs Strategy 2 verdict ordering**

```python
def test_compare_baskets_uses_the_spec_order() -> None:
    better = make_basket("STRATEGY_3", execution_uncertainty_count=0, decay_concern_count=0, largest_weight=0.35, weighted_pair_quality_score=84, deploy_ratio=0.80, weighted_effective_apr=10)
    worse = make_basket("STRATEGY_2", execution_uncertainty_count=1, decay_concern_count=0, largest_weight=0.40, weighted_pair_quality_score=85, deploy_ratio=1.00, weighted_effective_apr=12)
    verdict = compare_strategy_baskets(better, worse)
    assert verdict.method_verdict == "STRATEGY_3"
```

- [ ] **Step 3: Run the test script to confirm the Strategy 3 tests fail**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
FAIL because Strategy 3 combination search and comparison helpers do not exist yet
```

- [ ] **Step 4: Implement the top-8 pool, combination enumeration, and proportional weighting rules**

```python
from itertools import combinations


def build_strategy_3_basket(candidates: list[CoreCandidate], *, core_capital_usd: float) -> StrategyBasket:
    pool = sorted(candidates, key=lambda c: c.pair_quality_score or float("-inf"), reverse=True)[:8]
    valid_baskets: list[StrategyBasket] = []
    for size in (2, 3, 4):
        for combo in combinations(pool, size):
            basket = _materialize_strategy_3_combo(combo, core_capital_usd=core_capital_usd)
            if basket is not None:
                valid_baskets.append(basket)
    return sorted(valid_baskets, key=_strategy_3_sort_key)[0]
```

- [ ] **Step 5: Implement the verdict object and two-axis method / deployment result**

```python
@dataclass
class StrategyVerdict:
    method_verdict: str
    deployment_verdict: str
    rationale: list[str]
```

- [ ] **Step 6: Re-run the test script**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
Strategy 2, Strategy 3, and basket-comparison tests all pass
```

- [ ] **Step 7: Commit / checkpoint the Strategy 3 milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add strategy 3 basket search and verdict comparison"
```

### Task 6: Add the CLI report path and degraded-input output contract

**Files:**
- Create: `scripts/report_core_tier_portfolio_construction.py`
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`

- [ ] **Step 1: Write failing tests for the final human-readable report**

```python
def test_cli_report_contains_required_sections(tmp_path: Path) -> None:
    stdout = run_cli_capture([
        "--loris-csv", str(build_realistic_loris_fixture(tmp_path)),
        "--felix-cache", str(build_felix_fixture(tmp_path, ["DOGE"])),
        "--portfolio-capital", "1000000",
        "--core-capital", "600000",
    ])
    assert "# Core Tier Portfolio Construction Test" in stdout
    assert "## Strategy 3 Basket" in stdout
    assert "## Strategy 2 Basket" in stdout
    assert "## Near-Miss And Excluded Candidates" in stdout
    assert "Method Verdict:" in stdout
    assert "Deployment Verdict:" in stdout
```

- [ ] **Step 2: Run the test script to verify the CLI assertions fail**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
FAIL because the dedicated CLI entrypoint does not exist yet
```

- [ ] **Step 3: Implement the thin CLI wrapper**

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--loris-csv", type=Path, default=ROOT / "data" / "loris_funding_history.csv")
    ap.add_argument("--felix-cache", type=Path, default=ROOT / "data" / "felix_equities_cache.json")
    ap.add_argument("--portfolio-capital", type=float, default=1_000_000)
    ap.add_argument("--core-capital", type=float, default=600_000)
    return ap.parse_args(argv)
```

- [ ] **Step 4: Add the final renderer with the exact report sections**

```python
def render_core_tier_report(result: AnalysisResult) -> str:
    return "\n".join([
        "# Core Tier Portfolio Construction Test",
        f"Input State: {result.input_state}",
        "## Strategy 3 Basket",
        _format_basket(result.strategy_3_basket),
        "## Strategy 2 Basket",
        _format_basket(result.strategy_2_basket),
        "## Near-Miss And Excluded Candidates",
        _format_exclusions(result.excluded_candidates),
        f"Method Verdict: {result.verdict.method_verdict}",
        f"Deployment Verdict: {result.verdict.deployment_verdict}",
    ])
```

- [ ] **Step 5: Re-run the test script and then smoke-test the CLI with current data**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
python3 scripts/report_core_tier_portfolio_construction.py --portfolio-capital 1000000 --core-capital 600000
```

Expected:

```text
first command passes deterministically; second command prints a human-readable report with Strategy 3 basket, Strategy 2 basket, exclusions, and verdict lines
```

- [ ] **Step 6: Commit / checkpoint the CLI milestone**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/report_core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py
git commit -m "feat: add core tier portfolio construction report cli"
```

## Chunk 3: Documentation And Verification

### Task 7: Document the new analysis path in workspace docs

**Files:**
- Modify: `TOOLS.md`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Add the new script to `TOOLS.md`**

```markdown
### `scripts/report_core_tier_portfolio_construction.py`
- Purpose: compare Strategy 3 vs Strategy 2 for Core-tier construction using current funding data
- Inputs: `data/loris_funding_history.csv`, `data/felix_equities_cache.json`, `config/fees.json`
- Output: human-readable Core basket recommendation + verdict
- Safe for routine runs: **yes**
```

- [ ] **Step 2: Add the run command to `TOOLS.md`**

```markdown
.venv/bin/python scripts/report_core_tier_portfolio_construction.py --portfolio-capital 1000000 --core-capital 600000
```

- [ ] **Step 3: Add an on-demand Core-construction runbook note to `WORKFLOW.md`**

```markdown
### On-demand Core Tier Construction Test
Use `scripts/report_core_tier_portfolio_construction.py` when evaluating current Core deployment quality.
This path compares Strategy 3 vs Strategy 2 and may recommend partial deployment or no deployment.
```

- [ ] **Step 4: Run a contradiction search across docs**

Run:

```bash
grep -RIn "report_core_tier_portfolio_construction\|Core Tier Construction Test\|Strategy 3" TOOLS.md WORKFLOW.md
```

Expected:

```text
new entries appear exactly where intended with no contradictory wording
```

- [ ] **Step 5: Commit / checkpoint the docs update**

```bash
git add TOOLS.md WORKFLOW.md
git commit -m "docs: add core tier construction analysis workflow"
```

### Task 8: Final verification and execution handoff

**Files:**
- Modify: `scripts/core_tier_portfolio_construction.py`
- Modify: `scripts/report_core_tier_portfolio_construction.py`
- Modify: `scripts/test_core_tier_portfolio_construction.py`
- Modify: `TOOLS.md`
- Modify: `WORKFLOW.md`

- [ ] **Step 1: Run the full deterministic regression script**

Run:

```bash
python3 scripts/test_core_tier_portfolio_construction.py
```

Expected:

```text
all core-tier construction tests pass
```

- [ ] **Step 2: Run the live-data CLI once more**

Run:

```bash
python3 scripts/report_core_tier_portfolio_construction.py --portfolio-capital 1000000 --core-capital 600000
```

Expected:

```text
human-readable report prints without traceback and includes both strategy baskets plus the final verdict axes
```

- [ ] **Step 3: Verify the output does not dump raw CSV/JSON and clearly separates executable vs excluded names**

Run / inspect:

```text
Manually inspect the rendered report before declaring the feature ready.
Confirm it contains only human-readable summary sections.
Confirm executable names and excluded / cross-check-needed names are separated into distinct sections.
Confirm no raw CSV rows or JSON blobs are printed.
```

- [ ] **Step 4: Re-check verification evidence before claiming success**

Run / inspect:

```text
Re-check that the deterministic test script passed.
Re-check that the live-data CLI output contains both strategy baskets and both verdict axes.
Re-check that TOOLS.md and WORKFLOW.md were updated and do not contradict the final behavior.
Only then close the task.
```

- [ ] **Step 5: Commit / checkpoint the verified implementation**

```bash
git add scripts/core_tier_portfolio_construction.py scripts/report_core_tier_portfolio_construction.py scripts/test_core_tier_portfolio_construction.py TOOLS.md WORKFLOW.md
git commit -m "feat: add core tier portfolio construction analysis"
```
