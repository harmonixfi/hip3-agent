# HIP3 Fund Deployment Plan — 22 Apr 2026

**Capital:** $800,000 | **Target:** 6-7% APR | **Projected:** 7.04% ($56.4k/yr, $154/day)

---

## 1. Overview

### Allocation

| # | Protocol | Asset | Amount | APY | Annual $ | Daily $ |
|---|----------|-------|--------|-----|----------|---------|
| 1 | Felix | USDC | $300,000 | 6.86% | $20,580 | $56.38 |
| 2 | HyperLend | USDC | $230,000 | 4.36% | $10,028 | $27.47 |
| 3 | Felix | USDT0 | $100,000 | 15.39% | $15,390 | $42.16 |
| 4 | HypurrFi | USDT0 | $100,000 | 6.36% | $6,360 | $17.42 |
| 5 | HyperLend | USDT | $50,000 | 5.79% | $2,895 | $7.93 |
| | **Lending** | | **$780,000** | **7.08%** | **$55,253** | **$151.37** |
| 6 | HL spot-perp | LINK | $5,000 | 10.2% | $510 | $1.40 |
| 7 | HL spot-perp | FARTCOIN | $5,000 | 12.1% | $605 | $1.66 |
| 8 | Cross-venue | COPPER | $10,000 | TBD | — | — |
| | **Total** | | **$800,000** | **7.04%** | **$56,368** | **$154.43** |

### Protocol Concentration

| Protocol | Amount | % | Main Asset |
|----------|--------|---|------------|
| Felix/Morpho | $400,000 | 50.0% | USDC $300k + USDT0 $100k |
| HyperLend | $280,000 | 35.0% | USDC $230k + USDT $50k |
| HypurrFi | $100,000 | 12.5% | USDT0 $100k |
| HL (spot-perp) | $10,000 | 1.3% | LINK + FARTCOIN |
| Cross-venue | $10,000 | 1.3% | COPPER (on hold) |

### Why This Allocation

- **Felix USDC as anchor ($300k):** 6.86% APY on native USDC — no bridge risk, deepest pool on HyperEVM
- **HyperLend for diversification ($280k):** Aave V3 fork, battle-tested. USDC stable at 4.16% 7d avg. Reduces Felix concentration from 100% to 50%
- **USDT0 for yield boost ($200k, 25%):** Felix USDT0 at 15.39% pulls portfolio above 7%. Capped at 25% to limit bridge risk
- **No reserve:** All 3 lending protocols are liquid — can withdraw within hours if needed

---

## 2. Execution Sequence

### Step 1: Clean up existing positions
- [ ] EXIT OIL_BRENTOIL — close both legs
- [ ] LINK — close hyna leg, keep native HL short (restructure)

### Step 2: Deploy USDC lending
- [ ] Supply $300k USDC to Felix USDC Main vault
- [ ] Supply $230k USDC to HyperLend USDC pool
- [ ] Supply $50k USDT to HyperLend USDT pool

### Step 3: Swap USDC → USDT0
- [ ] Buy $20k USDT0 market order @ ~1.0003 (taker)
- [ ] Place $180k USDT0 limit order @ 1.0002 (maker)

### Step 4: Deploy USDT0 lending (as limit orders fill)
- [ ] Supply USDT0 to Felix USDT0 Main vault (target: $100k)
- [ ] Supply USDT0 to HypurrFi USDT0 Pooled (target: $100k)

### Step 5: COPPER evaluation
- [ ] Receive macro research report
- [ ] Combine with quant analysis → size or skip
- [ ] If validated: enter $10k cross-venue spread

---

## 3. Breakdown & Risk

### Lending Protocols

| Protocol | Tech | TVL / Cap | Our % of Pool | Rate Stability | Risk Tier |
|----------|------|-----------|---------------|----------------|-----------|
| Felix USDC | Morpho Blue | vault-managed | ~2.6% | — | LOW |
| Felix USDT0 | Morpho Blue | $11.66M TVL | 0.9% | — | MED (bridge) |
| HyperLend USDC | Aave V3 fork | $84.7M cap | 0.3% | 3.0–4.6% (7d) | LOW |
| HyperLend USDT | Aave V3 fork | $95.4M cap | 0.05% | 1.4–5.9% (7d) | LOW |
| HypurrFi USDT0 | Aave V3 + Euler V2 | $40M cap, $2.66M in | 3.8% | — | LOW-MED |

**HyperLend USDT note:** Live rate 5.79% but 7d avg only 3.29%. Current rate is a utilization spike. Conservative projection uses ~4%.

### USDT0 Exposure

| Source | Amount | % of Portfolio |
|--------|--------|---------------|
| Felix USDT0 | $100,000 | 12.5% |
| HypurrFi USDT0 | $100,000 | 12.5% |
| **Total** | **$200,000** | **25.0%** |

USDT0 = LayerZero OFT bridged USDT. Bridge risk is real but sized at 25% — a total loss scenario costs $200k, not fund-ending.

**USDT0 swap cost:** ~$200k needed. Best ask 1.0003, best bid 1.0001 (2 bps spread). $20k market + $180k limit @ 1.0002. Total cost ~$50. Breakeven <1 day.

### Risk Matrix

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| USDT0 bridge hack | Low (1-3%/yr) | -$200k (25%) | Capped at 25%. Split across 2 protocols. |
| Felix smart contract exploit | Very Low | -$400k (50%) | Morpho audited. USDC portion has no bridge risk. |
| HyperLend exploit | Very Low | -$280k (35%) | Aave V3 fork, proven codebase. |
| HypurrFi exploit | Very Low | -$100k (12.5%) | Smallest allocation. |
| USDT0 rate compression | Medium | -$10k/yr | Monitor weekly. Rebalance if < 8% sustained. |
| HyperLend rate volatility | Medium | ±$1k/yr | Small allocation ($50k USDT). Use 7d avg for projections. |
| Funding cap regime ends | Medium | -$550/yr | Tiny spot-perp allocation ($10k). |

### Stress Tests

| Scenario | APR | Daily $ | Hits 6%? |
|----------|-----|---------|----------|
| Base case | 7.04% | $154 | YES |
| USDT0 rates halve | 5.71% | $125 | NO |
| All lending -30% | 5.01% | $110 | NO |
| USDT0 drops to USDC level | 5.63% | $123 | NO |
| Felix + HyperLend USDC rates rise to 8% | 8.7% | $190 | YES |

### Monitoring Triggers

| Condition | Action |
|-----------|--------|
| Felix USDT0 rate < 8% sustained 2 weeks | Rebalance to Felix USDC |
| USDT0 depeg > 1% | Halt new USDT0 deployments |
| USDT0 depeg > 3% | Evaluate exit from USDT0 positions |
| Any position APR7 < 5% for 3+ days | Evaluate exit |
| Any position APR7 < 3% | Exit immediately |
| New lending protocol on HyperCore | Evaluate for diversification |

### Open Positions

| Position | Type | Size | Status | Trigger |
|----------|------|------|--------|---------|
| LINK | spot-perp | $5,000 | HOLD (after hyna close) | Exit if APR7 < 8% |
| FARTCOIN | spot-perp | $5,000 | HOLD | Exit if APR7 < 8% |
| COPPER | cross-venue | $10,000 | ON HOLD | Pending macro + quant research |

---

*Data freshness: Felix/HyperLend/HypurrFi rates 2026-04-22 (on-chain). HL funding at cap rate. USDT0/USDC book 2026-04-22 (API).*
