# Morning Review — 2026-04-30

**Data:** Vault pulse 2026-04-29 (01:12 UTC). **[STALE — no Apr 30 vault-pulse yet. All numbers are ~24h old.]** Rates from rates_history.csv (8-day window: Apr 22-29).

---

## 1. Portfolio Health

| Metric | Today (Apr 29 data) | Yesterday (Apr 28) | Target | Status |
|--------|---------------------|---------------------|--------|--------|
| Total Portfolio | $740,964 | $744,894 | $800k | YELLOW (-7.4%) |
| Deployed % | 95.3% ($706,409) | 94.8% ($706,375) | >85% | GREEN |
| Daily Yield | **$123.87/day** | $127.33/day | $154/day | **RED — 80.4% of target** |
| Blended APY | 6.40% | 6.58% | 7.04% | **RED (-64 bps below)** |
| USDT0 Exposure | $110,100 (14.9%) | $110,100 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 67.4% ($476k) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $15,303 (2.1%) | $19,300 (2.6%) | <$20k | GREEN |

**So what:** Third day of yield decline from the $155/day peak on Apr 27 — that milestone is now confirmed as a local high, not a floor. The $30/day yield gap ($154 - $124) is structural: our largest position (Felix USDC at $352k) has been sliding ~50 bps/day for 3 consecutive days and now sits at 6.39%, just 139 bps from its 5% exit trigger. Meanwhile, the deployment plan items that would close the gap — HyperLend USDT ($50k, +$8.58/day) and HypurrFi USDT0 ($100k, +$17/day) — remain at $0 deployed, now **8 days overdue**. The math is simple: we can't hit $154/day without either rate recovery at Felix or executing the diversification deployments. Both would be ideal.

**Felix concentration at 67.4% remains the single biggest structural risk.** Every day we don't deploy to HypurrFi/HyperLend, the concentration gets worse in relative terms as Felix rates compress.

---

## 2. Position Status

### RED/YELLOW — Needs Attention

```
lend_felix_usdt0 — 🟡 WATCH → ACT (YELLOW TRIGGER — Day 3 of 14, DECISION POINT)
  Rate: 6.48% APY (target 15.39%) — BELOW 8% exit threshold by 152 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $19.54
  Trigger: APR<8% for 2wk → YELLOW (Day 3 of 14). Counter started Apr 28.
  Trend (7d): 15.39→11.88→12.74→5.81→13.38→6.08→6.48
  Note: TODAY is the pre-announced day-3 evaluation point. The pattern is clear:
        lower highs on each recovery (15.39→13.38→6.48). Even if it bounces again,
        the structural trend is downward. At 6.48%, it's earning $19.54/day vs
        $42.16/day at the plan rate — a $22.62/day shortfall on this position alone.
        Recommendation: partial rebalance $30-50k to HypurrFi USDT0 (6.36%) IF
        available. The rate differential is small (6.48% vs 6.36%), but the
        diversification value is the real gain — reduces Felix concentration.
```

```
lend_felix_usdc_main — 🟡 WATCH (RATE SLIDE DAY 4?)
  Rate: 6.39% APY (target 6.86%) — below plan by 47 bps
  Amount: $351,700 (target $300,000) — 117% deployed ($52k above target)
  Daily: $61.57 (was $66.34 two days ago)
  Trigger: APR<5% for 3d → GREEN (139 bps headroom — tightened from 244→189→139 in 3 days)
  Trend: 6.86→5.55→5.16→9.02→7.44→6.89→6.39
  Note: Three confirmed consecutive declines at ~50 bps/day. If today's vault-pulse
        shows another 50 bps drop (~5.89%), headroom shrinks to 89 bps — one more
        bad day from trigger zone. Per lesson #8, don't extrapolate a short trend
        as gospel, but the 3-day vector is hard to ignore. Pre-plan the 5% scenario
        (see Risk Watch section from yesterday — still valid).
```

```
COPPER (xyz+flx) — ⚠️ MARGIN STRESS (review May 2)
  Notional: $3,927 ($1,968 xyz long + $1,959 flx short)
  uPnL: -$11.72 net (xyz -$30.33, flx +$18.61)
  cumFunding: $3.64 ($0.54 xyz + $3.10 flx)
  Margin holds: USDC $1,969 + USDH $2,021 = $3,990 (was $197 two days ago)
  Free cash in unified: $5,997 (was $9,797)
  Note: Test position (~$800 original intent). Margin has ballooned 20x. flx side
        earning ~$2.28/day in funding — needs ~3.5 more days to cover uPnL. Hard
        review May 2 is 2 days away. No action until then unless mark drops further.
```

### GREEN — On Track

```
lend_hyperlend_usdc — ✅ HOLD (MOST STABLE, BEST PERFORMER vs PLAN)
  Rate: 5.63% APY (target 4.36%) — ABOVE plan by 127 bps
  Amount: $230,209 (target $230,000) — 100% deployed ✓
  Daily: $35.51 (plan: $27.47) — 129% of plan yield
  Trigger: APR < 3% → GREEN (263 bps headroom)
  Trend: 3.84→4.96→5.06→5.56→5.61→5.63 — 6-day uptrend
  Note: Per lesson #8, HyperLend 7d range is 3.0-5.6%. Currently at the top of
        its historical range. Don't project this forever, but the uptrend is genuine.
        Best diversification story in the portfolio.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD
  Rate: 10.95% APR (cap rate — per lesson #10, regime artifact)
  Amount: $12,165 notional (59,944 spot / 60,180 total short)
  Daily: $3.66/day ($0.52 native + $3.14 hyna)
  Cumulative funding: $178.70
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
```

```
pos_link_native — ✅ HOLD
  Rate: 10.95% APR (cap rate)
  Amount: $3,160 (342.13 spot / 336 short)
  Daily: $0.93/day | Cumulative: $25.44 (net $19.49 after hyna dust)
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
```

```
lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 6.39% | $1.89/day
lend_felix_usde — ✅ HOLD | $3,600 @ 7.83% (+134 bps recovery) | $0.77/day
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate | Impact |
|------|--------|----------|-------------|------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC (6.85%) | 6.85% | +$1.74/day |
| USDC unified free | $3,043 | unified L1 | HypurrFi USDC (6.85%) | 6.85% | +$0.57/day |
| USDH unified free | $2,954 | unified L1 | Felix USDH (7.22%) | 7.22% | +$0.58/day |
| **Total idle** | **$15,297** | | | | **+$2.89/day** |

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 6.39% | 139 bps | 0 days below 5% | GREEN (tightening fast) |
| HyperLend USDC | APR < 3% | 5.63% | 263 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **6.48%** | **-152 bps below** | **Day 3** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.36% (not deployed) | 136 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% | watch | 2 bps | 98 bps | — | GREEN |
| USDT0 depeg > 3% | exit | 2 bps | 298 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend USDC 5.63% (closest) | 263 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger: Felix USDT0 < 8% for 2wk**
- Apr 25: 5.81% (day 1) → Apr 27: 13.38% → RESET
- **Apr 28: 6.08% (day 1 restart)**
- **Apr 29: 6.48% (day 2)**
- **Apr 30: [STALE — no fresh data] (day 3 by calendar)**
- Pattern: 3 out of last 5 snapshots below 8%. Lower recovery highs: 15.39→13.38→6.48. Average over last 5 snapshots: ~8.3% — barely clearing threshold. Structural decline.

**Multi-day trigger: Felix USDC < 5% for 3d**
- No days below 5% yet. But 3-day slide: 7.44 → 6.89 → 6.39 at ~50 bps/day.
- **At this pace, first breach ~May 2-3.** If slide accelerates (not uncommon after sustained compression), could be sooner.

---

## 4. Yesterday → Today

### Action Items from Apr 29 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Deploy $9,300 xyz idle → HypurrFi USDC | ⏳ **PENDING — 9 DAYS IDLE.** $14.36 in foregone yield since Apr 22. |
| P2 | HyperLend USDT — DECIDE ($50k) | ⏳ **OVERDUE — 8 DAYS.** Rate was 6.27% yesterday. $68.60 in cumulative foregone yield. |
| P3 | Felix USDT0 day-3 decision point | 🔍 **TODAY** — data stale, but day 3 has arrived. See recommendation in Section 5. |
| P4 | Deploy $3,043 USDC unified → HypurrFi | ⏳ **PENDING** |
| P5 | Deploy $2,954 USDH unified → Felix USDH | ⏳ **PENDING** |
| P6 | LINK hyna dust cleanup | ⏳ **OVERDUE — scheduled Apr 29, not executed.** cumFunding -$5.95 and slowly growing. |
| P6b | COPPER review (May 2) | ⏳ **2 days out** — on track |

### Material Changes (Apr 28 → Apr 29, most recent data)

| Change | Detail | Impact |
|--------|--------|--------|
| Felix USDC slide continued | 6.89% → 6.39% (-50 bps, 3rd consecutive day) | -$4.77/day — biggest single drag |
| Felix USDT0 partial recovery | 6.08% → 6.48% (+40 bps) | +$1.19/day — but still well below 8% threshold |
| Felix USDe/USDH recovered | +134/+101 bps respectively | +$0.31/day combined — small positions, small dollar impact |
| HyperLend USDC ticked up | 5.61% → 5.63% (+2 bps) | Negligible $ but confirms uptrend |
| HyperLend USDT jumped | 5.26% → 6.27% (+101 bps) | Makes $50k deployment more attractive — per lesson #8, may be a spike |
| Portfolio total declined | $744,894 → $740,964 (-$3,930) | COPPER MTM + spot-perp price moves |
| Daily yield declined | $127.33 → $123.87 (-$3.46/day) | **Third consecutive decline. Now 80.4% of target.** |

---

## 5. Today's Plan

### Priority 1: 🔴 Felix USDT0 Day-3 Evaluation (DECISION REQUIRED)

**Context:** Rate below 8% for 3 consecutive snapshots (6.08→6.48→[today unknown]). Lower recovery highs. This was the pre-committed decision point.

**Recommendation: HOLD for now, but set a hard partial-rebalance trigger.**

Reasoning:
- HypurrFi USDT0 rate (6.36%) is actually **lower** than Felix USDT0 (6.48%). Moving capital for diversification at a lower rate only makes sense if we believe Felix has elevated smart-contract/concentration risk that justifies a 12 bps yield sacrifice.
- Felix concentration (67.4%) IS a real concern, but moving $30k of USDT0 to HypurrFi only reduces Felix to 63.2% — still well above 50% cap. The concentration problem is structural and requires deploying new capital to non-Felix venues, not shuffling existing USDT0.
- **Action:** If Felix USDT0 drops below 5% for 2 consecutive days, initiate partial move of $30-50k to HypurrFi USDT0. Until then, hold — the 12 bps rate differential doesn't justify the execution cost.
- **Re-evaluate:** Day 7 (May 4). If still below 8% with no recovery above 10%, begin partial rotation regardless of HypurrFi rate.

### Priority 2: 🔴 Deploy $9,300 xyz Idle → HypurrFi USDC (9 DAYS OVERDUE)

- **What:** Withdraw from spot-perp xyz dex → HypurrFi USDC
- **Wallet:** spot_perp (0x3c2c)
- **Impact:** +$1.74/day. Also reduces Felix concentration by 1.3pts (67.4→66.1%).
- **Cumulative opportunity cost:** $14.36 foregone since Apr 22. Execute today.

### Priority 3: 🔴 HyperLend USDT — FINAL DECISION (8 DAYS OVERDUE)

- **What:** Deploy $50k USDC → USDT → HyperLend USDT
- **Rate (Apr 29):** 6.27% — jumped +101 bps. Per lesson #8, this is likely a utilization spike. 7d avg is probably ~5.3-5.5%.
- **Impact at conservative 5% avg:** +$6.85/day. Closes 23% of the $30/day yield gap.
- **Impact at current 6.27%:** +$8.58/day. Closes 28% of the gap.
- **Cumulative opportunity cost:** ~$50+ foregone over 8 days at average rate.
- **Concentration benefit:** Reduces Felix from 67.4% to 61.5%. HyperLend goes from 32.6% to 39.7%.
- **Blocker:** Needs USDC→USDT swap on HyperEVM. This is a routine swap that takes minutes.
- **Recommendation:** Execute or formally drop. No more "pending." If Bean doesn't want this position, remove it from the tracker.

### Priority 4: Deploy Unified Idle ($5,997)

- **USDC $3,043 → HypurrFi USDC (6.85%):** +$0.57/day
- **USDH $2,954 → Felix USDH (7.22%):** +$0.58/day
- **Impact:** +$1.15/day combined
- Note: Reduced from original $9,897 plan — COPPER margin holds consumed $3,800.

### Priority 5: LINK hyna Dust Cleanup (OVERDUE since Apr 29)

- Close 2.4 short hyna:LINK. cumFunding -$5.95.
- Trivial size ($22) but a slow bleed and dashboard noise.

### Priority 6: Run Vault-Pulse (TODAY's data is missing)

- This review is based on 24h-stale data. Run vault-pulse to get fresh Apr 30 snapshot.
- Critical for Felix USDT0 day-3 decision — need today's actual rate.

**Total impact if P2+P3+P4 execute: +$10.31-$12.04/day** → yield from $123.87 to ~$134-$136/day (87-88% of target)

---

## 6. Challenger Questions

1. **Felix USDC has now lost ~150 bps in 3 days (7.44→6.39) and we have $352k in it — 49% of ALL deployed capital.** Yesterday we said "pre-plan the 5% scenario." The pre-plan was written (see Apr 29 Risk Watch: staged rotation starting at 5.5%). But have we actually identified where $362.5k goes? HypurrFi USDC at 6.85% — what's the deposit cap? HyperLend USDC at 5.63% — at $230k already, going to $592k would be 80% of portfolio on one protocol. **The escape route is theoretical until we verify capacity at the destination. Check HypurrFi USDC headroom today.**

2. **The HyperLend USDT deployment has been "pending" for 8 days. At today's 6.27% rate, that's $50k × 6.27% ÷ 365 × 8 = $68.60 in foregone yield.** Bean committed to this in the deployment plan on Apr 22. The blocker has never been named — it's a USDC→USDT swap that takes minutes. Meanwhile, the portfolio runs $30/day below target and this single deployment closes 23-28% of the gap. **Is there an actual blocker, or has this fallen through the cracks? At what point does inaction become a conscious decision to forgo $8.58/day?**

3. **The COPPER test position has consumed $3,990 in margin, earned $3.64 in funding, and has a net loss of -$8.08 on $800 original test sizing.** The position's margin-to-notional ratio is now 100% ($3,990 margin on $3,927 notional). Per the cross-venue playbook exit rule: "price spread moves against entry by >0.5% → evaluate exit." Mark dropped 1.5-1.9% from entry — **the trigger has been breached by 3-4x.** The only reason to hold is if flx funding ($2.28/day) covers the MTM gap in ~3.5 days. But what if mark drops another 1%? Margin hold increases further, locking more idle capital. **Should we wait for the May 2 hard review, or is the breached exit trigger sufficient reason to close now and free $5,997 for lending at 6-7%?**

---

## 7. Risk Watch

### Scenario: Accumulated Deployment Inaction

```
Scenario: HyperLend USDT ($50k), HypurrFi USDT0 ($100k), and idle capital ($15k)
         remain undeployed for another 2 weeks while Felix rates continue compressing.
Probability: Medium (pattern of delayed execution — 8 days and counting on HyperLend USDT)
Impact: $165k at 0% + Felix rate compression = daily yield drops to $110-115/day
        (71-75% of target). Cumulative opportunity cost over 2 more weeks:
        $50k × ~5.5% ÷ 365 × 14 = $105 (HyperLend USDT)
        $15k × ~6.8% ÷ 365 × 14 = $39 (idle capital)
        Total: ~$144 in foregone yield, plus the compounding effect of missing the
        HyperLend USDT utilization spike window.
Trigger signal: Another morning review passes with P2 (xyz idle) and P3 (HyperLend USDT) 
                still marked PENDING.
Pre-planned response:
  1. Today: Execute xyz $9,300 → HypurrFi USDC (zero blockers, pure execution)
  2. Today: Execute USDC→USDT swap for $50k (5 min on HyperEVM)
  3. Today: Deploy $50k USDT → HyperLend USDT
  4. This week: Deploy unified idle ($5,997) to HypurrFi USDC + Felix USDH
  5. If all execute: Felix concentration drops from 67.4% to ~61.5%,
     daily yield rises to ~$134-136/day (87-88% of target)
```

**Why this scenario:** This isn't an external risk event — it's an execution risk. The portfolio's biggest problem right now isn't market conditions (rates are reasonable), it's unexecuted deployment plan items that have been pending for over a week. The market is doing its job; the gap is on our side.

---

## Reviews Due Today (Apr 30)

| Item | Status | Decision |
|------|--------|----------|
| Felix USDT0 day-3 check | 🔍 **TODAY** | HOLD — rate differential too small for HypurrFi move. Re-evaluate day 7 (May 4). Hard partial-rebalance at 5%. |
| LINK hyna dust cleanup | ⏳ **OVERDUE (Apr 29)** | Close 2.4 short. Trivial. |
| HyperLend USDT decision | ❗ **8 DAYS OVERDUE** | Execute or drop. No more "pending." |
| Deploy xyz idle $9,300 | ⏳ **9 DAYS IDLE** | → HypurrFi USDC. Zero blockers. |
| Deploy unified idle $5,997 | ⏳ **PENDING** | → HypurrFi USDC ($3,043) + Felix USDH ($2,954). |
| Run vault-pulse | 📊 **NEEDED** | Today's data is missing. Critical for Felix USDT0 rate check. |

---

*Generated 2026-04-30. Primary source: vault pulse 2026-04-29 (01:12 UTC — 24h stale). Rates from rates_history.csv (8-day window). All lessons from docs/lessons.md applied (cited: #8, #10, cross-venue playbook exit rule). Next: run vault-pulse for fresh data, then execute pending deployments.*
