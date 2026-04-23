# Morning Review — 2026-04-23

**Data:** Vault pulse on-chain ~04:10 UTC | Live rates refreshed ~04:24 UTC via HL API, HyperLend API, Morpho API

---

## 1. Portfolio Health

| Metric | Today | Target | Status |
|--------|-------|--------|--------|
| Total Portfolio | $757,847 | $800k | YELLOW (-5.3%) |
| Deployed % | 86.2% ($653,020) | >85% | GREEN |
| Daily Yield | $93.60/day | $154/day | RED (60.8% of target) |
| Blended APY | 5.23% | 7.04% | RED (-181 bps) |
| USDT0 Exposure | $25,200 (3.3%) | <$200k (25%) | GREEN (under cap, but underfunded) |
| Largest Protocol | Felix 55.8% ($423k) | <50% | YELLOW (+5.8pts over cap) |
| Idle Capital | $74,126 (9.8%) | <$20k | RED |

**So what:** Deployed percentage hit 86% — ahead of schedule for Day 2. But daily yield is only 61% of target because USDT0 positions are underfunded ($25k of $200k deployed) and LINK is bleeding. The $60/day shortfall breaks down: ~$44/day from missing USDT0 deployment, ~$11/day from rates below plan, ~$10/day from idle capital, ~$2/day from LINK paying funding. The USDT0 bottleneck is the single biggest drag.

Felix concentration at 55.8% is above the 50% cap — $81k of the overage is USDC parked in Felix while waiting for USDT0. Once USDT0 deploys to HypurrFi ($100k), Felix drops to ~43%. Temporary but worth tracking.

---

## 2. Position Status

### RED — Immediate Attention

```
pos_link_native — 🔴 EXIT
  Rate: -4.45% APR (live) / -8.04% (vault pulse 04:10 UTC) — improving but still NEGATIVE
  Amount: $3,084 (342 spot / 336 short)
  Daily: -$0.38/day (live rate)
  Lifetime funding earned: $20.67 (native) - $5.98 (hyna dust) = net $14.69
  Trigger: APR < 8% → RED (breached — funding negative)
  Note: Funding improved from -8.04% → -4.45% in 14 min, but still paying.
        At -4.45%, break-even erosion of $14.69 lifetime profit in ~39 days.
        Exit now to lock in $14.69 profit. Clean up hyna:LINK dust (2.4 short) simultaneously.
```

### YELLOW — Monitor

```
lend_hyperlend_usdc — 🟡 HOLD (monitor closely)
  Rate: 3.74% APR live (3.81% APY) | 7d avg: 4.16% | 7d range: 3.02-4.64%
  Amount: $230,020 (target $230,000) — 100% deployed ✓
  Daily: $24.20 (vs $27.47 plan)
  Trigger: APR < 3% → YELLOW — live rate 74 bps from trigger, 7d min touched 3.02%
  Note: Rate softening trend — dropped from ~4.6% highs to 3.74% live.
        7d avg (4.16%) still healthy. Per lesson #8, use 7d avg for decisions.
        Not actionable yet, but if 7d avg drops below 3.5%, start contingency planning.
```

```
lend_felix_usdc_main — 🟡 HOLD
  Rate: 5.56% APY (live) vs 6.86% target — 130 bps below plan
  Amount: $381,400 + $12,400 (alt) = $393,800 (target $300k — 131%, includes $81k parked)
  Daily: $59.86 (vs $56.38 plan — overdeployed compensates lower rate)
  Trigger: APR < 5% for 3d → GREEN (1 day data only, currently above 5%)
  Note: Rate 19% below plan target, but absolute yield on $393k exceeds $300k target yield.
        $81k excess is parked while waiting for USDT0 — will redeploy when USDT0 acquired.
```

```
lend_felix_usdt0 — 🟡 SCALING
  Rate: 11.88% APY (live) vs 15.39% target — 351 bps below plan
  Amount: $25,200 (target $100,000) — 25% deployed
  Daily: $8.20 (vs $42.16 at full deployment)
  Trigger: APR < 8% for 2wk → GREEN (388 bps headroom)
  Note: USDT0 acquisition is the bottleneck. $74.8k more needed to hit target.
        At 11.88%, this is the highest-yielding deployed position. Every $10k deployed = $3.26/day.
```

### GREEN — On Track

```
pos_fartcoin — ✅ HOLD
  Rate: 10.95% APR (live, cap rate) — at target
  Amount: $11,736 (59,944 spot ≈ 60,180 short → delta neutral ✓)
  Daily: ~$3.52 (cumulative funding: $151.07 — strong performer)
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Best spot-perp position. Consistently at cap rate. Multi-dex structure working
        (native 8,590 short + hyna 51,590 short). No action needed.
```

```
lend_felix_usde — ✅ HOLD
  Rate: 12.41% APY (live)
  Amount: $4,000
  Daily: $1.34
  Note: Small collateral position. Healthy rate.
```

```
pos_copper — ℹ️ TEST
  Amount: $799 (65.92 short xyz + 65.92 long flx)
  Cumulative funding: $1.40
  Note: Tiny test position, on hold pending macro research. No action.
```

### IDLE — Needs Deployment

| Item | Amount | Location | Action |
|------|--------|----------|--------|
| USDT0 swap order | ~$28.7k remaining | wallet 0x9653...2fEa L1 | **42.5% filled** (~$21.2k acquired). Active, filling. |
| Idle USDT0 | $4,976 | lending L1 | Deploy to Felix USDT0 |
| Idle USDC | $9,300 | spot-perp xyz dex | Redeploy to lending |
| Idle USDC | $5,043 | unified L1 | Deploy to lending |
| Idle USDH | $4,956 | unified L1 | Deploy to Felix USDH (8.69%) |

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Status |
|---------|------|---------|----------|--------|
| LINK funding | APR < 8% | **-4.45% APR** | BREACHED (-12.45pts) | 🔴 RED — exit |
| HyperLend USDC | APR < 3% | 3.74% live / 4.16% 7d avg | 74 bps live, 116 bps 7d | 🟡 YELLOW |
| Felix USDC | APR < 5% for 3d | 5.56% | 56 bps above trigger | 🟢 GREEN (only 1 day data) |
| Felix USDT0 | APR < 8% for 2wk | 11.88% | 388 bps | 🟢 GREEN |
| HypurrFi USDT0 | APR < 5% | 6.33% (not deployed) | 133 bps | 🟢 GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | 🟢 GREEN |
| USDT0 depeg > 1% | > 1% | 2 bps spread | 98 bps | 🟢 GREEN |
| USDT0 depeg > 3% | > 3% | 2 bps spread | 298 bps | 🟢 GREEN |
| Any lending < 3% | < 3% | HL USDC 3.74% closest | 74 bps | 🟡 YELLOW |

**Multi-day trigger note:** Only 2 days of rates_history data (Apr 22 plan targets + Apr 23 actuals). Cannot evaluate multi-day triggers (Felix USDC "< 5% for 3d", Felix USDT0 "< 8% for 2wk") with confidence yet. Will gain signal over the coming week.

---

## 4. Yesterday → Today

### Action Items from Journal (2026-04-22)

| Action | Status |
|--------|--------|
| Close hyna:LINK leg | ✅ DONE (Apr 22) — but 2.4 short dust remains |
| Close OIL_BRENTOIL | ✅ DONE (Apr 22) |
| Deploy $230k USDC to HyperLend | ✅ DONE (Apr 22) |
| Deploy $300k USDC to Felix USDC Main | ✅ DONE — $381,400 deployed (+$81k parked) |
| Place $30k USDT0 maker buy | SUPERSEDED — $49,840 order now, but 0.3% filled |
| Deploy $50k USDT to HyperLend USDT | ⏳ PENDING |
| Update positions.json with lending | ⏳ PENDING |
| After $30k fills: place next tranche | ⏳ PENDING — order barely filling |

### Material Changes (yesterday → today)

1. **Felix USDC deployed** — $393,800 now earning 5.56%. Capital utilization jumped from 30% → 86%. This is the biggest positive development.
2. **LINK funding flipped negative** — was +10.95% (cap rate), now -4.45%. Shorts paying longs. Exit signal triggered.
3. **USDT0 order increased to $49,840** — larger than the initial $30k planned, but only 0.3% filled ($149). Order may have been cancelled (no open orders found on any wallet at 04:24 UTC).
4. **Felix USDT0 partially funded** — $25,200 deployed (was $0 yesterday). Some USDT0 was acquired and deployed.
5. **Rate softening across board** — Felix USDC 6.86%→5.56%, HyperLend USDC 4.36%→3.74%, Felix USDT0 15.39%→11.88%. Broad-based, not asset-specific.

### Review Schedule — OVERDUE (22 days)

FARTCOIN and LINK reviews were due 2026-04-01. LINK review is now moot (exit). FARTCOIN at cap rate — update REVIEW_SCHEDULE.md with new dates and add lending position reviews (7-day cadence for first month).

---

## 5. Today's Plan

### Priority 1: 🔴 EXIT LINK Spot-Perp

- **What:** Close native LINK short (336 LINK) + clean hyna:LINK dust (2.4 short). Sell 342 LINK0 spot.
- **Wallet:** spot_perp (0x3c2c)
- **Why:** Funding negative (-4.45% APR). Every hour costs ~$0.016. Lifetime profit is $14.69 — protect it.
- **Impact:** Eliminates -$0.38/day drag. Frees ~$3k margin.
- **Caution:** Funding improved from -8.04% → -4.45% in 14 min. Could be recovering toward positive. But the trend over 24h is clearly negative (was at cap rate +10.95% yesterday). Don't wait for recovery — lock profit.

### Priority 2: ✅ USDT0 Swap Order — Actively Filling (No Action Needed)

- **Status:** Order on wallet `0x9653...2fEa` — 42.5% filled (~$21.2k acquired, $28.7k remaining at 1.0002 GTC)
- **Note:** Vault pulse (04:10 UTC) queried wrong wallet address and reported 0.3%. Order is healthy and filling.
- **Action:** Monitor. Deploy acquired USDT0 to Felix USDT0 as it accumulates. At current fill rate, remaining $28.7k should clear within hours. No need to bump price.

### Priority 3: Deploy Idle USDT0 ($4,976)

- **What:** Supply $4,976 USDT0 to Felix USDT0 vault
- **Wallet:** lending (0x9653), move from L1 → EVM
- **Impact:** +$1.62/day at 11.88% APY. Small but immediate.

### Priority 4: Deploy Idle USDH ($4,956)

- **What:** Supply $4,956 USDH to Felix USDH vault (8.69% APY)
- **Wallet:** unified (0xd473), move from L1 → EVM
- **Impact:** +$1.18/day

### Priority 5: Deploy $50k USDT to HyperLend

- **What:** Supply $50,000 USDT to HyperLend USDT pool
- **Wallet:** lending (0x9653)
- **Impact:** +$7.85/day at 5.73% live (but 7d avg only 3.64% — realistic: +$5/day)
- **Note:** HyperLend USDT 7d avg is 3.64%, well below the 5.79% plan target. Deploy anyway — idle cash at 0% is worse. But set expectations: $5/day not $8/day.

### Priority 6: Redeploy xyz Margin ($9,300)

- **What:** Withdraw $9,300 idle USDC from spot-perp xyz dex account. Deploy to Felix USDC or HyperLend.
- **Impact:** +$1.41/day at 5.56% (Felix) or +$0.95/day at 3.74% (HyperLend)

### Priority 7: Update REVIEW_SCHEDULE.md

- Add lending position review dates (7-day cadence through May)
- Remove LINK (exiting)
- Update FARTCOIN next review
- Add Felix USDC, HyperLend USDC, Felix USDT0 review entries

**Total impact of all actions: +$10-12/day** (bringing daily yield from $93.60 → ~$104-106)

---

## 6. Challenger Questions

1. **Felix concentration is 55.8% — above the 50% cap you set.** Yes, $81k is "parked while buying USDT0," but that USDT0 order is barely filling (0.3% in 24h+). If USDT0 acquisition takes 2 weeks at this pace, Felix stays above 50% for 2 weeks. Should you move $31k from Felix USDC to HyperLend USDC now to get under the cap, even if HyperLend pays 1.75pts less? The cap exists for a reason — are we suspending it on Day 2?

2. **The realistic blended APY is 5.23%, not 7.04%.** Even at full deployment with today's rates, the projection is:

   | Position | Amount | Live Rate | Daily $ |
   |----------|--------|-----------|---------|
   | Felix USDC | $300k | 5.56% | $45.68 |
   | HyperLend USDC | $230k | 4.16% (7d) | $26.22 |
   | Felix USDT0 | $100k | 11.88% | $32.55 |
   | HypurrFi USDT0 | $100k | 6.33% | $17.34 |
   | HyperLend USDT | $50k | 3.64% (7d) | $4.99 |
   | Spot-perp | $10k | 10.95% | $3.00 |
   | **Total** | **$790k** | **6.02%** | **$129.78** |

   That's $129.78/day — 16% below the $154 target. The shortfall is structural (rates are lower than plan), not just a deployment timing issue. Should we revise the target to 6% and call it realistic, or hunt for the missing $24/day through Frontier vaults or new USDT0 opportunities?

3. **HyperLend USDC 7d min touched 3.02%.** That's 2 bps from the 3% exit trigger. With $230k deployed, an exit means finding a new home for 30% of the portfolio. Felix USDC absorbs it easily (push Felix from 55.8% → 86% concentration — terrible). HypurrFi USDC at 3.85% is barely better than HyperLend. The exit contingency needs a real answer, not "move to Felix." Where does $230k go if HyperLend USDC trips the 3% trigger?

---

## 7. Risk Watch

### Scenario: USDT0 Acquisition Stalls — Deployment Plan Cannot Complete

**What:** The $49,840 USDT0 limit order at 1.0002 filled 0.3% in 24+ hours. At this rate, acquiring the remaining ~$175k USDT0 needed takes months. Felix USDT0 stays at 25% of target ($25k of $100k), HypurrFi USDT0 stays at 0%. The USDT0-dependent yield ($42/day from Felix USDT0 + $17/day from HypurrFi USDT0) never materializes.

**Probability:** Low-Medium (20-30%). ~~UPDATE: Order is 42.5% filled as of 04:24 UTC~~ — USDT0 acquisition is progressing. Remaining risk is fill pace for the last ~$28.7k and whether the $100k HypurrFi allocation can be sourced after this order completes.

**Impact:** -$44/day from USDT0 positions not funded. Blended APY stuck at ~5.2% instead of 6%. Annual shortfall: ~$16k.

**Trigger Signal:** Order fill rate. If <5% filled after 48 hours (by end of Apr 24), stalling is confirmed.

**Pre-planned Response:**
1. Move order to 1.0003 (eat 1 bps = $17.50 per $175k, breakeven in <1 hour of funding earned)
2. Or split: $50k market buy at 1.0004 (cost: $20, breakeven <1 day) + $125k limit at 1.0003
3. Deploy each tranche to Felix USDT0 / HypurrFi immediately upon receipt — don't batch
4. Worst case: if USDT0 acquisition remains impractical, reallocate $175k target to Felix USDC Frontier (9.37% APY) as USDC-denominated alternative

---

*Generated 2026-04-23 ~04:24 UTC. Primary source: vault pulse (04:10 UTC on-chain verified). Live rates refreshed via API. Next: daily vault-pulse + morning-review cycle.*
