# Morning Review — 2026-05-02

**Data:** Vault pulse 2026-05-01 (most recent — **no May 2 vault-pulse yet** [VERIFY]). Rates from rates_history.csv (10-day window: Apr 22 - May 1). All lessons from docs/lessons.md applied.

**STALE DATA WARNING:** All numbers below are from the May 1 snapshot. Rates, balances, and P&L may have shifted overnight. Run vault-pulse before acting on any recommendation.

---

## 1. Portfolio Health

| Metric | Today (May 1 data) | Yesterday | Target | Status |
|--------|---------------------|-----------|--------|--------|
| Total Portfolio | $744,911 | $740,964 | $800k | YELLOW (-6.9%) |
| Deployed % | 94.9% ($706,576) | 95.3% ($706,409) | >85% | GREEN |
| Daily Yield | **$129.84/day** | $123.87/day | $154/day | **RED — 84.3% of target** |
| Blended APY | 6.71% | 6.40% | 7.04% | YELLOW (-33 bps below) |
| USDT0 Exposure | $110,100 (14.8%) | $110,100 (14.9%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 67.4% ($476k) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $19,295 (2.6%) | $15,303 (2.1%) | <$20k | GREEN |

**So what:** The yield story hasn't changed in substance since yesterday. We're earning $129.84/day — $24.16/day short of target. The gap breaks down as:

- **$7.53/day** from undeployed HyperLend USDT ($50k × ~5.5% avg) — now **10 days overdue**
- **$21.71/day** from Felix USDT0 rate compression (6.78% vs 15.39% plan target) — structural, not actionable beyond the day-7 rebalance on May 4
- **$2-3/day** from scattered idle capital ($19.3k at 0%)

The controllable portion — HyperLend USDT deployment + idle redeployment — accounts for ~$10/day. That gets us to ~$140/day (91% of target). The remaining $14/day gap is rate environment (USDT0 compression) and portfolio size ($744k vs $800k plan).

Felix concentration at 67.4% is the **persistent structural risk**. Every deployment to Felix worsens it. The only meaningful fix is the HyperLend USDT deployment, which drops Felix to ~61.5%.

---

## 2. Position Status

### RED/YELLOW — Needs Attention

```
COPPER (xyz+flx) — 🔴 HARD REVIEW DUE TODAY (May 2)
  xyz LONG: 329.6 @ entry 6.063, mark 6.035 | uPnL -$9.23
  flx SHORT: 329.6 @ entry 5.998, mark 5.999 | uPnL -$0.11
  cumFunding: $3.84 ($2.03 xyz + $1.81 flx)
  Net P&L: cumFunding $3.84 - uPnL $9.34 = **-$5.50 UNDERWATER**

  ⚠️ THESIS BROKEN — flx cumFunding DECREASED $3.10 → $1.81 (-$1.29)
  The short leg PAID funding instead of earning it. Meanwhile xyz long
  received $1.49. Net funding change: +$0.20 over the period — near zero.
  
  VERDICT: EXIT.
  - flx funding confirmed negative (lesson #11 — thesis invalidated)
  - Position is -$5.50 after 10 days with broken funding economics
  - Margin lock: $3,990 ($1,989 USDC + $2,001 USDH) earning 0%
  - Alternative: freed USDH ($4,955 total including free) → Felix USDH 9.90%
    = $1.34/day. Freed USDC → HypurrFi USDC 6.06% = $0.33/day
  - Exiting turns a -$5.50 loss + $0/day drain into +$1.67/day income
  - At $3,965 notional for a test position, the lesson is learned
```

```
lend_felix_usdt0 — 🟡 WATCH (YELLOW TRIGGER — Day 5 of 14)
  Rate: 6.78% APY (target 15.39%) — BELOW 8% exit threshold by 122 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $20.45 (plan: $42.16 — 48% of plan yield)
  Trigger: APR<8% for 2wk → YELLOW (Day 5 of 14). Counter started Apr 28.
  Trend (8d): 15.39→11.88→12.74→5.81→13.38→6.08→6.48→6.78
  Note: Slow grind higher (+30 bps/snapshot avg) but lower-highs pattern
        intact: 15.39→13.38→6.78. Hard re-evaluation on May 4 (day 7).
        At current trajectory, won't reach 8% before 14-day trigger (May 11).
        However, per lesson #10, this market is spikey — a single event
        could reset the counter. No action until May 4.
```

```
Felix concentration — 🔴 RED (67.4% — 17pts over 50% cap)
  Felix: $476,300 / $706,576 deployed = 67.4%
  Per lesson #6: no single protocol > ~45%. We're 22pts over that.
  Path to reduce: HyperLend USDT deploy (-6.7pts → 60.7%). Idle xyz
  to HypurrFi (-0.9pts). Still above 50% even after both — structural.
  The only real fix is scaling HyperLend/HypurrFi allocations.
```

### GREEN — On Track

```
lend_felix_usdc_main — ✅ HOLD (STABLE at recovered level)
  Rate: 7.08% APY (target 6.86%) — ABOVE plan by 22 bps
  Amount: $351,800 (target $300,000) — 117% deployed
  Daily: $68.24 (plan: $56.38 — 121% of plan yield)
  Trigger: APR<5% for 3d → GREEN (308 bps headroom)
  Trend: 5.55→5.16→9.02→7.44→6.89→6.39→7.08
  Note: Rate stabilized around 7% after reversing the 3-day slide.
        This is the portfolio workhorse at $68.24/day (52.5% of total yield).
        Next review: May 5.
```

```
lend_hyperlend_usdc — ✅ HOLD (STABLE)
  Rate: 5.35% APY (target 4.36%) — ABOVE plan by 99 bps
  Amount: $230,276 (target $230,000) — 100% deployed
  Daily: $33.78 (plan: $27.47 — 123% of plan yield)
  Trigger: APR < 3% → GREEN (235 bps headroom)
  Trend (7d avg per lesson #8): ~5.0%. Range 3.0-5.6%.
  Note: Small 28 bps dip (5.63→5.35) — mean reversion, not concerning.
        Next review: May 5.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD (Cap rate)
  Rate: 10.95% APR (cap rate — lesson #10 caveat)
  Amount: $11,936 spot / $11,988 short (60,180 total)
  Daily: $3.59/day ($0.51 native + $3.08 hyna)
  Cumulative funding: $183.65 ($21.60 native + $162.05 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Next review: May 8.
```

```
pos_link_native — ✅ HOLD (Cap rate)
  Rate: 10.95% APR (cap rate)
  Amount: $3,121 (342.13 spot / 336 short)
  Daily: $0.92/day | Cumulative: $26.90 (net $20.97 after hyna dust -$5.93)
  Delta: neutral (1.1%) — slightly wide, monitor
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Next review: May 8.
```

```
lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 7.08% | $2.09/day
lend_felix_usde — ✅ HOLD | $3,600 @ 7.80% | $0.77/day
pos_link_hyna_dust — ⏰ CLEANUP OVERDUE (4 days) | $22 | cumFunding -$5.93
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate | Impact |
|------|--------|----------|-------------|------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC 6.06% (diversification) | 6.06% | +$1.54/day |
| USDC unified free | $3,043 | unified L1 | HypurrFi USDC 6.06% | 6.06% | +$0.51/day |
| USDH unified free | $2,954 | unified L1 | Felix USDH 9.90% | 9.90% | +$0.80/day |
| **Total idle** | **$15,297** | | | | **+$2.85/day** |

**Recommendation:** Deploy USDH → Felix USDH first (9.90% = best rate, zero blocker, $0.80/day). Deploy USDC idle to HypurrFi over Felix — yes it's 102 bps less yield, but it reduces Felix concentration. At $12.3k total USDC idle, the yield difference is $3.45/yr — trivial vs the concentration risk reduction.

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 7.08% | 308 bps | 0 days | **GREEN** |
| HyperLend USDC | APR < 3% | 5.35% | 235 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **6.78%** | **-122 bps below** | **Day 5** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.16% (not deployed) | 116 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% (watch) | spread | 2.90 bps | 97 bps | — | GREEN |
| USDT0 depeg > 3% (exit) | spread | 2.90 bps | 297 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend USDC 5.35% (closest) | 235 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger: Felix USDT0 < 8% for 2wk**
- Counter: Apr 28 (day 1) → Apr 29 (day 2) → Apr 30 (day 3) → May 1 (day 4) → **May 2 (day 5)**
- Rate trajectory: 6.08 → 6.48 → [no data] → 6.78 → [today unknown — no vault-pulse]
- Trend: +23 bps/day average. At that pace, reaches 8% around day 10 (May 7).
- Day 7 hard re-evaluation: **May 4 (Sunday).** If still below 8%, evaluate partial rotation ($30-50k to HypurrFi USDT0 at 6.16% — though that's even lower than Felix USDT0, making rotation unattractive).
- 14-day trigger fires: **May 11.**
- The lower-highs pattern (15.39 → 13.38 → 6.78) suggests a structural rate regime shift in USDT0 lending.

---

## 4. Yesterday → Today

### Action Items from May 1 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Deploy $2,954 USDH → Felix USDH (9.90%) | ⏳ **PENDING — 1 DAY.** No evidence of deployment in data. |
| P2 | Deploy $9,300 xyz idle → HypurrFi USDC | ⏳ **PENDING — 11 DAYS IDLE.** Cumulative foregone: ~$19. |
| P3 | HyperLend USDT ($50k) — FINAL DECISION | ❗ **OVERDUE — 10 DAYS.** Cumulative foregone: ~$83. |
| P4 | Deploy $3,043 USDC unified → HypurrFi USDC | ⏳ **PENDING — 1 DAY.** |
| P5 | LINK hyna dust cleanup | ⏳ **OVERDUE — 4 days (since Apr 29).** cumFunding -$5.93. |
| P6 | COPPER hard review prep | 📅 **DUE TODAY.** See Section 2 COPPER analysis above. |

**5 of 6 action items from yesterday are pending/overdue.** Only the COPPER prep (informational) was completed. This is the third consecutive review flagging these same items.

### Material Changes (Estimated, May 1 → May 2)

**No vault-pulse for May 2 — cannot confirm material changes.** Based on May 1 trajectory:

| Expected Change | Basis | Confidence |
|-----------------|-------|------------|
| Felix USDC ~7.0-7.2% | Rate stabilized around 7% | Medium |
| Felix USDT0 ~6.8-7.0% | +23 bps/day avg recovery | Low (spikey market) |
| HyperLend USDC ~5.2-5.4% | Minor mean reversion | Medium |
| LINK/FARTCOIN 10.95% | Cap rate regime | High (until it ends) |
| COPPER cumFunding ~ flat | Near-zero net funding | Medium |

---

## 5. Today's Plan

### Priority 1 — 🔴 COPPER EXIT (Hard Review — DUE TODAY)

- **What:** Close both COPPER legs (329.6 xyz LONG + 329.6 flx SHORT)
- **Wallet:** unified (0xd473)
- **Rationale:** flx cumFunding decreased $3.10 → $1.81. The short side paid funding — thesis broken. Per yesterday's decision matrix: "if flx funding confirmed negative → EXIT."
- **Expected loss on exit:** ~$5.50 (cumFunding $3.84 - uPnL ~$9.34). Accept as cost of learning.
- **Freed capital:** $1,989 USDC + $2,001 USDH in margin + $3,043 USDC + $2,954 USDH free = **$5,032 USDC + $4,955 USDH total on unified**
- **Redeploy immediately:**
  - $4,955 USDH → Felix USDH (9.90%) = **+$1.34/day**
  - $5,032 USDC → HypurrFi USDC (6.06%) = **+$0.84/day**
- **Net impact:** Exit -$0/day drain + gain **+$2.18/day** in lending
- **Lesson for journal:** Cross-venue thesis requires BOTH legs earning (or at least one paying near-zero). When the short leg pays funding, the trade is a pure directional bet on spread convergence — not our strategy.

### Priority 2 — ❗ HyperLend USDT ($50k) — EXECUTE OR DROP

- **What:** Deploy $50k USDC → swap to USDT → supply to HyperLend USDT
- **Rate (May 1):** 6.06%. Per lesson #8, 7d avg ~5.5%.
- **Impact at 5.5% avg:** **+$7.53/day** — closes 31% of the $24/day yield gap
- **Concentration benefit:** Felix drops from 67.4% to ~61.5% (-5.9pts)
- **This is the 10th day this appears as "overdue."** Cumulative opportunity cost: ~$83.
- **Recommendation:** EXECUTE. If there's a blocker Bean hasn't articulated, formally DROP and remove from tracker. The daily review cycle of flagging-without-acting wastes attention.
- **If blocked by USDC→USDT swap friction:** Quantify the blocker. Is it slippage? Bridge route? Time cost? Name the actual obstacle.

### Priority 3 — Deploy All Idle Capital ($15.3k + COPPER freed capital)

After COPPER exit, total idle across wallets:

| Source | Amount | Target | Rate | Daily |
|--------|--------|--------|------|-------|
| USDH (unified, all freed) | $4,955 | Felix USDH | 9.90% | +$1.34 |
| USDC (unified, all freed) | $5,032 | HypurrFi USDC | 6.06% | +$0.84 |
| USDC xyz idle | $9,300 | HypurrFi USDC | 6.06% | +$1.54 |
| **Total** | **$19,287** | | | **+$3.72/day** |

**Combined P1+P3 impact: +$3.72/day → yield from $129.84 to ~$133.56/day**
**Combined P1+P2+P3 impact: +$11.25/day → yield from $129.84 to ~$141.09/day (91.6% of target)**

### Priority 4 — LINK hyna Dust Cleanup (4 DAYS OVERDUE)

- Close 2.4 short hyna:LINK. cumFunding -$5.93 and growing.
- Trivial size ($22) — dashboard noise and slow bleed.
- **Just do it.** This takes 30 seconds.

### Priority 5 — Run Vault-Pulse

- Today's data is stale. Run vault-pulse to get fresh May 2 snapshot.
- Essential before executing any of the above actions (verify current rates, especially COPPER marks and flx funding).

---

## 6. Challenger Questions

1. **The COPPER "test" has been running 10 days, lost $5.50, exhibited negative short-side funding, and absorbed $3,990 in margin.** The experiment is conclusive: flx:COPPER funding is unreliable for cross-venue spread. But here's the real question — **do we have a cross-venue pipeline?** The playbook exists (`docs/playbook-cross-venue-spread.md`), but with COPPER failing, are there other cross-venue candidates being screened? If not, the $10k "cross-venue" budget should be formally reallocated to lending. $10k in Felix USDC at 7.08% = $1.94/day guaranteed vs $0/day in a thesis-broken spread. **Kill the allocation if there's no pipeline.**

2. **HyperLend USDT has been "overdue" for 10 consecutive morning reviews.** At $7.53/day, the cumulative foregone yield is now ~$83 — crossing from rounding error into real money. But the signal isn't the $83 — it's that **something is blocking execution and it hasn't been named.** Is it the USDC→USDT swap route? Concern about HyperLend USDT's volatile rate (lesson #8: 7d avg only 3.29% when plan was written, now ~5.5%)? Time? If the rate environment has genuinely changed and 5.5% avg on USDT doesn't justify the swap friction, that's a valid reason to DROP — but it needs to be an explicit decision, not drift. **Name the blocker or execute today.**

3. **Felix USDT0 at 6.78% on day 5 of 14 — but what's the plan B if it doesn't recover?** On May 4 (day 7), the plan says "evaluate partial rotation." But rotate WHERE? HypurrFi USDT0 is at 6.16% — LOWER than Felix USDT0. Rotating $30-50k from 6.78% to 6.16% loses $0.47-$0.85/day for a diversification benefit on a protocol that's also untested at scale. **If the USDT0 lending thesis is broken across all protocols (Felix AND HypurrFi both under 8%), should we start planning a USDT0→USDC exit path for the full $110k?** That would involve USDT0→USDC swap (2.9 bps spread = ~$32 cost) and redeploying to Felix USDC (7.08%) or HypurrFi USDC (6.06%). The rate difference (6.78% USDT0 vs 7.08% USDC) is minimal, but it eliminates bridge risk entirely.

---

## 7. Risk Watch

### Scenario: Deployment Drift — 10+ Days of Inaction Compounds

```
Scenario: The HyperLend USDT deployment and idle capital redeployment
         continue to slip for another 2 weeks. No new vault-pulse is run
         today, so no action items execute. COPPER remains open. The
         portfolio drifts at $129.84/day for the rest of May.
Probability: Medium-High (pattern established — 10 days of flagging same items)
Impact: -$330/month below target ($24.16/day × 30d)
        -$225/month from HyperLend USDT specifically
        -$112/month from idle capital
        Felix concentration stays at 67.4% — any Felix incident hits $476k
Trigger signal: Same action items appear in May 5 review still pending
Pre-planned response:
  1. If P1-P3 not executed by May 5: escalate — block all new analysis
     until pending deployments are executed or formally dropped
  2. Create a "deployment day" — dedicate 1 hour to executing all
     pending items in sequence: COPPER exit → USDH deploy → USDC deploy
     → HyperLend USDT decision → hyna cleanup
  3. Remove from tracker any item that's been overdue >14 days — it's
     not a plan anymore, it's aspirational
```

**Previous risk scenarios covered:** rate collapse (Apr 28), COPPER negative funding (May 1), USDT0 depeg (Apr 29). Today's scenario focuses on operational risk — the biggest drag on the portfolio right now isn't rates, it's execution velocity.

---

## Reviews Due Today (May 2)

| Item | Status | Action Required |
|------|--------|-----------------|
| **COPPER hard review** | 🔴 **DUE TODAY** | EXIT recommended. flx funding negative — thesis broken. |
| Felix USDT0 day-5 monitor | 🟡 YELLOW day 5 | No action until day-7 eval (May 4). Monitor only. |
| LINK hyna dust cleanup | ⏰ **4 DAYS OVERDUE** | Close 2.4 short. 30 seconds. |
| Deploy USDH $2,954 | ⏰ **1 DAY OVERDUE** | → Felix USDH 9.90%. +$0.80/day. Zero blocker. |
| Deploy xyz idle $9,300 | ⏰ **11 DAYS IDLE** | → HypurrFi USDC 6.06%. +$1.54/day. |
| Deploy USDC unified $3,043 | ⏰ **1 DAY OVERDUE** | → HypurrFi USDC 6.06%. +$0.51/day. |
| HyperLend USDT $50k | ❗ **10 DAYS OVERDUE** | Execute or drop. +$7.53/day if executed. |
| Run vault-pulse | 📋 **DATA STALE** | Run before executing any trades. |

**Execution order if Bean has 30 minutes today:**
1. Run vault-pulse (verify data freshness)
2. Exit COPPER (both legs, unified wallet)
3. Deploy USDH → Felix USDH (unified wallet — post COPPER exit)
4. Close hyna:LINK dust (spot-perp wallet)
5. Deploy USDC unified → HypurrFi USDC (unified wallet)

**If Bean has 60 minutes:** add xyz idle withdrawal + HypurrFi deploy, and the HyperLend USDT swap+deploy.

---

*Generated 2026-05-02. Primary source: vault pulse 2026-05-01 (STALE — no May 2 pulse). Rates from rates_history.csv (10-day window). All lessons from docs/lessons.md applied (cited: #6, #8, #10, #11). Key action: COPPER EXIT (thesis broken) + execute overdue deployments.*
