# Portfolio State — 2026-04-24 (VERIFIED)

**Data:** All positions verified on-chain ~01:20 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $381,400 | 5.16% | $53.91 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,042 | 4.96% | $31.28 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $55,200 | 12.74% | $19.26 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | 5.16% | $1.53 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 8.91% | $0.88 | on-chain |
| | **Subtotal** | | | **$681,042** | **5.81%** | **$106.86** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,193 | **+10.95% (EARNING)** | $20.91 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.98 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $11,982 | **1.78% APR** | native $18.17 / hyna $142.58 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | 65.92 short (xyz) + 65.92 long (flx) | $800 | builder dex | xyz $0.35 / flx $1.77 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle USDT0 | USDT0 | lending L1 | $24,760 | USDT0 swap completed — deploy to Felix USDT0 |
| 11 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy |
| 12 | Idle USDC | USDC | unified L1 | $5,042 | Deploy to lending |
| 13 | Idle USDH | USDH | unified L1 | $4,956 | Allocate to Felix USDH 6.47% or HypurrFi USDH 5.56% |
| | **Subtotal** | | | **$44,058** | |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$741,075** |
| Deployed (earning yield) | $681,042 (91.9%) |
| Trading positions | $15,975 (2.2%) |
| Idle + Pending | $44,058 (5.9%) |
| **Daily Yield** | **$108.39/day** |
| **Blended APY (deployed)** | **5.81%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **70.4%** |

### By Protocol

| Protocol | Amount | % | Daily $ |
|----------|--------|---|---------|
| Felix/Morpho | $451,000 | 60.9% | $75.58 |
| HyperLend | $230,042 | 31.1% | $31.28 |
| Hyperliquid (trading) | $15,975 | 2.2% | +$1.53 (LINK earning, FARTCOIN low) |
| Idle/Pending | $44,058 | 5.9% | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $24,761 | $666,642 | $691,403 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $10,898 | $0 | $10,898 |
| **Total** | | **$74,759** | **$681,042** | **$741,075** |

---

## 3. Alerts

### 🔴 CRITICAL: FARTCOIN Funding 1.78% APR — Below 8% Trigger

Funding dropped sharply from 10.95% to 1.78% APR (down ~84%). At 1.78% APR on ~$12K notional, daily earn ≈ $0.59/day. The position earned well while it lasted ($160+ cumulative), but the current rate is well below the 8% threshold.
- Native short cumFunding: $18.17
- hyna short cumFunding: $142.58
- Total cumFunding: **$160.75**
- At 1.78% APR: break-even on fees is long since passed — but dead money risk is real now
- Review needed: exit or hold waiting for rate recovery?

### 🟢 LINK Funding Flipped Positive — Now +10.95% APR

LINK funding reversed from -8.04% to +10.95% APR. Position is now earning again.
- Native short cumFunding: $20.91
- hyna dust cumFunding: -$5.98
- Net LINK cumFunding: **+$14.93** and growing

### 🟡 $44k Idle Capital

- $24.76k USDT0 on lending L1 (freshly acquired from completed swap — ready to deploy to Felix USDT0 at 12.74%)
- $9.3k USDC idle on xyz margin
- $5k USDC + $5k USDH on unified wallet
- Opportunity cost at 12.74% (USDT0): ~$8.62/day on idle USDT0 alone

### 🟡 Felix USDC Rate Softening — 5.16%

Rate dipped from 5.55% to 5.16%. Only 16 bps above the 5% trigger threshold. Not breached yet, but worth watching.

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $392,200 | 131% (includes $81k parked) |
| HyperLend USDC | $230,000 | $230,042 | 100% ✓ |
| Felix USDT0 | $100,000 | $55,200 | 55% |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,193 | Active (funding +10.95%) |
| FARTCOIN spot-perp | $5,000 | $11,982 | Active (funding 1.78% — review needed) |
| COPPER | $10,000 | $800 | Test only |

**Progress:** USDT0 swap order completed — $49.84K USDC converted to USDT0. $30K deployed to Felix USDT0, $24.76K idle on L1 ready to deploy.

---

*All data verified on-chain. Data pulled ~01:20 UTC 2026-04-24. Next update: morning-review agent.*
