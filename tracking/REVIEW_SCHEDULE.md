# Position Review Schedule

Last updated: 2026-05-01

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $351,800 | 7.08% ✅ | **2026-05-05 (Mon)** | APR < 5% for 3d (308 bps headroom — recovered from 139) | Rotate excess above $300k to HypurrFi USDC or HyperLend. Pre-plan: at 5.5% alert, at 5% start rotation. |
| HyperLend USDC | $230,276 | 5.35% | **2026-05-05 (Mon)** | APR < 3% (235 bps headroom) | Exit to Felix/HypurrFi |
| Felix USDT0 | $110,100 | 6.78% ⚠️ | **2026-05-04 (Sun)** | APR < 8% for 2wk (YELLOW day 4 of 14) | Day 7 hard re-evaluation. If still below 8% with no recovery above 10%, begin partial rotation ($30-50k to HypurrFi USDT0). Hard partial-rebalance if drops below 5%. |
| Felix USDC (alt) | $10,800 | 7.08% | **2026-05-08 (Thu)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 7.80% | **2026-05-08 (Thu)** | — | Small position. Monitor. |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $11,936 | 10.95% | **2026-05-08 (Thu)** | APR < 8% | Exit, redeploy to lending. Funding is binary (cap or dead). |
| LINK | $3,121 | 10.95% | **2026-05-08 (Thu)** | APR < 8% | Exit — funding is binary. Quick exit on flip. |
| LINK hyna dust | $22 | n/a | **2026-04-29 (Tue)** ⏰ **OVERDUE** | — | Clean up residual 2.4 short (cumFunding -$5.93). 3 days overdue. |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER | $3,965 | **2026-05-02 (Fri)** ⚠️ **TOMORROW** | 329.6 xyz LONG / 329.6 flx SHORT. cumFunding $3.84, uPnL -$9.34 net. Margin holds $3,990. **flx cumFunding DECREASED $3.10→$1.81 — verify.** Decision matrix: if flx funding negative → EXIT; if data artifact → HOLD if break-even in 3d; if unclear → EXIT. |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0. Rate 6.16%. Deprioritize unless Felix USDT0 stays below 8% past day 7. Consider redirecting $100k target to USDC lending if USDT0 thesis weakened. | **2026-05-05 (Mon)** |
| HyperLend USDT | $0 of $50k | **9 DAYS OVERDUE.** Rate 6.06% (May 1). ~$75 cumulative foregone yield. Execute USDC→USDT swap + deploy, or formally drop. | **2026-05-01 (Thu)** ⏰ **OVERDUE** |
| Idle xyz USDC | $9,300 | **10 days idle.** Deploy → Felix USDC (7.08%) for yield or HypurrFi USDC (6.06%) for diversification. ~$17 cumulative foregone yield. | **2026-05-01 (Thu)** ⏰ **OVERDUE** |
| Idle USDH | $2,954 free | Deploy → Felix USDH (9.90%) — best rate available. | **2026-05-01 (Thu)** ⏰ **OVERDUE** |
| Idle USDC unified | $3,043 free | Deploy → HypurrFi USDC (6.06%). | **2026-05-01 (Thu)** ⏰ **OVERDUE** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Review |
|----------|---------|-----|--------|--------|
| Felix/Morpho | 67.4% ($476k) | 50% | RED — 17pts over cap. Path to reduce: deploy $50k HyperLend USDT (-6.7pts) + idle to HypurrFi (-1.3pts) → ~59.4%. | Execute pending deployments. |
| USDT0 exposure | 14.8% ($110k) | 25% ($200k) | GREEN | Under cap. USDT0 thesis weakening (rate 6.78% vs 15.39% plan, spread widening). May cap at $110k. |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-05-01 | FARTCOIN | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (-0.4%). Next review May 8. |
| 2026-05-01 | LINK | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (1.1%). Next review May 8. |
| 2026-04-30 | Felix USDT0 | HOLD (day-3 review) | Rate 6.48%, still below 8% (YELLOW day 3). HypurrFi USDT0 rate (6.36%) lower — move not justified. HOLD until day 7 (May 4). Hard partial-rebalance if drops below 5%. |
| 2026-04-29 | COPPER | HOLD (reviewed) | cumFunding $3.64, uPnL -$11.72 net. Margin holds ballooned to $3,990. HOLD — hard exit May 2 if not break-even on funding vs uPnL. |
| 2026-04-29 | Felix USDT0 | WATCH (YELLOW day 2) | Rate partial recovery 6.08%→6.48%. Still below 8%. Check day 3 on Apr 30. |
| 2026-04-29 | Felix USDC Main | WATCH (rate sliding) | Rate 6.39% — 3-day slide at ~50 bps/day. 139 bps headroom vs 5% trigger. GREEN but tightening. |
| 2026-04-28 | Felix USDC Main | HOLD (reviewed) | Rate 6.89% (GREEN, 189 bps above 5% trigger). Settling toward plan target. |
| 2026-04-28 | HyperLend USDC | HOLD (reviewed) | Rate 5.61% (GREEN, 261 bps above 3% trigger). Most stable position — 5-day uptrend. |
| 2026-04-28 | Felix USDT0 | WATCH (YELLOW day 1) | Rate crashed 13.38% → 6.08%. Second dip below 8% in 4 days. Check again Apr 30. |
| 2026-04-27 | FARTCOIN | HOLD (overdue review — recovered) | Funding recovered to 10.95% from 1.78%. Cap rate regime restored. |
| 2026-04-27 | LINK | HOLD (RED cleared) | Funding recovered to 10.95% from 7.59%. Back at cap rate. |
| 2026-04-27 | Felix USDT0 | HOLD (YELLOW cleared) | Rate surged to 13.38% from 5.81%. Idle USDT0 deployed ($80k → $110k). |
| 2026-04-25 | USDT0 swap order | CLOSED (completed) | ~$49.84k USDC swapped to USDT0. All deployed to Felix USDT0. |
| 2026-04-23 | LINK | HOLD (overrode EXIT signal) | Funding recovered from -8.04% to +10.95% overnight |
| 2026-04-22 | OIL_BRENTOIL | EXIT (CLOSED) | Per deployment plan — capital redeployed to lending |
| 2026-04-22 | hyna:LINK | EXIT (CLOSED) | Restructured to native-only. 2.4 dust remains. |
| 2026-03-30 | ALL | HOLD all, no changes | 3 days too early for rotation |
| 2026-03-28 | ORCL | EXIT (CLOSED) | 15d avg -$1.33, slow recovery |
| 2026-03-28 | MU | EXIT (CLOSED) | +$2.85 lifetime, rotated to crypto |
| 2026-03-28 | CRCL | EXIT (CLOSED) | +$5.47 lifetime, locked profit |
| 2026-03-25 | MSTR | EXIT (CLOSED) | Dead money, $0.02/day on $982 notional |
