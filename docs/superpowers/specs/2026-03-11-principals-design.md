# PRINCIPALS.md Design Spec

**Date:** 2026-03-11
**Scope:** Trading principles, domain knowledge, and analytical guardrails for the Harmonix delta-neutral funding advisory agent.

## Purpose

Create `PRINCIPALS.md` — an assertion-based trading principles document that prevents the agent from making recurring analytical mistakes. The file focuses on **trading logic and analytical correctness**, not sizing rules (which remain in `WORKFLOW.md`).

## Pain Points Addressed

1. **Funding sign confusion** — agent frequently reverses the sign convention, recommending entry on negative funding or flagging positive funding as costly.
2. **Realized vs unrealized PnL mixing** — agent combines funding income with basis movement into a single headline number, producing misleading PnL.
3. **Incomplete cost accounting** — agent shows gross APR without deducting fees, slippage, and spread, making candidates appear more attractive than they are.

## Approach: Assertion-Based

Each principle is written as an explicit `ASSERT` statement. Critical mistakes are documented with `❌ WRONG` / `✅ RIGHT` examples. The agent must cross-check against these before outputting any recommendation.

## File Structure

### Section 1: Funding Mechanics

Establishes the sign convention for Hyperliquid and its implications for the long-spot + short-perp strategy.

**Assertions:**
- `funding_rate > 0` → longs pay shorts → short perp RECEIVES → strategy PROFITABLE
- `funding_rate < 0` → shorts pay longs → short perp PAYS → strategy BLEEDING
- `funding_rate = 0` → no funding flow → fees are pure cost
- A valid opportunity requires `funding_rate > 0` AND positive across APR7 and APR14 windows
- `funding_rate < 0` is NEVER an opportunity, regardless of magnitude
- "Large negative funding" means large LOSS, not large opportunity

**Self-check:** Before recommending ENTER/HOLD/INCREASE:
1. Confirm `funding_rate > 0` on current interval.
2. If `APR_latest`, `APR7`, and `APR14` are all positive → full conviction.
3. If `APR_latest` is negative but `APR7` and `APR14` remain above floor → downgrade conviction to MONITOR, do not reject outright.
4. If `APR7` or `APR14` is negative → do NOT recommend entry.

### Section 2: PnL Accounting

Defines how to calculate and report performance numbers.

**Headline PnL (Realized Only):**
- `headline_pnl = cumulative_funding_received − total_fees`
- `total_fees = entry_fees + exit_fees + slippage + spread_cost`
- Never includes unrealized basis change
- Open position: `headline_pnl = funding_received − entry_fees_only`

**Unrealized / MTM (Diagnostic Only):**
- `unrealized_pnl = current_basis − entry_basis`
- Reported separately, labeled "MTM" or "Unrealized"
- Never added to headline PnL
- Can be negative even when headline is positive (normal for carry trades)

**Cost Accounting:**
- Every displayed APR must be net of roundtrip fees
- `net_apr = gross_apr − fee_drag`
- `fee_drag` includes: maker/taker (both legs), slippage, spread
- If `net_apr < 0` → position is unprofitable regardless of gross rate

**Break-Even:**
- `break_even_days = total_entry_cost / daily_net_funding`
- Position before break-even is in "fee recovery" phase — flag in reports

**Self-check:** Confirm headline excludes MTM, all fee components deducted, realized/unrealized in separate fields, and positions pre-break-even labeled "Recovering Costs".

### Section 3: Opportunity Analysis

Rules for evaluating and comparing candidates.

**Candidate Qualification:**
- Only `funding_rate > 0` assets are candidates
- Floor: `APR14 >= 20%` (net of fees)
- Ranking uses net APR, never gross
- `stability_score = 0.55 × APR14 + 0.30 × APR7 + 0.15 × APR_latest` (all net)

**Trend Consistency (applies to candidate evaluation for new entry; for existing position management, see WORKFLOW.md Section 3):**
- Strong: APR_latest, APR7, APR14 all pointing same direction
- If APR_latest dropping while APR14 high → "decaying", not "strong"
- `APR_latest < APR7 < APR14` → deteriorating → MONITOR, not ENTER
- `APR_latest > APR7 > APR14` → accelerating → higher confidence

**Freshness Gate:**
- Never analyze stale data (> 4 hours)
- Missing data ≠ zero funding — flag as STALE, exclude from ranking

**Comparison:**
- Compare by net APR, stability score, break-even days, liquidity
- Higher gross APR with higher fees can be worse than lower gross with lower fees
- Never rank by single metric

**Self-check:** Before presenting candidate rankings:
1. Confirm all APR values shown are net (gross − fee drag).
2. Confirm data freshness < 4 hours for every ranked asset.
3. Confirm no missing-data assets are included in rankings (flag separately).
4. Confirm trend direction is noted alongside stability score.

### Section 4: Common Mistakes

Six documented anti-patterns with ❌/✅ examples:

1. **Reversed Funding Sign** — interpreting positive FR as cost, negative FR as opportunity
2. **Mixing Realized and Unrealized PnL** — summing funding income with basis movement
3. **Showing Gross APR Instead of Net** — ranking without fee deduction
4. **Ignoring Deteriorating Trend** — recommending entry on high APR14 while APR_latest is collapsing
5. **Treating Missing Data as Zero** — defaulting absent data to 0% instead of flagging stale
6. **Forgetting Break-Even in New Positions** — calling a position "profitable" before entry costs are recovered

Each mistake includes concrete numeric examples. Key examples:

**Mistake 1 — Reversed Funding Sign:**
- ❌ WRONG: "HYPE funding rate = -0.035% per 8h (-46% APR). Large magnitude = large opportunity."
- ✅ RIGHT: "HYPE funding rate = -0.035% per 8h. Negative = short perp PAYS. This is a COST of -46% APR, not an opportunity. Skip."

**Mistake 2 — Mixing Realized and Unrealized:**
- ❌ WRONG: "Position PnL = +$320 (funding $180 + basis gain $140)"
- ✅ RIGHT: "Headline PnL = +$180 (realized funding − fees). MTM: +$140 (unrealized, reported separately)."

**Mistake 3 — Gross vs Net APR:**
- ❌ WRONG: "Asset A gross 50% vs Asset B gross 30% → A is better"
- ✅ RIGHT: "Asset A net 28% (high fees) vs Asset B net 27% (low fees) → nearly equivalent, factor in stability and liquidity."

## Integration

**AGENTS.md update:** Add `PRINCIPALS.md` as step 3 in the reading sequence (after SOUL.md, before WORKFLOW.md). Principles must be internalized before any analysis begins.

**SOUL.md overlap note:** SOUL.md contains personality-level convictions that partially overlap with PRINCIPALS.md (e.g., "model fees + slippage + basis" maps to Section 2; "APR14 < 20% is not tradable" maps to Section 3). This is intentional: SOUL.md states character-level beliefs, PRINCIPALS.md provides mechanistic assertions with worked examples. Both should be maintained — if a principle changes, update both files.

**Relationship with existing files:**
| File | Focus | Change |
|------|-------|--------|
| `PRINCIPALS.md` | Analytical correctness, domain knowledge | **NEW** |
| `res-delta-neutral-rules.md` | Strategy rules (entry criteria, lifecycle, sizing) | No change |
| `SOUL.md` | Personality, non-negotiables | No change |
| `WORKFLOW.md` | Daily operational workflow, sizing rules | No change |

## Deliverables

1. `PRINCIPALS.md` — new file in workspace root
2. `AGENTS.md` — updated to include PRINCIPALS.md in reading sequence
