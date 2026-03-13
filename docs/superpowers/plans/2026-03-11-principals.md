# PRINCIPALS.md Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create `PRINCIPALS.md` — an assertion-based trading principles document that prevents Harmonix from making recurring analytical mistakes — and update `AGENTS.md` to load it at session start.

**Architecture:** Two files are modified/created. `PRINCIPALS.md` is a standalone document with four sections (Funding Mechanics, PnL Accounting, Opportunity Analysis, Common Mistakes), each using explicit ASSERT statements and ❌/✅ examples. `AGENTS.md` is updated to add `PRINCIPALS.md` as step 3 in the session reading sequence.

**Tech Stack:** Markdown only. No code changes. No tests.

**Spec:** `docs/superpowers/specs/2026-03-11-principals-design.md`

---

## Chunk 1: Create PRINCIPALS.md

### Task 1: Create PRINCIPALS.md

**Files:**
- Create: `PRINCIPALS.md` (workspace root)

---

- [ ] **Step 1: Create the file with Section 1 — Funding Mechanics**

Create `/Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/PRINCIPALS.md` with the following content for Section 1:

```markdown
# PRINCIPALS.md — Harmonix Trading Principles

These are the analytical laws Harmonix must follow. Every analysis, ranking, and recommendation must be cross-checked against these assertions before output.

---

## Section 1: Funding Mechanics

### Sign Convention (Hyperliquid)

ASSERT: funding_rate > 0 → longs pay shorts
ASSERT: funding_rate < 0 → shorts pay longs

### Implications for This Strategy (long spot + short perp)

ASSERT: funding_rate > 0 → short perp RECEIVES funding → strategy PROFITABLE
ASSERT: funding_rate < 0 → short perp PAYS funding → strategy BLEEDING
ASSERT: funding_rate = 0 → no funding flow → fees are pure cost with no offset

### Opportunity Screening

ASSERT: a valid opportunity requires funding_rate > 0 AND positive across APR7 and APR14 windows
ASSERT: funding_rate < 0 is NEVER an opportunity for this strategy, regardless of magnitude
ASSERT: "large negative funding" means large LOSS for short perp, not large opportunity

### Self-Check Before Any Entry Recommendation

Before recommending ENTER, HOLD, or INCREASE SIZE on any asset:
1. Confirm funding_rate > 0 on the current interval.
2. If APR_latest, APR7, and APR14 are all positive → full conviction.
3. If APR_latest is negative but APR7 and APR14 remain above floor → downgrade conviction to MONITOR, do not reject outright.
4. If APR7 or APR14 is negative → do NOT recommend entry.
```

- [ ] **Step 2: Append Section 2 — PnL Accounting**

Append the following to `PRINCIPALS.md`:

```markdown
---

## Section 2: PnL Accounting

### Headline PnL (Realized Only)

ASSERT: headline_pnl = cumulative_funding_received − total_fees
ASSERT: total_fees = entry_fees + exit_fees + slippage + spread_cost
ASSERT: headline_pnl NEVER includes unrealized basis change
ASSERT: for an open position, headline_pnl = funding_received − entry_fees_only (exit fees not yet incurred)

### Unrealized / Mark-to-Market (Diagnostic Only)

ASSERT: unrealized_pnl = current_basis − entry_basis (where basis = spot_price − perp_price)
ASSERT: unrealized_pnl is reported SEPARATELY, clearly labeled "MTM" or "Unrealized"
ASSERT: unrealized_pnl is NEVER added to headline_pnl
ASSERT: unrealized_pnl can be negative even when headline is positive — this is normal for carry trades

### Cost Accounting

ASSERT: every APR displayed must be NET of roundtrip fees
ASSERT: net_apr = gross_apr − fee_drag
ASSERT: fee_drag includes: maker/taker fees (both legs), estimated slippage, spread cost
ASSERT: if net_apr < 0 after costs → position is unprofitable regardless of gross funding rate

### Break-Even Analysis

ASSERT: break_even_days = total_entry_cost / daily_net_funding
ASSERT: total_entry_cost = spot_entry_fee + perp_entry_fee + slippage + spread
ASSERT: a position that has not passed break-even is in "fee recovery" phase — label it "Recovering Costs" in reports

### Self-Check Before Reporting PnL

1. Confirm headline number excludes all MTM / basis movement.
2. Confirm all fee components are deducted (trading fees, slippage, spread).
3. Confirm realized and unrealized are in separate fields — never summed.
4. If break-even not yet reached → label position "Recovering Costs".
```

- [ ] **Step 3: Append Section 3 — Opportunity Analysis**

Append the following to `PRINCIPALS.md`:

```markdown
---

## Section 3: Opportunity Analysis

> These rules apply to **candidate evaluation for new entry**. For existing position management (HOLD/MONITOR/EXIT decisions), see WORKFLOW.md Section 3.

### Candidate Qualification

ASSERT: only assets with funding_rate > 0 are candidates
ASSERT: candidate floor is APR14 >= 20% (net of fees)
ASSERT: APR used for ranking MUST be net_apr, never gross_apr
ASSERT: stability_score = 0.55 × APR14 + 0.30 × APR7 + 0.15 × APR_latest (all net values)

### Trend Consistency

ASSERT: a strong candidate has APR_latest, APR7, APR14 all pointing the same direction
ASSERT: if APR_latest is dropping while APR14 is high → label "decaying", not "strong"
ASSERT: APR_latest < APR7 < APR14 → funding deteriorating → recommend MONITOR, not ENTER
ASSERT: APR_latest > APR7 > APR14 → funding accelerating → higher confidence for entry

### Freshness Gate

ASSERT: never analyze or rank based on data older than 4 hours
ASSERT: missing data ≠ zero funding — missing data must be flagged as STALE, not defaulted to 0
ASSERT: if data age > 4 hours → degrade report, flag staleness explicitly, do not rank those assets

### Comparing Opportunities

ASSERT: compare candidates by net_apr, stability_score, break-even days, and liquidity
ASSERT: higher gross APR with higher fees can be WORSE than lower gross APR with lower fees
ASSERT: never rank by a single metric

### Self-Check Before Presenting Candidate Rankings

1. Confirm all APR values shown are net (gross − fee drag).
2. Confirm data freshness < 4 hours for every ranked asset.
3. Confirm no missing-data assets are included in rankings (flag them separately).
4. Confirm trend direction is noted alongside stability score.
```

- [ ] **Step 4: Append Section 4 — Common Mistakes**

Append the following to `PRINCIPALS.md`:

```markdown
---

## Section 4: Common Mistakes

This section documents specific errors this agent has made or is prone to making.
Before outputting any analysis or recommendation, cross-check against every item below.

---

### Mistake 1: Reversed Funding Sign

❌ WRONG: "HYPE funding rate = -0.035% per 8h (-46% APR). Large magnitude = large opportunity."
✅ RIGHT: "HYPE funding rate = -0.035% per 8h. Negative = short perp PAYS. This is a COST of -46% APR, not an opportunity. Skip."

❌ WRONG: "FR = 0.015% → shorts are paying, this is costly for our position."
✅ RIGHT: "FR = 0.015% → positive funding → shorts RECEIVE → strategy is earning."

❌ WRONG: "Large negative funding = large opportunity."
✅ RIGHT: "Large negative funding = large LOSS for short perp side."

---

### Mistake 2: Mixing Realized and Unrealized PnL

❌ WRONG: "Position PnL = +$320 (funding $180 + basis gain $140)"
✅ RIGHT: "Headline PnL = +$180 (realized funding − fees). MTM: +$140 (unrealized, reported separately)."

❌ WRONG: "This position is underwater" (when headline funding is +$50 but basis is −$200, combined to show −$150)
✅ RIGHT: "Headline PnL: +$50 (realized). MTM: −$200 (unrealized, diagnostic only). Basis drawdown does not affect realized funding profitability."

---

### Mistake 3: Showing Gross APR Instead of Net

❌ WRONG: "Asset A gross 50% vs Asset B gross 30% → A is better."
✅ RIGHT: "Asset A net 28% (high fees) vs Asset B net 27% (low fees) → nearly equivalent. Factor in stability score and liquidity before deciding."

❌ WRONG: "HYPE APR14 = 45% → top candidate." (without subtracting fee drag)
✅ RIGHT: "HYPE gross APR14 = 45%. Roundtrip fee drag = 3.2%. Net APR14 = 41.8% → top candidate."

---

### Mistake 4: Ignoring Deteriorating Trend

❌ WRONG: "APR14 = 35%, strong candidate." (while APR7 = 15% and APR_latest = 5%)
✅ RIGHT: "APR14 = 35% but APR7 = 15%, APR_latest = 5% → funding is collapsing. Label as 'decaying'. MONITOR only, do not enter."

---

### Mistake 5: Treating Missing Data as Zero

❌ WRONG: "Funding rate = 0% for this interval." (when data is actually missing)
✅ RIGHT: "Funding data unavailable for this interval → flag as STALE. Exclude from ranking. Do not interpret as zero funding."

---

### Mistake 6: Forgetting Break-Even in New Positions

❌ WRONG: "Position opened 2 days ago, PnL = +$12 → profitable."
✅ RIGHT: "Position opened 2 days ago. Funding earned = $12. Entry costs = $45. Still recovering costs ($33 remaining). Break-even in ~5.5 more days. Label: Recovering Costs."
```

- [ ] **Step 5: Verify the final file looks correct**

```bash
wc -l /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/PRINCIPALS.md
head -5 /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/PRINCIPALS.md
grep -n "^## Section" /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/PRINCIPALS.md
grep -n "^### Mistake" /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/PRINCIPALS.md
```

Expected output:
- ~140+ lines
- Header line: `# PRINCIPALS.md — Harmonix Trading Principles`
- 4 section headings: Section 1, 2, 3, 4
- 6 mistake headings: Mistake 1 through 6

- [ ] **Step 6: Commit PRINCIPALS.md**

```bash
cd /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral
git add PRINCIPALS.md
git commit -m "feat: add PRINCIPALS.md — trading principles and analytical guardrails

Adds assertion-based principles document covering:
- Funding sign convention (positive FR = short perp receives = profitable)
- PnL accounting (realized headline vs unrealized MTM, always separate)
- Opportunity analysis (net APR, freshness gate, trend consistency)
- 6 documented anti-patterns with ❌/✅ examples

Addresses recurring agent mistakes: funding sign reversal, realized/unrealized
mixing, gross APR display without fee deduction."
```

---

## Chunk 2: Update AGENTS.md

### Task 2: Update AGENTS.md reading sequence

**Files:**
- Modify: `AGENTS.md` (workspace root, lines 11–18)

---

- [ ] **Step 1: Read current AGENTS.md to confirm line content before editing**

```bash
cat -n /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral/AGENTS.md
```

Locate the "Every Session" block (lines 10–18). It currently reads:
```
1. Read `IDENTITY.md` — this is who you are and what you own.
2. Read `SOUL.md` — this is how you think.
3. Read `USER.md` — this is who you're helping.
4. Read `WORKFLOW.md` — this is the canonical report and ops workflow.
5. Read `TOOLS.md` — this is the real tool and script map.
6. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context.
7. **If in MAIN SESSION** (direct chat with Bean): also read `MEMORY.md`.
```

- [ ] **Step 2: Insert PRINCIPALS.md as step 3, renumber remaining steps**

Edit the "Every Session" block to become:

```markdown
## Every Session

Before doing anything else:
1. Read `IDENTITY.md` — this is who you are and what you own.
2. Read `SOUL.md` — this is how you think.
3. Read `PRINCIPALS.md` — these are the analytical laws you must never violate.
4. Read `USER.md` — this is who you're helping.
5. Read `WORKFLOW.md` — this is the canonical report and ops workflow.
6. Read `TOOLS.md` — this is the real tool and script map.
7. Read `memory/YYYY-MM-DD.md` (today + yesterday) for recent context.
8. **If in MAIN SESSION** (direct chat with Bean): also read `MEMORY.md`.
```

- [ ] **Step 3: Verify AGENTS.md diff looks correct**

```bash
cd /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral
git diff AGENTS.md
```

Expected: Step 3 inserted (PRINCIPALS.md), steps 3–7 renumbered to 4–8. No other changes.

- [ ] **Step 4: Commit AGENTS.md**

```bash
cd /Users/beannguyen/Development/openclaw/.openclaw/workspace-harmonix-delta-neutral
git add AGENTS.md
git commit -m "feat: load PRINCIPALS.md at session start (step 3 in reading sequence)

Ensures agent internalizes analytical principles before running any
analysis or producing recommendations."
```

---

## Done

Two commits, two files, no code changes. Harmonix now loads trading principles before every session.
