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

ASSERT: a valid entry opportunity requires funding_rate > 0 AND net APR7 >= floor AND net APR14 >= floor (floor = 20% net; see Section 3: Candidate Qualification)
ASSERT: APR_latest may be temporarily negative while APR7/APR14 hold above floor — downgrade conviction to MONITOR, do not reject outright
ASSERT: funding_rate < 0 is NEVER an opportunity for this strategy, regardless of magnitude
ASSERT: "large negative funding" means large LOSS for short perp, not large opportunity

### Self-Check Before Any Entry Recommendation

Before recommending ENTER, HOLD, or INCREASE SIZE on any asset:
1. Confirm funding_rate > 0 on the current interval.
2. If APR_latest, APR7, and APR14 are all positive → full conviction.
3. If APR_latest is negative but APR7 and APR14 remain above floor → downgrade conviction to MONITOR, do not reject outright.
4. If APR7 or APR14 is negative → do NOT recommend entry.

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
5. Confirm position data is not stale — if last position update > 4 hours ago, flag before reporting PnL.

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
