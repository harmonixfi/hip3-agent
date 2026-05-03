# Morning Review — 2026-05-03

**Data:** Vault pulse 2026-05-02 (~02:25 UTC on-chain verified). No May 3 vault-pulse exists — all numbers below are from the May 2 snapshot. Rates from rates_history.csv (11-day window: Apr 22 - May 2). All lessons from docs/lessons.md applied.

**HEADLINE:** Yield crashed to $115.18/day (74.8% of target) — worst since tracking began. Felix USDC -133bps on $351K drove a -$12.77/day single-position hit. Broad rate compression across ALL protocols except HyperLend USDC. COPPER short-side funding confirmed negative for day 2 — exit overdue. Deploy backlog now **12 days** for HyperLend USDT.

---

## 1. Portfolio Health

| Metric | Today (May 2 data) | Yesterday (May 1) | Target | Status |
|--------|---------------------|---------------------|--------|--------|
| Total Portfolio | $745,379 | $744,911 | $800k | YELLOW (-6.8%) |
| Deployed % | 94.8% ($706,711) | 94.9% ($706,576) | >85% | GREEN |
| Daily Yield | **$115.18/day** | $129.84/day | $154/day | **RED — 74.8% of target** |
| Blended APY | **5.72%** | 6.71% | 7.04% | **RED — 132 bps below target** |
| USDT0 Exposure | $110,100 (14.8%) | $110,100 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476K) | Felix 67.4% ($476K) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $19,279 (2.6%) | $19,295 (2.6%) | <$20k | GREEN |

**So what:** We've hit the worst yield number since tracking began. The $38.82/day gap to target breaks down:

- **$12.77/day** from Felix USDC rate compression (5.75% vs plan 6.86% on $351.9K) — this is the single biggest driver. Previously our workhorse at $68/day, now $55/day.
- **$10.42/day** from Felix USDT0 rate collapse (5.85% vs plan 15.39% on $110K) — structural USDT0 lending rate compression, day 5 of YELLOW trigger.
- **$7.53/day** from undeployed HyperLend USDT ($50K at 0% vs plan 5.5% avg) — now **12 days overdue**.
- **$3-5/day** from idle capital ($19.3K earning nothing) and scattered rate drops.
- **$3-4/day** from HypurrFi USDT0 still at $0 deployed vs $100K target — effectively dropped given USDT0 rate environment.

The controllable portion — HyperLend USDT deploy + idle redeploy — accounts for ~$10/day. That gets us to ~$125/day (81%). The remaining $29/day gap is rate environment (USDT0 collapse + Felix USDC dip + no HypurrFi deployment).

We are now in the "USDT0 rates halve" stress scenario from the deployment plan ($125/day, 5.71% — doesn't hit 6%). This was classified as MEDIUM probability. It happened.

---

## 2. Position Status

### RED — Immediate Action

```
COPPER (xyz+flx) — 🔴 EXIT OVERDUE (was due May 2)
  xyz LONG: 329.6 @ entry 6.063, mark 5.958 | uPnL -$34.51
  flx SHORT: 329.6 @ entry 5.998, mark 5.962 | uPnL +$11.99
  Net uPnL: -$22.52 (was -$9.34 — deteriorated -$13.18 in 1 day)
  cumFunding: $2.33 (xyz $2.69 - flx $0.36)
  Net P&L: cumFunding $2.33 - uPnL $22.52 = **-$20.19 UNDERWATER**

  ⚠️ THESIS BROKEN — DAY 2 OF NEGATIVE flx FUNDING
  flx cumFunding trajectory: +$3.10 → +$1.81 → -$0.36
  That's -$3.46 in 2 days on the flx side. Accelerating.
  
  xyz mark dropped 5.958 from entry 6.063 (-1.7%). Spread widened against us.
  This is exactly lesson #11 — spread moves against when funding spikes/flips.
  
  VERDICT: EXIT IMMEDIATELY.
  - Estimated loss: ~$20 (cumFunding $2.33 - uPnL $22.52)
  - Margin freed: ~$3,974 ($1,963 USDC + $2,011 USDH)
  - Total freed on unified: $5,006 USDC + $4,965 USDH = ~$9,971
  - Redeploy: USDH → Felix USDH (5.72% — note: USDH rates crashed from 9.90%)
             USDC → HypurrFi USDC (2.91% — crashed from 6.06%)
  - ⚠️ USDH and HypurrFi USDC rates both collapsed since yesterday.
    Redeployment targets need fresh rate check before acting.
```

```
Felix USDC Rate — 🔴 WATCH (75 bps from exit trigger)
  Rate: 5.75% (was 7.08% — CRASHED -133bps)
  Amount: $351,900 — portfolio workhorse (48% of daily yield)
  Daily: $55.44 (was $68.24 — lost $12.77/day overnight)
  Trigger: APR<5% for 3d → NOT STARTED (today is day 0 — 5.75% > 5%)
  BUT: only 75 bps headroom. One more -100bps day starts the clock.
  Trend (7d): 9.02→7.44→6.89→6.39→7.08→5.75 — lower highs, lower lows
  Note: The pattern is a downward channel. The 7.08% "recovery" on May 1
        was a dead cat bounce. If tomorrow prints <5.75%, we're in a
        deteriorating trend with $352K at risk. No action yet but HIGH ALERT.
```

### YELLOW — Monitoring

```
lend_felix_usdt0 — 🟡 WATCH (YELLOW TRIGGER — Day 5 of 14, DECLINING)
  Rate: 5.85% APY (target 15.39%) — BELOW 8% threshold by 215 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $17.64 (plan: $42.16 — 42% of plan yield)
  Trigger: APR<8% for 2wk → YELLOW (Day 5 of 14). Counter started Apr 28.
  Trend: 6.08→6.48→[stale]→6.78→5.85 — REVERSAL. The slow recovery is over.
  Note: Rate dropped -93bps. The lower-highs pattern continues (13.38→6.78→5.85).
        Day 7 hard re-eval is May 4 (TOMORROW). At 5.85% and declining,
        the question isn't whether to rotate — it's where to rotate TO.
        All USDT0 rates are depressed (HypurrFi USDT0 at 6.06% — barely better).
        The USDT0→USDC exit path ($32 swap cost, ~1 bps) should be on the table.
```

```
LINK funding — 🟡 WATCH (approaching 8% trigger)
  Rate: 8.75% APR (was 10.95% cap rate — dropped -220bps)
  Amount: $3,116 notional | Daily: $0.73
  Trigger: APR<8% → 75 bps headroom
  cumFunding: $27.83 (+$0.93/day)
  Delta: neutral (1.1%) ✓
  Note: Per lesson #10, this was at cap rate (10.95%) for the entire
        observation window. Now cap has lifted and real rate is 8.75%.
        This is the scenario we were warned about — cap rate ends, real rate
        could be much lower. One more drop starts the exit evaluation.
```

### GREEN — On Track

```
lend_hyperlend_usdc — ✅ HOLD (STABLE, BRIGHTSPOT)
  Rate: 5.58% APY (target 4.36%) — ABOVE plan by 122 bps
  Amount: $230,311 (target $230,000) — 100% deployed
  Daily: $35.18 (plan: $27.47 — 128% of plan yield)
  Trigger: APR < 3% → GREEN (258 bps headroom)
  Trend (per lesson #8, 7d avg): ~5.2%. Range 3.0-5.6%.
  Note: Only position to IMPROVE today (+23 bps). HyperLend is the most
        stable protocol in the portfolio. This validates the diversification thesis.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD (Cap rate, FUNDING SPIKE)
  Rate: 10.95% APR (still cap rate — lesson #10 caveat)
  Amount: $12,344 spot / $12,391 short (60,180 total)
  Daily: $3.72/day ($0.53 native + $3.19 hyna)
  Cumulative funding: $203.40 ($22.18 native + $181.22 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  ⚠️ hyna:FARTCOIN cumFunding spike: +$19.17 today vs $4.28/day expected.
     Likely a funding rate spike event. Verify if one-off or regime change.
  FARTCOIN price +3.4% ($0.1992→$0.2059). uPnL swings large but delta neutral.
  Next review: May 8.
```

```
lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 5.75% | $1.70/day
lend_felix_usde — ✅ HOLD | $3,600 @ 7.84% | $0.77/day (best risk-adjusted small position)
pos_link_hyna_dust — ⏰ CLEANUP OVERDUE (5 days) | $22 | cumFunding -$5.93
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate (May 2) | Impact |
|------|--------|----------|-------------|--------------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC or Felix USDC | 2.91% / 5.75% | +$0.74-$1.46/day |
| USDC unified (all, post COPPER exit) | $5,006 | unified L1 | Felix USDC 5.75% | 5.75% | +$0.79/day |
| USDH unified (all, post COPPER exit) | $4,965 | unified L1 | Felix USDH 5.72% | 5.72% | +$0.78/day |
| **Total** | **$19,271** | | | | **+$2.31-$3.03/day** |

**Rate crash changes redeployment calculus.** Yesterday HypurrFi USDC was 6.06% and Felix USDH was 9.90%. Today: HypurrFi USDC 2.91% and Felix USDH 5.72%. The diversification argument for HypurrFi USDC is now fighting a 284 bps rate penalty vs Felix USDC. At $14.3K total idle USDC, that's $1.11/day difference — not trivial at this scale. **Recommend: deploy idle USDC to Felix USDC (5.75%) not HypurrFi USDC (2.91%) given the rate crash.** Accept the concentration hit temporarily. Reassess when HypurrFi USDC recovers.

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 5.75% | **75 bps** | 0 days (>5%) | **YELLOW** (tight headroom) |
| HyperLend USDC | APR < 3% | 5.58% | 258 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **5.85%** | **-215 bps below** | **Day 5** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.06% (not deployed) | 106 bps | — | GREEN |
| LINK funding | APR < 8% | **8.75%** | **75 bps** | 0 | **YELLOW** (tight) |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | 0 | GREEN |
| USDT0 depeg > 1% (watch) | spread | 2.50 bps | 97.5 bps | — | GREEN |
| USDT0 depeg > 3% (exit) | spread | 2.50 bps | 297.5 bps | — | GREEN |
| Any lending < 3% | exit | HypurrFi USDC 2.91% (not deployed) | — | — | GREEN (no exposure) |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger: Felix USDT0 < 8% for 2wk**
- Counter: Apr 28 (day 1) → Apr 29 (day 2) → Apr 30 (day 3) → May 1 (day 4) → May 2 (day 5)
- Rate trajectory: 6.08 → 6.48 → [no data] → 6.78 → **5.85** — declining again after brief recovery
- Day 7 hard re-evaluation: **May 4 (TOMORROW).** This is the decision point.
- 14-day trigger fires: **May 11.**
- The recovery thesis (slow grind back to 8%) is invalidated. Rate reversed from 6.78% back down to 5.85%.

**NEW: Felix USDC headroom critical.** Only 75 bps from the 5% 3-day exit trigger on $351.9K. This was 308 bps yesterday. A single -75bps day tomorrow starts the 3-day clock on our largest position.

**NEW: LINK headroom critical.** Only 75 bps from the 8% exit trigger. Cap rate has lifted (per lesson #10 — this is the scenario we prepared for). Real funding rate could settle anywhere.

---

## 4. Yesterday → Today

### Action Items from May 2 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | COPPER EXIT (both legs, unified wallet) | ❗ **OVERDUE — 1 DAY.** Was due May 2. Position now -$20.19 (was -$5.50). Delay cost ~$15 in additional MTM loss. |
| P2 | Deploy $2,954 USDH → Felix USDH | ⏳ **PENDING — 2 DAYS.** But Felix USDH crashed 9.90%→5.72% — target rate changed. Still positive. |
| P3 | Deploy $9,300 xyz idle → HypurrFi USDC | ⏳ **PENDING — 12 DAYS IDLE.** HypurrFi USDC crashed 6.06%→2.91% — target needs reassessment. |
| P4 | Deploy $3,043 USDC unified → HypurrFi USDC | ⏳ **PENDING — 2 DAYS.** Same rate crash issue. |
| P5 | HyperLend USDT ($50k) — EXECUTE OR DROP | ❗ **OVERDUE — 12 DAYS.** Cumulative foregone: ~$97. Rate dropped to 5.17% (was 6.06%). |
| P6 | LINK hyna dust cleanup | ⏰ **OVERDUE — 5 days.** cumFunding -$5.93. |
| P7 | Run vault-pulse (get May 2 data) | ✅ **DONE.** May 2 vault-pulse ran at ~02:25 UTC. |

**6 of 7 action items still pending/overdue. Only vault-pulse was completed.** This is the FOURTH consecutive review flagging the same items. The deployment drift scenario from yesterday's risk watch is materializing.

### Material Changes (May 1 → May 2)

| Change | Detail | Impact |
|--------|--------|--------|
| Felix USDC **-133 bps** | 7.08% → 5.75% | **-$12.77/day** — largest single-position yield loss |
| Felix USDT0 **-93 bps** | 6.78% → 5.85% | -$2.80/day — YELLOW trigger day 5, declining |
| Felix USDH **-418 bps** | 9.90% → 5.72% | No direct exposure but kills idle USDH redeployment target |
| HypurrFi USDC **-315 bps** | 6.06% → 2.91% | No exposure but kills USDC→HypurrFi diversification path |
| HypurrFi USDH **-747 bps** | 9.78% → 2.31% | No exposure — USDH spike fully reversed |
| LINK funding **-220 bps** | 10.95% → 8.75% | -$0.19/day — cap rate lifted, real rate emerging |
| HyperLend USDC **+23 bps** | 5.35% → 5.58% | +$1.45/day — only rate that improved |
| COPPER uPnL **-$13.18** | -$9.34 → -$22.52 | -$13.18 additional MTM loss in 1 day |
| COPPER flx cumFunding | +$1.81 → -$0.36 | -$2.17 — short paying funding, day 2 |
| FARTCOIN hyna funding spike | +$4.28/day → +$19.17 | One-off spike? Verify. |
| Daily yield | $129.84 → **$115.18** | **-$14.66/day** — new low since tracking began |

**Pattern: Broad rate compression across ALL stablecoin lending.** Felix USDC, Felix USDT0, Felix USDH, HypurrFi USDC, HypurrFi USDH — all down. Only HyperLend USDC moved up. This looks like a market-wide deleveraging event or supply influx. Not specific to any protocol.

---

## 5. Today's Plan

### Priority 1 — 🔴 COPPER EXIT (1 DAY OVERDUE)

- **What:** Close both COPPER legs (329.6 xyz LONG + 329.6 flx SHORT)
- **Wallet:** unified (0xd473)
- **Why now:** Position deteriorated from -$5.50 to -$20.19 in one day. flx funding negative day 2, accelerating. Each day costs ~$1.73 in funding drain + MTM risk.
- **Expected loss:** ~$20 (accept as lesson cost)
- **Freed capital:** $5,006 USDC + $4,965 USDH on unified wallet
- **Post-exit redeployment:** Hold cash until rates stabilize. Don't chase crashed rates.

### Priority 2 — 🟡 Felix USDT0 Day 7 Prep (decision TOMORROW, May 4)

- **What:** Prepare decision framework for tomorrow's hard re-eval
- **Decision matrix:**
  - If rate recovered toward 7%+ → HOLD, extend
  - If rate still ~5.85% → Evaluate USDT0→USDC rotation for $30-50K
  - If rate dropped further → Plan full $110K USDT0→USDC exit path
- **USDT0→USDC swap cost:** $110K × 2.5 bps = ~$27.50 (trivial)
- **Rate comparison:** Felix USDT0 5.85% vs Felix USDC 5.75% — only 10 bps. The USDT0 bridge risk premium is earning essentially zero premium.
- **Key insight:** When USDT0 lending doesn't pay a meaningful premium over USDC lending, the bridge risk is uncompensated. This is the strongest argument for exit since the YELLOW trigger started.

### Priority 3 — Deploy xyz Idle ($9,300)

- **What:** Withdraw $9,300 USDC from xyz dex margin → deposit to Felix USDC Main
- **Wallet:** spot-perp (0x3c2c)
- **Rate:** Felix USDC 5.75% (better than HypurrFi USDC 2.91% — rate crash killed diversification argument)
- **Impact:** +$1.46/day
- **12 days idle.** Cumulative foregone: ~$22.
- **Concentration note:** Yes, this increases Felix from 67.4% to 68.7%. The alternative is HypurrFi USDC at 2.91% — 284 bps penalty. Not worth it at this rate differential.

### Priority 4 — HyperLend USDT Decision (12 DAYS OVERDUE)

- **What:** DECIDE: execute or formally DROP from tracker
- **Rate (May 2):** 5.17%. Per lesson #8, use 7d avg — estimate ~5.3%.
- **Context change:** Rate dropped from 6.06% (May 1) to 5.17% (May 2). Less compelling than a week ago.
- **If EXECUTE:** Impact +$7.07/day at 5.17%. Felix concentration drops to ~61%.
- **If DROP:** Free up $50K for Felix USDC at 5.75% (+$7.88/day, better rate but worse concentration)
- **Recommendation:** The concentration argument still favors HyperLend even at 5.17%. But the 12-day drift suggests an execution blocker. **Name the blocker or formally drop.**

### Priority 5 — LINK hyna Dust Cleanup (5 DAYS OVERDUE)

- Close 2.4 short hyna:LINK. cumFunding -$5.93.
- 30 seconds. Just do it.

### Priority 6 — Run Vault-Pulse for May 3

- All analysis today uses May 2 data (24+ hours stale).
- Rates may have shifted further given the broad compression trend.
- Run vault-pulse before acting on any recommendation.

**If Bean has 30 minutes today:**
1. Run vault-pulse (fresh data)
2. Exit COPPER (both legs)
3. Close hyna:LINK dust
4. Deploy xyz idle $9,300 → Felix USDC

**If Bean has 60 minutes:** Add USDT0 day-7 decision prep + HyperLend USDT final decision.

---

## 6. Challenger Questions

1. **Felix USDC at 5.75% on $351.9K is 75 bps from the 5% exit trigger — but exit to WHERE?** Yesterday HypurrFi USDC was 6.06%, today it's 2.91%. Felix USDH was 9.90%, today 5.72%. If Felix USDC triggers (<5% for 3d), the $351.9K needs a home. HyperLend USDC at 5.58% is the only protocol that held up — but it already has $230K (30.8% of deployed). Adding $100K would push HyperLend to 46% of deployed. The entire portfolio is ONE bad Felix day away from a forced rotation with nowhere good to go. **Do we need a contingency plan for a Felix USDC exit, or are we comfortable riding the 75 bps buffer?** The 7-day trend (9.02→5.75) suggests this isn't random noise — it's a multi-day compression.

2. **Felix USDT0 hard re-eval is TOMORROW (May 4, day 7) — but the strongest argument for exit isn't the trigger, it's the spread.** Felix USDT0 at 5.85% vs Felix USDC at 5.75% = 10 bps premium for taking bridge risk on $110K. That means we're earning $30/year in extra yield for $110K of USDT0 bridge exposure. The USDT0 thesis required a ~8-10% premium to justify bridge risk. At 10 bps, the risk-reward is broken regardless of whether we hit the 14-day trigger. **Should the day-7 decision be "start planning the full $110K rotation to USDC" rather than "wait for day 14"?**

3. **The FARTCOIN hyna leg earned $19.17 in funding today vs $4.28/day expected — a 4.5x spike.** This could be a one-off liquidation event or a regime shift. If FARTCOIN hyna funding stays elevated, this $12K position is suddenly earning $19/day = 57% APR. **But per lesson #10, single-regime data is misleading.** Is this spike from the +3.4% FARTCOIN price rally (leveraged longs piling in → funding spikes)? If the rally reverses, funding normalizes AND we take MTM loss on the spot leg (though delta neutral). **Should we be thinking about taking profit on the $203 cumulative funding and reducing size, or is this the kind of spike we should let ride?**

---

## 7. Risk Watch

### Scenario: Felix USDC Rate Continues Declining Below 5% Trigger

```
Scenario: Felix USDC drops another 75+ bps to <5%, starting the 3-day
          exit trigger clock on $351.9K — our largest position.
Probability: Medium (7d trend: 9.02→7.44→6.89→6.39→7.08→5.75 — downward
             channel with lower highs. One spike doesn't reverse the trend.)
Impact: If trigger fires (3 consecutive days <5%):
  - Must rotate $351.9K out of Felix USDC
  - HyperLend USDC is only viable destination (5.58%)
  - But HyperLend already at $230K. Adding $352K → $582K = 82% concentration
  - That CREATES a new concentration crisis while solving a rate crisis
  - Alternative: HypurrFi USDC at 2.91% — unacceptable rate
  - Portfolio would need to either: (a) accept HyperLend super-concentration,
    (b) accept HypurrFi poverty rate, or (c) find a new protocol entirely
Trigger signal: Felix USDC prints <5.50% on next vault-pulse
Pre-planned response:
  1. If rate <5.50%: begin researching alternative USDC lending protocols
  2. If rate <5.00% day 1: don't panic — monitor for 3d per trigger rule
  3. If rate <5.00% day 2: prepare HyperLend deposit path for $100-150K
     (not full $352K — split between HyperLend + HypurrFi if rates recover)
  4. If rate <5.00% day 3: execute rotation per plan
```

**Previous risk scenarios covered:** rate collapse (Apr 28), COPPER negative funding (May 1), USDT0 depeg (Apr 29), deployment drift (May 2). Today's focus: Felix USDC trigger — highest-impact single-position risk in the portfolio.

---

## Reviews Due Today (May 3)

| Item | Status | Action Required |
|------|--------|-----------------|
| **COPPER EXIT** | 🔴 **1 DAY OVERDUE** | EXIT both legs. -$20.19 and deteriorating. |
| Felix USDT0 day-7 prep | 🟡 YELLOW day 5 | Decision TOMORROW. Prepare exit vs hold framework. |
| LINK hyna dust cleanup | ⏰ **5 DAYS OVERDUE** | Close 2.4 short. 30 seconds. |
| Deploy xyz idle $9,300 | ⏰ **12 DAYS IDLE** | → Felix USDC 5.75%. +$1.46/day. |
| Deploy USDH unified $4,965 | ⏰ **PENDING.** | → Felix USDH 5.72% (was 9.90%). +$0.78/day. |
| Deploy USDC unified $5,006 | ⏰ **PENDING.** | → Felix USDC 5.75%. +$0.79/day. Post-COPPER exit. |
| HyperLend USDT $50k | ❗ **12 DAYS OVERDUE** | Execute ($5.17%) or formally DROP. ~$97 foregone. |
| Run vault-pulse | 📋 **DATA STALE** | Run before executing any trades. |

**Bean, the deploy backlog has been flagged for 12 consecutive reviews.** Same items, same status. The operational drag scenario from yesterday's risk watch is now the #1 portfolio risk — not rates, not concentration, but execution velocity. Consider blocking a 1-hour deployment session where everything pending gets done or formally dropped. The portfolio is bleeding $10+/day in foregone yield from inaction alone.

---

*Generated 2026-05-03. Primary source: vault pulse 2026-05-02 (~02:25 UTC on-chain). No May 3 vault-pulse — data is 24h+ stale. Rates from rates_history.csv (11-day window). All lessons applied (cited: #6, #8, #10, #11). Critical: COPPER EXIT overdue + Felix USDC 75bps from trigger + USDT0 day-7 decision tomorrow.*
