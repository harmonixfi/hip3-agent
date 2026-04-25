# Portfolio State — 2026-04-25 (VERIFIED)

**Data:** All positions verified on-chain ~01:15 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,500 | 9.02% | $86.86 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,073 | 5.06% | $31.91 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $80,000 | 5.81% | $12.73 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | 9.02% | $2.67 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 21.03% | $2.07 | on-chain |
| | **Subtotal** | | | **$675,973** | **7.59%** | **$136.24** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,215 | **7.59% — ⚠️ BELOW 8% TRIGGER** | $21.74 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $23 | n/a | -$5.97 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $11,943 | **10.95% APR — RECOVERED** | native $18.69 / hyna $144.11 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | 65.92 short (xyz) + 65.92 long (flx) | $799 | n/a (APR unavailable) | xyz $0.44 / flx $2.14 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle USDT0 | USDT0 | lending L1 | $29,980 | Up from $24.76K — additional swap activity likely. Deploy to Felix USDT0 (5.81%) |
| 11 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy |
| 12 | Idle USDC | USDC | unified L1 | $5,043 | $500 held as COPPER xyz margin |
| 13 | Idle USDH | USDH | unified L1 | $4,955 | $399 held as COPPER flx margin. Consider Felix USDH 8.06% |
| | **Subtotal** | | | **$49,278** | |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$741,207** |
| Deployed (earning yield) | $675,973 (91.2%) |
| Trading positions | $15,956 (2.2%) |
| Idle | $49,278 (6.6%) |
| **Daily Yield** | **$140.49/day** |
| **Blended APY (deployed)** | **7.59%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **91.2%** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $445,900 | 66.0% | $104.33 |
| HyperLend | $230,073 | 34.0% | $31.91 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $15,956 | — | $4.25 |
| Idle/Pending | $49,278 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $29,980 | $661,573 | $691,553 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $10,900 | $0 | $10,900 |
| **Total** | | **$80,000** | **$675,973** | **$741,207** |

---

## 3. Alerts

### 🔴 LINK Funding Dropped to 7.59% APR — Below 8% Trigger

LINK funding fell from +10.95% to +7.59% APR. Now below the 8% exit threshold.
- Native short: 336 contracts at $9.39 = $3,155 notional
- Daily earning: $0.66/day (at 7.59% APR)
- cumFunding native: $21.74; hyna dust: -$5.97 → net $15.77
- Action: Monitor. If below 8% for extended period, evaluate exit vs hold (rate may recover as it did for FARTCOIN)

### 🟡 Felix USDT0 Rate Crashed to 5.81% — First Day Below 8% Threshold

Felix USDT0 rate dropped sharply from 12.74% to 5.81% (down 693 bps in one day).
- $80,000 deployed at 5.81% = $12.73/day (was $19.26/day yesterday at 12.74%)
- Trigger fires at APR<8% for 2 weeks — today is day 1 below threshold
- Daily yield loss: ~$6.53/day vs yesterday
- Note: Idle $24.76K USDT0 successfully deployed to Felix USDT0 (position grew to $80K)
- Action: Monitor rate trend. If sustained below 8%, evaluate moving to Hyperithm USDT0 (8.10%) or Felix USDT0 Frontier (6.71%)

### 🟢 FARTCOIN Funding Recovered to 10.95% — Back Above 8% Trigger

FARTCOIN funding surged from 1.78% to 10.95% APR (6x recovery).
- Total short: 60,180 contracts at $0.199 = $11,976 notional
- Daily earning: $3.59/day (was $0.59/day yesterday)
- Total cumFunding: $162.80 ($18.69 native + $144.11 hyna)
- Position no longer in RED — cleared

### 🟡 $49.3K Idle Capital

- $29.98K USDT0 on lending L1 (up from $24.76K — likely new USDC→USDT0 swap executed)
- $9.3K USDC idle on xyz margin (no positions)
- $5K USDC + $5K USDH on unified wallet ($900 held as COPPER margin)
- Opportunity cost at Felix USDH 8.06%: ~$3.28/day on USDH alone
- Action: Deploy USDT0 to Felix USDT0 or Hyperithm USDT0 (8.10%). Deploy USDH to Felix USDH (8.06%)

### Notable Rate Changes vs Yesterday

| Protocol | Yesterday | Today | Change |
|----------|-----------|-------|--------|
| Felix USDC | 5.16% | **9.02%** | **+386 bps ↑** |
| Felix USDC Frontier | 6.85% | **10.10%** | **+325 bps ↑** |
| Felix USDT0 | 12.74% | **5.81%** | **-693 bps ↓** |
| Felix USDe | 8.91% | **21.03%** | **+1,212 bps ↑** |
| Felix USDH | 6.47% | **8.06%** | **+159 bps ↑** |
| HyperLend USDC | 4.96% | **5.06%** | **+10 bps ↑** |
| HypurrFi USDT0 | 6.25% | **6.13%** | -12 bps |
| LINK funding | 10.95% | **7.59%** | **-336 bps ↓** |
| FARTCOIN funding | 1.78% | **10.95%** | **+917 bps ↑** |

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,300 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,073 | 100% ✓ |
| Felix USDT0 | $100,000 | $80,000 | 80% |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,215 | Active (funding 7.59% — below 8% trigger) |
| FARTCOIN spot-perp | $5,000 | $11,943 | Active (funding 10.95% — recovered) |
| COPPER | $10,000 | $799 | Test only |

**Progress:** Felix USDT0 at $80K (up from $55.2K — idle deployed). $29.98K USDT0 still idle on L1 (new swap likely). Felix USDC rate surged to 9.02% — previously idle/parked capital is now earning well.

---

*All data verified on-chain. Data pulled ~01:15 UTC 2026-04-25. Next update: morning-review agent.*
