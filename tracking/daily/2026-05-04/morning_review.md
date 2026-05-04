# Morning Review — 2026-05-04

**Data:** Vault pulse 2026-05-04 (~01:35 UTC on-chain verified). Rates from rates_history.csv (12-day window: Apr 22 – May 4). All lessons from docs/lessons.md applied.

**HEADLINE:** Yield surged to **$197.16/day (128% of target)** — best day since tracking began. Three rate spikes drove +$45.25/day overnight: HyperLend USDC 6.01%→**11.33%** (+532bps, +$33.59/d), Felix USDT0 8.53%→**12.16%** (+363bps, +$10.97/d), Felix USDe 6.87%→**17.76%** (+1089bps). Felix USDT0 YELLOW counter **RESETS** to GREEN. Felix USDC headroom restored to 320bps (was 75 yesterday). Per lesson #8, treat single-day spikes with caution — these are likely utilization-driven and may mean-revert. **COPPER bleeding RESUMED Day 4 — exit now 2 days overdue.** New GOLD spot-perp opened on unified wallet without thesis documentation. Deploy backlog: 13 days for HyperLend USDT.

---

## 1. Portfolio Health

| Metric | Today (May 4) | Yesterday (May 3) | Target | Status |
|--------|---------------|-------------------|--------|--------|
| Total Portfolio | $745,711 | $745,601 | $800k | YELLOW (-6.8%) |
| Deployed % | 94.8% ($706,985) | 94.8% ($706,948) | >85% | GREEN |
| Daily Yield | **$197.16/day** | $153.43/day | $154/day | **GREEN — 128.0% of target** |
| Blended APY | **10.18%** | 7.92% | 7.04% | **GREEN — 314 bps above target** |
| USDT0 Exposure | $110,200 (14.8%) | $110,200 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476,600) | Felix 67.4% ($476,600) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $18,548 (2.5%) | $19,282 (2.6%) | <$20k | GREEN |

**So what:** This is the cleanest yield day on record — but the structure of the gain matters more than the headline. **One protocol (HyperLend USDC) drove 73% of the +$45/day improvement** by itself. That is concentration of yield-source, not diversification. If HyperLend USDC mean-reverts to its 7d range (3.0–6.0%, per lesson #8), we lose ~$33/day instantly and revert to ~$165/day. Don't anchor on $197/day as the new baseline. The structural problems remain unchanged: Felix concentration 67.4% (RED), HyperLend USDT at $0 deploy (13 days overdue), and HypurrFi USDT0 at $0 deploy. Rates ran in our favor, but execution velocity didn't move.

---

## 2. Position Status

### RED — Immediate Action

```
COPPER (xyz+flx) — 🔴 EXIT 2 DAYS OVERDUE (DAY 4 OF BROKEN THESIS)
  xyz LONG: 329.6 @ entry 6.063, mark 5.950 | uPnL -$37.11
  flx SHORT: 329.6 @ entry 5.998, mark 5.951 | uPnL +$15.51
  Net uPnL: -$21.60 (was -$22.52 — barely improved -$0.92)
  cumFunding: +$2.71 ($3.33 xyz - $0.62 flx)
  Net P&L: -$18.89 UNDERWATER

  flx cumFunding trajectory: +$3.10 → +$1.81 → -$0.36 → -$0.36 → -$0.62
  After 1-day pause on May 3, bleeding RESUMED today (-$0.26).
  xyz LONGs are now BEING PAID funding (+$0.49 today) — this is unusual
  and suggests flx funding is structurally negative now, not just dipping.

  ⚠️ THESIS BROKEN. Original setup: short flx (receive high +funding),
     long xyz (near-zero cost). Reality: flx is paying us NEGATIVE funding
     while xyz is paying us POSITIVE funding. The trade now works in reverse
     direction and we're paying for that inefficiency on entry/exit fees.

  VERDICT: EXIT IMMEDIATELY (3rd consecutive recommendation)
  - Realized loss: ~$19 (cumFunding $2.71 - uPnL $21.60)
  - Margin freed: ~$3,974 ($1,963 USDC xyz + $2,011 USDH flx)
  - Total unified after exit: $4,270 + $2,000 + $4,968 + $2,014 + GOLD($800)
                             = ~$14,052 cash to redeploy or hold
  - Each day of delay costs roughly -$0.26 funding + MTM swing risk
```

### YELLOW — Monitoring

```
GOLD spot-perp (NEW) — 🟡 NEEDS THESIS DOCUMENTATION
  Spot: 0.1599 XAUT0 @ $4,586.25/oz = $733
  Short: 0.1728 xyz:GOLD @ $4,600 = $795 notional
  uPnL: +$2.32 | cumFunding: +$0.37
  Delta: -8% net short (mismatch — spot 0.1599 vs short 0.1728)
  Funding rate: NOT VISIBLE from standard API (xyz builder dex)

  Concerns:
  1. Delta -8% is wider than acceptable for "neutral" spot-perp.
     Either intentional (size XAUT0 differently) or sizing error.
  2. Builder dex funding rate is not queryable from standard API,
     making trigger evaluation (APR<8%) impossible without manual checks.
  3. Position consumed $737 idle USDC from unified — capital that was
     flagged in May 3 review for Felix USDC redeployment.

  No exit recommendation until thesis documented and funding rate verified.
```

```
Felix Concentration — 🟡 STRUCTURAL (UNCHANGED)
  Felix/Morpho: 67.4% of deployed ($476,600) | Cap: 50%
  Breach: +17.4 percentage points (~$118K excess)
  Path to fix:
  - Deploy HyperLend USDT $50K → Felix drops to ~63%
  - Deploy HypurrFi USDT0 $100K → Felix drops to ~58%
  - Both deploys executed → Felix drops to ~55% (still over but close)
  Note: Today's HyperLend USDC surge to 11.33% means the case for adding
        MORE USDC to HyperLend (instead of Felix) just got stronger.
        7d avg ~5.5% → 11.33% live = use 7d for projection per lesson #8.
```

### GREEN — On Track (sorted by daily $ contribution)

```
lend_hyperlend_usdc — ✅ HOLD (BIGGEST CONTRIBUTOR TODAY)
  Rate: 11.33% APY (was 6.01%) — SURGE +532 bps
  Amount: $230,385 (target $230,000) — 100% deployed
  Daily: $71.52 (was $37.93 — +$33.59/d)
  Trigger: APR < 3% → GREEN (833 bps headroom)
  Trend (12d range): 3.84-11.33%, 7d avg ~5.6%
  Note: Per lesson #8, this is a utilization spike — DO NOT project
        forward at 11.33%. Realistic forward run-rate ~$36/day.
        Today's bonus: enjoy +$33/day. Tomorrow: don't be surprised
        if it gives back 200+ bps.

lend_felix_usdc_main — ✅ HOLD (RECOVERED FROM YESTERDAY'S SCARE)
  Rate: 8.20% APY (was 8.48% — small dip -28bps)
  Amount: $352,000 (target $300,000) — 117% deployed
  Daily: $79.05 (was $81.79)
  Trigger: APR < 5% for 3d → GREEN (320 bps headroom — restored from 75)
  Trend (7d): 5.75 → 8.48 → 8.20 — bounced hard from yesterday's low
  Note: The "75 bps from trigger" alarm yesterday is fully reset.

lend_felix_usdt0 — ✅ HOLD (YELLOW COUNTER RESET TO GREEN)
  Rate: 12.16% APY (was 8.53%) — SURGE +363 bps
  Amount: $110,200 (target $100,000) — 110% deployed
  Daily: $36.72 (was $25.75 — +$10.97/d)
  Trigger: APR < 8% for 2wk → GREEN (counter RESETS, was Day 5)
  Trend (7d): 5.85 → 8.53 → 12.16 — strong recovery
  USDT0 vs USDC premium: 12.16% - 8.20% = 396 bps (was 5 bps yesterday)
  Note: Yesterday's "consider full $110K USDT0→USDC rotation" CANCELED.
        Bridge risk is fully compensated again at 396 bps premium.

lend_felix_usde — ✅ HOLD (BEST SMALL POSITION)
  Rate: 17.76% APY (was 6.87%) — SURGE +1089 bps
  Amount: $3,600 | Daily: $1.75
  Note: Tiny position. Rate is anomalous — likely thin pool utilization
        spike. Don't size up based on this.

pos_fartcoin_native+hyna — ✅ HOLD
  Rate: 13.00% APR (was 10.95%) — +205 bps
  Notional: $12,408 spot / $12,450 short | Daily: $4.43
  cumFunding: $247.01 ($24.11 native + $222.90 hyna)
  Note: Per lesson #10, cap rate (10.95%) had been masking the real rate.
        Today's 13.00% is the real rate emerging — and it's GOOD.
        But +205bps single-day move on hyna leg ($222.90 - $205.10 = +$17.80)
        again suggests a funding spike, not a stable rate. Continue monitoring.

pos_link_native — ✅ HOLD
  Rate: 10.95% APR (flat) | Notional: $3,090 | Daily: $0.93
  cumFunding: $29.56 (+$0.92/d) | Delta neutral (1.1%) ✓
  Note: Yesterday's "75 bps from 8% trigger" alarm cleared (10.95% > 8%).

lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 8.20% | $2.43/day
pos_link_hyna_dust — ⏰ CLEANUP 6 DAYS OVERDUE | $22 | cumFunding -$5.91
```

### IDLE — Deploy Candidates

| Item | Amount | Days | Best Target | Rate | Daily $ |
|------|--------|------|-------------|------|---------|
| xyz dex idle | $6,300 | **13 days** | Felix USDC or HyperLend USDC | 8.20% / 11.33% | +$1.42-$1.96 |
| Native spot (margin buffer) | $3,000 | 1 day | Hold for LINK/FARTCOIN margin | — | $0 (intentional) |
| Unified USDC free | $2,270 | ongoing | Felix USDC | 8.20% | +$0.51 |
| Unified USDH free | $2,954 | ongoing | Felix USDH | 6.72% | +$0.54 |
| **Total free idle** | **$11,524** | | | | **+$2.47-$3.01/day** |

Post-COPPER exit adds ~$3,977 USDC + USDH, bringing free idle to ~$15,500.

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 8.20% | 320 bps | 0 | GREEN |
| HyperLend USDC | APR < 3% | 11.33% | **833 bps** | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | 12.16% | 416 bps | **0 (RESET)** | GREEN |
| HypurrFi USDT0 | APR < 5% (not deployed) | 7.40% | 240 bps | — | GREEN |
| HyperLend USDT | (not deployed) | 5.49% | — | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | 0 | GREEN |
| FARTCOIN funding | APR < 8% | 13.00% | 500 bps | 0 | GREEN |
| USDT0 depeg > 1% (watch) | spread | 2.0 bps | 98 bps | — | GREEN |
| USDT0 depeg > 3% (exit) | spread | 2.0 bps | 298 bps | — | GREEN |
| Felix concentration | < 50% | 67.4% | -17.4pts | structural | **RED** |

**Felix USDT0 multi-day counter:** Apr 28 (D1) → Apr 29 (D2) → May 1 (D4) → May 2 (D5, 5.85%) → May 3 (8.53%, RESET) → May 4 (12.16%, confirmed RESET). Counter at 0. **Yesterday's "Day 7 hard re-eval" decision is no longer needed.**

**Per lesson #8 caveat:** HyperLend USDC at 11.33% is a single-day print well above its 7d average (~5.6%). For projections, do NOT use 11.33%. Use 5-6% range. The +$33.59/day boost may evaporate within 24-48 hours.

---

## 4. Yesterday → Today

### Action Items from May 3 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | COPPER EXIT (both legs) | ❗ **OVERDUE — 2 DAYS.** Bleeding resumed today (-$0.26). Net P&L now -$18.89. |
| P2 | Felix USDT0 day-7 prep | ✅ **MOOT.** Rate surged to 12.16% — counter RESET to GREEN. Decision no longer needed. |
| P3 | Deploy xyz idle $9,300 → Felix USDC | ⚠️ **PARTIAL.** $3K moved to native spot for margin (not deployed to lending). $6,300 still idle. **13 days now.** |
| P4 | HyperLend USDT $50K — execute or DROP | ❗ **OVERDUE — 13 DAYS.** No decision logged. Today's HyperLend USDC at 11.33% strengthens case for adding USDC there instead. |
| P5 | LINK hyna dust cleanup | ⏰ **OVERDUE — 6 days.** cumFunding -$5.91. |
| P6 | Run vault-pulse | ✅ **DONE** (~01:35 UTC May 4). |
| — | **NEW** GOLD spot-perp opened | ⚠️ **UNDOCUMENTED.** Position opened on unified wallet without thesis logged. Used $737 idle USDC. Builder dex — funding not queryable from standard API. |

**6 of 7 prior action items still pending or overdue.** Only vault-pulse executed. The "deploy backlog" warning is now structural — not a single-session miss but a 12-13 day pattern. Meanwhile a NEW position was opened without going through the deployment plan review process.

### Material Changes (May 3 → May 4)

| Change | Detail | Impact |
|--------|--------|--------|
| HyperLend USDC **+532 bps** | 6.01% → 11.33% | **+$33.59/day** — biggest single-day yield boost on record |
| Felix USDT0 **+363 bps** | 8.53% → 12.16% | **+$10.97/day** — YELLOW counter resets |
| Felix USDe **+1089 bps** | 6.87% → 17.76% | +$1.07/day on tiny position |
| FARTCOIN **+205 bps** | 10.95% → 13.00% | +$0.68/day, real rate emerges from cap |
| Felix USDC -28 bps | 8.48% → 8.20% | -$0.96/day, minor dip |
| Felix USDH -56 bps | 7.28% → 6.72% | No exposure but worse target for USDH redeploy |
| HypurrFi USDC -175 bps | 6.77% → 5.02% | No exposure, kills USDC diversification |
| HypurrFi USDH +234 bps | 2.63% → 4.97% | No exposure |
| HyperLend USDT +9 bps | 5.40% → 5.49% | Within noise |
| USDT0 spread tightened | 3.20 → 2.00 bps | Cleaner depeg |
| COPPER flx funding | -$0.36 → -$0.62 | -$0.26, bleeding resumed Day 4 |
| FARTCOIN hyna spike | +$17.80 (vs ~$4.28/d) | Repeat anomaly — see prior session |
| **Daily yield** | $153.43 → **$197.16** | **+$43.73/day** — new high |
| **NEW** GOLD position | spot+short on unified | $1,528 notional, delta -8% |

**Pattern: Broad rate decompression** — basically the inverse of yesterday's broad compression. The 1-day flip from $115/day (May 2) → $153/day (May 3) → $197/day (May 4) shows how fast the rate environment whipsaws. Anchoring on either extreme is dangerous. Working forward estimate: $150-170/day blended is the realistic 7d range.

---

## 5. Today's Plan

### Priority 1 — 🔴 COPPER EXIT (NOW 2 DAYS OVERDUE — 4th REQUEST)

- **What:** Close both legs (329.6 xyz LONG + 329.6 flx SHORT)
- **Wallet:** unified (0xd473)
- **Why now:** Day 4 of broken thesis. flx is paying us NEGATIVE funding while xyz is paying us POSITIVE — the entire trade structure is inverted. Realized loss is fixed at ~$19. Each delay day adds -$0.26 funding drain plus MTM exposure on a position that has no remaining edge.
- **Freed capital:** ~$3,977 ($1,963 USDC + $2,014 USDH)
- **Bean: if the blocker is operational (fees, slippage), document it. If it's emotional ("don't want to realize a loss"), recognize it. The trade is no longer in the portfolio's interest.**

### Priority 2 — 📋 DOCUMENT GOLD POSITION THESIS

- **What:** Write 1-paragraph entry: why opened, expected funding, exit conditions, delta target
- **Where:** New journal entry or appended to portfolio_state notes
- **Why:** Position appeared without thesis. Builder dex funding rate not visible from standard API → no automated trigger evaluation possible. Delta -8% is wider than spec for a "neutral" spot-perp. Need to know if these are intentional design choices or sizing errors.
- **Specific questions to answer:** (a) Is this a directional micro-bet via under-hedging? (b) How will funding rate be monitored if not via standard API? (c) What's the size cap?

### Priority 3 — DECIDE: HyperLend USDT $50k (13 DAYS OVERDUE)

- **Context shift:** HyperLend USDC at 11.33% live (5.5% 7d avg) makes the comparison harder.
- **Option A — Deploy as planned:** $50K USDT @ 5.49% = $7.52/day. Diversifies asset within HyperLend. Concentration improves.
- **Option B — Redirect to HyperLend USDC:** Add $50K to existing $230K = $280K @ 11.33% live (or 5.5% 7d avg) = $7.53-$31.04/day. Same concentration math.
- **Option C — Formally drop:** Acknowledge execution friction, redirect $50K to Felix USDC ($7.88/day at 8.20%) and accept Felix concentration creep to ~70%.
- **Recommendation:** **Option A or C. Pick one TODAY.** Bean — if no decision is made by May 5, defaulting to Option C and updating the deployment plan formally to retire this slot.

### Priority 4 — Deploy Free Idle ($11,524 + $3,977 post-COPPER)

| Wallet | Amount | Target | Rate | Daily |
|--------|--------|--------|------|-------|
| xyz dex | $6,300 | Felix USDC | 8.20% | +$1.42 |
| unified USDC free | $2,270 | Felix USDC | 8.20% | +$0.51 |
| unified USDH free | $2,954 | Felix USDH | 6.72% | +$0.54 |
| Post-COPPER USDC | $1,963 | Felix USDC | 8.20% | +$0.44 |
| Post-COPPER USDH | $2,014 | Felix USDH | 6.72% | +$0.37 |
| **Total** | **$15,501** | | | **+$3.28/day** |

Yes, this worsens Felix concentration to ~69%. Acceptable in current rate environment — the alternative venues (HypurrFi USDC at 5.02%) carry too large a rate penalty to justify diversification on this magnitude.

### Priority 5 — LINK hyna Dust Cleanup (6 DAYS OVERDUE)

- Close 2.4 hyna:LINK short. cumFunding -$5.91. 30 seconds of work.

**If Bean has 30 minutes today:**
1. Exit COPPER (both legs, unified)
2. Document GOLD thesis (5 minutes)
3. Close hyna:LINK dust (30 seconds)
4. Deploy xyz idle $6,300 → Felix USDC

**If Bean has 60 minutes:** Add HyperLend USDT decision (Option A/B/C) + post-COPPER redeployment.

---

## 6. Challenger Questions

1. **HyperLend USDC at 11.33% live, 5.5% 7d avg — what's the projection rate for capacity planning?** Today's $71.52/day from this position is 36% of total daily yield. Per lesson #8, the 7d average is the right number for forward planning ($35/day). If you build a deployment plan around $71/day, the next utilization dip cuts your margin to target by 50%. Conversely, if 11.33% is sustainable for 3+ days, the case for redirecting the HyperLend USDT $50K slot to MORE HyperLend USDC becomes overwhelming — but you need 3+ days of confirmation before sizing up. **Do we have a formal "rate confirmation" rule (e.g., "rate must hold above X% for N days before sizing up")?** Without one, we're going to repeatedly enter on spikes and exit on dips.

2. **Felix USDT0 just bounced from 5.85% to 12.16% in 2 days — and yesterday's review concluded "USDT0 thesis broken, plan full $110K rotation."** The whipsaw illustrates a real problem: our trigger framework (YELLOW for 14d) is slow, but our recommendations are fast. Yesterday's "the bridge risk is uncompensated" analysis was technically correct AT THAT MOMENT but the rate moved 631 bps in 2 days, making the recommendation obsolete before it could execute. **Should we formalize a "wait for X days of confirmation before recommending full rotation" rule?** Or are we comfortable with this level of recommendation churn? The cost of acting on yesterday's recommendation today would have been $11/day in lost yield.

3. **The new GOLD position consumed $737 of idle USDC that was on the May 3 deploy backlog (P4: "Deploy USDC unified → HypurrFi USDC").** That capital was supposed to fund a documented diversification target and instead funded an undocumented new strategy. Combined with $3K moved from xyz dex to native spot for margin (not deployment to lending), the net effect is: TWO action items got executed in ways that worked AGAINST the morning review's recommendations. **Is the morning review document being used as a planning input, or is it being treated as advisory-only after-the-fact?** This isn't a process complaint — it's a question about whether the review's structure adds value or whether it should be re-scoped to better match how decisions actually get made.

---

## 7. Risk Watch

### Scenario: Rate Mean-Reversion (HyperLend USDC + Felix USDT0 give back the spike)

```
Scenario: Today's HyperLend USDC 11.33% and Felix USDT0 12.16% are
          utilization-driven spikes. Within 1-3 days, both revert toward
          7d averages: HyperLend USDC ~5.5%, Felix USDT0 ~7.5%.
Probability: HIGH (lesson #8 — single-day spikes typically don't sustain).
             Distribution check: in last 12 days, HyperLend USDC has
             touched 11%+ exactly once (today). Base rate for sustained
             3+ day prints above 8% = 0%.
Impact:
  - HyperLend USDC: 11.33% → 5.5% on $230K = -$36.74/day
  - Felix USDT0: 12.16% → 7.5% on $110K = -$14.05/day
  - Combined: -$50.79/day → portfolio reverts from $197/d to ~$146/d
Trigger signal:
  - Either rate drops >300bps in any single day → mean-reversion confirmed
  - Both rates hold within 100bps for 48hr → spike was sustainable
Pre-planned response:
  1. HOLD positions through reversion — sizing should NOT change based
     on a single-day spike (we're not in this for the spike, we're in for
     the average rate)
  2. DO NOT add fresh capital to HyperLend USDC at the spike rate.
     If sizing up, wait for 7d avg to confirm above 7% sustainably.
  3. If HypurrFi/HyperLend lending becomes more competitive than Felix
     after reversion, that's the signal to actually rotate
  4. Frame the +$45/day boost as "cumulative yield over the next ~3 days"
     rather than "new daily run rate" — i.e., a $135 windfall, not a
     permanent $1,400/month pay raise
```

**Previous risk scenarios covered:** rate collapse (Apr 28), COPPER negative funding (May 1), USDT0 depeg (Apr 29), deployment drift (May 2), Felix USDC trigger (May 3). Today's focus: rate mean-reversion — the symmetric counterpart of yesterday's "rate continues compressing" scenario. Both directions need to be respected; we are not in a stable rate regime.

---

## Reviews Due Today (May 4)

| Item | Status | Action Required |
|------|--------|-----------------|
| **COPPER EXIT** | 🔴 **2 DAYS OVERDUE** | EXIT both legs. -$18.89 and Day 4 broken thesis. |
| GOLD position docs | 🟡 **NEW, UNDOCUMENTED** | Log thesis + funding-monitoring approach. |
| Deploy xyz idle $6,300 | ⏰ **13 DAYS IDLE** | → Felix USDC (8.20%). +$1.42/day. |
| Deploy USDH unified $2,954 | ⏰ **PENDING.** | → Felix USDH (6.72%). +$0.54/day. |
| Deploy USDC unified $2,270 | ⏰ **PENDING.** | → Felix USDC (8.20%). +$0.51/day. |
| HyperLend USDT $50k | ❗ **13 DAYS OVERDUE** | Final decision (Option A/B/C). Default = drop on May 5. |
| LINK hyna dust cleanup | ⏰ **6 DAYS OVERDUE** | Close 2.4 short. 30 seconds. |
| Felix USDT0 day-7 prep | ✅ **CLEARED** | Rate surged 12.16%, counter reset. No action. |
| LINK 8% trigger watch | ✅ **CLEARED** | 10.95% steady, 295 bps headroom. No action. |
| Felix USDC 5% trigger watch | ✅ **CLEARED** | 8.20% recovered, 320 bps headroom. No action. |

**Bean — yesterday's review flagged 6 overdue items. Today: 5 overdue items + 1 new undocumented position + 0 progress on the 12-day backlog.** The morning review process is producing reliable diagnostics but not driving execution. If there's a structural reason the recommendations aren't being acted on (operational friction, time scarcity, disagreement with framing), name it — the review structure can be adjusted. If there's no structural reason, consider blocking 30-60 minutes today specifically for backlog clearance.

---

*Generated 2026-05-04. Primary source: vault pulse 2026-05-04 (~01:35 UTC). Rates from rates_history.csv (12-day window). All lessons applied (cited: #6, #8, #10, #11). Critical: COPPER 2-day overdue + new undocumented GOLD + HyperLend USDT 13-day overdue + rate mean-reversion risk on today's $45/day windfall.*
