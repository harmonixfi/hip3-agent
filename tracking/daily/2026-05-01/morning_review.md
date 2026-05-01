# Morning Review — 2026-05-01

**Data:** Vault pulse 2026-05-01 (01:15 UTC). Rates from rates_history.csv (10-day window: Apr 22 - May 1). All lessons from docs/lessons.md applied.

---

## 1. Portfolio Health

| Metric | Today | Yesterday (Apr 29) | Target | Status |
|--------|-------|---------------------|--------|--------|
| Total Portfolio | $744,911 | $740,964 | $800k | YELLOW (-6.9%) |
| Deployed % | 94.9% ($706,576) | 95.3% ($706,409) | >85% | GREEN |
| Daily Yield | **$129.84/day** | $123.87/day | $154/day | **RED — 84.3% of target** |
| Blended APY | 6.71% | 6.40% | 7.04% | YELLOW (-33 bps below) |
| USDT0 Exposure | $110,100 (14.8%) | $110,100 (14.9%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 67.4% ($476k) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $19,295 (2.6%) | $15,303 (2.1%) | <$20k | GREEN |

**So what:** First yield improvement in 4 days — $129.84 vs $123.87 (+$5.97/day). The driver is Felix USDC's rate recovery from 6.39% to 7.08% (+69 bps), which alone added $6.65/day on our $352k position. This is encouraging but doesn't change the structural picture: daily yield is still $24/day below the $154 target, and the two deployment plan items that close the gap — HypurrFi USDT0 ($100k) and HyperLend USDT ($50k) — remain at $0, now **9 days overdue**. The yield gap is 58% structural (undeployed capital) and 42% rate compression (Felix USDT0 at 6.78% vs 15.39% plan). Felix concentration at 67.4% is unchanged and remains the single biggest structural risk.

Positive signal: Felix USDC reversing its 3-day slide suggests we may have found a rate floor around 6.4%. If this holds, the 5% exit trigger is no longer an immediate concern (308 bps headroom vs 139 bps two days ago).

---

## 2. Position Status

### RED/YELLOW — Needs Attention

```
lend_felix_usdt0 — 🟡 WATCH (YELLOW TRIGGER — Day 4 of 14)
  Rate: 6.78% APY (target 15.39%) — BELOW 8% exit threshold by 122 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $20.45 (plan: $42.16 — 48% of plan yield)
  Trigger: APR<8% for 2wk → YELLOW (Day 4 of 14). Counter started Apr 28.
  Trend (8d): 15.39→11.88→12.74→5.81→13.38→6.08→6.48→6.78
  Note: Gradual recovery +30 bps (6.48→6.78) but still far from 8% reset threshold.
        Pattern of lower highs persists: 15.39→13.38→6.78. Rate would need +122 bps
        to clear YELLOW. Day 7 hard re-evaluation on May 4 as committed. At current
        trajectory (+15 bps/day), needs 8 more days to reach 8% — wouldn't make it
        before the 14-day trigger fires on May 11. However, this market is spikey
        (lesson #10) — a single utilization event could reset the counter overnight.
```

```
Felix concentration — 🔴 RED (67.4% — 17pts over 50% cap)
  Felix: $476,300 / $706,576 deployed = 67.4%
  Risk: Any Felix/Morpho incident impacts 2/3 of deployed capital
  Path to reduce: Deploy idle $9,300 to HypurrFi (-1.3pts). Deploy $50k HyperLend USDT
  (-6.7pts → 59.4%). Both pending >9 days. Only the HyperLend USDT deployment
  meaningfully moves the needle.
```

### GREEN — On Track

```
lend_felix_usdc_main — ✅ HOLD (RECOVERED — Best rate since Apr 28)
  Rate: 7.08% APY (target 6.86%) — ABOVE plan by 22 bps
  Amount: $351,800 (target $300,000) — 117% deployed
  Daily: $68.24 (plan: $56.38 — 121% of plan yield)
  Trigger: APR<5% for 3d → GREEN (308 bps headroom — widened from 139 bps!)
  Trend: 5.55→5.16→9.02→7.44→6.89→6.39→7.08
  Note: 3-day slide REVERSED. 7.08% is above plan target for the first time since
        Apr 27. Headroom doubled in 2 days (139→308 bps). The 5% trigger concern
        from Apr 30 review is defused for now. This is the portfolio's highest-earning
        position at $68.24/day (52.5% of total yield).
```

```
lend_hyperlend_usdc — ✅ HOLD (STABLE but easing)
  Rate: 5.35% APY (target 4.36%) — ABOVE plan by 99 bps
  Amount: $230,276 (target $230,000) — 100% deployed
  Daily: $33.78 (plan: $27.47 — 123% of plan yield)
  Trigger: APR < 3% → GREEN (235 bps headroom)
  Trend (7d): 3.84→4.96→5.06→5.56→5.61→5.63→5.35
  Note: Per lesson #8, 7d range 3.0-5.6%. Rate eased 28 bps after 6-day uptrend —
        likely mean reversion, not concerning. Still 99 bps above plan. 7d average
        ~5.0%, well above the 3% exit trigger.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD (REVIEW DUE TODAY — GREEN)
  Rate: 10.95% APR (cap rate — per lesson #10, regime artifact)
  Amount: $11,936 notional (59,944 spot / 60,180 total short)
  Daily: $3.59/day ($0.51 native + $3.08 hyna)
  Cumulative funding: $183.65 ($21.60 native + $162.05 hyna)
  Delta: neutral (-0.4%)
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Review: DUE TODAY. Verdict: HOLD. At cap rate, no reason to exit. Per lesson #10,
          cap rate could end abruptly — when it does, reassess immediately.
```

```
pos_link_native — ✅ HOLD (REVIEW DUE TODAY — GREEN)
  Rate: 10.95% APR (cap rate)
  Amount: $3,121 (342.13 spot / 336 short)
  Daily: $0.92/day | Cumulative: $26.90 (net $20.97 after hyna dust -$5.93)
  Delta: neutral (1.1%)
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Review: DUE TODAY. Verdict: HOLD. Same as FARTCOIN — cap rate, all green.
```

```
COPPER (xyz+flx) — ⚠️ TEST POSITION (hard review TOMORROW May 2)
  Notional: $3,965 ($1,988 xyz long + $1,977 flx short)
  uPnL: -$9.34 net (improved from -$11.72 — mark recovering)
  cumFunding: $3.84 ($2.03 xyz + $1.81 flx)
  ⚠️ flx cumFunding DECREASED $3.10→$1.81 — unusual. Possible negative funding on
     flx:COPPER (shorts paid longs). Verify in tomorrow's review.
  Net P&L: cumFunding $3.84 - uPnL $9.34 = -$5.50 underwater
  Margin holds: ~$3,990. Free in unified: $3,043 USDC + $2,954 USDH = $5,997
  Note: Mark prices recovering (+1%). Tomorrow's review is the hard decision point.
        At current trajectory, 2-3 more days to break even on funding vs uPnL —
        IF flx funding stops going negative. The flx cumFunding decrease is a concern.
```

```
lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 7.08% | $2.09/day
lend_felix_usde — ✅ HOLD | $3,600 @ 7.80% | $0.77/day
pos_link_hyna_dust — ⏰ CLEANUP OVERDUE | $22 | cumFunding -$5.93 (slow bleed)
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate | Impact |
|------|--------|----------|-------------|------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | Felix USDC (7.08%) or HypurrFi USDC (6.06%) | 6-7% | +$1.53-$1.80/day |
| USDC unified free | $3,043 | unified L1 | HypurrFi USDC (6.06%) | 6.06% | +$0.51/day |
| USDH unified free | $2,954 | unified L1 | Felix USDH (9.90%) | 9.90% | +$0.80/day |
| **Total idle** | **$15,297** | | | | **+$2.84-$3.11/day** |

**Note:** HypurrFi USDC rate dropped significantly (6.85%→6.06%, -79 bps). Felix USDC at 7.08% is now the better USDC target. However, deploying xyz idle to Felix USDC increases Felix concentration further (67.4%→68.7%). Deploying to HypurrFi at 6.06% sacrifices 102 bps but reduces concentration. **Trade-off: yield vs diversification.**

Felix USDH at 9.90% is the best rate in the portfolio for USDH — the $2,954 idle USDH should go there (no concentration trade-off since it's already USDH on unified).

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 7.08% | **308 bps** | 0 days below 5% | **GREEN** (recovered, headroom doubled) |
| HyperLend USDC | APR < 3% | 5.35% | 235 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **6.78%** | **-122 bps below** | **Day 4** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.16% (not deployed) | 116 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% (watch) | spread | 2.90 bps | 97 bps | — | GREEN |
| USDT0 depeg > 3% (exit) | spread | 2.90 bps | 297 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend USDC 5.35% (closest) | 235 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger: Felix USDT0 < 8% for 2wk**
- Apr 25: 5.81% → Apr 27: 13.38% → **RESET**
- Apr 28: 6.08% (day 1)
- Apr 29: 6.48% (day 2)
- Apr 30: [no vault-pulse] (day 3 by calendar — no reset, rate unknown but no evidence of recovery above 8%)
- **May 1: 6.78% (day 4)**
- Trend: slow recovery (+30 bps/snapshot). At +30 bps/day: reaches 8% around day 8 (May 5-6). But the lower-highs pattern (15.39→13.38→6.78) suggests the rate regime has shifted downward.
- **Decision point remains May 4 (day 7).** If not above 8%, begin evaluating partial rotation.

**Felix USDC < 5% trigger: DEFUSED.** Rate reversed from 6.39% to 7.08%. Three-day slide broken. Headroom 308 bps — widest since Apr 27. No near-term concern.

---

## 4. Yesterday → Today

### Action Items from Apr 30 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Felix USDT0 day-3 evaluation | ✅ **DONE** — Decision was HOLD. Now day 4, rate improved to 6.78%. Next evaluation: May 4 (day 7). |
| P2 | Deploy $9,300 xyz idle → HypurrFi USDC | ⏳ **PENDING — 10 DAYS IDLE.** ~$17/day foregone since Apr 22 at current rates. |
| P3 | HyperLend USDT ($50k) — DECIDE | ⏳ **OVERDUE — 9 DAYS.** Rate was 6.27% Apr 29, now 6.06%. ~$75+ cumulative foregone yield. |
| P4 | Deploy unified idle ($3,043 USDC + $2,954 USDH) | ⏳ **PENDING** |
| P5 | LINK hyna dust cleanup | ⏳ **OVERDUE — scheduled Apr 29.** cumFunding -$5.93. |
| P6 | Run vault-pulse | ✅ **DONE** — May 1 data available. |

### Material Changes (Apr 29 → May 1)

| Change | Detail | Impact |
|--------|--------|--------|
| Felix USDC **recovered** | 6.39% → 7.08% (+69 bps) | **+$6.65/day** — biggest positive move, above plan target |
| Felix USDT0 slow recovery | 6.48% → 6.78% (+30 bps) | +$0.91/day — still below 8% YELLOW |
| HyperLend USDC eased | 5.63% → 5.35% (-28 bps) | -$1.77/day — mean reversion after 6-day uptrend |
| Felix USDH surged | 7.22% → **9.90%** (+268 bps) | New opportunity — we have $2,954 idle USDH |
| HypurrFi USDC dropped | 6.85% → 6.06% (-79 bps) | Makes xyz idle deployment to HypurrFi less attractive |
| HypurrFi USDH surged | 4.56% → **9.78%** (+522 bps) | USDH rates broadly strong across protocols |
| COPPER marks recovering | xyz 5.971→6.035, flx 5.942→5.999 | uPnL improved -$11.72 → -$9.34 |
| COPPER flx cumFunding ↓ | $3.10 → $1.81 (-$1.29) | **UNUSUAL — verify.** Possible negative funding. |
| Daily yield improved | $123.87 → **$129.84** (+$5.97) | First improvement in 4 days. 84.3% of target. |
| Portfolio value up | $740,964 → $744,911 (+$3,947) | Interest accrual + mark recovery |
| USDT0 spread widened | 2.00 → 2.90 bps (+0.9 bps) | Still far from 100 bps watch level. GREEN. |

---

## 5. Today's Plan

### Priority 1: Deploy $2,954 USDH → Felix USDH (9.90%)

- **What:** Supply idle USDH from unified wallet to Felix USDH vault
- **Wallet:** unified (0xd473)
- **Rate:** 9.90% — **highest-yielding opportunity in the portfolio right now**
- **Impact:** +$0.80/day
- **Why now:** USDH rates surged +268 bps overnight. This is free money sitting idle. Zero blocker.

### Priority 2: Deploy $9,300 xyz Idle (10 DAYS OVERDUE)

- **What:** Withdraw from spot-perp xyz dex → lending
- **Wallet:** spot_perp (0x3c2c)
- **Trade-off:** Felix USDC (7.08%, +$1.80/day) vs HypurrFi USDC (6.06%, +$1.54/day, reduces concentration)
- **Recommendation:** Split — $5k to HypurrFi USDC (diversification) + $4.3k stays in Felix. Or if Bean prioritizes yield, all to Felix USDC.
- **Cumulative opportunity cost:** ~$17 foregone since Apr 22.

### Priority 3: HyperLend USDT — FINAL DECISION (9 DAYS OVERDUE)

- **What:** Deploy $50k USDC → USDT → HyperLend USDT
- **Rate (May 1):** 6.06% (down from 6.27%). Per lesson #8, 7d avg likely ~5.5%.
- **Impact at conservative 5.5% avg:** +$7.53/day. Closes 31% of the $24/day yield gap.
- **Concentration benefit:** Felix drops from 67.4% to ~61.5%. HyperLend goes from 32.6% to ~39.7%.
- **This is the single highest-impact deployment decision in the portfolio.** It adds more daily yield than all idle capital combined and meaningfully reduces concentration risk.
- **Cumulative opportunity cost:** ~$75+ foregone over 9 days.
- **Recommendation:** Execute or formally drop. If dropped, remove from tracker and adjust targets.

### Priority 4: Deploy $3,043 USDC Unified → HypurrFi USDC (6.06%)

- **What:** Deploy free USDC from unified wallet
- **Impact:** +$0.51/day
- **Also reduces Felix concentration by ~0.4pts**

### Priority 5: LINK hyna Dust Cleanup (OVERDUE since Apr 29)

- Close 2.4 short hyna:LINK. cumFunding -$5.93 and growing.
- Trivial size ($22) but slow bleed and dashboard noise.

### Priority 6: COPPER Hard Review Prep (TOMORROW May 2)

- Prepare for the committed May 2 decision point.
- Key question: flx cumFunding decreased (-$1.29). Is flx:COPPER funding negative? If so, the thesis (earn flx funding, neutral on xyz) is broken.
- Decision matrix for tomorrow:
  - If flx funding confirmed negative → EXIT. Free $5,997 for lending.
  - If flx funding positive and cumFunding decrease was a data artifact → HOLD if break-even within 3 days.
  - If unclear → EXIT. Test position doesn't warrant extended uncertainty.

**Total impact if P1-P4 execute: +$10.64/day** → yield from $129.84 to ~$140.48/day (91.2% of target)

---

## 6. Challenger Questions

1. **Felix USDH just surged to 9.90% — the highest lending rate we can actually access — and we have $4,955 USDH sitting idle (only $2,954 free after COPPER margin).** If we exit COPPER tomorrow (freeing $2,001 USDH margin), that's $4,955 × 9.90% ÷ 365 = $1.34/day vs COPPER's theoretical funding of ~$1-2/day with a -$5.50 unrealized loss. Is COPPER's uncertain funding (with a DECREASING cumFunding) really better than a guaranteed 9.90% on USDH? The COPPER test position has consumed $3,990 in margin to earn $3.84 in cumulative funding — a -$5.50 net loss after 10 days. **At what point does a "test" that's underwater and exhibiting anomalous funding behavior get called a failed experiment?**

2. **The HyperLend USDT deployment is now 9 days overdue with ~$75 in cumulative foregone yield.** This isn't a large number, but the signal is: **the yield gap is $24/day and we control $7.53/day of it through a single deployment that takes 30 minutes to execute.** That's 31% of the gap, closed permanently. Every day we don't deploy, we're choosing to forgo $7.53/day — that's $226/month. Meanwhile, every morning review flags this as "overdue" and nothing changes. **Is there an unspoken reason this deployment isn't happening, or has it genuinely fallen through the cracks?**

3. **USDT0 spread widened from 2.0 to 2.9 bps — still small, but the direction matters.** We have $110k in USDT0 positions and the deployment plan targets $200k (25% exposure). The spread widening, combined with Felix USDT0's rate decline from 15.39% to 6.78%, means the USDT0 thesis is weakening on both fronts: lower yield AND slightly worse exit liquidity. **Should we still target $200k USDT0 exposure, or has the rate environment changed enough to cap at the current $110k and redirect the remaining $100k HypurrFi target to USDC lending?**

---

## 7. Risk Watch

### Scenario: COPPER Margin Expansion + Negative Funding

```
Scenario: COPPER flx side has turned funding-negative. If this persists, the short
         is now PAYING funding instead of earning it. Combined with the xyz long
         (which may also be paying or earning minimal funding), the position becomes
         a pure directional bet on spread convergence — the opposite of our thesis.
Probability: Medium-High (flx cumFunding decrease from $3.10 to $1.81 is strong evidence)
Impact: -$1-2/day in negative funding + continued margin lock-up ($3,990).
        If COPPER mark drops another 2%, additional margin could be required,
        further reducing free capital. Worst case: margin call forces liquidation
        at the worst price.
Trigger signal: Tomorrow's COPPER review (May 2). Verify flx funding rate sign.
Pre-planned response:
  1. If flx funding confirmed negative → EXIT both legs immediately
  2. Free $3,990 in margin → $1,989 USDC + $2,001 USDH
  3. Deploy freed USDC to HypurrFi USDC (6.06%) = +$0.33/day
  4. Deploy ALL $4,955 USDH to Felix USDH (9.90%) = +$1.34/day
  5. Net gain: exit a -$1-2/day drain, gain +$1.67/day in lending = $3-4/day swing
```

---

## Reviews Due Today (May 1)

| Item | Status | Decision |
|------|--------|----------|
| FARTCOIN review | ✅ **REVIEWED TODAY** | HOLD — 10.95% cap rate, GREEN. Next review May 8. |
| LINK review | ✅ **REVIEWED TODAY** | HOLD — 10.95% cap rate, GREEN. Next review May 8. |
| LINK hyna dust cleanup | ⏰ **OVERDUE (since Apr 29)** | Close 2.4 short. Trivial. |
| Deploy xyz idle $9,300 | ⏰ **10 DAYS IDLE** | Deploy to Felix USDC or split with HypurrFi. |
| HyperLend USDT ($50k) | ❗ **9 DAYS OVERDUE** | Execute or formally drop. |
| Deploy unified idle ($5,997) | ⏰ **PENDING** | USDH → Felix USDH (9.90%). USDC → HypurrFi (6.06%). |
| COPPER hard review | 📅 **TOMORROW (May 2)** | Prepare: verify flx funding sign. Decision matrix above. |
| Felix USDT0 day-7 check | 📅 **May 4 (Sun)** | Rate must reach 8% to clear YELLOW. Currently 6.78%. |

---

*Generated 2026-05-01. Primary source: vault pulse 2026-05-01 (01:15 UTC — fresh). Rates from rates_history.csv (10-day window). All lessons from docs/lessons.md applied (cited: #8, #10, #6). Next: execute pending deployments (USDH → Felix first — zero blockers, best rate), prep COPPER review for May 2.*
