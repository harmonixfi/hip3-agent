# Core Tier Portfolio Construction Test Design

**Date:** 2026-03-13
**Status:** Approved for review
**Owner:** Harmonix

## Goal

Design a data-driven test that compares two Core-tier portfolio construction methods for a future HIP3-style vault and determines which method produces the more deployable basket under current market conditions.

This is an operational analysis design, not an auto-trading design.

## Scope

In scope:
- Core tier only
- Advisory only
- Pair selection and basket construction logic
- Comparison of two candidate-selection methods using current data
- Proposed sizing for a hypothetical large portfolio

Out of scope:
- Auto-execution
- Satellite tier design
- Cross-venue perp-perp construction
- Live order placement
- Production automation changes

## Working Assumptions

- Reference portfolio size for design/test purposes: **$1,000,000 USDC**
- Target Core allocation for comparison: **$600,000 USDC**
- If current market quality does not support full deployment, **underdeployment is allowed and preferred over forced allocation**
- Any eventual live pilot may scale the resulting construction down to a smaller amount such as **$300,000 USDC**

## Objective

The analysis should answer one practical question:

> Given current funding and market data, should Core-tier construction default to a portfolio-construction-first method, or fall back to a simpler stability-first method?

The analysis should not force a basket if current conditions are weak. A valid conclusion is that neither method supports full Core deployment.

## Strategy Labels Used In This Design

This design intentionally uses the labels **Strategy 3** and **Strategy 2** because those were the labels approved for this comparison request.

- **Strategy 3** = portfolio-construction-first
- **Strategy 2** = stability-first fallback

There is no Strategy 1 in scope. The numbering is preserved only so the later analysis and recommendation language matches the approved request exactly.

## Universe And Tradeability Rules

The candidate universe should include funding opportunities from:
- `hyperliquid`
- `tradexyz`
- `hyena`
- `kinetiq`

For each candidate asset, the analysis must separately determine whether a viable spot leg exists on:
- Hyperliquid spot
- Felix equities

Tradeability must be modeled explicitly.

### Tradeability statuses

Each candidate should be labeled as one of:
- `EXECUTABLE` — clear spot leg available for intended structure, with no unresolved symbol-mapping or venue-availability doubts
- `CROSS_CHECK_NEEDED` — funding opportunity exists, but at least one of the following remains unresolved:
  - spot existence on Hyperliquid cannot be verified from current data
  - Felix equities membership or mapping is ambiguous
  - ticker normalization is unclear
  - the funding asset and spot asset appear related but cannot be confirmed as the same executable base
- `NON_EXECUTABLE` — no acceptable spot leg found for Core construction after checking available Hyperliquid/Felix sources

A candidate may look attractive on funding but still be excluded from the main Core basket if it is not executable.

## Data Sources And Pull Surface

The analysis should use the local Harmonix runtime as the primary source of truth where possible.

### Required inputs

1. **Funding history / APR windows**
   - primary source: `scripts/pull_loris_funding.py`
   - expected artifact: `data/loris_funding_history.csv`

2. **Market / venue context for Hyperliquid-side state**
   - source: `scripts/pull_hyperliquid_v3.py`

3. **Spot availability cross-check inputs**
   - Hyperliquid spot listings from local/runtime-accessible market data
   - Felix equities membership/cache when available

4. **Optional liquidity / OI context**
   - use the best available venue-level OI or liquidity field already present in current data sources
   - if exact OI rank is unavailable, use a clearly labeled proxy instead of inventing precision

### Step 0: input verification before analysis

Before running either strategy comparison, verify that:
- required files or runtime data sources are present
- freshness can be computed
- the candidate universe loaded successfully
- spot-availability lookup loaded successfully, even if only partially

If this verification fails, the analysis must stop and report a degraded input state rather than pretending the universe is complete.

### Missing-data handling

- If one funding venue is missing from the current pull, candidates from that venue should be excluded from ranked selection and listed under flags if they were otherwise relevant.
- If spot availability cannot be resolved, the candidate may remain visible but must not be treated as fully executable.
- Missing data must never be silently interpreted as zero funding, zero OI, or no spot.

## Shared Data Gate

Before a candidate can enter the Core test universe, it must pass these baseline checks:

- data freshness: **< 12 hours**
- available metrics: `APR_latest`, `APR7`, `APR14`
- enough history to assess regime quality
- no obvious data corruption or unusable gaps

Candidates that fail the shared gate should not enter the primary basket selection runs, but should still appear in a flagged or near-miss section when relevant.

## Trading Plan Alignment And Override Rules

The trading plan is the default operating framework, but this design allows controlled flexibility because the plan was written before inspecting the current live universe.

### Precedence rules

1. **Hard disqualifiers override everything**
   - non-executable structure
   - broken current funding regime
   - materially stale or missing data

2. **Trading-plan thresholds are default anchors, not blind mandates**
   - pair `APR14 >= 10%`
   - preference for realistic breakeven, using **7 days** as the default guide
   - preference for strong liquidity / OI quality

3. **Flexible override is allowed only with explicit justification**
   - if a candidate fails a default threshold but still deserves consideration, the analysis must say exactly which threshold was relaxed, why, and what risk it introduces
   - relaxed-threshold candidates cannot be treated as top-conviction anchor names without that note

4. **Current regime quality beats lagging windows**
   - if a name passes the trading-plan threshold but `APR_latest` and recent regime quality are clearly deteriorating, it should be excluded or downgraded despite passing lagging screens

This rule resolves conflicts between the written plan and real-time analysis: the plan supplies the baseline, but broken execution or broken regime quality has priority.

## Core Candidate Philosophy

For Core-tier construction, the system should prefer:
- durable positive funding
- trend alignment across windows
- liquidity and size capacity
- realistic fee recovery
- clean execution paths

over raw headline APR.

## Shared Candidate Screening For Both Methods

The analysis should screen candidates using soft Core-oriented standards:

- pair structure must be compatible with spot-plus-perp Core construction
- current funding regime should still be acceptable
- pair `APR14` should generally clear a Core-level floor, with **10% pair APR** used as the initial anchor rather than an immutable cutoff
- breakeven should generally be realistic, with **7 days** as the preferred guideline
- names with clearly broken current regime should not make the final pick list even if lagging windows remain attractive

This is a screening framework, not a blind rule engine.

## Canonical Metrics Used In This Design

Two different scores are used and must not be confused.

### 1. `stability_score`

This remains the funding persistence metric inherited from the trading-plan framework:

`stability_score = 0.55 * APR14 + 0.30 * APR7 + 0.15 * APR_latest`

Use `stability_score` as a funding-shape input and as a reported comparison field.

### 2. `pair_quality_score`

This is the broader Core construction score used for ranking and basket selection in this design. It combines funding persistence with execution reality.

`pair_quality_score =`
- `30% funding consistency`
- `25% trend alignment`
- `20% liquidity / OI quality`
- `15% effective APR after structure penalty`
- `10% breakeven / cost realism`

The design should use:
- `stability_score` to describe funding persistence
- `pair_quality_score` to drive final candidate ranking and portfolio construction

## Pair-Level Evaluation Axes

Each candidate should be evaluated on five dimensions, normalized to a **0-100** scale before applying weights.

### 1. Funding consistency
Weight: **30%**

Assess how often funding has remained positive and how noisy the series is. Core positions should not be built on rare spikes or unstable sign flips.

Operational definition:
- standard lookback = **last 30 calendar days** of usable funding observations
- fallback lookback = **last 14 calendar days** only when the symbol or venue does not yet have 30 days of history, and this must be flagged as shorter-history evidence
- primary method: use interval-level or daily funding history to estimate the share of positive observations over the defined lookback window
- preferred interpretation:
  - near-100 score for names with persistently positive funding and low sign-flip frequency
  - mid score for names with mixed but still mostly positive funding
  - low score for names with frequent sign flips or obvious instability
- if only summary windows are available, use a conservative proxy from `APR_latest`, `APR7`, and `APR14`, and label the result as approximate

### 2. Trend alignment
Weight: **25%**

Assess the relationship between:
- `APR_latest`
- `APR7`
- `APR14`

Strong Core candidates should show either aligned positive windows or at least no clear collapse in recent funding. Names whose `APR14` looks strong while `APR7` and `APR_latest` are decaying should be downgraded hard.

Operational definition:
- high score when all three windows are positive and recent windows are not materially weaker
- medium score when all three are positive but trend is flattening
- low score when `APR14` remains elevated but `APR7` and `APR_latest` clearly weaken
- zero or near-zero score when current funding has flipped against the strategy

### 3. Liquidity / OI quality
Weight: **20%**

Core construction needs size. Liquidity and open-interest quality matter more than cosmetic APR.

Operational definition:
- primary field = `oi_rank` from the latest eligible observation for each `exchange + symbol` in `data/loris_funding_history.csv`
- lower `oi_rank` is better
- if `oi_rank` is present, convert it into a 0-100 score using transparent buckets across the Core universe
- if `oi_rank` is missing for a candidate, fall back to the best available venue-level liquidity field already present in runtime data; if no such field exists, assign a conservative low-confidence liquidity score and flag `LOW_LIQUIDITY_CONFIDENCE`
- if only a proxy is available, report it explicitly as a proxy rather than as a true OI rank

### 4. Effective APR after structure penalty
Weight: **15%**

For spot-perp construction, pair APR is not the same as portfolio yield on deployed capital. The analysis should anchor on:

- `effective_apr_anchor = pair_apr / 2`

This is an **unlevered comparison anchor** for test consistency, not a claim about live leveraged ROE. Because both strategies compare the same structure family, the test should use the same unlevered anchor for every candidate.

Operational definition:
- score candidates off `effective_apr_anchor`
- higher score for higher positive effective APR
- do not let this component dominate weaker consistency or execution quality

### 5. Breakeven / cost realism
Weight: **10%**

Candidates that take too long to recover fees and expected slippage are poor Core holdings even if funding looks good in isolation.

Operational definition:
- use **`assumed_capital = $150,000` per candidate** as the normalized Core test lot for pair-level breakeven comparison
- `estimated_total_roundtrip_cost = spot_entry_fee + perp_entry_fee + spot_exit_fee + perp_exit_fee + slippage_allowance + spread_allowance`
- `estimated_daily_net_funding = effective_apr_anchor * 150000 / 365`
- `breakeven_estimate = estimated_total_roundtrip_cost / estimated_daily_net_funding`
- if a stricter existing runtime cost model is available, use it and label it as the source of truth
- if some cost components are missing, keep the estimate approximate and flag the name instead of pretending precision
- if later basket sizing assigns a materially larger per-name allocation than the normalized lot, the final write-up must note that real breakeven may be worse because execution cost can scale non-linearly with size

## Strategy 2: Stability-First Fallback

This method is the simpler baseline.

### Method
- rank individual **executable** candidates primarily by `stability_score`
- require a minimum acceptable `pair_quality_score` of **60 / 100** so that strong funding persistence does not override bad execution reality
- use `pair_quality_score` as the first tie-break field when `stability_score` names are close
- take the best names in order
- build a basket only after the ranking is produced
- apply final portfolio guardrails after ranking

### Sizing method
- begin with a simple quality-ranked allocation
- default starting template for a 2-pair basket: `50 / 50`, then reduce any name that violates liquidity or concentration comfort
- default starting template for a 3-pair basket: `40 / 35 / 25`
- default starting template for a 4-pair basket: `35 / 30 / 20 / 15`
- no single name may exceed **40% of Core capital**
- if the next ranked name is materially weaker, keep the residual capital idle instead of forcing a full basket

### Intended use
This method is the fallback when market breadth is limited or when portfolio optimization adds little value beyond a strong quality ranking.

## Strategy 3: Portfolio-Construction-First

This is the preferred default to test first.

### Method
Instead of asking only which individual pairs rank highest, this method asks which **combination** of 2 to 4 pairs creates the best Core basket.

### Construction principles
- start from candidates that pass the shared data gate and screening framework
- identify **1 to 2 anchor names** with the strongest liquidity and funding consistency
- add pair 3 or pair 4 only if doing so improves the overall basket rather than diluting it
- avoid forcing deployment into lower-quality names solely to hit the target allocation
- allow idle capital when market quality is insufficient

### Sizing method
- size anchors first
- preferred anchor range: **25% to 40% of Core capital per anchor** depending on quality and liquidity
- additional names should generally receive smaller allocations than anchors unless the basket quality is unusually flat
- if the best basket after testing combinations only justifies 2 strong names, stop at 2 and keep the remainder idle
- if a 3rd or 4th name lowers overall deployability, exclude it

### Combination-evaluation method
This section is the core differentiator of Strategy 3.

1. Build a **Strategy 3 pool** from the top **8 executable candidates** by `pair_quality_score` after shared screening.
2. If fewer than 8 executable candidates exist, extend the pool with the highest-ranked `CROSS_CHECK_NEEDED` names, but mark them as execution-risk candidates.
3. Enumerate every **2-name, 3-name, and 4-name combination** from that pool.
4. For each combination, assign provisional capital weights using these rules:
   - start with weights proportional to `pair_quality_score`
   - cap any single name at **40% of Core capital**
   - require every included name to receive at least **15% of Core capital**; otherwise that combination is invalid for that cardinality
   - any capital that cannot be assigned without violating those rules remains **idle**
5. For each valid combination, compute:
   - weighted `pair_quality_score`
   - weighted `stability_score`
   - weighted `effective_apr_anchor`
   - execution-uncertainty count
   - decay-concern count
   - largest position weight
   - deploy ratio = deployed capital / 600000
6. Rank valid combinations in this exact order:
   - lower execution-uncertainty count
   - lower decay-concern count
   - lower largest position weight
   - higher weighted `pair_quality_score`
   - higher deploy ratio
   - higher weighted `effective_apr_anchor`
7. The top-ranked valid combination is the Strategy 3 basket.
8. If no valid 3-name or 4-name combination beats the best 2-name combination on this ordering, keep the smaller basket and leave residual capital idle.

This makes Strategy 3 an explicit basket-selection process rather than a vague "pick good names" instruction.

### Basket objective
The basket should aim to:
- maximize weighted quality and weighted effective APR
- minimize concentration risk
- minimize regime fragility
- minimize execution uncertainty
- avoid forced deployment into marginal names

### Output behavior
A valid Strategy 3 output may deploy less than the full Core target if current data does not justify full exposure.

## Operational Flag Vocabulary

The working dataset should use explicit flags where relevant. At minimum:
- `STALE_DATA`
- `MISSING_APR_WINDOW`
- `MISSING_SPOT`
- `CROSS_CHECK_NEEDED`
- `SHORT_HISTORY`
- `DECAYING_REGIME`
- `HIGH_BREAKEVEN`
- `LOW_LIQUIDITY_CONFIDENCE`
- `VENUE_DATA_MISSING`

Flags are descriptive. They do not all automatically exclude a candidate, but they must be surfaced in the final analysis.

## Comparison Metric Definitions

The two methods must be compared using a consistent scorecard.

### Required comparison fields
- number of selected pairs
- total capital deployed
- idle capital remaining
- weighted effective APR
- weighted quality / stability
- concentration risk
- count of selected names with decay concerns
- count of selected names with execution uncertainty
- overall deployability judgment

APR alone must not determine the winner.

### Quantified definitions

- **decay concern** = any selected name flagged `DECAYING_REGIME`, or any name where recent windows show a clear deterioration pattern such as materially weaker `APR_latest` versus `APR7` and `APR14`
- **execution uncertainty** = any selected name with tradeability status `CROSS_CHECK_NEEDED`, or a selected name carrying `MISSING_SPOT` or `CROSS_CHECK_NEEDED`
- **concentration risk** = basket-level concentration summary based on capital allocation share, with explicit note whenever any name exceeds preferred concentration even if it stays below the hard 40% cap

### Winner selection order

If the two strategies produce different outputs, choose the winner in this order:

1. lower execution uncertainty
2. lower decay-concern count
3. better concentration profile
4. higher weighted `pair_quality_score`
5. higher deployable capital without a material quality drop
6. higher weighted effective APR

If both strategies produce effectively the same basket within these criteria, the verdict should explicitly say:

- **no material difference under current data**
- operational default should revert to **Strategy 2** for simplicity until Strategy 3 proves incremental value

## Win Conditions

The preferred method for the current regime is the one that produces the more credible deployable basket under the ordered comparison above.

If both methods require low-quality names to fill the basket, the correct conclusion is that **the current market does not support full Core deployment**.

## Analysis Outputs

The final analysis deliverable should include:

1. **Core shortlist recommendation**
   - 2 to 4 names if available
   - recommended sizing per name
   - total deployed amount
   - idle capital if warranted

2. **Strategy 3 basket**
   - selected names
   - sizing
   - rationale for each inclusion

3. **Strategy 2 basket**
   - selected names
   - sizing
   - rationale for each inclusion

4. **Near-miss and excluded candidates**
   - names that nearly qualified
   - names with attractive funding but missing or unclear spot access
   - names excluded because the current regime is decaying

5. **Verdict**
   - whether Strategy 3 should be the default in the current regime
   - whether Strategy 2 is the better fallback
   - whether there is no material difference between them
   - whether Core should be fully deployed, partially deployed, or left mostly idle

## Required Candidate Table

The working analysis dataset should include, at minimum, these columns per candidate:

- `symbol`
- `funding_venue`
- `spot_on_hyperliquid`
- `spot_on_felix`
- `tradeability_status`
- `APR_latest`
- `APR7`
- `APR14`
- `stability_score`
- `pair_quality_score`
- `effective_apr_anchor`
- `freshness_hours`
- `OI_or_liquidity_proxy`
- `breakeven_estimate`
- `flags`

## Reporting Principles

The final write-up should follow these principles:
- numbers first
- no raw data dump in chat
- clearly separate attractive funding from executable construction
- state when data quality is degraded
- state when a pair is excluded because current funding is weakening
- state when capital should remain idle
- explicitly note any flexible override of the trading-plan baseline

## Final Verdict Structure

The final verdict should report **two separate axes**.

### Axis 1: method verdict
- `STRATEGY_3`
- `STRATEGY_2`
- `NO_MATERIAL_DIFFERENCE`
- `NO_DEPLOYABLE_METHOD`

### Axis 2: deployment verdict
- `FULL_CORE_DEPLOY`
- `PARTIAL_CORE_DEPLOY`
- `MINIMAL_PILOT_ONLY`
- `DO_NOT_DEPLOY`

This avoids mixing method selection with deployment sizing.

## Non-Negotiables

- Do not force full Core deployment if the market does not justify it
- Do not treat attractive funding as executable if spot access is unclear
- Do not let lagging APR windows override an obviously broken current regime
- Do not choose names for Core solely because they improve nominal APR
- Keep the final recommendation advisory only

## Ready-For-Analysis Checklist

- universe defined across approved venues
- tradeability status modeled explicitly
- data sources identified
- input verification step defined
- shared data gate defined
- trading-plan override rules defined
- canonical metric definitions defined
- sizing methods defined for both strategies
- Strategy 3 and Strategy 2 comparison framework defined
- final outputs and verdict axes defined
