# Morning Review — 2026-04-28

**Data:** Vault pulse on-chain ~01:25 UTC | Rates from rates_history.csv (7 days: Apr 22-28)

---

## 1. Portfolio Health

| Metric | Today | Yesterday (Apr 27) | Target | Status |
|--------|-------|---------------------|--------|--------|
| Total Portfolio | $744,894 | $742,140 | $800k | YELLOW (-6.9%) |
| Deployed % | 94.8% ($706,375) | 95.1% ($706,125) | >85% | GREEN |
| Daily Yield | **$127.33/day** | $155.51/day | $154/day | **RED — 82.7% of target** |
| Blended APY | 6.58% | 8.04% | 7.04% | **YELLOW (-46 bps below target)** |
| USDT0 Exposure | $110,100 (14.8%) | $110,000 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476k) | Felix 67.4% ($476k) | <50% | RED (+17.4pts over cap) |
| Idle Capital | $19,300 (2.6%) | $19,297 (2.6%) | <$20k | GREEN |

**So what:** Yesterday was a milestone — first day above $154 target. Today it's gone. A broad rate compression across all Felix vaults wiped $28/day overnight. The single biggest hit: Felix USDT0 crashed from 13.38% to 6.08% (-730 bps), costing $21.97/day on our largest yield contributor. Felix USDe (-651 bps) and Felix USDH (-510 bps) also dropped hard, though their smaller balances limit the dollar impact.

**The structural problem is visible now.** Felix concentration at 67.4% means a Felix rate compression event — which is exactly what happened today — hits 67% of our earning power. HyperLend USDC, by contrast, held steady at 5.61% (+5 bps). If we'd deployed $100k to HypurrFi and $50k to HyperLend USDT as planned, the yield hit would be dampened by diversification. Today's compression is the concrete cost of concentration.

**Is this a regime change or a 1-day dip?** Felix USDT0 has been volatile: 15.39 → 11.88 → 12.74 → 5.81 → 13.38 → **6.08**. This is the second time below 8% in 4 days. Last time (Apr 25) it recovered in 2 days. But the pattern is: every spike is followed by a deeper crash. The rate may recover again, but the trend of wider swings is concerning.

---

## 2. Position Status

### RED/YELLOW — Needs Attention

```
lend_felix_usdt0 — 🟡 WATCH (YELLOW TRIGGER — Day 1 of 14)
  Rate: 6.08% APY (target 15.39%) — BELOW 8% exit threshold by 192 bps
  Amount: $110,100 (target $100,000) — 110% deployed
  Daily: $18.35 (was $40.32 yesterday — -$21.97/day impact)
  Trigger: APR<8% for 2wk → YELLOW (Day 1). Last dip: Apr 25 (recovered in 2d).
  Trend: 15.39 → 11.88 → 12.74 → 5.81 → 13.38 → 6.08 — volatile, second dip below 8%
  Note: This is the biggest drag on portfolio yield. At 6.08%, this $110k earns less than
        HyperLend USDC (5.61% on $230k = $35.39/day). Per lesson #10, rate is volatile and
        could recover. But two dips below 8% in 4 days makes the pattern less reassuring.
        Watch through the week — if still below 8% by Apr 30, start evaluating rebalance.
```

```
lend_felix_usde — 🟡 WATCH (RATE COMPRESSION)
  Rate: 6.49% APY (was 15.00% yesterday — -651 bps crash)
  Amount: $3,600 | Daily: $0.64 (was $1.48)
  Note: Small position, limited dollar impact ($0.84/day loss). But the same
        compression pattern as USDT0. Felix lending rates are broadly softening.
```

```
⚠️ COPPER (xyz+flx) — VERIFY WITH BEAN
  Old (Apr 27): 65.92 xyz SHORT + 65.92 flx LONG, $801 notional, cumFunding $2.96
  New (Apr 28): 329.6 xyz LONG + 329.6 flx SHORT, $3,991 notional, cumFunding $0.97
  Change: Direction REVERSED + size 5x. New cumFunding confirms fresh positions.
  Note: This was a test position. The reversal + scaling suggests Bean restructured
        the trade (perhaps funding direction flipped, making the reverse direction
        profitable). Needs explicit verification — was this intentional?
```

### GREEN — On Track

```
lend_felix_usdc_main — ✅ HOLD
  Rate: 6.89% APY (target 6.86%) — at plan target (+3 bps)
  Amount: $351,700 (target $300,000) — 117% deployed
  Daily: $66.34 (was $71.67 — -$5.33/day from -55 bps compression)
  Trigger: APR < 5% for 3d → GREEN (189 bps headroom)
  Trend: 6.86 → 5.55 → 5.16 → 9.02 → 7.44 → 6.89 — settling toward plan rate
  Note: Rate dipped but still healthy at plan target level. The $52k parked above
        $300k target earns at same rate — no concern. 189 bps headroom vs 5% trigger
        is tighter than yesterday (was 244 bps). Monitor if downtrend continues.
```

```
lend_hyperlend_usdc — ✅ HOLD (MOST STABLE POSITION)
  Rate: 5.61% APY (target 4.36%) — ABOVE plan target (+125 bps)
  Amount: $230,175 (target $230,000) — 100% deployed ✓
  Daily: $35.39 (plan: $27.47) — 129% of plan target
  Trigger: APR < 3% → GREEN (261 bps headroom)
  Trend: 3.84 → 4.96 → 5.06 → 5.56 → 5.61 — 5-day uptrend, steadiest position
  Note: Per lesson #8, HyperLend is volatile (range 3.0-5.9%) but current trend is
        bullish. While Felix rates compressed broadly, HyperLend actually ticked UP.
        This is the resilience argument for diversification.
```

```
pos_fartcoin (native + hyna) — ✅ HOLD
  Rate: 10.95% APR (cap rate — stable)
  Amount: $12,034 notional (59,944 spot / 60,180 total short)
  Daily: $3.61/day
  Cumulative funding: $172.22 ($20.32 native + $151.90 hyna)
  Delta: neutral (-0.4%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Still at cap rate. Price declined slightly ($0.2111 → $0.2008, -5%).
        Delta remains tight. Cap rate regime holds.
```

```
pos_link_native — ✅ HOLD
  Rate: 10.95% APR (cap rate — stable)
  Amount: $3,194 (342.13 spot / 336 short)
  Daily: $0.96/day
  Cumulative funding: $24.51 native (net $18.56 after hyna dust -$5.95)
  Delta: neutral (1.1%) ✓
  Trigger: APR < 8% → GREEN (295 bps headroom)
  Note: Stable at cap rate. Small position, minimal portfolio impact.
```

```
lend_felix_usdc_alt — ✅ HOLD
  Rate: 6.89% APY | Amount: $10,800 | Daily: $2.04
  Note: Tracking main Felix USDC. Small position.
```

```
pos_copper — ℹ️ VERIFY (see alert above)
  Cumulative funding: $0.97 ($0.15 xyz + $0.82 flx). Reversed+scaled. Verify with Bean.
```

### IDLE — Deploy Candidates

| Item | Amount | Location | Best Target | Rate Today | Impact |
|------|--------|----------|-------------|------------|--------|
| USDC xyz margin | $9,300 | spot-perp xyz dex | HypurrFi USDC | 6.92% | +$1.76/day |
| USDH unified | $4,854 free | unified L1 | Felix USDH | 6.21% | +$0.83/day |
| USDC unified | $4,943 free | unified L1 | HypurrFi USDC | 6.92% | +$0.94/day |
| **Total idle** | **$19,097** | | | | **+$3.53/day** |

Note: Target rates declined from yesterday (HypurrFi USDC was 8.30%, now 6.92%; Felix USDH was 11.31%, now 6.21%). Deployment impact reduced accordingly but still worth doing.

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days | Status |
|---------|------|---------|----------|--------------|--------|
| Felix USDC | APR < 5% for 3d | 6.89% | 189 bps | 0 days | GREEN |
| HyperLend USDC | APR < 3% | 5.61% | 261 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | **6.08%** | **-192 bps below** | **Day 1** | **YELLOW** |
| HypurrFi USDT0 | APR < 5% | 6.28% (not deployed) | 128 bps | — | GREEN |
| LINK funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| FARTCOIN funding | APR < 8% | 10.95% | 295 bps | — | GREEN |
| USDT0 depeg > 1% | watch | 1 bps | 99 bps | — | GREEN |
| USDT0 depeg > 3% | exit | 1 bps | 299 bps | — | GREEN |
| Any lending < 3% | exit | HyperLend USDT 5.26% (closest) | 226 bps | — | GREEN |
| Felix concentration | < 50% | **67.4%** | BREACHED (+17.4pts) | ongoing | **RED** |

**Multi-day trigger tracking (Felix USDT0 < 8% for 2wk):**
- Apr 25: 5.81% — below 8% (day 1)
- Apr 27: 13.38% — above 8% → counter RESET
- **Apr 28: 6.08% — below 8% (day 1 again)**
- Pattern: 2 out of last 4 snapshots below 8%. Rate is oscillating around the 8% threshold.

**Multi-day trigger tracking (Felix USDC < 5% for 3d):**
- No days below 5% in last 7 snapshots. Nearest was 5.16% on Apr 24. Today at 6.89%. GREEN.
- Headroom tightened from 244 bps (Apr 27) to 189 bps (Apr 28) — directional trend toward trigger, but still comfortable.

---

## 4. Yesterday → Today

### Action Items from Apr 27 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | Update REVIEW_SCHEDULE.md | ✅ **DONE** — Updated in Apr 27 review run |
| P2 | Deploy $9,300 xyz idle to HypurrFi USDC | ⏳ **PENDING** — Still idle. Rate dropped 8.30% → 6.92%, still worth deploying for $1.76/day |
| P3 | Deploy $4,556 USDH to Felix USDH | ⏳ **PENDING** — Still idle. Rate crashed 11.31% → 6.21%. Impact reduced from $1.41/day to $0.83/day |
| P4 | Deploy $4,544 USDC to HypurrFi USDC | ⏳ **PENDING** — Still idle. Rate dropped 8.30% → 6.92%. Impact reduced from $1.03/day to $0.94/day |
| P5 | Address HypurrFi USDT0 deployment gap | ⏳ **PENDING** — Still $0 of $100k. Today's rate compression (HypurrFi USDT0 at 6.28%) makes the case weaker |
| P6 | Investigate HyperLend USDT ($50k) | ⏳ **OVERDUE** — 6 days since plan Day 1. $50k × 5.26% = $7.20/day opportunity cost |

### Material Changes (Apr 27 → Apr 28)

| Change | Detail | Impact |
|--------|--------|--------|
| **Felix rates broadly compressed** | USDT0: -730 bps, USDe: -651 bps, USDH: -510 bps, USDC: -55 bps | **-$28.18/day** — biggest single-day yield drop |
| **Daily yield dropped below target** | $155.51 → $127.33 (-$28.18, -18.1%) | Yesterday's milestone erased |
| **Felix USDT0 YELLOW again** | 6.08% — day 1 below 8% (second time in 4 days) | Watch counter. Pattern: dips recover in 1-2 days so far |
| **COPPER restructured** | Reversed direction + 5x scaled ($801 → $3,991) | **[VERIFY]** — intentional? |
| **HyperLend stable** | USDC +5 bps (5.61%), USDT -13 bps (5.26%) | Confirms diversification value |
| **HypurrFi rates dipped** | USDT0 -113 bps (6.28%), USDC -138 bps (6.92%) | Weakens case for HypurrFi deployment at current rates |
| **FARTCOIN price -5%** | $0.2111 → $0.2008 | Notional reduced $12,656 → $12,034. Delta still neutral. |

---

## 5. Today's Plan

### Priority 1: ⚠️ Verify COPPER Restructure with Bean
- **What:** COPPER positions reversed direction and scaled 5x since yesterday
- **Action:** Confirm this was intentional. If yes, document rationale in journal.
- **If unintentional:** Investigate possible liquidation/auto-deleveraging event

### Priority 2: Deploy $9,300 xyz Idle → HypurrFi USDC (6.92%)
- **What:** Withdraw from spot-perp xyz dex → HypurrFi USDC
- **Wallet:** spot_perp (0x3c2c) → HypurrFi
- **Why still HypurrFi:** Felix concentration is RED (67.4%). Rate dropped from 8.30% to 6.92% but still above HyperLend USDC (5.61%). Diversification benefit remains.
- **Impact:** +$1.76/day

### Priority 3: Deploy $4,854 USDH → Felix USDH (6.21%)
- **What:** Move free USDH from unified L1 → Felix USDH vault
- **Wallet:** unified (0xd473) → EVM → Felix
- **Impact:** +$0.83/day. Rate crashed from 11.31% to 6.21% — less exciting but still earning vs 0%.
- **Note:** $90 stays locked as COPPER flx margin

### Priority 4: Deploy $4,943 USDC → HypurrFi USDC (6.92%)
- **What:** Move free USDC from unified L1 → HypurrFi USDC
- **Wallet:** unified (0xd473) → HypurrFi
- **Impact:** +$0.94/day. Same diversification logic as P2.

### Priority 5: Monitor Felix USDT0 Rate
- **What:** Watch whether 6.08% rate recovers or continues declining
- **Decision point:** If still below 8% by Apr 30 (day 3), escalate to deeper analysis
- **If rate stays depressed:** Evaluate partial rebalance — move $30-50k to HypurrFi USDT0 (6.28%) for diversification, or to HyperLend USDC if USDC rates hold
- **Context:** Last dip (Apr 25, 5.81%) recovered to 13.38% in 2 days. But this rate instability strengthens the argument for not having $110k in one volatile pool.

### Priority 6: HyperLend USDT Decision — Execute or Drop
- **What:** $50k target, 6 days overdue. Rate 5.26%.
- **Decision needed:** What's the actual blocker? If USDT availability, execute a USDC→USDT swap. If operational constraint, acknowledge and remove from plan.
- **Impact:** +$7.20/day at 5.26%
- **Note:** HyperLend USDT rate is volatile per lesson #8 (range 1.4-5.9%, 7d avg ~4%). At 5.26% today, it's above 7d average but don't project this forward.

**Total impact of P2-P4 (no blockers): +$3.53/day** → daily yield from $127.33 to ~$130.86/day (still $23/day below target)

---

## 6. Challenger Questions

1. **Felix USDT0 has now dipped below 8% twice in 4 days (5.81% on Apr 25, 6.08% today) with a 13.38% spike in between. Is this "recovering" or "dying in volatile spasms"?** The 14-day trigger is designed for sustained underperformance, but it resets after every recovery. What if the rate oscillates: 3 days below 8%, 1 day above, 3 days below, 1 day above — forever resetting the 14-day counter while averaging 7%? Today's $110k at 6.08% earns $18.35/day. The same capital at HyperLend USDC (5.61%) would earn $16.90/day — only $1.45/day difference but with much lower volatility. Is the optionality of a 13%+ spike worth the rollercoaster? **Should the trigger be redesigned: instead of "14 consecutive days < 8%," use "7d rolling average < 8%"?**

2. **Today's rate compression is concentrated on Felix/Morpho — all 4 vaults declined simultaneously.** HyperLend went UP (+5 bps). HypurrFi dipped moderately (-113 to -138 bps). This is a Felix-specific event, not market-wide. With 67.4% of deployed capital in Felix, a Felix-specific compression hits 2/3 of our earning power. **This is the concentration risk playing out in real time.** It's not a hack or exploit — it's the mild version: a rate compression that costs $28/day instead of $476k. The question isn't if Felix will compress again, but when. Every day we delay deploying to HypurrFi/HyperLend, we're betting this doesn't get worse.

3. **The HyperLend USDT $50k deployment has been "pending" for 6 days — that's now ~$43 in forfeited yield.** Meanwhile, the rate compression today makes diversification MORE urgent, not less. HyperLend USDC is the only position that went UP today. Deploying $50k to HyperLend USDT at 5.26% = $7.20/day immediately, plus it reduces Felix concentration by ~1%. The yield isn't spectacular, but it's STABLE — and stability is what the portfolio needs right now. **What is literally stopping this from happening today?**

---

## 7. Risk Watch

### Scenario: Sustained Felix Rate Compression (All Vaults Below 7% for 2+ Weeks)

**What:** Felix/Morpho rates have compressed across all vaults simultaneously. If this isn't a 1-day dip but the start of a broader lending rate decline on HyperEVM (e.g., new lending competition, decreased borrowing demand, protocol changes), all Felix positions would underperform.

**Current state:**
| Felix Vault | Peak (7d) | Today | Decline |
|-------------|-----------|-------|---------|
| USDC | 9.02% | 6.89% | -213 bps |
| USDT0 | 13.38% | 6.08% | -730 bps |
| USDe | 21.03% | 6.49% | -1,454 bps |
| USDH | 11.31% | 6.21% | -510 bps |

**Probability:** Medium. Lending rates are cyclical and correlated with on-chain borrowing demand. One-day compressions happen frequently. But the magnitude (all 4 vaults, -55 to -730 bps simultaneously) suggests a structural shift in borrowing demand, not random noise.

**Impact:** If Felix rates stabilize at today's levels (blended ~6.5% across vaults), daily lending yield drops to ~$87/day from Felix + $35/day from HyperLend = $122/day lending + $5/day trading = **$127/day** — exactly today's snapshot. This is a -$27/day sustained drag, meaning the portfolio earns ~$127/day ($46k/yr, 6.2% on $744k) instead of target $154/day.

**Trigger signal:** Felix USDT0 rate below 8% for 3+ consecutive snapshots. Felix USDC approaching 5% trigger. HypurrFi/HyperLend rates also declining (would confirm market-wide, not Felix-specific).

**Pre-planned response:**
1. **If 1-day dip (recovers by Apr 30):** No action needed. Continue monitoring.
2. **If sustained 3+ days:** Deploy all idle capital ($19k) to HypurrFi for diversification. Evaluate moving $50k from Felix USDT0 to HypurrFi USDT0.
3. **If 7+ days below 7% blended:** Full rebalance review. Move $76k+ from Felix to HypurrFi/HyperLend to bring concentration below 55%. Accept the yield haircut for survivability.
4. **Nuclear option (if Felix rates drop below 4%):** Exit Felix USDT0 entirely, park in HyperLend USDC or HypurrFi.

**Bottom line:** Today's compression is a stress test. The portfolio survived but yield dropped 18% in one day. The concentration risk thesis from yesterday's Challenger Q1 is no longer hypothetical — it happened, in mild form. Use this as motivation to accelerate diversification.

---

## Reviews Due Today (Apr 28)

Per REVIEW_SCHEDULE.md:
- [x] Felix USDC Main — **REVIEWED above.** Rate 6.89% (GREEN, 189 bps above 5% trigger). HOLD.
- [x] HyperLend USDC — **REVIEWED above.** Rate 5.61% (GREEN, 261 bps above 3% trigger). HOLD.
- [x] LINK hyna dust — **STILL PENDING cleanup.** 2.4 short, cumFunding -$5.95. Clean up when convenient.
- [x] HypurrFi USDT0 deployment — **STILL $0.** Rate 6.28% today (was 7.41%). Deployment less attractive at current rates but still needed for diversification.
- [x] HyperLend USDT deployment — **6 DAYS OVERDUE.** Needs decision: execute or drop.
- [x] Idle xyz USDC ($9,300) — **STILL PENDING.** Deploy to HypurrFi USDC (6.92%).
- [x] Idle USDH ($4,854 free) — **STILL PENDING.** Deploy to Felix USDH (6.21%).
- [x] Idle USDC unified ($4,943 free) — **STILL PENDING.** Deploy to HypurrFi USDC (6.92%).

---

*Generated 2026-04-28. Primary source: vault pulse (01:25 UTC on-chain verified). Rates from portfolio_state.md and rates_history.csv (7-day window). Next: daily vault-pulse + morning-review cycle.*
