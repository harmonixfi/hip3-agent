# Position Review Schedule

Last updated: 2026-05-03

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $351,900 | 5.75% ⚠️ | **2026-05-05 (Mon)** | APR < 5% for 3d (75 bps headroom — TIGHT) | Rotate $100-150K to HyperLend USDC. Research alternative USDC protocols. |
| HyperLend USDC | $230,311 | 5.58% ✅ | **2026-05-05 (Mon)** | APR < 3% (258 bps headroom) | Exit to Felix/HypurrFi |
| Felix USDT0 | $110,100 | 5.85% ⚠️ | **2026-05-04 (Sun) — DAY 7 HARD RE-EVAL** | APR < 8% for 2wk (YELLOW day 5 of 14) | USDT0 premium over USDC = 10 bps — uncompensated bridge risk. Evaluate full $110K USDT0→USDC rotation. Swap cost ~$27.50. Hard trigger fires May 11. |
| Felix USDC (alt) | $10,800 | 5.75% | **2026-05-08 (Thu)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 7.84% | **2026-05-08 (Thu)** | — | Small position. Best risk-adjusted rate in portfolio. |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $12,344 | 10.95% | **2026-05-08 (Thu)** | APR < 8% | Exit, redeploy to lending. Verify hyna funding spike ($19.17 vs $4.28/day expected). |
| LINK | $3,116 | 8.75% ⚠️ | **2026-05-05 (Mon)** — moved up | APR < 8% (75 bps headroom — TIGHT) | Exit, redeploy to lending. Cap rate lifted — real rate emerging. |
| LINK hyna dust | $22 | n/a | **2026-04-29 (Tue)** ⏰ **5 DAYS OVERDUE** | — | Clean up 2.4 short (cumFunding -$5.93). |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER | ~$3,929 | **2026-05-02 (Fri)** 🔴 **1 DAY OVERDUE** | EXIT IMMEDIATELY. flx cumFunding negative day 2 (-$0.36, was +$1.81). Net P&L -$20.19. Thesis broken per lesson #11. |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HyperLend USDT | $0 of $50k | ❗ **12 DAYS OVERDUE.** Rate dropped to 5.17% (was 6.06%). ~$97 cumulative foregone yield. Execute or formally drop by May 5. | **OVERDUE — final decision by 2026-05-05** |
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0. Rate 6.06%. USDT0 thesis weakening (all USDT0 rates <8%). Consider formally dropping if day-7 USDT0 review recommends exit. | **2026-05-05 (Mon)** |
| Idle xyz USDC | $9,300 | ⏰ **12 days idle.** Deploy → Felix USDC (5.75%). HypurrFi USDC crashed to 2.91% — not viable for diversification. ~$22 cumulative foregone. | **OVERDUE — execute ASAP** |
| Idle USDH (unified) | $4,965 (all freed post-COPPER exit) | Deploy → Felix USDH (5.72% — crashed from 9.90%). Reassess rate before deploying. | **Execute after COPPER exit** |
| Idle USDC (unified) | $5,006 (all freed post-COPPER exit) | Deploy → Felix USDC (5.75%). | **Execute after COPPER exit** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Path to Reduce |
|----------|---------|-----|--------|----------------|
| Felix/Morpho | 67.4% ($476K) | 50% | RED — 17pts over cap | HyperLend USDT deploy (-5.9pts → 61.5%). But idle USDC redeploy to Felix worsens it. Structural issue — needs new protocol or larger HyperLend allocation. |
| USDT0 exposure | 14.8% ($110K) | 25% ($200K) | GREEN | USDT0 thesis broken (5.85% vs USDC 5.75% = 10bps premium). Day 7 review may trigger USDT0→USDC rotation. If so, USDT0 drops to 0%. |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-05-03 | COPPER | **EXIT (1 day overdue)** | flx cumFunding negative day 2 (-$0.36). Net P&L -$20.19. Thesis broken. Deteriorated -$15 from yesterday's -$5.50. |
| 2026-05-02 | COPPER | **EXIT (recommended)** | flx cumFunding decreased $3.10→$1.81 — short side paid funding, thesis broken. Net P&L: -$5.50. |
| 2026-05-01 | FARTCOIN | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (-0.4%). Next review May 8. |
| 2026-05-01 | LINK | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (1.1%). Next review May 8. |
| 2026-04-30 | Felix USDT0 | HOLD (day-3 review) | Rate 6.48%, still below 8% (YELLOW day 3). HypurrFi USDT0 rate (6.36%) lower — move not justified. HOLD until day 7 (May 4). |
| 2026-04-29 | COPPER | HOLD (reviewed) | cumFunding $3.64, uPnL -$11.72 net. Hard exit May 2 if not break-even. |
| 2026-04-29 | Felix USDT0 | WATCH (YELLOW day 2) | Rate partial recovery 6.08%→6.48%. Still below 8%. |
| 2026-04-29 | Felix USDC Main | WATCH (rate sliding) | Rate 6.39% — 3-day slide. 139 bps headroom vs 5% trigger. |
| 2026-04-28 | Felix USDC Main | HOLD (reviewed) | Rate 6.89% (GREEN, 189 bps above 5% trigger). |
| 2026-04-28 | HyperLend USDC | HOLD (reviewed) | Rate 5.61% (GREEN, 261 bps above 3% trigger). |
| 2026-04-28 | Felix USDT0 | WATCH (YELLOW day 1) | Rate crashed 13.38% → 6.08%. |
| 2026-04-27 | FARTCOIN | HOLD (recovered) | Funding recovered to 10.95% from 1.78%. |
| 2026-04-27 | LINK | HOLD (RED cleared) | Funding recovered to 10.95% from 7.59%. |
| 2026-04-27 | Felix USDT0 | HOLD (YELLOW cleared) | Rate surged to 13.38%. Idle USDT0 deployed. |
| 2026-04-25 | USDT0 swap order | CLOSED (completed) | ~$49.84k USDC swapped to USDT0. All deployed. |
| 2026-04-23 | LINK | HOLD (overrode EXIT signal) | Funding recovered from -8.04% to +10.95% overnight |
| 2026-04-22 | OIL_BRENTOIL | EXIT (CLOSED) | Per deployment plan — capital redeployed to lending |
| 2026-04-22 | hyna:LINK | EXIT (CLOSED) | Restructured to native-only. 2.4 dust remains. |
| 2026-03-30 | ALL | HOLD all, no changes | 3 days too early for rotation |
| 2026-03-28 | ORCL | EXIT (CLOSED) | 15d avg -$1.33, slow recovery |
| 2026-03-28 | MU | EXIT (CLOSED) | +$2.85 lifetime, rotated to crypto |
| 2026-03-28 | CRCL | EXIT (CLOSED) | +$5.47 lifetime, locked profit |
| 2026-03-25 | MSTR | EXIT (CLOSED) | Dead money, $0.02/day on $982 notional |
