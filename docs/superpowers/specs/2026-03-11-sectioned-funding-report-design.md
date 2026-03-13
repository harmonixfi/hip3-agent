# Sectioned Funding Report Design

**Date:** 2026-03-11
**Status:** Approved for planning
**Owner:** Harmonix

## Goal

Reshape the Harmonix daily funding report flow so the agent assembles the final message from three independently rendered sections:

1. `Portfolio Summary`
2. `Top 10 Rotation Candidates - General`
3. `Top 10 Rotation Candidates - Equities`

The runtime must continue using a single entrypoint script, but the script should render one section per invocation via explicit CLI section selection.

## Context

Current behavior is centered on `scripts/report_daily_funding_with_portfolio.py`, which renders a combined report in one run and supports an `--equities` filter for candidate output. That is not enough for the desired operating model:

- the agent should orchestrate report assembly section by section
- the `general` and `equities` candidate lists must be mutually exclusive
- workflow documentation should define which section commands to run, not assume one monolithic daily output

Discord delivery is out of scope for this design. OpenClaw agent delivery support already exists elsewhere.

## Non-Goals

- No changes to chat delivery infrastructure
- No auto-execution or trading-state changes
- No expansion of the strategy universe beyond current candidate inputs
- No redesign of on-demand rotation analysis beyond preserving compatibility

## Recommended Approach

Use one CLI entrypoint with explicit section dispatch, while internally refactoring the reporting code into section-oriented helpers.

This keeps the user-facing and workflow-facing contract simple:

- one script to call
- one explicit `--section` selector
- one deterministic output block per invocation

It also avoids the ambiguity of flag combinations such as `--equities` plus ad hoc exclusion flags.

## CLI Contract

The primary daily section mode should use:

```bash
python scripts/report_daily_funding_with_portfolio.py --section portfolio-summary
python scripts/report_daily_funding_with_portfolio.py --section rotation-general --top 10
python scripts/report_daily_funding_with_portfolio.py --section rotation-equities --top 10
```

### Section values

- `portfolio-summary`
- `rotation-general`
- `rotation-equities`

### CLI rules

- `--section` is the source of truth for daily report section rendering.
- Each invocation prints exactly one human-readable section.
- `--top` applies to rotation sections and should default to `10` for the sectioned daily workflow.
- `--top` must be an integer `>= 1`; invalid values such as `0` or negative numbers must fail with non-zero exit.
- If `--top` is passed with a value other than `10`, the section header should reflect the actual rendered count target, for example `Top 15 Rotation Candidates - General`.
- `--rotate-from` and `--rotate-to` remain supported for on-demand rotation analysis.
- `--section` and `--rotate-from/--rotate-to` are mutually exclusive.
- Legacy `--equities` should be removed from the daily reporting contract.
- `--equities` must be rejected with non-zero exit.
- invoking the script with neither `--section` nor `--rotate-from/--rotate-to` must fail fast with non-zero exit

### Invalid combinations

The script should exit non-zero for:

- unknown `--section` values
- `--section` used together with `--rotate-from`
- `--section` used together with `--rotate-to`
- only one of `--rotate-from` / `--rotate-to` provided

## Section Contracts

### 1. Portfolio Summary

The `portfolio-summary` section should render only the portfolio review block.

It continues using current DB, cashflow, and carry inputs to produce position-level advisory rows.

#### Required fields

- `symbol`
- `amount ($)`
- `start time`
- `avg 15d funding ($)`
- `funding 1d / 2d / 3d ($)`
- `open fees ($)`
- `breakeven time`
- `advisory`

#### Semantics

- field meanings stay aligned with the existing feature spec and workflow contract
- no Felix-equities filtering applies here
- section header should be `## Portfolio Summary`

#### Empty state

If no open positions are tracked, the section should still render the header and a clear empty-state line:

- `(no open positions tracked)`

#### Flagged Positions subsection

At the end of the section, render:

- `### Flagged Positions`

This subsection lists tracked positions that were rendered with degraded confidence or omitted from the main portfolio table because of non-fatal data quality issues.

Relevant issues include:

- missing carry inputs for a specific position
- incomplete cashflow history for a specific position
- fee resolution that required fallback estimation

Each flagged row should include at least:

- `symbol`
- short issue summary
- whether the main row was rendered with fallback values or omitted

### 2. Top 10 Rotation Candidates - General

The `rotation-general` section should render only the non-equities candidate block.

#### Candidate source

- `data/loris_funding_history.csv`
- same ranking windows and stability score as current runtime
- candidate universe uses the supported report exchanges already admitted by the runtime candidate loader

#### Candidate loader contract

The shared candidate loader must provide, at minimum, for each candidate identity (`symbol + exchange`):

- `symbol`
- `exchange`
- `latest_ts`
- `apr_latest`
- `apr_1d`
- `apr_2d`
- `apr_3d`
- `apr_7d`
- `apr_14d`
- `stability_score`
- `sample_count_14d`
- `sample_count_3d`
- `flags`

Flag vocabulary used by this design:

- `STALE`
- `LOW_14D_SAMPLE`
- `LOW_3D_SAMPLE`
- `BROKEN_PERSISTENCE`
- `SEVERE_STRUCTURE`

`BROKEN_PERSISTENCE` and `SEVERE_STRUCTURE` are exclusionary flags for ranked candidates and must be surfaced through `Flagged Candidates`.

#### Filters

Apply filters in this order:

1. restrict to candidate-eligible names only
2. remove symbols currently held in the portfolio
3. remove candidates whose normalized symbol belongs to the Felix equities universe
4. rank remaining symbols by stability score
5. take top `N`

#### Header

- `## Top {N} Rotation Candidates - General`

#### Fields

- `rank`
- `symbol`
- `venue`
- `APR14`
- `APR7`
- `APR 1d / 2d / 3d`
- `stability score`
- `note`

#### Candidate eligibility gate

Before Felix-based splitting, the shared candidate universe must apply the strategy qualification gate:

- `APR14 >= 20%`
- latest symbol funding snapshot age `< 6` hours
- 14-day sample count `>= 16`
- 3-day sample count `>= 3`
- no severe exclusion flags

For this design, severe exclusion flags are:

- stale symbol funding
- low 14-day sample count
- low 3-day sample count
- broken persistence across the lookback windows
- severe structural flags from the candidate loader

Names that fail this gate must not appear in the ranked candidate list for either rotation section.

They should instead be surfaced in `Flagged Candidates` if they are relevant to that section split.

If the latest funding snapshot is stale across the whole candidate set, the ranked list should be empty for that section run. In that case, the section renders as degraded and surfaces names only under `Flagged Candidates`.

If the Felix classification cache is stale but still parseable, ranking and section partitioning may continue using the cached symbol set. In that case, the section must render as degraded and show a warning that the split may be outdated.

#### Empty state

If filtering leaves no eligible candidates, the section should still render the header and:

- `(no eligible general candidates)`

#### Flagged Candidates subsection

At the end of the section, render:

- `### Flagged Candidates`

This subsection lists symbols relevant to the general split that were excluded from the ranked list because of:

- stale data
- low sample quality
- broken persistence
- severe structural flags

Each flagged row should include at least:

- `symbol`
- short exclusion reason
- relevant flags or freshness note

In normal classification conditions, `Flagged Candidates` for `rotation-general` contains only non-Felix symbols that failed the candidate eligibility gate.

If Felix classification is stale or unavailable, `rotation-general` should not attempt a definitive general/equities split for flagged names. In that case, the subsection should contain only names already known to be non-Felix from trusted cached classification; otherwise it should emit a single explanatory line that flagged candidates could not be partitioned reliably.

### 3. Top 10 Rotation Candidates - Equities

The `rotation-equities` section should render only the Felix-equities candidate block.

#### Candidate source

- `data/loris_funding_history.csv`
- same ranking windows and stability score as current runtime
- candidate universe uses the supported report exchanges already admitted by the runtime candidate loader

#### Candidate loader contract

The shared candidate loader must provide, at minimum, for each symbol:

- `symbol`
- `latest_ts`
- `apr_latest`
- `apr_1d`
- `apr_2d`
- `apr_3d`
- `apr_7d`
- `apr_14d`
- `stability_score`
- `sample_count_14d`
- `sample_count_3d`
- `flags`

Flag vocabulary used by this design:

- `STALE`
- `LOW_14D_SAMPLE`
- `LOW_3D_SAMPLE`
- `BROKEN_PERSISTENCE`
- `SEVERE_STRUCTURE`

`BROKEN_PERSISTENCE` and `SEVERE_STRUCTURE` are exclusionary flags for ranked candidates and must be surfaced through `Flagged Candidates`.

#### Filters

Apply filters in this order:

1. restrict to candidate-eligible names only
2. remove symbols currently held in the portfolio
3. keep only symbols that belong to the Felix equities universe
4. rank remaining symbols by stability score
5. take top `N`

#### Header

- `## Top {N} Rotation Candidates - Equities`

#### Fields

- `rank`
- `symbol`
- `APR14`
- `APR7`
- `APR 1d / 2d / 3d`
- `stability score`
- `note`

#### Candidate eligibility gate

Before Felix-based splitting, the shared candidate universe must apply the strategy qualification gate:

- `APR14 >= 20%`
- latest symbol funding snapshot age `< 6` hours
- 14-day sample count `>= 16`
- 3-day sample count `>= 3`
- no severe exclusion flags

For this design, severe exclusion flags are:

- stale symbol funding
- low 14-day sample count
- low 3-day sample count
- broken persistence across the lookback windows
- severe structural flags from the candidate loader

Names that fail this gate must not appear in the ranked candidate list for either rotation section.

They should instead be surfaced in `Flagged Candidates` if they are relevant to that section split.

If the latest funding snapshot is stale across the whole candidate set, the ranked list should be empty for that section run. In that case, the section renders as degraded and surfaces names only under `Flagged Candidates`.

#### Empty state

If filtering leaves no eligible candidates, the section should still render the header and:

- `(no eligible equities candidates)`

#### Flagged Candidates subsection

At the end of the section, render:

- `### Flagged Candidates`

This subsection lists symbols relevant to the equities split that were excluded from the ranked list because of:

- stale data
- low sample quality
- broken persistence
- severe structural flags

Each flagged row should include at least:

- `symbol`
- short exclusion reason
- relevant flags or freshness note

In normal classification conditions, `Flagged Candidates` for `rotation-equities` contains only Felix symbols that failed the candidate eligibility gate.

If Felix classification is stale or unavailable, `rotation-equities` should not attempt a definitive general/equities split for flagged names. In that case, the subsection should contain only names already known to be Felix from trusted cached classification; otherwise it should emit a single explanatory line that flagged candidates could not be partitioned reliably.

## Filtering Invariants

The daily rotation sections must obey these invariants:

- `rotation-general` and `rotation-equities` are mutually exclusive sets for a given snapshot
- a symbol must never appear in both sections in the same report assembly
- both sections exclude symbols already held in the current portfolio
- Felix-equities membership is the only boundary between the two rotation sections
- the same candidate eligibility gate is applied before the Felix split

If Felix-equities membership cannot be determined reliably, the script must not silently pretend the split is valid.

## Felix Membership Resolution Contract

Felix-equities membership is the classification boundary for the two rotation sections.

### Source of truth

- primary source: Felix equities asset API
- local cache file: `data/felix_equities_cache.json`

### Output contract

Membership resolution returns:

- a set of uppercase ticker symbols
- metadata describing freshness and whether the result is trusted for section splitting

### Symbol normalization

All comparisons across:

- Loris candidate symbols
- held portfolio symbols
- Felix membership symbols

must use the same normalization rule:

- uppercase ASCII ticker
- trim surrounding whitespace
- compare the base ticker only, with no venue prefix or suffix

This normalization contract is required before:

- held-symbol exclusion
- Felix general/equities splitting
- flagged-candidate partitioning

### Freshness rules

- cache validity target remains `24` hours
- fresh cache is acceptable for normal section rendering
- stale cache may be used only to emit a degraded section with an explicit warning
- absence of both fresh API data and any cache means membership is unavailable

### Auth expectations

- if API auth is available through environment, use it
- if auth is absent or fetch fails, the runtime may fall back to cache
- auth absence must not be silently interpreted as a successful fresh lookup

### Failure behavior

- `rotation-general` and `rotation-equities` must never claim normal filtering when membership resolution is unavailable
- section output should clearly indicate degraded classification state
- ranked output behavior must follow this table:

| Felix classification state | Ranked general/equities output | Section state |
|---|---|---|
| fresh API | allowed | `NORMAL` if no other degradation |
| fresh cache | allowed | `NORMAL` if no other degradation |
| stale cache | do not render ranked lists; render empty ranked block + explanatory warning + any safely partitionable flagged names | `DEGRADED` |
| no cache and no API | do not render ranked lists; render empty ranked block + explanatory warning | `DEGRADED` |

This contract keeps the classification unit bounded: resolve membership once, expose `symbols + freshness + trusted/degraded state`, and let section renderers consume that result.

## Freshness And Degraded-State Rules

### Portfolio Summary

Degraded conditions should reflect failures or stale state in the portfolio/carry inputs, such as:

- missing or incomplete carry inputs
- cashflow data gaps that materially reduce confidence

Hard-fail conditions for `portfolio-summary`:

- missing required DB tables

`portfolio-summary` should exit non-zero for hard-fail conditions instead of rendering a degraded section body.

For non-fatal portfolio degradation, the section should still render best-effort portfolio rows and list degraded symbols under `Flagged Positions`.

### Rotation sections

Degraded conditions should reflect failures or stale state in:

- latest Loris funding snapshot
- Felix-equities membership resolution

If Felix-equities fetch or cache resolution fails:

- `rotation-general` must clearly state it is degraded because exclusion cannot be trusted
- `rotation-equities` must clearly state it is degraded because inclusion cannot be trusted

No silent fallback to an unfiltered candidate list is allowed.

Hard-fail conditions for rotation sections should be kept narrow. Missing Loris data, stale funding, or stale Felix classification should normally produce degraded section output rather than a non-zero exit, as long as the script can still render a truthful human-readable section.

## Section Result Interface

The section commands need a minimal orchestration contract so the agent can build one global header without parsing ambiguous prose.

For daily section mode:

- `stdout`: the human-readable section body only
- exit code `0`: section rendered successfully, either `NORMAL` or `DEGRADED`
- non-zero exit: hard failure, section could not be rendered truthfully

The implementation should expose section status in a machine-readable way for orchestration:

- stderr should emit exactly one machine-readable JSON line for section status metadata
- stdout remains reserved for the human-readable section body

The stderr JSON metadata must contain:

- `section`
- `state`: `NORMAL` or `DEGRADED`
- `snapshot_ts`
- `warnings`: array of warning or degradation reasons
- `hard_fail`: boolean, always `false` on exit code `0`

On non-zero exit, stderr should still emit one final JSON metadata line when possible with:
On non-zero exit, stderr must still emit one final JSON metadata line with:

- `section`
- `state`: `HARD_FAIL`
- `snapshot_ts`: `null` if unavailable
- `warnings`: array containing the failure reason
- `hard_fail`: `true`

Planning must preserve the unit boundary:

- section renderer produces human text on stdout
- orchestrator consumes explicit stderr JSON metadata separately

For one daily assembly, all section runs must be treated as part of the same snapshot window. The orchestrator should run the sections back-to-back after data-refresh steps, and the global header `snapshot timestamp` should be the maximum `snapshot_ts` reported by successfully rendered sections.

## Global Header Contract

The assembled daily report must begin with one global header block produced by the agent orchestration layer, not by the section commands.

The global header must include:

- snapshot timestamp
- report timezone
- workflow state: `NORMAL` or `DEGRADED`
- warning line near the top when freshness, integrity, or classification coverage is degraded

Section commands should not repeat this shared header. They only render their own section body.

The agent assembles the final report as:

1. global header
2. `Portfolio Summary`
3. `Top 10 Rotation Candidates - General`
4. `Top 10 Rotation Candidates - Equities`

All three of those sections are required daily sections for the workflow contract.

The global header state should be derived from section status metadata:

- `NORMAL` only if all rendered sections report `NORMAL`
- `DEGRADED` if any rendered section reports `DEGRADED`
- `DEGRADED` if any required section hard-fails and a partial report is sent

If a required section exits non-zero, the agent should still send a partial report using the sections that rendered successfully and add a failure warning in the global header naming the missing section(s).

This spec includes the orchestration-layer change required to consume per-section stderr metadata and assemble a partial report when a section hard-fails.

## Workflow Contract

`WORKFLOW.md` should stop describing the daily report as a single monolithic script output contract.

Instead, the workflow should define report assembly as:

1. run `portfolio-summary`
2. run `rotation-general`
3. run `rotation-equities`
4. build one global header containing snapshot/freshness/workflow-state metadata
5. combine the header and three rendered outputs in that fixed order

The workflow should describe the final human-facing report sections as:

1. `Portfolio Summary`
2. `Top 10 Rotation Candidates - General`
3. `Top 10 Rotation Candidates - Equities`

`Rotation Cost Analysis` should move out of the required daily report template and remain an on-demand workflow path.

## Backward Compatibility

The existing on-demand rotation analysis mode remains supported:

```bash
python scripts/report_daily_funding_with_portfolio.py \
  --rotate-from <position_id|ticker> \
  --rotate-to <symbol>
```

This mode is separate from the new daily section assembly contract and should keep printing only the rotation analysis block.

There is no default combined-report mode after this change. Daily callers must migrate to explicit `--section` usage.

## Code-Structure Guidance

The entrypoint should remain `scripts/report_daily_funding_with_portfolio.py`, but the implementation should be internally decomposed into clearer units:

- section selection / CLI validation
- shared portfolio-loading helpers
- shared candidate-loading helpers
- Felix-universe membership resolution
- section-specific renderers

This is a bounded refactor in service of the new report contract, not a general rewrite.

## Documentation Updates Required

The implementation plan must update these files so the daily contract has one consistent source of truth:

- `WORKFLOW.md`
- `TOOLS.md`
- `spec/report-pipeline.md`
- `spec/report-scripts.md`
- `spec/feat-delta-neutral-agent.md`

After this change set, these docs must no longer describe the old daily contract as:

- `Top 5 Rotation Candidates`
- daily-required `Rotation Cost Analysis`

The updated source of truth for the daily report contract should be the workspace docs above, with the feature spec aligned to match.

## Testing Scope

The implementation should include tests for:

- section dispatch returns only the requested block
- invoking the script with no `--section` and no rotation args fails non-zero
- `rotation-general` excludes all Felix-equities symbols
- `rotation-equities` includes only Felix-equities symbols
- held symbols are excluded from both rotation sections
- symbol normalization is applied consistently across candidates, held symbols, and Felix membership symbols
- overlap between `rotation-general` and `rotation-equities` is empty for the same input dataset
- candidate eligibility gate excludes names below `APR14 < 20%` or with broken freshness/persistence from the ranked list
- flagged candidates subsection includes excluded stale/weak/broken names instead of silently dropping them
- invalid CLI combinations fail with non-zero exit
- `--equities` fails with non-zero exit
- stale or missing Loris data produces degraded rotation output
- globally stale candidate data produces an empty ranked list plus populated `Flagged Candidates`
- Felix-membership resolution failures produce explicit degraded output
- missing required DB tables fail clearly for portfolio rendering
- degraded portfolio inputs surface under `Flagged Positions`
- stderr metadata emits exactly one JSON line on `NORMAL`, `DEGRADED`, and `HARD_FAIL` paths
- partial-report orchestration uses successful sections, marks the header degraded, and names any failed required section

## Open Decisions Already Resolved

These decisions are fixed by this design:

- use one entrypoint, not multiple scripts
- render one section per invocation
- use explicit `--section` selection
- define `general` as symbols not in Felix equities
- define `equities` as symbols in Felix equities
- exclude held symbols from both rotation sections
- keep Discord delivery out of scope

## Ready-For-Planning Checklist

- scope is limited to one reporting workflow change
- CLI contract is explicit
- section boundaries are well-defined
- degraded-state behavior is specified
- workflow assembly behavior is specified
- testing targets are defined
