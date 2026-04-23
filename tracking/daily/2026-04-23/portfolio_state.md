# Portfolio State — 2026-04-23 (VERIFIED)

**Data:** All positions verified on-chain ~04:10 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $381,400 | 5.55% | $57.97 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,020 | 3.84% | $24.20 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $25,200 | 11.88% | $8.20 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $12,400 | 5.55% | $1.89 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $4,000 | 12.24% | $1.34 | on-chain |
| | **Subtotal** | | | **$653,020** | **5.23%** | **$93.60** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342 spot / 336 short (native) | $3,084 | **-8.04% (PAYING)** | $20.67 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.98 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $11,736 | 10.95% (native) | $151.07 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | 65.92 short (xyz) + 65.92 long (flx) | $799 | builder dex | $1.40 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short → **neutral** | | | |

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Swap order | USDC→USDT0 | lending L1 | $49,840 | Limit @1.0002, 0.3% filled |
| 11 | Idle USDT0 | USDT0 | lending L1 | $4,976 | Deploy to Felix USDT0 |
| 12 | Idle USDC | USDC | unified L1 | $5,043 | Deploy to lending |
| 13 | Idle USDH | USDH | unified L1 | $4,956 | Deploy to Felix USDH |
| 14 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy |
| | **Subtotal** | | | **$74,115** | |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$757,847** |
| Deployed (earning yield) | $653,020 (86.2%) |
| Trading positions | $15,681 (2.1%) |
| Idle + Pending | $74,126 (9.8%) |
| **Daily Yield** | **$93.60/day** |
| **Blended APY (deployed)** | **5.23%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **60.8%** |

### By Protocol

| Protocol | Amount | % | Daily $ |
|----------|--------|---|---------|
| Felix/Morpho | $423,000 | 55.8% | $69.40 |
| HyperLend | $230,020 | 30.4% | $24.20 |
| Hyperliquid (trading) | $15,681 | 2.1% | -$0.68 (LINK paying) |
| Idle/Pending | $74,126 | 9.8% | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $54,827 | $636,620 | $691,447 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $16,400 | $55,500 |
| Unified | 0xd473...210a | $10,900 | $0 | $10,900 |
| **Total** | | **$104,827** | **$653,020** | **$757,847** |

---

## 3. Alerts

### 🔴 CRITICAL: LINK Funding NEGATIVE -8.04% APR

Funding flipped negative. Shorts are now PAYING longs. Native short 336 LINK (~$3,084) now costs ~$0.68/day.
- Lifetime funding earned: $20.67 (native) - $5.98 (hyna dust) = **net $14.69**
- At -8.04% APR, break-even erosion in ~22 days (but should exit now)
- hyna:LINK dust (2.4 short) also paying — clean up both

### 🟡 HyperLend USDC Rate 3.84% — Near 3% Exit Trigger

Live 3.84% APY (on-chain confirmed). 3% exit trigger is 84 bps away. Monitor daily.

### 🟡 $74k Idle Capital

- $49.8k USDC in USDT0 swap order (0.3% filled — barely moving)
- $9.3k idle xyz margin
- $5k USDC + $5k USDH on unified wallet
- $5k USDT0 on lending L1
- Opportunity cost: ~$10/day at 5% APY

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $393,800 | 131% (includes $81k parked) |
| HyperLend USDC | $230,000 | $230,020 | 100% ✓ |
| Felix USDT0 | $100,000 | $25,200 | 25% |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,084 | **EXIT — funding negative** |
| FARTCOIN spot-perp | $5,000 | $11,736 | Active (delta neutral, 10.95% APR) |
| COPPER | $10,000 | $799 | Test only |

**Bottleneck:** USDT0 acquisition. $49.8k limit order at 1.0002 is 0.3% filled (~$149 executed). Ask is 1.0004 — order is 2 bps below market.

---

*All data verified on-chain. Data pulled ~04:10 UTC 2026-04-23. Next update: morning-review agent.*
