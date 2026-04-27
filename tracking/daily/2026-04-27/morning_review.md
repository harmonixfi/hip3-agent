# Morning Review — 2026-04-27

**Data:** Vault pulse on-chain ~01:15 UTC | Rates from rates_history.csv (6 days: Apr 22-27)

---

## 1. Portfolio Health

| Metric | Today | Apr 25 | Target | Status |
|--------|-------|--------|--------|--------|
| Total Portfolio | $742,140 | $741,207 | $800k | YELLOW (-7.2%) |
| Deployed % | 95.1% ($706,125) | 91.2% ($675,973) | >85% | GREEN |
| Daily Yield | **$155.51/day** | $140.49/day | $154/day | **GREEN — 101% of target** |
| Blended APY | 8.04% | 7.59% | 7.04% | GREEN (+100 bps) |
| USDT0 Exposure | $110,000 (14.8%) | $80,000 (10.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 66.0% ($446k) | <50% | RED (+17.4pts over cap) |
| Idle Capital | $19,297 (2.6%) | $49,278 (6.6%) | <$20k | GREEN |

**So what:** Milestone day — daily yield crossed $154 target for the first time at $155.51. The $15/day jump from Apr 25 came from two sources: Felix USDT0 surging to 13.38% (+$27.59/day from rate recovery + $30k additional deployment) and LINK funding recovering to cap rate (+$0.32/day). The portfolio is now 95% deployed with only $19k idle — capital efficiency is excellent.

**The problem is concentration.** Felix/Morpho now holds 67.4% of deployed capital ($476k), up from 60.9% on Apr 24. This is 17 pts above the 50% cap. Every USDT0 deployment has gone to Felix rather than HypurrFi as originally planned. The yield premium (Felix USDT0 13.38% vs HypurrFi USDT0 7.41%) makes this rational on a per-position basis, but the portfolio-level risk is growing. HypurrFi USDT0 remains at $0 of $100k target. HyperLend USDT remains at $0 of $50k target. Both are now overdue.

**Portfolio total gap:** $742k vs $800k target = $58k gap. This is primarily the HypurrFi USDT0 ($100k) and HyperLend USDT ($50k) allocations that never deployed. These positions would add ~$25/day at plan rates. However, current daily yield already exceeds target thanks to above-plan rates on existing positions.

---

## 2. Position Status

### GREEN — All Positions On Track

```
lend_felix_usdt0 — ✅ HOLD (STAR PERFORMER)
  Rate: 13.38% APY (target 15.39%) — below plan but surged +757 bps from 5.81%
  Amount: $110,000 (target $100,000) — 110% deployed ✓
  Daily: $40.32 (plan: $42.16) — 96% of plan target
  Trigger: APR < 8% for 2wk → GREEN (538 bps headroom). YELLOW trigger from Apr 25 CLEARED.
  Trend: 15.39 → 11.88 → 12.74 → 5.81 → 13.38 — volatile but recovered strongly
  Note: Per lesson #10, this rate is volatile (range 5.81%-15.39% in 5 days). Today's 13.38% is
        very healthy. The $30k idle USDT0 deployed on Apr 26 was the right call — position is
        now the single largest yield contributor at $40.32/day (26% of total daily yield).
```

```
lend_felix_usdc_main — ✅ HOLD
  Rate: 7.44% APY (target 6.86%) — ABOVE plan target (+58 bps)
  Amount: $351,600 (target $300,000) — 117% deployed (includes ~$52k parked)
  Daily: $71.67 (plan: $56.38) — 127% of plan target
  Trigger: APR < 5% for 3d → GREEN (244 bps headroom)
  Trend: 6.86 → 5.55 → 5.16 → 9.02 → 7.44 — recovered from Apr 24 scare, now settling
  Note: Apr 24 review flagged Felix USDC approaching 5% trigger (was at 5.16%, only 16 bps
        headroom). Rate rebounded to 9.02% on Apr 25 then settled at 7.44% today. The 3-day
        trigger concern has fully dissipated. Still the anchor position at $71.67/day.
```

```
lend_hyperlend_usdc — ✅ HOLD
  Rate: 5.56% APY (target 4.36%) — ABOVE plan target (+120 bps)
  Amount: $230,125 (target $230,000) — 100% deployed ✓
  Daily: $35.05 (plan: $27.47) — 128% of plan target
  Trigger: APR < 3% → GREEN (256 bps headroom)
  Trend: 3.84 → 4.96 → 5.06 → 5.56 — steady 4-day uptrend (+172 bps from trough)
  Note: Per lesson #8, HyperLend is volatile (7d range historically 3.0-5.9%). Current 5.56% is
        at the high end of its range. Don't project this forward — use 7d avg ~4.5% for planning.
        Still, healthy position well above 3% trigger.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD
  Rate: 10.95% APR (was 1.78% on Apr 24 — FULL RECOVERY)
  Amount: $12,656 notional (8,590 native short + 51,590 hyna short + 59,944 spot)
  Daily: $3.81/day ($0.54 native + $3.27 hyna)
  Cumulative funding: $170.95 ($19.76 native + $151.19 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Dramatic recovery mirrors LINK pattern. Apr 24 was 1.78% (RED trigger breached), now
        back at cap rate 10.95%. Per lesson #10, this confirms funding is binary: cap rate or dead.
        FARTCOIN review was due Apr 26 (OVERDUE) but funding has recovered — extend review.
```

```
pos_link_native — ✅ HOLD
  Rate: 10.95% APR (was 7.59% on Apr 25 — recovered from YELLOW)
  Amount: $3,261 (342.13 spot / 336 short)
  Daily: $0.98/day
  Cumulative funding: $23.56 native (net $17.60 after hyna dust -$5.96)
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Back at cap rate after dipping to 7.59%. LINK funding history: 10.95 → -8.04 → 10.95 →
        7.59 → 10.95. Wildly volatile. Hold while at cap rate, but keep tight leash.
```

```
lend_felix_usdc_alt — ✅ HOLD
  Rate: 7.44% APY | Amount: $10,800 | Daily: $2.20
  Note: Small position, tracking main Felix USDC. No action needed.
```

```
lend_felix_usde — ✅ HOLD
  Rate: 15.00% APY (down from 21.03% — still very healthy)
  Amount: $3,600 | Daily: $1.48
  Note: Rate dipped but 15% is strong. Collateral position — monitor only.
```

```
pos_copper — ℹ️ TEST (~$801)
  Cumulative funding: $2.96 ($0.70 xyz + $2.26 flx). On hold. No action needed.
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Impact |
|------|--------|----------|-------------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC (8.30%) | +$2.11/day |
| USDH unified | $4,556 free | unified L1 | Felix USDH (11.31%) | +$1.41/day |
| USDC unified | $4,544 free | unified L1 | HypurrFi USDC (8.30%) | +$1.03/day |
| **Total idle** | **$18,400** | | | **+$4.55/day** |

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 7.44% | 244 bps | 0 days | GREEN |
| HyperLend USDC | APR < 3% | 5.56% | 256 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | 13.38% | 538 bps | 0 days (reset) | GREEN |
| HypurrFi USDT0 | APR < 5% | 7.41% (not deployed) | 241 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% | watch | 2 bps | 98 bps | — | GREEN |
| USDT0 depeg > 3% | exit | 2 bps | 298 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend 5.56% (closest) | 256 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger tracking (Felix USDT0 < 8% for 2wk):**
- Apr 25: 5.81% — below 8% (day 1)
- Apr 27: 13.38% — above 8% → counter RESET to 0

**Multi-day trigger tracking (Felix USDC < 5% for 3d):**
- No days below 5% in the last 5 snapshots. Nearest was 5.16% on Apr 24. GREEN.

---

## 4. Yesterday → Today

### Action Items from Apr 24 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Deploy $24.76k USDT0 to Felix USDT0 | ✅ **DONE** — $30k deployed. Felix USDT0 now $110k (+$55k from Apr 24). |
| P2 | FARTCOIN: monitor 24h, exit if <5% on Apr 25 | ✅ **RESOLVED** — Funding recovered to 10.95% APR. HOLD. |
| P3 | Deploy idle USDH ($4,956) to Felix USDH | ⏳ **PENDING** — Still idle on unified L1. Felix USDH now 11.31% (was 6.47%). |
| P4 | Redeploy xyz margin ($9,300) | ⏳ **PENDING** — Still idle on xyz dex. |
| P5 | Deploy idle USDC ($5,042) | ⏳ **PENDING** — Still idle on unified L1. |
| P6 | Update REVIEW_SCHEDULE.md | ⏳ **OVERDUE** — Schedule still stale (last updated Apr 24, data outdated). |
| P7 | Deploy $50k USDT to HyperLend | ⏳ **OVERDUE** — Still at $0. Day 1 plan item, now 5 days late. |

### Material Changes (Apr 25 → Apr 27)

| Change | Detail |
|--------|--------|
| **Felix USDT0 surged** | 5.81% → 13.38% (+757 bps). YELLOW trigger cleared. Rate doubled. |
| **Idle USDT0 deployed** | $29.98k moved to Felix USDT0. Position grew $80k → $110k. L1 now empty ($0.85 HYPE dust). |
| **LINK recovered** | 7.59% → 10.95% (+336 bps). Back at cap rate. RED trigger from Apr 25 cleared. |
| **Felix USDC softened** | 9.02% → 7.44% (-158 bps). Settled after Apr 25 spike. Still healthy. |
| **Felix USDe dropped** | 21.03% → 15.00% (-603 bps). Still healthy at 15% but notable decline. |
| **Felix USDH surged** | 8.06% → 11.31% (+325 bps). Makes idle USDH deployment more attractive. |
| **Daily yield up** | $140.49 → $155.51 (+$15.02/day, +10.7%). **Crossed $154 target for the first time.** |
| **Deployed % up** | 91.2% → 95.1% (+3.9pts). Idle capital nearly eliminated. |
| **USDT0 swap complete** | Order closed. All USDT0 acquired and deployed. No more pending swaps. |

---

## 5. Today's Plan

### Priority 1: Update REVIEW_SCHEDULE.md
- **What:** Schedule is stale with outdated amounts, rates, and missing review dates
- **Impact:** Operational hygiene. Multiple reviews are now overdue (FARTCOIN Apr 26, LINK hyna Apr 25, HyperLend USDT Apr 26)
- **Action:** Updated below in this morning review run

### Priority 2: Deploy $9,300 xyz Idle to HypurrFi USDC
- **What:** Withdraw $9,300 from spot-perp xyz dex → HypurrFi USDC (8.30% APY)
- **Wallet:** spot_perp (0x3c2c) → HypurrFi
- **Why HypurrFi not Felix:** Felix concentration is 67.4% (RED). Any new USDC deployment should go to HypurrFi or HyperLend for diversification
- **Impact:** +$2.11/day

### Priority 3: Deploy $4,556 Idle USDH to Felix USDH
- **What:** Move $4,556 USDH from unified L1 → Felix USDH vault (11.31% APY)
- **Wallet:** unified (0xd473) → EVM → Felix
- **Impact:** +$1.41/day. Felix USDH at 11.31% is the highest USDH rate available
- **Note:** $399 stays locked as COPPER flx margin

### Priority 4: Deploy $4,544 Idle USDC to HypurrFi USDC
- **What:** Move $4,544 USDC from unified L1 → HypurrFi USDC (8.30% APY)
- **Wallet:** unified (0xd473) → HypurrFi
- **Why HypurrFi:** Felix concentration reduction. HypurrFi USDC at 8.30% beats HyperLend USDC at 5.56%
- **Impact:** +$1.03/day

### Priority 5: Address HypurrFi USDT0 Deployment Gap
- **What:** Evaluate whether to acquire more USDT0 for HypurrFi ($0 of $100k target)
- **Blocker:** No idle USDT0 available — all deployed to Felix. New USDT0 requires USDC→USDT0 swap
- **Decision needed:** Is the Felix concentration (67.4%) serious enough to justify a $50-100k USDC→USDT0 swap + HypurrFi deployment at lower yield (7.41% vs Felix 13.38%)?
- **Impact:** $50k at HypurrFi 7.41% = $10.15/day, reduces Felix % by ~7pts

### Priority 6: Investigate HyperLend USDT Deployment
- **What:** Day 1 plan item, 5 days overdue. $50k target at 5.39% APY = $7.38/day
- **Blocker:** Requires USDT availability or USDC→USDT swap path
- **Impact:** +$7.38/day, also diversifies away from Felix

**Total impact of P2-P4 (no blockers): +$4.55/day** → daily yield from $155.51 to ~$160.06/day

---

## 6. Challenger Questions

1. **Felix concentration is 67.4% and still growing — when does this become an actual problem, not just a dashboard RED?** The deployment plan set 50% as the cap. We're 17 pts over. Every single USDT0 dollar has gone to Felix because of yield premium (13.38% vs HypurrFi 7.41%). At $476k in Felix, a Morpho exploit wipes 64% of the portfolio. The yield difference on $100k between Felix USDT0 (13.38%) and HypurrFi USDT0 (7.41%) is ~$16.30/day. Is $16.30/day enough to justify the concentration risk? If Felix caps weren't violated, the blended yield would be lower but the portfolio would survive a single-protocol failure. **What would Frank say?**

2. **FARTCOIN and LINK are both at 10.95% (cap rate) again — but 5 days of data show they swing between cap rate and near-zero.** FARTCOIN: 10.95 → 1.78 → 10.95. LINK: 10.95 → -8.04 → 10.95 → 7.59 → 10.95. Per lesson #10, cap rate data tells you about the regime, not the asset. The combined $16k in spot-perp earns $4.79/day at cap rate but could flip to $0/day overnight. At $16k, the downside is limited. But should we set an automatic exit rule: "if funding < 5% for 3 consecutive snapshots, exit and redeploy to lending"? That way we capture the cap rate upside without requiring daily manual checks.

3. **$50k HyperLend USDT has been "pending" since Day 1 (Apr 22) — that's $7.38/day opportunity cost × 5 days = ~$37 already forfeited.** The rate is now 5.39% (per lesson #8, 7d avg matters more — historical range 1.4-5.9%). What's the actual blocker? If it's a USDC→USDT swap, that should take <24h. If it's an operational constraint (USDT not available on HyperEVM?), we should know and either fix it or drop it from the plan.

---

## 7. Risk Watch

### Scenario: Felix/Morpho Smart Contract Exploit

**What:** Felix holds $476k (67.4% of deployed capital) across 4 vaults: USDC Main ($351.6k), USDT0 ($110k), USDC alt ($10.8k), USDe ($3.6k). A Morpho Blue vulnerability or Felix vault manager error could freeze or drain all vaults simultaneously.

**Probability:** Very Low (1-2%/yr). Morpho Blue is audited and battle-tested. But per lesson #6, Euler was also "audited and battle-tested" before losing $197M.

**Impact:** -$476,000 (64% of portfolio). Surviving portfolio = $266k ($230k HyperLend USDC + $17k trading + $19k idle). Daily yield drops from $155 to ~$40/day. Fund would need 18+ months to recover to $742k at remaining yield.

**Trigger signal:** Morpho security alerts, Felix governance announcements, unusual TVL drops, audit findings. Monitor @MorphoLabs and Felix channels.

**Pre-planned response:**
1. If suspicious activity detected: withdraw all Felix positions immediately (USDC is liquid, minutes to exit)
2. If exploit confirmed: withdraw remaining HyperLend positions too (contagion risk on HyperEVM)
3. Minimum viable response: reduce Felix to $300k (-$176k) and deploy excess to HypurrFi. This alone cuts exposure from 67% to 50%

**Bottom line:** The concentration cap exists for this exact scenario. At 67.4%, we're running without the safety margin. The mathematically optimal action is to move $76k+ from Felix to HypurrFi/HyperLend even at lower rates. The daily yield cost (~$5/day) buys portfolio survivability.

---

*Generated 2026-04-27. Primary source: vault pulse (01:15 UTC on-chain verified). Rates from rates_history.csv (6-day window). Next: daily vault-pulse + morning-review cycle.*
