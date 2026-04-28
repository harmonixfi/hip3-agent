# Position Review Schedule

Last updated: 2026-04-28

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $351,700 | 6.89% | **2026-05-05 (Mon)** | APR < 5% for 3d | Rotate excess above $300k to HypurrFi USDC or HyperLend |
| HyperLend USDC | $230,175 | 5.61% | **2026-05-05 (Mon)** | APR < 3% | Exit to Felix/HypurrFi |
| Felix USDT0 | $110,100 | 6.08% ⚠️ | **2026-04-30 (Wed)** | APR < 8% for 2wk (YELLOW day 1) | If still below 8% on Apr 30: evaluate partial rebalance to HypurrFi USDT0 |
| Felix USDC (alt) | $10,800 | 6.89% | **2026-05-04 (Sun)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 6.49% | **2026-05-04 (Sun)** | — | Collateral position. Rate crashed from 15% — monitor |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $12,034 | 10.95% | **2026-05-01 (Thu)** | APR < 8% | Exit, redeploy $12k to lending. Funding is binary (cap or dead). |
| LINK | $3,194 | 10.95% | **2026-05-01 (Thu)** | APR < 8% | Exit — funding is binary. Quick exit on flip. |
| LINK hyna dust | $22 | n/a | **2026-04-29 (Tue)** | — | Clean up residual 2.4 short (paying -$5.95 cumulative). Overdue. |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER | $3,991 ⚠️ | **2026-04-29 (Tue)** | Positions reversed direction + 5x scaled. Now 329.6 xyz LONG / 329.6 flx SHORT. cumFunding $0.97. **VERIFY with Bean.** |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0. Rate 6.28% (down from 7.41%). Deprioritize unless Felix USDT0 stays below 8% | **2026-05-05 (Mon)** |
| HyperLend USDT | $0 of $50k | Blocked — need USDT availability or USDC→USDT swap. **6 days overdue.** Rate 5.26%. | **2026-04-29 (Tue)** — DECIDE: execute or drop |
| Idle xyz USDC | $9,300 | Ready to deploy → HypurrFi USDC (6.92%) | **2026-04-29 (Tue)** |
| Idle USDH | $4,854 free | Ready to deploy → Felix USDH (6.21%) | **2026-04-29 (Tue)** |
| Idle USDC unified | $4,943 free | Ready to deploy → HypurrFi USDC (6.92%) | **2026-04-29 (Tue)** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Review |
|----------|---------|-----|--------|--------|
| Felix/Morpho | 67.4% ($476k) | 50% | RED — 17pts over cap. Today's rate compression (-$28/day) is the cost of concentration. | Accelerate diversification |
| USDT0 exposure | 14.8% ($110k) | 25% ($200k) | GREEN | Under cap |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
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
