# Portfolio State — 2026-04-27 (VERIFIED)

**Data:** All positions verified on-chain ~01:15 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,600 | 7.44% | $71.67 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,125 | 5.56% | $35.05 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,000 | 13.38% | $40.32 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | 7.44% | $2.20 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 15.00% | $1.48 | on-chain |
| | **Subtotal** | | | **$706,125** | **8.04%** | **$150.72** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,261 | **10.95% — ✅ RECOVERED** | $23.56 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $23 | n/a | -$5.96 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,656 | **10.95% APR** | native $19.76 / hyna $151.19 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | 65.92 short (xyz) + 65.92 long (flx) | $801 | n/a (APR unavailable) | xyz $0.70 / flx $2.26 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate |
| 11 | Idle USDC | USDC | unified L1 | $5,042 | $498 held as COPPER xyz margin |
| 12 | Idle USDH | USDH | unified L1 | $4,955 | $399 held as COPPER flx margin. Felix USDH now 11.31% |
| | **Subtotal** | | | **$19,297** | |

> **Deployed:** Idle $29.98K USDT0 (lending L1) confirmed deployed to Felix USDT0 — position grew $80K → $110K. L1 now shows only $0.85 HYPE dust.

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$742,140** |
| Deployed (earning yield) | $706,125 (95.1%) |
| Trading positions | $16,718 (2.3%) |
| Idle | $19,297 (2.6%) |
| **Daily Yield** | **$155.51/day** |
| **Blended APY (deployed)** | **8.04%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **101.0% — ✅ FIRST TIME ABOVE TARGET** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,000 | 67.4% | $115.67 |
| HyperLend | $230,125 | 32.6% | $35.05 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $16,718 | — | $4.79 |
| Idle/Pending | $19,297 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.85 | $691,725 | $691,726 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $10,900 | $0 | $10,900 |
| **Total** | | **$50,001** | **$706,125** | **$756,126** |

---

## 3. Alerts

### ✅ All Positions GREEN — No Active Triggers

### ✅ Daily Yield $155.51 — First Time Above $154 Target (101%)

- Total deployed: $706,125 earning $150.72/day at 8.04% blended APY
- Trading: $4.79/day from FARTCOIN ($3.81) + LINK ($0.98)
- Milestone: $154/day target finally reached after idle USDT0 deployment

### ✅ LINK Funding Recovered to 10.95% APR — RED Trigger Cleared

LINK funding surged from 7.59% to 10.95% APR (+336 bps).
- Native short: 336 contracts @ $9.532 = $3,203 notional
- Daily earning: $0.98/day (was $0.66/day)
- cumFunding native: $23.56 (net of hyna dust -$5.96 = $17.60 net)
- Position now at 10.95% — back above 8% threshold

### ✅ Felix USDT0 Surged to 13.38% — YELLOW Trigger Cleared

Felix USDT0 rate surged from 5.81% to 13.38% (+757 bps).
- $110,000 deployed at 13.38% = $40.32/day (was $12.73/day)
- Was YELLOW trigger (day 1 below 8% on 2026-04-25) — now well above 8%
- Trigger counter reset → GREEN
- Position grew: $80K → $110K (idle $29.98K USDT0 deployed on 2026-04-26)

### 🟡 $9.3K USDC Idle on xyz Margin (No Positions)

- $9,300 USDC sitting in spot-perp xyz dex with no active positions
- At HypurrFi USDC 8.30% APY: opportunity cost ~$2.11/day
- Consider deploying to lending: HypurrFi USDC (8.30%) or Felix USDC (7.44%)

### 🟡 $5K USDH Idle on Unified Wallet

- $4,955 USDH in unified wallet ($399 locked as COPPER flx margin, $4,556 free)
- Felix USDH jumped to 11.31% APY (was 8.06% yesterday)
- Opportunity cost at Felix USDH 11.31%: ~$1.53/day on free portion
- Consider deploying to Felix USDH (currently best rate)

### Notable Rate Changes vs Yesterday (2026-04-25)

| Protocol | 2026-04-25 | 2026-04-27 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 9.02% | **7.44%** | -158 bps ↓ |
| Felix USDC Frontier | 10.10% | **7.93%** | -217 bps ↓ |
| Felix USDT0 | 5.81% | **13.38%** | **+757 bps ↑** |
| Felix USDe | 21.03% | **15.00%** | -603 bps ↓ |
| Felix USDH | 8.06% | **11.31%** | **+325 bps ↑** |
| Felix USDH Frontier | 6.56% | **9.00%** | **+244 bps ↑** |
| HyperLend USDC | 5.06% | **5.56%** | +50 bps ↑ |
| HyperLend USDT | 5.12% | **5.39%** | +27 bps ↑ |
| HypurrFi USDT0 | 6.13% | **7.41%** | +128 bps ↑ |
| HypurrFi USDC | 8.66% | **8.30%** | -36 bps |
| HypurrFi USDH | 5.57% | **2.49%** | -308 bps ↓ |
| LINK funding | 7.59% | **10.95%** | **+336 bps ↑** |
| FARTCOIN funding | 10.95% | **10.95%** | flat |

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,400 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,125 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,000 | 110% ✓ (idle deployed) |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,261 | Active (funding 10.95% — recovered) |
| FARTCOIN spot-perp | $5,000 | $12,656 | Active (funding 10.95%) |
| COPPER | $10,000 | $801 | Test only |

**Progress:** Felix USDT0 now $110K — idle USDT0 fully deployed. Daily target $154/day achieved for first time at $155.51/day. $9.3K xyz idle still undeployed (main drag). HypurrFi USDT0 $100K target remains unfilled.

---

*All data verified on-chain. Data pulled ~01:15 UTC 2026-04-27. Next update: morning-review agent.*
