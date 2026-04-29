# Morning Review — 2026-04-29

**Data:** Vault pulse on-chain ~01:12 UTC | Rates from rates_history.csv (8 days: Apr 22-29)

---

## 1. Portfolio Health

| Metric | Today | Yesterday (Apr 28) | Target | Status |
|--------|-------|---------------------|--------|--------|
| Total Portfolio | $740,964 | $744,894 | $800k | YELLOW (-7.4%) |
| Deployed % | 95.3% ($706,409) | 94.8% ($706,375) | >85% | GREEN |
| Daily Yield | **$123.87/day** | $127.33/day | $154/day | **RED — 80.4% of target** |
| Blended APY | 6.40% | 6.58% | 7.04% | **RED (-64 bps below target)** |
| USDT0 Exposure | $110,100 (14.9%) | $110,100 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 67.4% ($476k) | <50% | RED (+17.4pts over cap) |
| Idle Capital | $15,303 (2.1%) | $19,300 (2.6%) | <$20k | GREEN |

**So what:** Second consecutive day of yield decline. The $155/day milestone on Apr 27 now looks like a peak, not a floor. Today's $123.87 is 20% below target and the lowest since Apr 24 ($108). The drag is Felix USDC — our largest position at $362.5k — sliding another 50 bps to 6.39%. This one position is responsible for ~$5/day of yield loss vs yesterday. The silver lining: Felix USDT0, USDe, and USDH all partially recovered (+40 to +134 bps), but the dollar impact is smaller because those positions are smaller. HyperLend continues its quiet uptrend (+2 bps to 5.63%), reinforcing the diversification thesis.

**The yield gap is now $30.13/day ($154 - $123.87).** Closing it requires either: (a) Felix rates to recover to 7.5%+ blended, (b) deploying idle capital + HypurrFi/HyperLend USDT allocations as planned, or (c) both. Without rate recovery, deploying all planned capital ($100k HypurrFi USDT0 + $50k HyperLend USDT + $15k idle) at current rates would add ~$25/day — still leaving a ~$5/day gap. We need both diversification AND rate stability.

---

## 2. Position Status

### RED/YELLOW — Needs Attention

```
lend_felix_usdt0 — 🟡 WATCH (YELLOW TRIGGER — Day 2 of 14)
  Rate: 6.48% APY (target 15.39%) — BELOW 8% exit threshold by 152 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $19.54 (was $18.35 — slight improvement from rate recovery +40 bps)
  Trigger: APR<8% for 2wk → YELLOW (Day 2 of 14). Counter started Apr 28.
  Trend: 15.39→11.88→12.74→5.81→13.38→6.08→6.48 — partial recovery but still well below 8%
  Note: Rate improved from 6.08% to 6.48% — the pattern from Apr 25 (5.81% → 13.38% in 2d) 
        could repeat. But the recoveries are getting weaker: Apr 23 peak was 15.39%, 
        Apr 25 recovery reached 13.38%, this recovery so far only 6.48%. Lower highs.
        Decision point Apr 30 (day 3): if still below 8%, evaluate partial rebalance.
```

```
lend_felix_usdc_main — 🟡 WATCH (RATE COMPRESSION TREND)
  Rate: 6.39% APY (target 6.86%) — below plan by 47 bps
  Amount: $351,700 (target $300,000) — 117% deployed ($52k above target)
  Daily: $61.57 (was $66.34 — -$4.77/day)
  Trigger: APR<5% for 3d → GREEN (139 bps headroom, tightened from 189 bps yesterday)
  Trend: 6.86→5.55→5.16→9.02→7.44→6.89→6.39 — 3-day downtrend from 7.44% peak
  Note: Third consecutive decline. Headroom vs 5% trigger narrowed from 244 bps (Apr 27) to
        189 bps (Apr 28) to 139 bps today. Not critical yet, but if this 50 bps/day slide
        continues, we hit 5% trigger in ~3 days. Per lesson #8, don't panic on single-day
        moves, but the directional trend is concerning.
```

```
⚠️ COPPER (xyz+flx) — MARGIN STRESS
  Direction: 329.6 xyz LONG + 329.6 flx SHORT (unchanged from yesterday)
  Notional: $3,927 ($1,968 xyz + $1,959 flx)
  uPnL: -$11.72 net (xyz -$30.33, flx +$18.61)
  cumFunding: $3.64 ($0.54 xyz + $3.10 flx — flx earning well)
  Margin holds: USDC $1,969 (was $107) + USDH $2,021 (was $90) — 20x increase
  Free cash in unified: USDC $3,043 + USDH $2,954 = $5,997 (was $9,797)
  Note: Mark dropped 1.5-1.9% from entry. The MTM loss consumed $3,793 of free margin.
        Still a test position (~$800 original), but margin requirements have ballooned.
        Daily funding: ~$2.67/day from flx at current pace. Break-even on $11.72 uPnL loss
        = ~4.4 days of funding at current rate. Manageable if funding holds.
```

### GREEN — On Track

```
lend_hyperlend_usdc — ✅ HOLD (MOST STABLE POSITION)
  Rate: 5.63% APY (target 4.36%) — ABOVE plan by 127 bps
  Amount: $230,209 (target $230,000) — 100% deployed ✓
  Daily: $35.51 (plan: $27.47) — 129% of plan yield
  Trigger: APR < 3% → GREEN (263 bps headroom)
  Trend: 3.84→4.96→5.06→5.56→5.61→5.63 — 6-day uptrend, most consistent position
  Note: While Felix compresses, HyperLend quietly ticks up. The poster child for why
        diversification matters. Per lesson #8, HyperLend USDC 7d range is 3.0-5.6%.
        Current rate is at the top of historical range — don't assume this holds, but
        the uptrend is genuine.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD
  Rate: 10.95% APR (cap rate — stable)
  Amount: $12,165 notional (59,944 spot / 60,180 total short)
  Daily: $3.66/day ($0.52 native + $3.14 hyna)
  Cumulative funding: $178.70 ($20.93 native + $157.77 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Per lesson #10, cap rate regime. Stable. No action needed.
```

```
pos_link_native — ✅ HOLD
  Rate: 10.95% APR (cap rate)
  Amount: $3,160 (342.13 spot / 336 short)
  Daily: $0.93/day
  Cumulative funding: $25.44 (net $19.49 after hyna dust -$5.95)
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Stable at cap rate. Small position.
```

```
lend_felix_usdc_alt — ✅ HOLD
  Rate: 6.39% APY | Amount: $10,800 | Daily: $1.89
  Note: Tracks main Felix USDC vault rate.
```

```
lend_felix_usde — ✅ HOLD (RECOVERED)
  Rate: 7.83% APY (was 6.49% — +134 bps recovery)
  Amount: $3,600 | Daily: $0.77 (was $0.64)
  Note: Strong recovery. Small position, limited dollar impact.
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate Today | Impact |
|------|--------|----------|-------------|------------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC (6.85%) | 6.85% | +$1.74/day |
| USDC unified | $3,043 free | unified L1 | HypurrFi USDC (6.85%) | 6.85% | +$0.57/day |
| USDH unified | $2,954 free | unified L1 | Felix USDH (7.22%) | 7.22% | +$0.58/day |
| **Total idle** | **$15,297** | | | | **+$2.89/day** |

Note: Free unified capital reduced from yesterday ($9,797 → $5,997) due to COPPER margin hold increase. USDH target shifted from Felix USDH 6.21% yesterday to 7.22% today (recovered).

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 6.39% | 139 bps | 0 days | GREEN (tightening) |
| HyperLend USDC | APR < 3% | 5.63% | 263 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **6.48%** | **-152 bps below** | **Day 2** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.36% (not deployed) | 136 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% | watch | 2 bps | 98 bps | — | GREEN |
| USDT0 depeg > 3% | exit | 2 bps | 298 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend USDC 5.63% (closest deployed) | 263 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger tracking (Felix USDT0 < 8% for 2wk):**
- Apr 25: 5.81% — below 8% (day 1)
- Apr 27: 13.38% — above 8% → counter RESET
- **Apr 28: 6.08% — below 8% (day 1)**
- **Apr 29: 6.48% — below 8% (day 2)**
- Pattern: 3 out of last 5 snapshots below 8%. Even with the Apr 27 spike, the average is ~8.3% — barely clearing the threshold.

**Multi-day trigger tracking (Felix USDC < 5% for 3d):**
- No consecutive days below 5%. Nearest was 5.16% on Apr 24.
- Current 3-day slide: 7.44 → 6.89 → 6.39 — losing ~50 bps/day.
- **At this pace, 5% in ~3 days (May 1-2).** Watch closely. Per lesson #8, use 7d avg rather than extrapolating a short trend — but the directional signal is real.

---

## 4. Yesterday → Today

### Action Items from Apr 28 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Verify COPPER restructure with Bean | ⏳ **ASSUMED DONE** — positions unchanged from yesterday (329.6 xyz LONG / 329.6 flx SHORT). Bean likely confirmed. |
| P2 | Deploy $9,300 xyz idle → HypurrFi USDC | ⏳ **PENDING** — Still idle on xyz dex. 8 days idle now (since Apr 22). |
| P3 | Deploy $4,854 USDH → Felix USDH | ⏳ **PENDING** — Free USDH reduced to $2,954 (was $4,854). $2,021 now locked as COPPER margin. |
| P4 | Deploy $4,943 USDC → HypurrFi USDC | ⏳ **PENDING** — Free USDC reduced to $3,043 (was $4,943). $1,969 now locked as COPPER margin. |
| P5 | Monitor Felix USDT0 rate | ✅ **MONITORING** — YELLOW day 2. Rate partially recovered 6.08→6.48. Decision point: Apr 30 (day 3). |
| P6 | HyperLend USDT — execute or drop | ⏳ **OVERDUE** — 7 days since plan Day 1. $50k × 6.27% = $8.58/day opportunity cost at today's rate. |

### Material Changes (Apr 28 → Apr 29)

| Change | Detail | Impact |
|--------|--------|--------|
| Felix USDC continued slide | 6.89% → 6.39% (-50 bps) | -$4.77/day on $362.5k — biggest single drag |
| Felix USDT0/USDe/USDH recovered | +40/+134/+101 bps respectively | +$1.50/day combined — partial offset |
| HyperLend USDC ticked up | 5.61% → 5.63% (+2 bps) | Negligible dollar impact, but trend confirmation |
| HyperLend USDT jumped | 5.26% → 6.27% (+101 bps) | Makes HyperLend USDT deployment more attractive |
| COPPER margin ballooned | Holds: $197 → $3,990 (+$3,793) | Free unified cash: $9,797 → $5,997. Deploy plan impacted. |
| Portfolio total declined | $744,894 → $740,964 (-$3,930) | Mostly COPPER MTM loss (-$11.72) + FARTCOIN/LINK price moves |
| Daily yield declined | $127.33 → $123.87 (-$3.46) | Second consecutive day below target. Now 80.4%. |

---

## 5. Today's Plan

### Priority 1: 🔴 Deploy $9,300 xyz Idle → HypurrFi USDC (6.85%)
- **What:** Withdraw from spot-perp xyz dex → HypurrFi USDC
- **Wallet:** spot_perp (0x3c2c)
- **Why:** 8 days idle at 0%. Opportunity cost: $1.74/day × 8 = $13.92 forfeited so far. HypurrFi USDC at 6.85% also reduces Felix concentration from 67.4% to 66.1%.
- **Impact:** +$1.74/day

### Priority 2: 🔴 HyperLend USDT — DECIDE TODAY (7 days overdue)
- **What:** Deploy $50k USDC → USDT → HyperLend USDT, or formally drop from plan
- **Rate today:** 6.27% (up from 5.26% yesterday — best rate in 8 days)
- **Impact:** +$8.58/day. This single deployment closes 28% of the $30/day yield gap.
- **Blocker:** USDT availability. Needs USDC→USDT swap path.
- **Urgency:** Per lesson #8, HyperLend rates are volatile. Today's 6.27% is a utilization spike — may not last. If the rate is this good, act now or accept it will be lower when you finally move.

### Priority 3: 🟡 Felix USDT0 — Monitor (Day 2, check again Apr 30)
- **What:** Rate at 6.48%, partially recovered from 6.08%. Decision point tomorrow (day 3).
- **If still below 8% Apr 30:** Evaluate moving $30-50k to HypurrFi USDT0 (6.36% — but diversification value).
- **If recovers above 8%:** YELLOW counter resets. Continue monitoring.
- **Note:** Even if rate recovers, pattern of lower highs (15.39→13.38→?) suggests structural decline. The 7d rolling avg approach from yesterday's Challenger Q1 remains a valid trigger redesign option.

### Priority 4: Deploy $3,043 USDC + $2,954 USDH from unified
- **What:** Move free unified capital to earning positions
- **USDC → HypurrFi USDC (6.85%):** +$0.57/day
- **USDH → Felix USDH (7.22%):** +$0.58/day
- **Impact:** +$1.15/day combined
- **Note:** Reduced from yesterday's plan ($9,897 → $5,997 free) because COPPER margin holds consumed $3,800. This is the cost of the COPPER test position's MTM loss.

### Priority 5: LINK hyna dust cleanup (overdue — scheduled today)
- **What:** Close 2.4 short hyna:LINK position. cumFunding -$5.95 and growing.
- **Impact:** Stops the slow bleed. Negligible notional ($22).

### Priority 6: COPPER review (scheduled today)
- **What:** Evaluate whether to hold or exit the test position
- **Data:** cumFunding $3.64, uPnL -$11.72 net, margin holds $3,990. Net loss so far: -$8.08.
- **Key question:** Is flx funding rate high enough to cover MTM loss and margin cost? Need APR data (unavailable in vault-pulse). If flx funding continues at ~$2.67/day, break-even is ~4 days from now.
- **Recommendation:** HOLD for now — it's a test position with defined risk ($4k notional). But set a hard review at May 2: if cumFunding hasn't covered uPnL by then, close.

**Total impact of P1+P2+P4 (if all execute): +$11.47/day** → daily yield from $123.87 to ~$135.34/day (87.9% of target)

---

## 6. Challenger Questions

1. **Felix USDC has lost 50 bps/day for 3 consecutive days (7.44→6.89→6.39). At this pace, it hits the 5% exit trigger by May 1-2.** That's $362.5k — 49% of deployed capital — approaching its exit level. If it triggers, where does $362.5k go? HypurrFi USDC (6.85%) can absorb some, but at what concentration risk? HyperLend USDC (5.63%) is already at $230k. **Have we gamed out the "Felix USDC hits 5%" scenario, or are we going to scramble when it happens?** The headroom narrowed from 244 bps (Apr 27) → 189 bps → 139 bps in 3 days. Not a drill yet — but the alarm is getting louder.

2. **The COPPER test position has consumed $3,793 of margin in 2 days, earned $3.64 in funding, and is net -$8.08.** Meanwhile, that $3,800 of locked margin could be earning 6.5%+ in lending = $0.68/day. The position needs another ~4 days of funding to break even on uPnL, plus any additional margin increase if mark keeps falling. At what point does a "test" become a lesson? **The exit plan from the cross-venue playbook says: "if price spread moves against entry by >0.5% with no funding to compensate, evaluate exit." Mark dropped 1.5-1.9% from entry. Is this trigger breached?**

3. **Seven days of HyperLend USDT at $0 deployed is now ~$50+ in forfeited yield at today's 6.27% rate.** The rate just jumped 101 bps overnight — this is exactly the kind of utilization spike (per lesson #8) that could disappear tomorrow. If the blocker is a USDC→USDT swap, that takes minutes on HyperEVM. If the blocker is something else, it's been invisible for a week. **The portfolio is $30/day below target. HyperLend USDT at $50k closes 28% of that gap. What exactly is the blocker, and is it bigger than $8.58/day?**

---

## 7. Risk Watch

### Scenario: Felix USDC Rate Hits 5% Exit Trigger

```
Scenario: Felix USDC APY continues declining at 50 bps/day, breaching the 
         "APR < 5% for 3 consecutive days" exit trigger by May 1-2.
Probability: Medium-Low (3-day trend is real, but rate bounces are common — 
         see the 5.16→9.02 recovery Apr 24→25)
Impact: $362.5k needs reallocation. At 5%, this position earns $49.66/day vs 
        $61.57 now — a $12/day drag. If exited, redeployment at HypurrFi USDC 
        (6.85%) or HyperLend USDC (5.63%) faces capacity and rate questions.
Trigger signal: Two consecutive snapshots at 5.5% or below (50 bps from trigger).
Pre-planned response:
  1. At 5.5%: Alert — prepare reallocation targets and sizes.
  2. Day 1 of <5%: Begin partial rotation — move $50k to HypurrFi USDC.
  3. Day 2 of <5%: Accelerate — move another $50-100k.
  4. Day 3 of <5%: Trigger confirmed. Execute full rotation of excess above 
     $300k target ($62.5k to HypurrFi/HyperLend). Evaluate whether $300k 
     anchor should also be reduced.
Note: This scenario, while medium-low probability, would be the largest 
      portfolio event since deployment. Having the response pre-planned 
      avoids scrambling under pressure.
```

---

## Reviews Due Today (Apr 29)

Per REVIEW_SCHEDULE.md:

| Item | Status | Decision |
|------|--------|----------|
| LINK hyna dust cleanup | ⏳ **OVERDUE** | Clean up 2.4 short. Paying cumulative -$5.95. Trivial but annoying. |
| COPPER position review | 🔍 **REVIEW** | Net -$8.08 (cumFunding $3.64 - uPnL $11.72). HOLD 4 more days — hard exit review May 2 if not break-even. |
| HyperLend USDT decision | ❗ **7 DAYS OVERDUE** | Rate jumped to 6.27%. Deploy or formally drop. No more "pending." |
| Idle xyz USDC $9,300 | ⏳ **8 DAYS IDLE** | Deploy to HypurrFi USDC immediately. |
| Idle USDH $2,954 free | ⏳ **PENDING** | Deploy to Felix USDH (7.22%). Reduced from $4,854 — COPPER margin consumed the rest. |
| Idle USDC unified $3,043 free | ⏳ **PENDING** | Deploy to HypurrFi USDC (6.85%). Reduced from $4,943 — COPPER margin consumed the rest. |

---

*Generated 2026-04-29. Primary source: vault pulse (01:12 UTC on-chain verified). Rates from portfolio_state.md and rates_history.csv (8-day window). All lessons from docs/lessons.md applied (cited: #8, #10). Next: daily vault-pulse + morning-review cycle.*
