# Position Review Schedule

Last updated: 2026-04-27

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $351,600 | 7.44% | **2026-04-28 (Mon)** | APR < 5% for 3d | Rotate excess above $300k to HypurrFi USDC or HyperLend |
| HyperLend USDC | $230,125 | 5.56% | **2026-04-28 (Mon)** | APR < 3% | Exit to Felix/HypurrFi |
| Felix USDT0 | $110,000 | 13.38% | **2026-05-04 (Sun)** | APR < 8% for 2wk | Rebalance to Felix USDC or HypurrFi |
| Felix USDC (alt) | $10,800 | 7.44% | **2026-05-04 (Sun)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 15.00% | **2026-05-04 (Sun)** | — | Collateral position |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $12,656 | 10.95% | **2026-05-01 (Thu)** | APR < 8% | Exit, redeploy $12k to lending. Funding is binary (cap or dead). |
| LINK | $3,261 | 10.95% | **2026-05-01 (Thu)** | APR < 8% | Exit — funding is binary. Quick exit on flip. |
| LINK hyna dust | $23 | n/a | **2026-04-28 (Mon)** | — | Clean up residual 2.4 short (paying -$5.96 cumulative) |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER (test) | $801 | **2026-05-04 (Sun)** | Test position. On hold pending macro research. cumFunding $2.96. |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0, need USDC→USDT0 swap | **2026-04-28 (Mon)** — decide: swap or deprioritize |
| HyperLend USDT | $0 of $50k | Blocked — need USDT availability or USDC→USDT swap | **2026-04-28 (Mon)** — 5 days overdue |
| Idle xyz USDC | $9,300 | Ready to deploy → HypurrFi USDC (8.30%) | **2026-04-28 (Mon)** |
| Idle USDH | $4,556 free | Ready to deploy → Felix USDH (11.31%) | **2026-04-28 (Mon)** |
| Idle USDC unified | $4,544 free | Ready to deploy → HypurrFi USDC (8.30%) | **2026-04-28 (Mon)** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Review |
|----------|---------|-----|--------|--------|
| Felix/Morpho | 67.4% ($476k) | 50% | RED — 17pts over cap | Deploy HypurrFi USDT0 to reduce; route new USDC to HypurrFi/HyperLend |
| USDT0 exposure | 14.8% ($110k) | 25% ($200k) | GREEN | Under cap |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
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
