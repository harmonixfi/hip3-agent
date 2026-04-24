# Position Review Schedule

Last updated: 2026-04-24

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $381,400 | 5.16% | **2026-04-28 (Mon)** | APR < 5% for 3d | Rotate excess $81k to HypurrFi USDC or Felix Frontier |
| HyperLend USDC | $230,042 | 4.96% | **2026-04-28 (Mon)** | APR < 3% | Exit to Felix/HypurrFi |
| Felix USDT0 | $55,200 | 12.74% | **2026-05-01 (Thu)** | APR < 8% for 2wk | Rebalance to Felix USDC |
| Felix USDC (alt) | $10,800 | 5.16% | **2026-05-01 (Thu)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 8.91% | **2026-05-01 (Thu)** | — | Collateral position |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $11,982 | 1.78% | **2026-04-26 (Sat)** | APR < 8% (BREACHED) | EXIT if < 5% on Apr 25 pulse. Redeploy to lending. |
| LINK | $3,193 | 10.95% | **2026-04-28 (Mon)** | APR < 8% | EXIT — funding is binary (cap rate or negative). Quick exit on flip. |
| LINK hyna dust | $22 | n/a | **2026-04-25 (Fri)** | — | Clean up residual 2.4 short |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER (test) | $800 | **2026-05-01 (Thu)** | Test position. On hold pending macro research. |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| Felix USDT0 (scale to $100k) | $24,760 idle → deploy | Ready NOW | **2026-04-24** |
| HypurrFi USDT0 | $0 of $100k | Need USDT0 acquisition | **2026-04-28** |
| HyperLend USDT | $0 of $50k | Pending — check USDT availability | **2026-04-26** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Review |
|----------|---------|-----|--------|--------|
| Felix/Morpho | 60.9% ($451k) | 50% | 🔴 OVER | Reduces when HypurrFi USDT0 deploys |
| USDT0 exposure | 7.4% ($55.2k) | 25% ($200k) | 🟢 Under | Scaling per plan |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-04-23 | LINK | HOLD (overrode EXIT signal) | Funding recovered from -8.04% to +10.95% overnight |
| 2026-04-22 | OIL_BRENTOIL | EXIT (CLOSED) | Per deployment plan — capital redeployed to lending |
| 2026-04-22 | hyna:LINK | EXIT (CLOSED) | Restructured to native-only. 2.4 dust remains. |
| 2026-03-30 | ALL | HOLD all, no changes | 3 days too early for rotation |
| 2026-03-28 | ORCL | EXIT (CLOSED) | 15d avg -$1.33, slow recovery |
| 2026-03-28 | MU | EXIT (CLOSED) | +$2.85 lifetime, rotated to crypto |
| 2026-03-28 | CRCL | EXIT (CLOSED) | +$5.47 lifetime, locked profit |
| 2026-03-25 | MSTR | EXIT (CLOSED) | Dead money, $0.02/day on $982 notional |
