# Sectioned Funding Report Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the daily funding report flow to explicit per-section rendering so the agent can assemble `Portfolio Summary`, `Top N Rotation Candidates - General`, and `Top N Rotation Candidates - Equities` from one script entrypoint.

**Architecture:** Keep `scripts/report_daily_funding_with_portfolio.py` as the single entrypoint, but refactor it into clear internal units for CLI validation, shared portfolio/candidate loading, section rendering, and stderr status metadata. Extend the existing focused script test harness first, then update workflow/spec docs so the new section contract becomes the documented source of truth.

**Tech Stack:** Python 3, `argparse`, `sqlite3`, CSV I/O, existing `tracking.position_manager.carry` helpers, markdown docs, existing `scripts/test_harmonix_report.py` test harness.

---

## File Structure

### Existing files to modify

- `scripts/report_daily_funding_with_portfolio.py`
  Single runtime entrypoint. Keep only CLI wiring, DB setup, mode dispatch, and rotation-analysis entry logic after the refactor.
- `scripts/report_daily_funding_sections.py`
  New focused helper module for section status types, candidate-pool building, Felix classification behavior, section rendering, and local global-header assembly helpers.
- `scripts/test_harmonix_report.py`
  Extend the existing focused test script to cover section dispatch, candidate split rules, status metadata, local header-assembly helpers, hard-fail/degraded behavior, and on-demand rotation compatibility.
- `WORKFLOW.md`
  Replace the old monolithic daily-report contract with the section-assembly workflow and global-header rules.
- `TOOLS.md`
  Update the command map and operational notes to describe per-section invocations rather than `--equities`.
- `spec/report-pipeline.md`
  Rewrite runtime behavior to match section mode, metadata channel, and flagged subsection semantics.
- `spec/report-scripts.md`
  Rewrite CLI and output contract documentation around `--section`, `--top`, and on-demand rotation mode.
- `spec/feat-delta-neutral-agent.md`
  Align the product-level report format with the new three-section contract and remove daily-required rotation-cost analysis.

### New runtime file required

- Create `scripts/report_daily_funding_sections.py` up front.
- Put all section-specific behavior there:
  - `SectionStatus`
  - `FlaggedCandidate`
  - symbol normalization
  - candidate-pool building
  - Felix classification handling
  - section renderers
  - local `build_global_header(...)` helper for contract verification
- Keep `scripts/report_daily_funding_with_portfolio.py` as a thin entrypoint so the main script does not absorb more reporting responsibilities.

## Chunk 1: Runtime And Tests

### Task 1: Lock The CLI Contract With Failing Tests

**Files:**
- Modify: `scripts/test_harmonix_report.py`
- Modify: `scripts/report_daily_funding_with_portfolio.py`
- Create: `scripts/report_daily_funding_sections.py`

- [ ] **Step 1: Add failing CLI-contract tests to `scripts/test_harmonix_report.py`**

```python
        # section mode requires explicit section or rotation args
        try:
            report.main_for_test(["--db", str(db_path)])
            raise AssertionError("expected missing-section failure")
        except SystemExit as exc:
            assert exc.code != 0

        try:
            report.main_for_test(["--db", str(db_path), "--equities"])
            raise AssertionError("expected --equities rejection")
        except SystemExit as exc:
            assert exc.code != 0

        try:
            report.main_for_test(["--db", str(db_path), "--section", "unknown"])
            raise AssertionError("expected unknown-section failure")
        except SystemExit as exc:
            assert exc.code != 0

        try:
            report.main_for_test(["--db", str(db_path), "--section", "rotation-general", "--rotate-from", "BTC", "--rotate-to", "ETH"])
            raise AssertionError("expected section-plus-rotation failure")
        except SystemExit as exc:
            assert exc.code != 0

        try:
            report.main_for_test(["--db", str(db_path), "--rotate-from", "BTC"])
            raise AssertionError("expected partial-rotation failure")
        except SystemExit as exc:
            assert exc.code != 0

        try:
            report.main_for_test(["--db", str(db_path), "--section", "rotation-general", "--top", "0"])
            raise AssertionError("expected invalid --top failure")
        except SystemExit as exc:
            assert exc.code != 0
```

- [ ] **Step 2: Run the focused test script to confirm the new assertions fail**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
FAIL or AssertionError for missing `main_for_test()` / missing `--section` validation / missing `--equities` rejection / missing `--top >= 1` validation
```

- [ ] **Step 3: Add minimal CLI-parsing helpers in `scripts/report_daily_funding_with_portfolio.py`**

```python
SECTION_PORTFOLIO = "portfolio-summary"
SECTION_ROTATION_GENERAL = "rotation-general"
SECTION_ROTATION_EQUITIES = "rotation-equities"
VALID_SECTIONS = {
    SECTION_PORTFOLIO,
    SECTION_ROTATION_GENERAL,
    SECTION_ROTATION_EQUITIES,
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)
    ap.add_argument("--section", choices=sorted(VALID_SECTIONS))
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--oi-max", type=int, default=200)
    ap.add_argument("--rotate-from", type=str, default=None)
    ap.add_argument("--rotate-to", type=str, default=None)
    ap.add_argument("--equities", action="store_true", default=False)
    ns = ap.parse_args(argv)
    validate_args(ns)
    return ns
```

- [ ] **Step 4: Add validation that matches the spec**

```python
def validate_args(args: argparse.Namespace) -> None:
    if args.top < 1:
        raise SystemExit(1)
    if args.equities:
        raise SystemExit(1)
    if bool(args.rotate_from) != bool(args.rotate_to):
        raise SystemExit(1)
    if args.section and (args.rotate_from or args.rotate_to):
        raise SystemExit(1)
    if not args.section and not (args.rotate_from and args.rotate_to):
        raise SystemExit(1)
```

- [ ] **Step 5: Add a thin testable entrypoint wrapper**

```python
def main_for_test(argv: list[str]) -> int:
    return run(parse_args(argv))


def main() -> int:
    return run(parse_args())
```

- [ ] **Step 6: Re-run the focused test script**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
still failing later tests, but the CLI-contract assertions now pass
```

- [ ] **Step 7: Commit the CLI-contract test scaffold**

```bash
git add scripts/test_harmonix_report.py scripts/report_daily_funding_with_portfolio.py
git commit -m "test: lock sectioned report cli contract"
```

### Task 2: Add Section Result Metadata And Portfolio Section Output

**Files:**
- Modify: `scripts/report_daily_funding_with_portfolio.py`
- Modify: `scripts/test_harmonix_report.py`

- [ ] **Step 1: Add failing tests for portfolio section rendering and stderr metadata**

```python
        stdout, stderr, rc = report.run_cli_capture(
            ["--db", str(db_path), "--section", "portfolio-summary"]
        )
        assert rc == 0
        assert "## Portfolio Summary" in stdout
        assert stdout.splitlines()[0] == "## Portfolio Summary"
        assert "(no open positions tracked)" in stdout or "- BTC |" in stdout
        assert "### Flagged Positions" in stdout
        meta = json.loads(stderr.splitlines()[-1])
        assert meta["section"] == "portfolio-summary"
        assert meta["state"] in {"NORMAL", "DEGRADED"}
        assert meta["hard_fail"] is False
```

- [ ] **Step 2: Run the focused test script to verify the new assertions fail**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
FAIL because section renderer and stderr JSON metadata do not exist yet
```

- [ ] **Step 3: Introduce a small section-result contract inside the report script**

```python
from scripts.report_daily_funding_sections import SectionStatus, emit_status
```

- [ ] **Step 4: Add explicit test helpers in `scripts/test_harmonix_report.py`**

```python
def run_cli_capture(argv: list[str], **kw) -> tuple[str, str, int]:
    ...


def extract_ranked_symbols(section_text: str) -> set[str]:
    ...
```

- [ ] **Step 5: Extract a portfolio section renderer that returns text plus status**

```python
def render_portfolio_summary_section(
    *,
    position_rows: list[dict[str, Any]],
) -> tuple[str, SectionStatus]:
    ...
```

- [ ] **Step 6: Make portfolio hard-fail only on missing required DB tables**

```python
required_tables = ("pm_positions", "pm_legs", "pm_cashflows")
missing_tables = [name for name in required_tables if not _table_exists(con, name)]
if missing_tables:
    emit_status(SectionStatus("portfolio-summary", "HARD_FAIL", None, [f"missing tables: {', '.join(missing_tables)}"], True))
    return 1
```

- [ ] **Step 7: Add best-effort `Flagged Positions` rendering**

```python
lines.append("")
lines.append("### Flagged Positions")
if not flagged_positions:
    lines.append("- (none)")
else:
    for item in flagged_positions:
        lines.append(f"- {item['symbol']} | {item['issue']} | {item['mode']}")
```

- [ ] **Step 7: Re-run the focused test script**
- [ ] **Step 8: Re-run the focused test script**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
portfolio section assertions pass; remaining rotation-section assertions may still fail
```

- [ ] **Step 8: Commit the portfolio-section milestone**
- [ ] **Step 9: Commit the portfolio-section milestone**

```bash
git add scripts/test_harmonix_report.py scripts/report_daily_funding_with_portfolio.py
git commit -m "feat: add portfolio summary section contract"
```

### Task 3: Add Shared Candidate Loader Flags And Section Split Tests

**Files:**
- Modify: `scripts/test_harmonix_report.py`
- Modify: `scripts/report_daily_funding_with_portfolio.py`
- Create: `scripts/report_daily_funding_sections.py`

- [ ] **Step 1: Extend test fixtures so rotation candidates can represent**

```python
        now = datetime.now(timezone.utc)
        fixture_rows = [
            # ranked general
            ("hyperliquid", "ATOM", 0.00040, 20, 20, "fresh", []),
            # ranked equities
            ("hyperliquid", "DOGE", 0.00039, 20, 20, "fresh", []),
            # held symbol, should be excluded from both ranked lists
            ("hyperliquid", "BTC", 0.00038, 20, 20, "fresh", []),
            # APR14 below 20%, should move to flagged
            ("hyperliquid", "WEAKAPR", 0.00002, 20, 20, "fresh", []),
            # stale symbol, should move to flagged
            ("hyperliquid", "STALECOIN", 0.00041, 20, 20, "stale", ["STALE"]),
            # low sample, should move to flagged
            ("hyperliquid", "LOWSAMPLE", 0.00042, 10, 2, "fresh", ["LOW_14D_SAMPLE", "LOW_3D_SAMPLE"]),
            # broken persistence, should move to flagged
            ("hyperliquid", "BROKEN", 0.00043, 20, 20, "fresh", ["BROKEN_PERSISTENCE"]),
            # severe structure, should move to flagged
            ("hyperliquid", "STRUCT", 0.00044, 20, 20, "fresh", ["SEVERE_STRUCTURE"]),
        ]
        felix_membership = {"DOGE", "DOGE ", "doge"}
        expected_ranked_general = {"ATOM"}
        expected_ranked_equities = {"DOGE"}
        expected_flagged = {"WEAKAPR", "STALECOIN", "LOWSAMPLE", "BROKEN", "STRUCT"}
```

- [ ] **Step 2: Add failing assertions for general/equities split**

```python
        stdout_general, stderr_general, rc_general = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-general", "--top", "10"]
        )
        stdout_equities, stderr_equities, rc_equities = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-equities", "--top", "10"]
        )
        assert rc_general == 0
        assert rc_equities == 0
        assert "## Top 10 Rotation Candidates - General" in stdout_general
        assert "## Top 10 Rotation Candidates - Equities" in stdout_equities
        assert "DOGE" not in stdout_general
        assert "DOGE" in stdout_equities
        assert "BTC" not in stdout_general
        assert "BTC" not in stdout_equities
        assert "WEAKAPR" not in stdout_general
        assert "STALECOIN" not in stdout_general
        assert "LOWSAMPLE" not in stdout_general
        assert "BROKEN" not in stdout_general
        assert "STRUCT" not in stdout_general
        assert "### Flagged Candidates" in stdout_general
        assert "### Flagged Candidates" in stdout_equities
        assert "WEAKAPR" in stdout_general or "WEAKAPR" in stdout_equities
        assert "STALECOIN" in stdout_general or "STALECOIN" in stdout_equities

        stdout_general_15, stderr_general_15, rc_general_15 = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-general", "--top", "15"]
        )
        assert rc_general_15 == 0
        assert "## Top 15 Rotation Candidates - General" in stdout_general_15

        stdout_missing_loris, stderr_missing_loris, rc_missing_loris = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-general", "--top", "10"],
            loris_mode="missing",
        )
        assert rc_missing_loris == 0
        assert "### Flagged Candidates" in stdout_missing_loris

        stdout_global_stale, stderr_global_stale, rc_global_stale = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-general", "--top", "10"],
            loris_mode="globally_stale",
        )
        assert rc_global_stale == 0
        assert "(no eligible general candidates)" in stdout_global_stale
        assert "### Flagged Candidates" in stdout_global_stale
        assert expected_ranked_general == extract_ranked_symbols(stdout_general)
        assert expected_ranked_equities == extract_ranked_symbols(stdout_equities)
```

- [ ] **Step 3: Add failing assertions for status JSON on `NORMAL`, `DEGRADED`, and `HARD_FAIL` paths**

```python
        assert len(stderr_general.splitlines()) == 1
        meta_general = json.loads(stderr_general.splitlines()[-1])
        assert meta_general["section"] == "rotation-general"
        assert meta_general["state"] in {"NORMAL", "DEGRADED"}
        assert meta_general["hard_fail"] is False

        stdout_stale, stderr_stale, rc_stale = report.run_cli_capture(
            ["--db", str(db_path), "--section", "rotation-general", "--top", "10"],
            force_felix_state="stale_cache",
        )
        assert rc_stale == 0
        assert len(stderr_stale.splitlines()) == 1
        meta_stale = json.loads(stderr_stale.splitlines()[-1])
        assert meta_stale["state"] == "DEGRADED"
        assert meta_stale["hard_fail"] is False
        assert "could not be partitioned reliably" in stdout_stale or "ranked split omitted" in stdout_stale

        stdout_fail, stderr_fail, rc_fail = report.run_cli_capture(
            ["--db", str(db_path), "--section", "portfolio-summary"],
            drop_tables=True,
        )
        assert rc_fail == 1
        assert len(stderr_fail.splitlines()) == 1
        meta_fail = json.loads(stderr_fail.splitlines()[-1])
        assert meta_fail["state"] == "HARD_FAIL"
        assert meta_fail["hard_fail"] is True
```

- [ ] **Step 4: Add failing assertions for symbol normalization and no-overlap invariants**

```python
        assert "DOGE" not in stdout_general
        assert "DOGE" in stdout_equities
        assert "doge" not in stdout_general.lower()
        general_ranked = extract_ranked_symbols(stdout_general)
        equities_ranked = extract_ranked_symbols(stdout_equities)
        assert general_ranked.isdisjoint(equities_ranked)
```

- [ ] **Step 5: Inline the candidate ranking windows and score formula in the loader path**

```python
APR windows: latest, 1d, 2d, 3d, 7d, 14d
stability = 0.55 * apr_14d + 0.30 * apr_7d + 0.15 * apr_latest
```

- [ ] **Step 6: Normalize symbols before held-symbol exclusion and Felix membership checks**

```python
def normalize_symbol(raw: str) -> str:
    return str(raw or "").strip().upper()
```

- [ ] **Step 7: Split candidate rendering into shared filtering plus section-specific partitioning**

```python
@dataclass
class FlaggedCandidate:
    symbol: str
    reason: str
    flags: list[str]


def build_candidate_pool(...) -> tuple[list[CandidateRow], list[FlaggedCandidate], SectionStatus]:
    ...


def render_rotation_section(
    *,
    section: str,
    ranked_rows: list[CandidateRow],
    flagged_rows: list[FlaggedCandidate],
    top: int,
) -> str:
    ...
```

- [ ] **Step 8: Make stale or unavailable Felix classification collapse ranked output to empty degraded sections**

```python
if membership_state in {"stale_cache", "unavailable"}:
    ranked_rows = []
    warnings.append("Felix classification unavailable; ranked split omitted")
```

- [ ] **Step 9: Add missing/global-stale Loris handling in the candidate-pool builder**

```python
if not csv_path.exists():
    return [], build_flagged_candidates_from_missing_source(...), degraded_status("missing loris csv")
if latest_global_age_hours >= 6:
    return [], build_flagged_candidates_from_stale_pool(...), degraded_status("stale candidate funding")
```

- [ ] **Step 10: Re-run the focused test script**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
harmonix report tests passed
```

- [ ] **Step 11: Commit the rotation-section implementation**

```bash
git add scripts/test_harmonix_report.py scripts/report_daily_funding_with_portfolio.py
git commit -m "feat: add sectioned rotation candidate rendering"
```

### Task 4: Preserve On-Demand Rotation Analysis And Verify End-To-End CLI Behavior

**Files:**
- Modify: `scripts/test_harmonix_report.py`
- Modify: `scripts/report_daily_funding_with_portfolio.py`
- Modify: `scripts/report_daily_funding_sections.py`

- [ ] **Step 1: Add regression assertions that rotation-analysis mode still works**

```python
        stdout_rotation, stderr_rotation, rc_rotation = report.run_cli_capture(
            ["--db", str(db_path), "--rotate-from", "BTC", "--rotate-to", "ETH"]
        )
        assert rc_rotation == 0
        assert "# Rotation Cost Analysis" in stdout_rotation
```

- [ ] **Step 2: Add a local header-assembly contract test for upstream orchestration**

```python
        header = report_sections.build_global_header(
            [
                SectionStatus("portfolio-summary", "NORMAL", "2026-03-11T01:00:00Z", [], False),
                SectionStatus("rotation-general", "DEGRADED", "2026-03-11T01:05:00Z", ["stale candidate funding"], False),
            ],
            failed_sections=["rotation-equities"],
        )
        assert "State: DEGRADED" in header
        assert "rotation-equities" in header
        assert "2026-03-11T01:05:00Z" in header
```

- [ ] **Step 3: Add an end-to-end CLI smoke test for each required daily section**

```python
        for section in ["portfolio-summary", "rotation-general", "rotation-equities"]:
            stdout, stderr, rc = report.run_cli_capture(["--db", str(db_path), "--section", section])
            assert rc == 0
            assert len(stderr.splitlines()) == 1
            meta = json.loads(stderr.splitlines()[0])
            assert meta["section"] == section
            assert meta["state"] in {"NORMAL", "DEGRADED"}
            assert meta["hard_fail"] is False
            assert stdout.splitlines()[0].startswith("## ")
```

- [ ] **Step 4: Run the full focused test script again**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
harmonix report tests passed
```

- [ ] **Step 5: Run a manual CLI sanity pass against the workspace script help**

Run:

```bash
python3 scripts/report_daily_funding_with_portfolio.py --help
```

Expected:

```text
help output lists `--section`, `--top`, `--rotate-from`, `--rotate-to` and no supported daily `--equities` path
```

- [ ] **Step 6: Commit the runtime verification milestone**

```bash
git add scripts/test_harmonix_report.py scripts/report_daily_funding_with_portfolio.py
git commit -m "test: verify sectioned report runtime end to end"
```

## Chunk 2: Docs And Contract Alignment

### Task 5: Update Workflow And Tooling Docs

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `TOOLS.md`

- [ ] **Step 1: Rewrite `WORKFLOW.md` daily report assembly**

```markdown
1. Build global header from upstream-consumed stderr metadata
2. `Portfolio Summary`
3. `Top 10 Rotation Candidates - General`
4. `Top 10 Rotation Candidates - Equities`
```

- [ ] **Step 2: Add the missing workflow contract bullets to `WORKFLOW.md`**

```markdown
- all three section runs are required daily sections
- partial report on hard-fail still sets workflow state to `DEGRADED`
- the upstream agent/global-header builder should use the maximum successful section `snapshot_ts`
- `Rotation Cost Analysis` is on-demand only, not a daily-required block
```

- [ ] **Step 3: Rewrite `TOOLS.md` command examples**

```markdown
python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

- [ ] **Step 4: Add the removed CLI paths and failure contract to `TOOLS.md`**

```markdown
- `--equities` is rejected
- default no-`--section` daily mode is removed
- `--section` is mutually exclusive with `--rotate-from/--rotate-to`
```

- [ ] **Step 5: Review the rendered markdown for internal contradictions**

Run:

```bash
rg -n "Top 5 Rotation Candidates|--equities|Rotation Cost Analysis|one-shot|combined report|default mode" WORKFLOW.md TOOLS.md
```

Expected:

```text
remaining matches only where the docs intentionally describe on-demand rotation analysis or historical context
```

- [ ] **Step 6: Commit the workflow/tooling docs**

```bash
git add WORKFLOW.md TOOLS.md
git commit -m "docs: align workflow and tools with sectioned report"
```

### Task 6: Update Runtime Specs

**Files:**
- Modify: `spec/report-pipeline.md`
- Modify: `spec/report-scripts.md`
- Modify: `spec/feat-delta-neutral-agent.md`

- [ ] **Step 1: Rewrite `spec/report-scripts.md` around section mode**

```markdown
- `--section portfolio-summary|rotation-general|rotation-equities`
- `--top <n>` with `n >= 1`, default `10` in daily section mode
- `--rotate-from/--rotate-to` remains on-demand only
- `--equities` fails with non-zero exit
- `--section` is mutually exclusive with rotation-analysis flags
- missing both section mode and rotation mode fails with non-zero exit
- there is no default combined-report mode
- unknown `--section` fails non-zero
- section mode prints exactly one section per invocation
- non-default `--top` changes the section header count
```

- [ ] **Step 2: Rewrite `spec/report-pipeline.md` to document**

```markdown
- one section per invocation
- stdout section body vs stderr JSON metadata separation
- stderr JSON fields: `section`, `state`, `snapshot_ts`, `warnings`, `hard_fail`
- global-header assembly behavior
- upstream partial-report behavior when a required section hard-fails
- global header state derivation and snapshot timestamp derivation
- `Flagged Positions` and `Flagged Candidates`
```

- [ ] **Step 3: Update `spec/feat-delta-neutral-agent.md` report format**

```markdown
upstream global header
1. Portfolio Summary
2. Top 10 Rotation Candidates - General
3. Top 10 Rotation Candidates - Equities
`Rotation Cost Analysis` is on-demand only, not a daily-required block
```

- [ ] **Step 4: Run a contradiction search across specs**

Run:

```bash
rg -n "Top 5 Rotation Candidates|--equities|one run|Rotation Cost Analysis|combined report|default mode" spec/report-pipeline.md spec/report-scripts.md spec/feat-delta-neutral-agent.md
```

Expected:

```text
no stale daily-contract wording remains, except on-demand rotation-analysis references
```

- [ ] **Step 5: Commit the spec alignment**

```bash
git add spec/report-pipeline.md spec/report-scripts.md spec/feat-delta-neutral-agent.md
git commit -m "docs: align report specs with sectioned output contract"
```

### Task 7: Final Verification And Handoff

**Files:**
- Modify: `scripts/report_daily_funding_with_portfolio.py`
- Modify: `scripts/test_harmonix_report.py`
- Modify: `WORKFLOW.md`
- Modify: `TOOLS.md`
- Modify: `spec/report-pipeline.md`
- Modify: `spec/report-scripts.md`
- Modify: `spec/feat-delta-neutral-agent.md`

- [ ] **Step 1: Run the focused test harness**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
harmonix report tests passed
```

- [ ] **Step 2: Run targeted contract searches**

Run:

```bash
rg -n "Top 5 Rotation Candidates|--equities" scripts/report_daily_funding_with_portfolio.py scripts/test_harmonix_report.py WORKFLOW.md TOOLS.md spec/report-pipeline.md spec/report-scripts.md spec/feat-delta-neutral-agent.md
```

Expected:

```text
no remaining daily-contract references to the removed `--equities` path or `Top 5` rotation template
```

- [ ] **Step 3: Run a manual section smoke pass if local data is available, otherwise run the deterministic fixture-backed smoke in `scripts/test_harmonix_report.py`**

Run:

```bash
python3 scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
python3 scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
python3 scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

Expected:

```text
either real-data commands exit cleanly with one section plus one stderr JSON line, or the fixture-backed harness proves the same contract deterministically
```

- [ ] **Step 4: Verify degraded and partial-report behavior through the focused harness**

Run:

```bash
python3 scripts/test_harmonix_report.py
```

Expected:

```text
includes coverage for degraded Felix classification, hard-fail portfolio path, and the stderr metadata contract consumed by the upstream partial-report/header builder
```

- [ ] **Step 5: Apply @verification-before-completion before claiming success**

```text
Re-check test output, CLI output, and doc contradictions before closing the task.
```

- [ ] **Step 6: Commit the verified feature**

```bash
git add scripts/report_daily_funding_with_portfolio.py scripts/test_harmonix_report.py WORKFLOW.md TOOLS.md spec/report-pipeline.md spec/report-scripts.md spec/feat-delta-neutral-agent.md
git commit -m "feat: add sectioned funding report workflow"
```
