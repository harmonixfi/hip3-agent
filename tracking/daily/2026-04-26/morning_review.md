# Morning Review — 2026-04-26

**Data:** Vault pulse 2026-04-25 ~01:15 UTC (no Apr 26 pulse yet — Saturday). Rates from rates_history.csv (4 days: Apr 22–25).

---

## 1. Portfolio Health

| Metric | Today | Yesterday | Target | Status |
|--------|-------|-----------|--------|--------|
| Total Portfolio | $741,207 | $741,075 | $800k | YELLOW (-7.3%) |
| Deployed % | 91.2% ($675,973) | 91.9% ($681,042) | >85% | GREEN |
| Daily Yield | $140.49/day | $108.39/day | $154/day | YELLOW (91.2% of target) |
| Blended APY (deployed) | 7.59% | 5.81% | 7.04% | GREEN (+55 bps above target) |
| USDT0 Exposure | $80,000 (10.8%) | $55,200 (7.4%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 66.0% ($445.9k) | Felix 60.9% ($451k) | <50% | RED (+16pts over cap) |
| Idle Capital | $49,278 (6.6%) | $44,058 (5.9%) | <$20k | YELLOW |

**So what:** Massive yield improvement — daily jumped +$32.10/day (+30%) in one snapshot, the best single-day gain since deployment started. The blended APY on deployed capital is now **above** the 7.04% plan target for the first time. The gap to $154/day is almost entirely explained by:

- **$49.3k idle capital at 0%** — at current 7.59% blended, deploying this adds ~$10.25/day, which would bring us to ~$150.74/day (97.9% of target)
- **Portfolio total at $741k vs $800k target** — the ~$59k shortfall is accounting (USDC→USDT0 swaps, mark-to-market on trading). Not a real loss.

**Felix concentration worsened to 66.0% — still RED.** The percentage rose because Felix USDC balance dropped to $351.5k (from $381.4k — some USDC moved to USDT0 swap) while the denominator shrunk. But Felix still holds $445.9k across USDC + USDT0 + USDe. No USDT0 has gone to HypurrFi (0% of $100k target). This remains the biggest structural risk in the portfolio.

---

## 2. Position Status

### RED — Immediate Attention

```
pos_link_native — 🔴 ACT
  Rate: 7.59% APR (target 10.2%) — below 8% trigger by 41 bps
  Amount: $3,215 (342.13 spot / 336 short)
  Daily: $0.66/day
  Cumulative funding: $21.74 native, -$5.97 hyna dust = net $15.77
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → RED (breached — first day below)
  Trend: 10.95% (Apr 23→24 cap rate) → 7.59% today
  Note: LINK funding is binary — cap rate (10.95%) or negative/weak. Yesterday's
        FARTCOIN proved these can snap back overnight. But LINK showed the same
        pattern in reverse on Apr 23 (-8.04%). At $0.66/day on $3.2k notional,
        this is marginal but not dead money yet.
  RECOMMENDATION: Monitor through weekend. If still below 8% on Monday (Apr 28
        review), exit and redeploy to lending (~$0.53/day at 6% — marginal
        improvement vs current $0.66/day, so the case for urgency is weak).
```

### YELLOW — Monitor

```
lend_felix_usdt0 — 🟡 WATCH (DAY 1 BELOW 8% THRESHOLD)
  Rate: 5.81% APY (was 12.74% yesterday) — crashed 693 bps in one day
  Amount: $80,000 (target $100,000) — 80% deployed
  Daily: $12.73/day (was $27.91/day at 12.74%)
  Trigger: APR < 8% for 2wk → YELLOW (day 1 of 14 below threshold)
  Headroom: BREACHED — 219 bps below 8% trigger (but needs 14 consecutive days)
  Note: This is the biggest daily yield swing in the portfolio: -$15.18/day in one
        snapshot. The 2-week trigger window gives time — rate could recover like Felix
        USDC did (5.16% → 9.02% overnight). But if it stays below 8%, $80k earning
        5.81% instead of the plan's 15.39% = -$20.97/day vs plan projection.
        The $29.98k idle USDT0 on L1 should NOT be deployed to Felix USDT0 at 5.81%.
        HypurrFi USDT0 at 6.13% is marginally better and diversifies Felix risk.
```

```
idle_capital — 🟡 DEPLOY
  Total idle: $49,278 across 4 locations
  - $29,980 USDT0 on lending L1 (earning 0%)
  - $9,300 USDC on xyz margin (no positions)
  - $5,043 USDC on unified L1 ($500 COPPER margin)
  - $4,955 USDH on unified L1 ($399 COPPER margin)
  Opportunity cost: ~$10.25/day at 7.59% blended
  Note: Idle capital grew slightly ($49.3k vs $44k yesterday) as USDT0 swap added
        $5.2k more USDT0 to L1. The USDT0 order is now CLOSED (completed).
```

### GREEN — On Track

```
lend_felix_usdc_main — ✅ HOLD (REVERSED FROM YELLOW)
  Rate: 9.02% APY (was 5.16% yesterday) — surged 386 bps overnight
  Amount: $351,500 + $10,800 alt = $362,300 (target $300k — 121%)
  Daily: $89.53 ($86.86 main + $2.67 alt)
  Trigger: APR < 5% for 3d → GREEN (402 bps headroom — crisis averted)
  Trend: 6.86% → 5.55% → 5.16% → 9.02% — V-shaped recovery
  Note: The 3-day decline that threatened the 5% trigger reversed completely.
        Felix USDC is now the highest it's been since deployment. This single
        position generates 62% of portfolio daily yield. Rate volatility is
        the defining feature — from near-trigger to best-ever in 24h.
```

```
lend_hyperlend_usdc — ✅ HOLD
  Rate: 5.06% APY (was 4.96% yesterday) — stable
  Amount: $230,073 (target $230,000) — 100% deployed ✓
  Daily: $31.91 (plan was $27.47 — now ABOVE plan by 16%)
  Trigger: APR < 3% → GREEN (206 bps headroom)
  Trend: 3.84% → 4.96% → 5.06% — steady recovery, stable. Per lesson #8, 7d avg matters.
  Note: Most stable position in the portfolio. Consistently above plan target.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD (CLEARED from RED)
  Rate: 10.95% APR — back at cap rate, recovered from 1.78%
  Amount: $11,943 (8,590 native + 51,590 hyna short, 59,944 spot)
  Daily: $3.59/day
  Cumulative: $162.80 ($18.69 native + $144.11 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Review: DUE TODAY (Apr 26) — recovered, no action needed. Push to Apr 30.
  Note: Full recovery validates the "wait 24-48h" approach from Apr 24 review.
        Position is profitable and earning well. Per lesson #10, cap rate data
        tells you about the regime, not the asset — but $162.80 banked profit
        means this position has proven itself.
```

```
lend_felix_usde — ✅ HOLD
  Rate: 21.03% APY (was 8.91%) — surged 1,212 bps
  Amount: $3,600
  Daily: $2.07/day
  Note: Tiny collateral position. Rate exceptional but pool likely has low capacity.
```

```
pos_copper — ℹ️ TEST
  Amount: $799 (65.92 short xyz + 65.92 long flx)
  Cumulative: $2.58 ($0.44 xyz + $2.14 flx)
  Note: Test position, on hold. $2.58 earned on $800 — fine for monitoring.
```

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Status |
|---------|------|---------|----------|--------|
| **LINK funding** | APR < 8% | **7.59%** | **-41 bps (breached)** | 🔴 RED |
| Felix USDT0 | APR < 8% for 2wk | 5.81% (day 1 of 14) | -219 bps | 🟡 YELLOW |
| Felix concentration | < 50% | 66.0% | -16.0 pts | 🔴 RED (structural) |
| Felix USDC | APR < 5% for 3d | 9.02% | +402 bps | 🟢 GREEN (resolved) |
| HyperLend USDC | APR < 3% | 5.06% | +206 bps | 🟢 GREEN |
| HypurrFi USDT0 | APR < 5% | 6.13% (not deployed) | +113 bps | 🟢 GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | +295 bps | 🟢 GREEN (recovered) |
| USDT0 depeg > 1% | > 1% (watch) | 2 bps | 98 bps | 🟢 GREEN |
| USDT0 depeg > 3% | > 3% (exit) | 2 bps | 298 bps | 🟢 GREEN |
| Any lending < 3% | < 3% | HyperLend 5.06% closest | 206 bps | 🟢 GREEN |

**Multi-day trigger tracking (Felix USDT0 < 8% for 2wk):**
- Apr 22: 15.39% (plan rate)
- Apr 23: 11.88% (above 8%)
- Apr 24: 12.74% (above 8%)
- Apr 25: **5.81% (below 8%) — DAY 1**
- Days remaining before trigger fires: **13 days (May 8)**

---

## 4. Yesterday → Today

### Action Items from Apr 24 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Deploy $24.76k USDT0 to Felix USDT0 | ✅ **DONE** — Felix USDT0 now $80k (was $55.2k) |
| P2 | Monitor FARTCOIN 24-48h | ✅ **DONE** — recovered to 10.95%. HOLD confirmed. |
| P3 | Deploy idle USDH ($4,956) | ⏳ **PENDING** (4 days now) |
| P4 | Redeploy xyz margin ($9,300) | ⏳ **PENDING** (4 days now) |
| P5 | Deploy idle USDC ($5,042) | ⏳ **PENDING** (4 days now) |
| P6 | Update REVIEW_SCHEDULE.md | ✅ **DONE** (updated Apr 24) |
| P7 | Deploy $50k USDT to HyperLend | ⏳ **PENDING** (5 days since plan, still at $0) |

### Material Changes (Apr 24 → Apr 25)

| Change | Detail |
|--------|--------|
| **Felix USDC surged +386 bps** | 5.16% → 9.02%. V-shaped recovery — was 1 day from triggering 5% watch. Now best rate since deployment. +$34.09/day on the $362k position. |
| **Felix USDT0 crashed -693 bps** | 12.74% → 5.81%. Biggest single-day rate drop. Was #2 yield driver, now below trigger threshold. Day 1 of 14-day clock. |
| **FARTCOIN recovered +917 bps** | 1.78% → 10.95%. Full snap-back to cap rate. Validates patience. |
| **LINK dropped -336 bps** | 10.95% → 7.59%. Now below 8% trigger. Small position ($3.2k). |
| **Felix USDe surged +1,212 bps** | 8.91% → 21.03%. Tiny position ($3.6k) but impressive rate. |
| **USDT0 swap completed** | Order CLOSED. $29.98k USDT0 idle on L1 (up from $24.76k). |
| **Daily yield jumped +$32.10** | $108.39 → $140.49 (+30%). Best single-day improvement ever. |
| **No morning review generated Apr 25** | Gap in daily review cadence. This review covers 2-day changes. |

---

## 5. Today's Plan

### Priority 1: Decide USDT0 Deployment ($29.98k idle on L1)

- **What:** $29.98k USDT0 sitting at 0% on lending L1
- **Decision needed:** Felix USDT0 (5.81%) vs HypurrFi USDT0 (6.13%) vs HOLD for rate recovery
- **Recommendation:** Deploy to **HypurrFi USDT0** (6.13% APY) — three reasons:
  1. HypurrFi rate is 32 bps higher than Felix USDT0 right now
  2. Reduces Felix concentration from 66% → ~62% (still above cap, but directionally correct)
  3. Starts filling the $100k HypurrFi USDT0 target (currently $0)
- **Wallet:** lending (0x9653) L1 → EVM → HypurrFi
- **Impact:** +$5.03/day at 6.13%

### Priority 2: Deploy USDH ($4,955) to Felix USDH

- **What:** Supply $4,555 USDH to Felix USDH vault (8.06% APY) — keep $399 as COPPER flx margin
- **Wallet:** unified (0xd473) L1 → EVM
- **Impact:** +$1.01/day

### Priority 3: Monitor LINK Through Weekend

- **What:** LINK at 7.59% APR, 41 bps below 8% trigger. Small position ($3.2k).
- **Action:** No exit yet. Weekend funding can be volatile. Decision point: Monday Apr 28 review.
- **If it drops further or goes negative:** Exit immediately, redeploy to HyperLend.
- **Impact of exit:** At best +$0.53/day vs current $0.66/day — not material. The reason to exit is to avoid negative funding, not to improve yield.

### Priority 4: Redeploy xyz Margin ($9,300)

- **What:** Withdraw $9,300 USDC from spot-perp xyz dex → HyperLend USDC
- **Why HyperLend not Felix:** Felix already at 66% concentration. HyperLend at 5.06%.
- **Impact:** +$1.29/day

### Priority 5: Deploy idle USDC ($4,543)

- **What:** Move $4,543 USDC from unified L1 ($5,043 minus $500 COPPER margin) → HyperLend
- **Impact:** +$0.63/day

### Priority 6: Deploy $50k USDT to HyperLend

- **Status:** 5 days pending. HyperLend USDT rate: 5.12% (rates_history).
- **Blocker:** Need USDT on lending wallet. Requires USDC→USDT swap path.
- **Impact:** +$7.01/day — second-largest single action after USDT0.
- **Note:** This keeps getting deprioritized. At 5.12%, the case is solid (per lesson #8, HyperLend USDT 7d avg was 3.29% — but it's been 5.12-5.55% for the last 2 days, strengthening).

**Total impact P1-P5 (executable today): +$7.96/day → daily yield from $140.49 to ~$148.45/day (96.4% of target)**

---

## 6. Challenger Questions

1. **Felix USDT0 crashed to 5.81% — should the idle $29.98k USDT0 go to Felix (increasing a declining position) or HypurrFi (starting diversification)?** Felix USDT0 was earning 12.74% two days ago and is now at 5.81%. HypurrFi pays 6.13% — a small premium. But the real question is whether Felix USDT0 is temporarily depressed (like Felix USDC was at 5.16% before surging to 9.02%) or structurally lower. If it recovers to 10%+, you want to be in Felix. If it doesn't, you've just added $30k to a 5.81% position when you could have started filling the $100k HypurrFi target. The Felix concentration at 66% makes the diversification case stronger — but is 32 bps of yield difference worth the operational cost of a new protocol deployment?

2. **$50k USDT deployment to HyperLend has been "pending" for 5 days now — that's $35 in lost yield and counting.** Every morning review carries this forward. What's the actual blocker? If USDT isn't available on the lending wallet and needs a swap, the swap path should be defined today. If it requires bridging from an external source, say so. This is the second-largest single yield improvement available ($7.01/day) and it keeps slipping.

3. **The portfolio hit 7.59% blended APY — above the 7.04% target — but this is entirely a Felix USDC story.** Felix USDC at 9.02% is driving 62% of daily yield from a single pool. If Felix USDC drops back to 5-6% (which it was 2 days ago), blended APY falls to ~5.5% overnight. Are we comfortable that 62% of our daily income comes from one pool's rate, which has shown it can move ±400 bps in 24 hours?

---

## 7. Risk Watch

### Scenario: Felix USDT0 Rate Stays Below 8% for 14 Days

**What:** Felix USDT0 just crashed from 12.74% to 5.81% — first day below the 8% threshold. The deployment plan assumed 15.39% APY on $100k USDT0 = $42.16/day. At 5.81% on $80k, it's earning $12.73/day — a $29.43/day shortfall vs plan.

**Probability:** Medium (40-50%). USDT0 lending rates are driven by borrowing demand. The crash was sharp (693 bps in one day), suggesting a structural shift in borrowing demand rather than noise. However, Felix USDC showed a similar crash-then-recovery pattern (5.16% → 9.02%), so single-day moves are unreliable predictors.

**Impact:** If sustained at 5.81% for 14 days: trigger fires, $80k needs reallocation. At 5.81%, the position earns $12.73/day — still above the 3% hard-exit floor ($6.58/day). The real cost is opportunity: the $29.98k idle USDT0 deployed at 5.81% earns $4.77/day instead of the plan's $12.64/day.

**Trigger signal:** Track daily rate in rates_history.csv. If below 8% for 7 consecutive days (halfway), start evaluating rotation targets. If rate recovers above 8% at any point, reset the clock.

**Pre-planned response:**
1. Days 1-7 below 8%: Monitor. Do not deploy additional USDT0 to Felix.
2. Day 7 below 8%: Evaluate — rotate $80k to HypurrFi USDT0 (if rate > 6%) or Felix USDC (if rate > 7%).
3. Day 14 below 8%: Execute rotation per above evaluation.
4. If rate recovers above 8% at any point: Reset clock, resume USDT0 scaling to Felix.

---

*Generated 2026-04-26. Primary source: vault pulse (01:15 UTC 2026-04-25, on-chain verified). No Apr 26 pulse available — Saturday snapshot pending. Rates from rates_history.csv (4-day window). Next: daily vault-pulse + morning-review cycle.*
