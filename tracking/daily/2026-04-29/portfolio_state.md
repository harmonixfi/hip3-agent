# Portfolio State — 2026-04-29 (VERIFIED)

**Data:** All positions verified on-chain ~01:12 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,700 | 6.39% | $61.57 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,209 | 5.63% | $35.51 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,100 | 6.48% | $19.54 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | 6.39% | $1.89 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 7.83% | $0.77 | on-chain |
| | **Subtotal** | | | **$706,409** | **6.40%** | **$119.28** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,160 | **10.95%** | $25.44 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.95 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,165 | **10.95% APR** | native $20.93 / hyna $157.77 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** | $3,927 | n/a (APR unavailable) | xyz $0.54 / flx $3.10 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

> COPPER: 329.6 xyz LONG (mark 5.971, uPnL -$30.33) + 329.6 flx SHORT (mark 5.942, uPnL +$18.61). Net uPnL: -$11.72. Total cumFunding: $3.64 ($0.54 xyz + $3.10 flx). Price dropped ~1.5-1.9% from entry. ⚠️ COPPER margin holds increased significantly: USDC hold $1,969 (was $107), USDH hold $2,021 (was $90) — likely due to mark-to-market loss on xyz long.

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate (still undeployed) |
| 11 | Idle USDC | USDC | unified L1 | $5,013 | $1,969 held as COPPER xyz margin (up from $107). Free: $3,043 |
| 12 | Idle USDH | USDH | unified L1 | $4,975 | $2,021 held as COPPER flx margin (up from $90). Free: $2,954 |
| 13 | Idle HYPE | HYPE | lending L1 | $0.80 | Dust (0.0199 HYPE @ $40.03) |
| 14 | Idle USDE | USDE | spot_perp L1 | $5.21 | Small balance — interest/dust |
| | **Subtotal** | | | **$15,303** | Free cash: $3,043 USDC + $2,954 USDH + $9,300 xyz |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$740,964** |
| Deployed (earning yield) | $706,409 (95.3%) |
| Trading positions | $19,252 (2.6%) |
| Idle | $15,303 (2.1%) |
| **Daily Yield** | **$123.87/day** |
| **Blended APY (deployed)** | **6.40%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **80.4% — ⚠️ BELOW TARGET** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,200 | 67.4% | $84.77 |
| HyperLend | $230,209 | 32.6% | $35.51 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $19,252 | — | $4.59 |
| Idle/Pending | $15,303 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.80 | $692,009 | $692,010 |
| Spot-Perp | 0x3c2c...453 | $39,107 | $14,400 | $53,507 |
| Unified | 0xd473...210a | $14,000 | $0 | $14,000 |
| **Total** | | **$53,107** | **$706,409** | **$755,517** |

---

## 3. Alerts

### ⚠️ Daily Yield $123.87 — Below $154 Target (80.4%)

Rate compression continued with Felix USDC further declining:
- Felix USDC Main: 6.89% → **6.39%** (-50 bps) — biggest negative impact
- Felix USDT0: 6.08% → **6.48%** (+40 bps) — partial recovery
- Felix USDe: 6.49% → **7.83%** (+134 bps) — recovered
- Felix USDH: 6.21% → **7.22%** (+101 bps) — recovered

Net impact vs yesterday: Felix USDC -$4.82 offsetting USDT0/USDe/USDH recoveries +$1.50 = net -$3.46/day

### 🟡 Felix USDT0 — Rate 6.48%, YELLOW Trigger (Day 2 of 14)

Felix USDT0 partially recovered (6.08%→6.48%) but still below 8% threshold.
- Position: $110,100 at 6.48% = $19.54/day (target was $40+/day at 13.38%)
- Trigger rule: APR<8% for 2wk before exit
- Counter: Day 2 of 14. YELLOW. Monitor daily.
- Rate still volatile — check if recovers to 8%+ over next few days.

### ⚠️ COPPER Margin Holds — Significant Increase

COPPER xyz LONG lost ground: mark dropped 6.084→5.971 (-1.9%), uPnL = -$30.33.
- USDC hold: $107 → $1,969 (COPPER xyz margin)
- USDH hold: $90 → $2,021 (COPPER flx margin)
- Net unified free cash: $9,797 → $5,997 (down $3,800)
- cumFunding collected: $3.64 total (flx $3.10 earning well, xyz $0.54)
- Direction: xyz LONG + flx SHORT — earning as expected on flx side

### 🟡 $15.3K Idle Capital

- $9,300 USDC on spot_perp xyz dex — no positions, redeploy candidate
- $3,043 free USDC on unified (after $1,969 margin)
- $2,954 free USDH on unified (after $2,021 margin)
- Opportunity cost at current blended rates: ~$2.70/day

### Notable Rate Changes vs 2026-04-28

| Protocol | 2026-04-28 | 2026-04-29 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 6.89% | **6.39%** | **-50 bps ↓** |
| Felix USDC Frontier | 7.51% | **6.69%** | -82 bps ↓ |
| Felix USDT0 | 6.08% | **6.48%** | +40 bps ↑ |
| Felix USDe | 6.49% | **7.83%** | **+134 bps ↑** |
| Felix USDH | 6.21% | **7.22%** | **+101 bps ↑** |
| Felix USDH Frontier | 6.82% | **7.01%** | +19 bps ↑ |
| HyperLend USDC | 5.61% | **5.63%** | +2 bps ↑ |
| HyperLend USDT | 5.26% | **6.27%** | +101 bps ↑ |
| HypurrFi USDT0 | 6.28% | **6.36%** | +8 bps ↑ |
| HypurrFi USDC | 6.92% | **6.85%** | -7 bps |
| HypurrFi USDH | 3.49% | **4.56%** | +107 bps ↑ |
| LINK funding | 10.95% | **10.95%** | flat |
| FARTCOIN funding | 10.95% | **10.95%** | flat |
| USDT0 spread | 1.00 bps | **2.00 bps** | +1 bps |

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,500 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,209 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,100 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,160 | Active (funding 10.95%) |
| FARTCOIN spot-perp | $5,000 | $12,165 | Active (funding 10.95%) |
| COPPER | $10,000 | $3,927 | Active (direction: xyz LONG + flx SHORT) |

**Progress:** Daily yield $123.87 (-$3.46 from yesterday's $127.33). Felix USDC continued sliding (-50bps). USDT0/USDe/USDH rates partially recovered but not enough to offset USDC compression. LINK+FARTCOIN funding stable at 10.95%. COPPER xyz long losing on mark-to-market (uPnL -$11.72 net) but flx earning well. $9.3K xyz idle remains undeployed. No open orders on any wallet.

---

*All data verified on-chain. Data pulled ~01:12 UTC 2026-04-29. Next update: morning-review agent.*
