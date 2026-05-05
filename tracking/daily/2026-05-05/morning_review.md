# Morning Review — 2026-05-05

**Data:** Vault pulse 2026-05-04 (~01:35 UTC). No May 5 vault-pulse snapshot available — using latest data. Rates from rates_history.csv (13-day window: Apr 22 – May 4). All lessons from docs/lessons.md applied.

**HEADLINE:** Portfolio running hot at **$197.16/day (128% target)** but this is a single-day spike — not a new baseline. Per lesson #8, HyperLend USDC at 11.33% and Felix USDT0 at 12.16% are utilization-driven and will likely mean-revert to 5-6% and 7-8% respectively within 1-3 days, pulling yield back to ~$146-165/day. **COPPER EXIT now 3 DAYS OVERDUE** (5th consecutive recommendation). GOLD position remains undocumented. **HyperLend USDT $50K hits HARD DEADLINE today** — default to DROP if no decision. 14-day deploy backlog. Felix concentration stuck at 67.4% (RED).

---

## 1. Portfolio Health

| Metric | Today (May 4 data) | Yesterday (May 3) | Target | Status |
|--------|--------------------|--------------------|--------|--------|
| Total Portfolio | $745,711 | $745,601 | $800k | YELLOW (-6.8%) |
| Deployed % | 94.8% ($706,985) | 94.8% ($706,948) | >85% | GREEN |
| Daily Yield | **$197.16/day** | $153.43/day | $154/day | GREEN — 128% of target |
| Blended APY | **10.18%** | 7.92% | 7.04% | GREEN — 314 bps above target |
| USDT0 Exposure | $110,200 (14.8%) | $110,200 (14.8%) | <$200k (25%) | GREEN |
| Largest Protocol | Felix 67.4% ($476,600) | Felix 67.4% ($476,600) | <50% | **RED (+17.4pts over cap)** |
| Idle Capital | $18,548 (2.5%) | $19,282 (2.6%) | <$20k | GREEN |

**So what:** The $197/day headline is misleading as a forward-looking number. Per lesson #8, 73% of the +$45/day improvement came from a single utilization spike on HyperLend USDC (6.01%→11.33%). In 13 days of data, HyperLend USDC has never printed above 6.01% except today. **Realistic forward run-rate: $150-170/day.** The structural drags remain unchanged for the 4th consecutive day: Felix concentration at RED (67.4%), HyperLend USDT $50K undeployed (14 days), HypurrFi USDT0 $0 of $100K deployed, and ~$15.5K free idle capital earning nothing. The portfolio is earning well because lending rates ran hot — not because execution improved.

---

## 2. Position Status

### RED — Immediate Action

```
COPPER (xyz+flx) — 🔴 EXIT 3 DAYS OVERDUE (DAY 5 OF BROKEN THESIS)
  xyz LONG: 329.6 @ entry 6.063, mark 5.950 | uPnL -$37.11
  flx SHORT: 329.6 @ entry 5.998, mark 5.951 | uPnL +$15.51
  Net uPnL: -$21.60
  cumFunding: +$2.71 ($3.33 xyz - $0.62 flx)
  Net P&L: -$18.89 UNDERWATER

  flx cumFunding trajectory: +$3.10 → +$1.81 → -$0.36 → -$0.36 → -$0.62
  5 consecutive days of broken thesis. Bleeding resumed Day 4 after 1-day pause.
  xyz LONGs earning positive funding (unusual — trade fully inverted).

  VERDICT: EXIT IMMEDIATELY (5th consecutive recommendation)
  - Realized loss: ~$19 (cumFunding $2.71 - uPnL $21.60)
  - Margin freed: ~$3,977 ($1,963 USDC + $2,014 USDH)
  - Each day of delay: ~-$0.26 funding + MTM swing risk
  - 5 reviews have now recommended exit. Loss is growing, not shrinking.
```

### YELLOW — Monitoring

```
GOLD spot-perp (NEW — DAY 2) — 🟡 THESIS UNDOCUMENTED
  Spot: 0.1599 XAUT0 @ $4,586.25/oz = $733
  Short: 0.1728 xyz:GOLD @ $4,600 = $795 notional
  uPnL: +$2.32 | cumFunding: +$0.37
  Delta: -8% net short (spot 0.1599 vs short 0.1728 — wider than spec)
  Funding rate: NOT VISIBLE from standard API (xyz builder dex)
  Review due: May 7

  ⚠️ 3 open issues remain from May 4 review:
  1. Delta -8% — intentional or sizing error?
  2. No automated trigger evaluation possible (builder dex)
  3. Consumed $737 idle that was earmarked for deployment plan
  Position is small (~$1,528) so risk is contained. But running
  undocumented positions is a process violation, not a size issue.
```

```
Felix Concentration — 🟡 STRUCTURAL (UNCHANGED DAY 4)
  Felix/Morpho: 67.4% of deployed ($476,600) | Cap: 50%
  Breach: +17.4 percentage points (~$118K excess)
  No path to resolution without deploying to HyperLend/HypurrFi.
  Today's HyperLend USDT deadline may determine trajectory.
```

```
HyperLend USDT $50K — 🟡 HARD DEADLINE TODAY (14 DAYS OVERDUE)
  Rate: 5.49% (7d avg unknown — insufficient data points at 5.49%)
  Original plan target: $50,000 at 5.79%
  Status: $0 deployed. 14 days since deployment plan created.
  Per May 4 review: default to DROP if no action by May 5.
  Decision options remain: A) Deploy as planned. B) Redirect to
  HyperLend USDC. C) Formally drop, redirect to Felix USDC.
```

### GREEN — On Track (sorted by daily $ contribution)

```
lend_felix_usdc_main — ✅ HOLD
  Rate: 8.20% APY (13d range: 5.16-9.02%) — stable mid-range
  Amount: $352,000 (117% of $300K target)
  Daily: $79.05 | Trigger: APR<5% for 3d → GREEN (320 bps headroom)
  Trend: 5.75→8.48→8.20 — stabilized after May 2 scare
  Note: Anchor position. Rate back in healthy zone after dip to 5.75%.

lend_hyperlend_usdc — ✅ HOLD (BIGGEST CONTRIBUTOR — SPIKE WARNING)
  Rate: 11.33% APY (13d range: 3.84-11.33%) — ALL-TIME HIGH
  Amount: $230,385 (100% of target)
  Daily: $71.52 | Trigger: APR<3% → GREEN (833 bps headroom)
  Per lesson #8: 7d avg ~5.5%. Today's 11.33% is a spike.
  13-day history: never above 6.01% until today. Zero precedent.
  Forward projection: use $35-38/day, not $71.52/day.

lend_felix_usdt0 — ✅ HOLD (COUNTER RESET)
  Rate: 12.16% APY (13d range: 5.81-15.39%) — strong recovery
  Amount: $110,200 (110% of $100K target)
  Daily: $36.72 | Trigger: APR<8% for 2wk → GREEN (counter at 0)
  Trend: 5.85→8.53→12.16 — sharp V-recovery from Day 5 YELLOW
  USDT0/USDC premium: 396 bps — bridge risk fully compensated.

pos_fartcoin_native+hyna — ✅ HOLD
  Rate: 13.00% APR (+205 bps from 10.95% cap)
  Notional: $12,408 spot / $12,450 short | Daily: $4.43
  cumFunding: $247.01 total ($24.11 native + $222.90 hyna)
  Delta: -0.4% — neutral ✓ | hyna spike +$17.80 yesterday

pos_link_native — ✅ HOLD
  Rate: 10.95% APR (flat at cap) | Notional: $3,090 | Daily: $0.93
  cumFunding: $29.56 | Delta: 1.1% — neutral ✓

lend_felix_usde — ✅ HOLD (tiny)
  Rate: 17.76% (spike, per lesson #8) | $3,600 | $1.75/day

lend_felix_usdc_alt — ✅ HOLD | $10,800 @ 8.20% | $2.43/day

pos_link_hyna_dust — ⏰ CLEANUP 7 DAYS OVERDUE | $22 | cumFunding -$5.91
```

### IDLE — Deploy Candidates

| Item | Amount | Days Idle | Best Target | Rate | Daily $ |
|------|--------|-----------|-------------|------|---------|
| xyz dex idle | $6,300 | **14 days** | Felix USDC | 8.20% | +$1.42 |
| Native spot buffer | $3,000 | 2 days | Hold (margin) | — | $0 |
| Unified USDC free | $2,270 | ongoing | Felix USDC | 8.20% | +$0.51 |
| Unified USDH free | $2,954 | ongoing | Felix USDH | 6.72% | +$0.54 |
| **Total free idle** | **$11,524** | | | | **+$2.47/day** |

Post-COPPER exit adds ~$3,977, bringing free idle to ~$15,500 (+$3.28/day at Felix rates).

---

## 3. Trigger Check

| Trigger | Rule | Current | Headroom | Consec. Days Below | Status |
|---------|------|---------|----------|--------------------|--------|
| Felix USDC | APR < 5% for 3d | 8.20% | 320 bps | 0 | GREEN |
| HyperLend USDC | APR < 3% | 11.33% | 833 bps | — | GREEN |
| Felix USDT0 | APR < 8% for 2wk | 12.16% | 416 bps | 0 (RESET from Day 5) | GREEN |
| HypurrFi USDT0 | APR < 5% (not deployed) | 7.40% | 240 bps | — | GREEN |
| HyperLend USDT | (not deployed) | 5.49% | — | — | N/A |
| LINK funding | APR < 8% | 10.95% | 295 bps | 0 | GREEN |
| FARTCOIN funding | APR < 8% | 13.00% | 500 bps | 0 | GREEN |
| USDT0 depeg > 1% (watch) | spread | 2.0 bps | 98 bps | — | GREEN |
| USDT0 depeg > 3% (exit) | spread | 2.0 bps | 298 bps | — | GREEN |
| Any lending < 3% | all rates | lowest 5.49% | 249 bps | — | GREEN |
| Felix concentration | < 50% | 67.4% | -17.4pts | structural | **RED** |

**All rate triggers GREEN.** The Felix USDT0 counter fully reset from Day 5 — the 2-week evaluation is a clean slate. USDT0 spread at 2.0 bps is as tight as it gets.

**Per lesson #8:** HyperLend USDC's 833 bps headroom is inflated by the spike. At 7d avg (~5.5%), effective headroom is ~250 bps. Still GREEN, but not as comfortable as the headline suggests.

---

## 4. Yesterday → Today

### Action Items from May 4 Morning Review

| # | Action | Status |
|---|--------|--------|
| P1 | COPPER EXIT (both legs) | ❗ **OVERDUE — 3 DAYS.** 5th consecutive recommendation. No execution logged. |
| P2 | Document GOLD thesis | ❗ **OVERDUE.** No thesis file found. Position running 2 days undocumented. |
| P3 | LINK hyna dust cleanup | ⏰ **OVERDUE — 7 days.** cumFunding -$5.91. |
| P4 | Deploy xyz idle $6,300 → Felix USDC | ⏰ **14 DAYS IDLE.** No action. |
| P5 | HyperLend USDT $50k — decide (Option A/B/C) | ❗ **TODAY IS HARD DEADLINE.** May 4 review said "default to DROP if no action by May 5." |

**0 of 5 action items executed.** This is the 3rd consecutive day with zero backlog progress. The morning review is functioning as a diagnostic log, not a decision driver.

### Material Changes Expected (May 4 → May 5)

No new vault-pulse data for May 5. Changes to watch when vault-pulse runs:
- HyperLend USDC: will the 11.33% spike sustain or revert? (per lesson #8, HIGH probability of reversion)
- Felix USDT0: 12.16% — second consecutive day needed to confirm recovery vs spike
- FARTCOIN: 13.00% — first day above cap rate, watch for sustainability
- COPPER: cumFunding trajectory — is bleed accelerating?

---

## 5. Today's Plan

### Priority 1 — 🔴 COPPER EXIT (3 DAYS OVERDUE — 5th RECOMMENDATION)

- **What:** Close both legs (329.6 xyz LONG + 329.6 flx SHORT)
- **Wallet:** unified (0xd473)
- **Why:** Day 5 of broken thesis. flx cumFunding trajectory: +$3.10→+$1.81→-$0.36→-$0.36→-$0.62. Thesis fully inverted. Net P&L -$18.89 and worsening. This is the 5th review recommending exit. The loss is $19 now — it could be $25+ by May 6 if spread widens further.
- **Freed capital:** ~$3,977 ($1,963 USDC + $2,014 USDH)
- **Impact:** Stops -$0.26+/day bleed. Frees margin for redeployment to lending at 6-8% → +$0.73-0.87/day swing.

### Priority 2 — 📋 HyperLend USDT $50K DECISION (HARD DEADLINE)

Per May 4 review, today is the default-to-DROP deadline. Options:

| Option | Deploy To | Rate | Daily $ | Pros | Cons |
|--------|-----------|------|---------|------|------|
| A | HyperLend USDT $50K | 5.49% | +$7.52 | Diversifies. Plan-aligned. | HyperLend USDT 7d range: 5.12-6.27% — volatile. Need USDT source. |
| B | HyperLend USDC $50K | 5.5% (7d avg) | +$7.53 | Same diversification. Simpler execution. | Sizes up an already-at-target position. |
| C | DROP — redirect to Felix USDC | 8.20% | +$11.23 | Highest yield. No USDT conversion. | Felix concentration → ~70%. |

**If no explicit decision by end of day: auto-execute Option C** (drop HyperLend USDT slot, redirect next idle USDC to Felix, update deployment plan).

### Priority 3 — 📋 DOCUMENT GOLD THESIS

- Write 1-paragraph entry: why opened, expected funding, exit conditions, delta target
- Address the 3 open questions: (a) Is -8% delta intentional? (b) How will builder dex funding be monitored? (c) Size cap?
- 5 minutes of work. No capital at risk from delay, but process integrity matters.

### Priority 4 — Deploy Free Idle ($11,524 → $15,501 post-COPPER)

| Wallet | Amount | Target | Rate | Daily |
|--------|--------|--------|------|-------|
| xyz dex | $6,300 | Felix USDC | 8.20% | +$1.42 |
| unified USDC free | $2,270 | Felix USDC | 8.20% | +$0.51 |
| unified USDH free | $2,954 | Felix USDH | 6.72% | +$0.54 |
| Post-COPPER USDC | $1,963 | Felix USDC | 8.20% | +$0.44 |
| Post-COPPER USDH | $2,014 | Felix USDH | 6.72% | +$0.37 |
| **Total** | **$15,501** | | | **+$3.28/day** |

### Priority 5 — LINK hyna Dust Cleanup (7 DAYS OVERDUE)

- Close 2.4 hyna:LINK short. cumFunding -$5.91. Literally 30 seconds.

**If Bean has 15 minutes today:**
1. Exit COPPER (5 min)
2. Decide HyperLend USDT — A, B, or C (2 min)
3. Close hyna:LINK dust (30 sec)
4. Write 1-paragraph GOLD thesis (5 min)

**If Bean has 30 minutes:** Add idle capital deployment ($6.3K xyz + unified free).

---

## 6. Challenger Questions

1. **The COPPER exit has now been recommended 5 times across 5 consecutive reviews. Net P&L is -$18.89 and the flx cumFunding trajectory is strictly worsening (+$3.10→-$0.62).** What is the actual blocker? If it's operational (multi-dex exit sequencing, gas timing), document the friction and I can help plan the execution steps. If it's "I'll get to it," the math is simple: each day of delay costs ~$0.26 in direct funding bleed plus opportunity cost of $3,977 locked margin ($0.73/day at Felix rates). That's $1.00/day total — which sounds small until you note that the GOLD position you DID find time to open earns $0.37/day in cumFunding so far. **Closing COPPER frees more daily value than GOLD generates.**

2. **Felix USDT0 has now whipsawed: 15.39%→5.81%→12.16% in 13 days. The 2-week YELLOW counter triggered at Day 5, we were preparing for full rotation, then the rate spiked 631 bps in 2 days and the counter reset.** This pattern will repeat. The current trigger framework (APR<8% for 14 consecutive days) is designed for gradual decay, not for a pool that oscillates ±400 bps every 3-5 days. **Should we add a "volatility filter" — if the trailing 14d rate has a standard deviation >300 bps, consider it structurally unstable regardless of whether it happens to be above 8% today?** At $110K exposure, the difference between 5.81% and 12.16% is $19/day in daily yield — that's a planning problem, not just a monitoring problem.

3. **The morning review has now produced 0 completed action items for 3 consecutive days (May 3, 4, 5).** Meanwhile, a new position (GOLD) was opened that was NOT on any review's action list, and capital was moved ($3K to native spot) in a way that contradicted the review's deployment recommendation. The pattern suggests the review is being read for market awareness but not used as an execution checklist. **Two options: (A) Accept this and re-scope the review to be purely informational — stop tracking action items, overdue counts, and deadlines. (B) Carve out 15 minutes after each review specifically for backlog execution.** Option A is honest; Option B is effective. Which one matches how this actually works?

---

## 7. Risk Watch

### Scenario: Execution Drift Compounds Into Material Opportunity Cost

```
Scenario: The deploy backlog (14 days and growing) compounds into a
          structural yield gap that offsets rate gains.

Current idle capital: $15,501 (free idle + post-COPPER exit)
Opportunity cost at weighted avg lending rate (7.5%): $3.18/day

If backlog persists another 7 days:
  - 21 total days × $3.18/day = $66.80 in foregone yield
  - Add COPPER bleed: 7 × $1.00/day = $7.00
  - Total: ~$74 opportunity cost from inaction alone

For context: This exceeds the lifetime cumFunding earned by
COPPER ($2.71), GOLD ($0.37), and LINK ($29.56) — combined.

Probability: HIGH — 3 consecutive zero-execution days is a pattern,
             not a one-off.

Trigger signal:
  - May 6 review shows 0 action items completed → pattern confirmed
  - Any review shows >$20K idle for >14 days → systemic

Pre-planned response:
  1. If 0 execution by May 6: propose "auto-deploy" rule — idle USDC
     >$5K for >7 days auto-routes to Felix USDC (highest rate among
     USDC options) unless explicitly blocked.
  2. If COPPER still open by May 6: escalate from "recommend exit"
     to "this is a dead position — remove from tracking and stop
     reporting on it" to free review bandwidth.
  3. Consider whether the 15-min morning review execution block
     should become part of vault-pulse (auto-deploy script).
```

**Previous risk scenarios covered:** rate collapse (Apr 28), COPPER negative funding (May 1), USDT0 depeg (Apr 29), deployment drift (May 2), Felix USDC trigger (May 3), rate mean-reversion (May 4). Today's focus: execution drift — the meta-risk that correct analysis without timely action is no better than wrong analysis.

---

## Reviews Due Today (May 5)

| Item | Status | Action Required |
|------|--------|-----------------|
| **COPPER EXIT** | 🔴 **3 DAYS OVERDUE** | EXIT both legs. -$18.89 and Day 5 broken thesis. 5th recommendation. |
| **HyperLend USDT $50K** | ❗ **HARD DEADLINE** | Decide Option A/B/C. Default = DROP + redirect to Felix USDC. |
| GOLD position docs | 🟡 **2 DAYS OVERDUE** | Write thesis + monitoring plan. |
| Deploy xyz idle $6,300 | ⏰ **14 DAYS IDLE** | → Felix USDC (8.20%). +$1.42/day. |
| Deploy USDH unified $2,954 | ⏰ PENDING | → Felix USDH (6.72%). +$0.54/day. |
| Deploy USDC unified $2,270 | ⏰ PENDING | → Felix USDC (8.20%). +$0.51/day. |
| LINK hyna dust cleanup | ⏰ **7 DAYS OVERDUE** | Close 2.4 short. 30 seconds. |
| HyperLend USDC spike check | 📊 May 6 | Review if 11.33% sustained or reverted. Per lesson #8. |
| Felix USDT0 recovery confirm | 📊 May 8 | Verify 12.16% holds for 3+ days. |
| GOLD position review | 📊 May 7 | First review — requires funding data. |

**Bean — the backlog now has 7 active items including 2 at RED/DEADLINE priority. 15 minutes of execution time today would clear 4 of them (COPPER, hyna dust, HyperLend USDT decision, GOLD docs). The morning review cannot substitute for execution. It can only make the cost of not executing increasingly visible.**

---

*Generated 2026-05-05. Primary source: vault pulse 2026-05-04 (~01:35 UTC) — no May 5 snapshot available. Rates from rates_history.csv (13-day window). All lessons applied (cited: #8, #10, #11). Critical: COPPER 3 days overdue (5th rec) + HyperLend USDT hard deadline + execution drift pattern (0 actions/3 days) + rate mean-reversion risk.*
