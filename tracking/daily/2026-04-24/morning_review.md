# Morning Review — 2026-04-24

**Data:** Vault pulse on-chain ~01:20 UTC | Rates from rates_history.csv (3 days: Apr 22-24)

---

## 1. Portfolio Health

| Metric | Today | Yesterday | Target | Status |
|--------|-------|-----------|--------|--------|
| Total Portfolio | $741,075 | $757,847 | $800k | YELLOW (-7.4%) |
| Deployed % | 91.9% ($681,042) | 86.2% ($653,020) | >85% | GREEN |
| Daily Yield | $108.39/day | $93.60/day | $154/day | RED (70.4% of target) |
| Blended APY | 5.81% | 5.23% | 7.04% | RED (-123 bps) |
| USDT0 Exposure | $55,200 (7.4%) | $25,200 (3.3%) | <$200k (25%) | GREEN (under cap, scaling) |
| Largest Protocol | Felix 60.9% ($451k) | Felix 55.8% ($423k) | <50% | RED (+10.9pts over cap) |
| Idle Capital | $44,058 (5.9%) | $74,126 (9.8%) | <$20k | YELLOW (improving) |

**So what:** Good progress overnight. Daily yield jumped +$14.79/day (+16%) thanks to $30k USDT0 deployment to Felix (now earning 12.74%) and LINK flipping positive. Deployed % crossed 91.9%. The $46/day shortfall to target breaks down:

- ~$26/day from USDT0 positions still underfunded ($55k of $200k target deployed)
- ~$8/day from HypurrFi USDT0 at $0 of $100k target
- ~$8/day from missing HyperLend USDT ($0 of $50k)
- ~$4/day from rate softening vs plan (Felix USDC 5.16% vs 6.86% plan)

**Felix concentration is now 60.9% — RED.** Worsened from 55.8% because $30k USDT0 deployed to Felix (not HypurrFi). The $81k USDC parked in Felix is still there. To get under 50%, need to either: (a) deploy $100k to HypurrFi USDT0, or (b) move $81k from Felix USDC to HyperLend. The USDT0 path is the plan — but it requires acquiring another ~$145k USDT0 beyond what's on hand.

**Portfolio total dropped $16.8k** from $757.8k to $741.1k. This is likely accounting: USDT0 swap converted ~$50k USDC to USDT0, some of which deployed, and trading position mark-to-market. Not a real loss — verify the total against wallet balances if concerned.

---

## 2. Position Status

### RED — Immediate Attention

```
pos_fartcoin (native + hyna) — 🔴 ACT
  Rate: 1.78% APR (was 10.95% yesterday, 12.10% plan) — down 84%
  Amount: $11,982 notional (8,590 native short + 51,590 hyna short + 59,944 spot)
  Daily: ~$0.58/day at 1.78% APR
  Cumulative funding: $160.75 ($18.17 native + $142.58 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → RED (breached — 622 bps below trigger)
  Note: Sharp single-day drop from cap rate to near-zero. This could be:
        (a) Temporary — a market regime shift that reverses in 1-3 days
        (b) Structural — cap rate period ended (per lesson #10, cap rate data tells you nothing about normal conditions)
        At $0.58/day, this is dead money on $12k notional. However, $160.75 cumulative profit is already banked.
        RECOMMENDATION: Monitor 24-48h. If funding doesn't recover above 5% APR by Apr 26, exit and redeploy $12k to lending (~$1.90/day at 5.81% blended).
```

### YELLOW — Monitor

```
lend_felix_usdc_main — 🟡 WATCH
  Rate: 5.16% APY (was 5.55% yesterday, 6.86% plan) — declining 3 days straight
  Amount: $381,400 + $10,800 (alt) = $392,200 (target $300k — 131%)
  Daily: $55.44 ($53.91 main + $1.53 alt)
  Trigger: APR < 5% for 3d → GREEN (day 0 — rate above 5%, not breached yet)
  Headroom: 16 bps above 5% trigger
  Trend: 6.86% → 5.55% → 5.16% — steady decline, -39 bps/day avg
  Note: At current decline rate, hits 5% trigger within 1 day. If trend continues, 3-day trigger
        could fire by Apr 27-28. Not actionable yet, but this is the position to watch most closely.
        Per lesson #8, single-day rates are noisy — but 3 consecutive days of decline is a trend.
```

```
lend_felix_usdt0 — 🟡 SCALING
  Rate: 12.74% APY (was 11.88% yesterday, 15.39% plan) — rate recovered +86 bps
  Amount: $55,200 (target $100,000) — 55% deployed (+$30k overnight)
  Daily: $19.26 (vs $42.16 at full deployment)
  Trigger: APR < 8% for 2wk → GREEN (474 bps headroom)
  Note: Rate stabilizing above 12%. $24.76k USDT0 idle on L1 ready to deploy NOW.
        At 12.74%, every $10k deployed = $3.49/day. Deploying the idle $24.76k adds $8.64/day.
        This is the single highest-impact action available today.
```

### GREEN — On Track

```
lend_hyperlend_usdc — ✅ HOLD
  Rate: 4.96% APY (was 3.84% yesterday) — strong recovery +112 bps
  Amount: $230,042 (target $230,000) — 100% deployed ✓
  Daily: $31.28 (vs $27.47 plan — now ABOVE plan target)
  Trigger: APR < 3% → GREEN (196 bps headroom)
  Trend: improved from 3.84% → 4.96%. Per lesson #8, use 7d avg for decisions.
  Note: Yesterday's concern about approaching 3% trigger has eased significantly.
        Rate recovered to near plan levels. Continue monitoring — HyperLend is volatile (lesson #8).
```

```
pos_link_native — ✅ HOLD (REVERSED from yesterday's EXIT call)
  Rate: +10.95% APR (was -8.04% yesterday) — full reversal, back at cap rate
  Amount: $3,193 (342.13 spot / 336 short)
  Daily: $0.94/day
  Cumulative funding: $20.91 (native) - $5.98 (hyna dust) = net $14.93
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Dramatic recovery. Yesterday was EXIT signal, today back at cap rate.
        This volatility (10.95% → -8.04% → 10.95% in 48h) confirms lesson #10 — cap rate
        data is regime-dependent. LINK funding is binary: cap rate or negative.
        HOLD while positive, but keep a tight leash — exit quickly on next flip.
```

```
pos_link_hyna_dust — ℹ️ CLEAN UP
  Amount: $22 (2.4 short)
  Cumulative funding: -$5.98
  Note: Residual dust, paying funding. Clean up when convenient — not urgent at $22 notional.
```

```
lend_felix_usde — ✅ HOLD
  Rate: 8.91% APY (was 12.24% yesterday — declined but still healthy)
  Amount: $3,600
  Daily: $0.88
  Note: Small collateral position. Rate softened but still good.
```

```
pos_copper — ℹ️ TEST
  Amount: $800 (65.92 short xyz + 65.92 long flx)
  Cumulative funding: $2.12 ($0.35 xyz + $1.77 flx)
  Note: Tiny test, on hold. No action needed.
```

### IDLE — Deploy Today

| Item | Amount | Location | Priority | Impact |
|------|--------|----------|----------|--------|
| Idle USDT0 | $24,760 | lending L1 | **P1** | +$8.64/day at 12.74% |
| Idle USDC | $9,300 | spot-perp xyz dex | P3 | +$1.26/day at 4.96% |
| Idle USDC | $5,042 | unified L1 | P4 | +$0.69/day |
| Idle USDH | $4,956 | unified L1 | P4 | +$0.88/day at 6.47% |
| **Total idle** | **$44,058** | | | **+$11.47/day potential** |

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Status |
|---------|------|---------|----------|--------|
| FARTCOIN funding | APR < 8% | **1.78% APR** | BREACHED (-622 bps) | 🔴 RED |
| Felix USDC | APR < 5% for 3d | 5.16% (day 0 above) | 16 bps | 🟡 YELLOW |
| HyperLend USDC | APR < 3% | 4.96% | 196 bps | 🟢 GREEN (improved) |
| Felix USDT0 | APR < 8% for 2wk | 12.74% | 474 bps | 🟢 GREEN |
| HypurrFi USDT0 | APR < 5% | 6.25% (not deployed) | 125 bps | 🟢 GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | 🟢 GREEN (recovered) |
| USDT0 depeg > 1% | > 1% | 1.0 bps spread | 99 bps | 🟢 GREEN |
| USDT0 depeg > 3% | > 3% | 1.0 bps spread | 299 bps | 🟢 GREEN |
| Any lending < 3% | < 3% | HyperLend 4.96% closest | 196 bps | 🟢 GREEN |
| Felix concentration | < 50% | 60.9% | BREACHED (+10.9pts) | 🔴 RED |

**Multi-day trigger tracking (Felix USDC < 5% for 3d):**
- Apr 22: 6.86% (plan rate, above 5%)
- Apr 23: 5.55% (above 5%)
- Apr 24: 5.16% (above 5%)
- Consecutive days below 5%: **0** — trigger NOT firing. But trending toward it.

---

## 4. Yesterday → Today

### Action Items from Yesterday's Morning Review

| Action | Status |
|--------|--------|
| P1: EXIT LINK spot-perp | **SKIPPED** — Bean held, and LINK recovered to +10.95%. Good call to wait. |
| P2: Monitor USDT0 swap order (42.5% filled) | ✅ **DONE** — Order completed. ~$49.84k total USDC→USDT0. |
| P3: Deploy idle USDT0 ($4,976) to Felix USDT0 | ✅ **DONE** — $30k total deployed to Felix USDT0 (now $55.2k). |
| P4: Deploy idle USDH ($4,956) | ⏳ PENDING — still idle on unified L1 |
| P5: Deploy $50k USDT to HyperLend | ⏳ PENDING |
| P6: Redeploy xyz margin ($9,300) | ⏳ PENDING |
| P7: Update REVIEW_SCHEDULE.md | ⏳ **OVERDUE** — schedule last updated Mar 30 |

### Material Changes (Apr 23 → Apr 24)

| Change | Detail |
|--------|--------|
| **USDT0 swap completed** | $49.84k order filled. $30k deployed to Felix USDT0. $24.76k idle on L1. Major milestone. |
| **FARTCOIN funding collapsed** | 10.95% → 1.78% APR (-917 bps). Was best performer, now dead money. |
| **LINK funding recovered** | -8.04% → +10.95% APR (+1899 bps). Full reversal back to cap rate. |
| **HyperLend USDC recovered** | 3.84% → 4.96% (+112 bps). Yesterday's concern resolved. |
| **Felix USDC continued decline** | 5.55% → 5.16% (-39 bps). Now only 16 bps from 5% trigger. |
| **Deployed % up** | 86.2% → 91.9% (+5.7pts). Idle capital down $30k. |
| **Daily yield up** | $93.60 → $108.39 (+$14.79/day, +16%). Best single-day improvement. |

---

## 5. Today's Plan

### Priority 1: Deploy $24.76k USDT0 to Felix USDT0

- **What:** Move $24,760 USDT0 from lending L1 → EVM → Felix USDT0 vault
- **Wallet:** lending (0x9653)
- **Impact:** +$8.64/day at 12.74% APY. Felix USDT0 goes from $55.2k → $80k (80% of $100k target)
- **Why now:** Highest ROI action. USDT0 is sitting at 0% yield on L1. Every hour of delay costs $0.36.

### Priority 2: Decide FARTCOIN — Monitor 24h Then Reassess

- **What:** Do NOT exit yet. Monitor funding rate through Apr 24-25.
- **Why wait:** The drop could be temporary (LINK did -8.04% → +10.95% in 24h). FARTCOIN has banked $160.75 cumulative profit — there's no urgency to exit a profitable position.
- **Decision point:** If funding < 5% APR on Apr 25 vault pulse → exit. Redeploy $12k to lending (+$1.90/day at 5.81%).
- **If funding recovers >8%:** Hold. The position has proven it can earn.

### Priority 3: Deploy Idle USDH ($4,956)

- **What:** Supply $4,956 USDH to Felix USDH vault (6.47% APY)
- **Wallet:** unified (0xd473), move L1 → EVM
- **Impact:** +$0.88/day

### Priority 4: Redeploy xyz Margin ($9,300)

- **What:** Withdraw $9,300 USDC from spot-perp xyz dex → deploy to HyperLend USDC
- **Why HyperLend not Felix:** Felix is already 60.9% concentrated. HyperLend at 4.96% is acceptable.
- **Impact:** +$1.26/day

### Priority 5: Deploy Idle USDC ($5,042)

- **What:** Move $5,042 USDC from unified L1 → HyperLend or Felix
- **Impact:** +$0.69/day

### Priority 6: Update REVIEW_SCHEDULE.md

- **22 days overdue.** Schedule is stale (last updated Mar 30, still has HYPE/GOLD reviews from Apr 1).
- Add lending position reviews on 7-day cadence
- Update FARTCOIN review date
- Add LINK with note about funding volatility

### Priority 7: Deploy $50k USDT to HyperLend

- **What:** Supply $50,000 USDT to HyperLend USDT pool
- **Status:** Still pending from Day 1 plan. HyperLend USDT rate today: 5.55% (improved from 5.90% plan target — actually healthy now)
- **Blocker:** Need to verify USDT availability on lending wallet. May require USDC→USDT swap.
- **Impact:** +$7.60/day

**Total impact of P1-P5 (no blockers): +$11.47/day** → daily yield from $108.39 to ~$119.86/day

---

## 6. Challenger Questions

1. **Felix concentration is 60.9% and GROWING, not shrinking.** Yesterday it was 55.8%, today 60.9%. The plan was to shrink it by deploying to HypurrFi USDT0 — but no USDT0 has gone to HypurrFi yet (0% of $100k target). Meanwhile, every USDT0 deployment goes to Felix. With the USDT0 swap completed ($49.84k total), you now have $55.2k in Felix USDT0 and $0 in HypurrFi. Should the NEXT $24.76k of USDT0 go to HypurrFi instead of Felix, even though Felix pays 12.74% vs HypurrFi's 6.25%? The concentration cap exists because protocol risk is real — at what point does the yield premium stop justifying the concentration?

2. **FARTCOIN earned $160.75 over its lifetime but is now a $12k position earning $0.58/day.** That's 1.78% APR vs 5.81% blended lending. The $12k deployed in lending would earn $1.91/day — a $1.33/day improvement. But LINK just proved that funding can snap back overnight (from -8.04% to +10.95%). The question: is FARTCOIN's funding profile more like LINK (binary cap-rate-or-nothing, driven by market sentiment) or is this a structural shift (the speculative fervor that drove cap-rate funding is fading)? Check the broader HL funding environment — are other mid-cap perps also compressing?

3. **$50k USDT deployment to HyperLend has been "pending" for 3 days now.** It was Step 2 in the Day 1 plan. At 5.55% APY, that's $7.60/day sitting at 0%. Three days of delay = $22.80 in lost yield. What's the actual blocker — is USDT available on the lending wallet, or does it need a swap? If it needs a swap, the USDC→USDT pathway should be mapped today.

---

## 7. Risk Watch

### Scenario: Felix USDC Rate Breaks 5% Trigger — $392k Needs a Plan

**What:** Felix USDC has declined 3 straight days: 6.86% → 5.55% → 5.16%. If this trend continues, it crosses 5% within 24h. The trigger rule is "APR < 5% for 3 consecutive days." At current trajectory, the 3-day trigger could fire by Apr 27-28.

**Probability:** Medium (30-40%). Rate compression across DeFi lending is a known pattern in sideways markets. The decline is broad-based, not Felix-specific (HyperLend also dropped before recovering).

**Impact:** $392,200 in Felix USDC earning below 5% APY. At 4.5% (plausible floor), daily yield drops from $55.44 to $48.35 — a $7.09/day loss. Not catastrophic, but the trigger exists because sustained sub-5% rates signal capital should move.

**Trigger signal:** Tomorrow's vault pulse rate. If Felix USDC < 5.0%, start the 3-day clock. Watch Felix USDC Frontier rate (6.85% today) as a potential rotation target within the same protocol.

**Pre-planned response:**
1. Day 1 below 5%: No action. Monitor.
2. Day 2 below 5%: Evaluate rotation targets — Felix Frontier (6.85%), HyperLend USDC (4.96%), HypurrFi USDC (7.76%).
3. Day 3 below 5%: Rotate $81k (the "parked" excess above $300k target) to HypurrFi USDC (7.76%) or Felix Frontier. This also reduces Felix concentration from 60.9% toward 50%.
4. If rate recovers above 5% at any point, reset the clock.

**Note:** HypurrFi USDC at 7.76% today is the highest USDC rate in the portfolio. If Felix USDC trigger fires, the answer may be HypurrFi — which also diversifies away from Felix concentration risk. Two problems solved with one move.

---

*Generated 2026-04-24. Primary source: vault pulse (01:20 UTC on-chain verified). Rates from rates_history.csv (3-day window). Next: daily vault-pulse + morning-review cycle.*
