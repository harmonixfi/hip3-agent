# Position Review Schedule

Last updated: 2026-05-02

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $351,800 | 7.08% ✅ | **2026-05-05 (Mon)** | APR < 5% for 3d (308 bps headroom) | Rotate excess above $300k to HypurrFi USDC or HyperLend. |
| HyperLend USDC | $230,276 | 5.35% | **2026-05-05 (Mon)** | APR < 3% (235 bps headroom) | Exit to Felix/HypurrFi |
| Felix USDT0 | $110,100 | 6.78% ⚠️ | **2026-05-04 (Sun) — DAY 7 HARD RE-EVAL** | APR < 8% for 2wk (YELLOW day 5 of 14) | If still below 8% with no recovery above 10%, evaluate partial rotation ($30-50k). Also evaluate USDT0→USDC exit path if all USDT0 rates are depressed. Hard trigger fires May 11. |
| Felix USDC (alt) | $10,800 | 7.08% | **2026-05-08 (Thu)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 7.80% | **2026-05-08 (Thu)** | — | Small position. Monitor. |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $11,936 | 10.95% | **2026-05-08 (Thu)** | APR < 8% | Exit, redeploy to lending. |
| LINK | $3,121 | 10.95% | **2026-05-08 (Thu)** | APR < 8% | Exit, redeploy to lending. |
| LINK hyna dust | $22 | n/a | **2026-04-29 (Tue)** ⏰ **4 DAYS OVERDUE** | — | Clean up 2.4 short (cumFunding -$5.93). |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER | $3,965 | **2026-05-02 (Fri)** 🔴 **TODAY** | VERDICT: EXIT. flx cumFunding decreased $3.10→$1.81 — short side paid funding, thesis broken. Net P&L: -$5.50. Close both legs, redeploy freed capital to lending (USDH → Felix 9.90%, USDC → HypurrFi 6.06%). |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HyperLend USDT | $0 of $50k | ❗ **10 DAYS OVERDUE.** Rate ~5.5% 7d avg. ~$83 cumulative foregone yield. Execute or formally drop. | **OVERDUE — decide by 2026-05-05** |
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0. Rate 6.16%. Deprioritize unless Felix USDT0 exits. Consider redirecting $100k target to USDC if USDT0 thesis weakened. | **2026-05-05 (Mon)** |
| Idle xyz USDC | $9,300 | ⏰ **11 days idle.** Deploy → HypurrFi USDC (6.06%) for diversification. ~$19 cumulative foregone. | **OVERDUE — execute ASAP** |
| Idle USDH (unified) | $2,954 free (+ $2,001 if COPPER exits) | Deploy → Felix USDH (9.90%). Best rate available. | **OVERDUE — execute after COPPER exit** |
| Idle USDC (unified) | $3,043 free (+ $1,989 if COPPER exits) | Deploy → HypurrFi USDC (6.06%). | **OVERDUE — execute after COPPER exit** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Path to Reduce |
|----------|---------|-----|--------|----------------|
| Felix/Morpho | 67.4% ($476k) | 50% | RED — 17pts over cap | Deploy $50k HyperLend USDT (-5.9pts) + idle USDC to HypurrFi (-1.3pts) → ~60.2%. Still above 50%. |
| USDT0 exposure | 14.8% ($110k) | 25% ($200k) | GREEN | USDT0 thesis weakening (6.78% vs 15.39% plan). May cap at $110k and redirect HypurrFi target to USDC. |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-05-02 | COPPER | **EXIT (recommended)** | flx cumFunding decreased — short side paid funding. Thesis broken. -$5.50 net after 10 days. Redeploy freed capital to lending. |
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
