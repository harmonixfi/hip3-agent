# Portfolio State — 2026-05-04 (VERIFIED)

**Data:** All positions verified on-chain ~01:35 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $352,000 | **8.20%** | $79.05 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,385 | **11.33%** | $71.52 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,200 | **12.16%** | $36.72 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | **8.20%** | $2.43 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | **17.76%** | $1.75 | on-chain |
| | **Subtotal** | | | **$706,985** | **10.18%** blended | **$191.47** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,090 | **10.95%** | $29.56 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.91 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,408 | **13.00% APR** | native $24.11 / hyna $222.90 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** | $3,924 | n/a | xyz $3.33 / flx **-$0.62** |
| 10 | Spot-Perp | GOLD | unified (0xd473) | **0.1599 XAUT0 spot / 0.1728 SHORT (xyz)** | $1,528 | builder dex | $0.37 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |
| | | | | GOLD delta: 0.1599 XAUT0 spot vs 0.1728 short → **slight net short** (-8%) | | | |

> COPPER: 329.6 xyz LONG (entry 6.063, mark 5.950, uPnL -$37.11) + 329.6 flx SHORT (entry 5.998, mark 5.951, uPnL +$15.51). Net uPnL: -$21.60. Total cumFunding: +$2.71 ($3.33 xyz - $0.62 flx). **flx:COPPER bleeding RESUMED** — cumFunding moved from -$0.36 → -$0.62 (-$0.26 today). Day 4 of negative/stagnant cumFunding on flx side. xyz side earned +$0.49 today.

> FARTCOIN: Mark $0.2069 (was $0.2053 +0.8%). hyna cumFunding: $222.90 (was $205.10 +$17.80 today — elevated spike). Native cumFunding: $24.11 (+$0.67). Funding rate moved up 10.95%→13.0% APR. Large uPnL swings (-$277.92 native, -$1,987.42 hyna) delta neutral via spot.

> GOLD: **NEW POSITION** opened on unified wallet. 0.1599 XAUT0 spot ($733) + 0.1728 xyz:GOLD SHORT ($795). uPnL +$2.32, cumFunding $0.37. Slight net short (delta -8%). $737 USDC used to purchase XAUT0. Builder dex funding rate not available from standard API.

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 11 | Idle margin | USDC | spot_perp xyz dex | $6,300 | No positions — 13 days undeployed. Was $9,300 (-$3K moved to native). Opportunity cost ~$1.42/day at 8.20%. |
| 12 | Native spot | USDC | spot_perp native | $3,000 | Moved from xyz dex. Serves as margin buffer for native LINK/FARTCOIN perp positions. |
| 13 | Idle USDC | USDC | unified L1 | $4,270 | Was $5,007 (-$737 used for XAUT0). Hold $2,000 as COPPER+GOLD margin. Free: $2,270. |
| 14 | Idle USDH | USDH | unified L1 | $4,968 | Hold $2,014 as flx COPPER margin. Free: $2,954. |
| 15 | Idle HYPE | HYPE | lending L1 | $0.82 | Dust (0.0199 HYPE @ $41.30) |
| 16 | Idle USDE | USDE | spot_perp L1 | $8.96 | Interest accrual dust (was $8.30) |
| | **Subtotal** | | | **$18,548** | Free cash: $2,270 USDC + $2,954 USDH (unified) |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$745,711** |
| Deployed (earning yield) | $706,985 (94.8%) |
| Trading positions | $20,178 (2.7%) |
| Idle | $18,548 (2.5%) |
| **Daily Yield** | **$197.16/day** |
| **Blended APY (deployed)** | **10.18%** |
| Plan target | $154/day |
| Current vs target | **128.0% — significantly above target** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,600 | 67.4% | $120.95 |
| HyperLend | $230,385 | 32.6% | $71.52 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $20,178 | — | $5.69 |
| Idle/Pending | $18,548 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.82 | $692,585 | $692,586 |
| Spot-Perp | 0x3c2c...453 | $39,200 | $14,400 | $53,600 |
| Unified | 0xd473...210a | $14,000 | $0 | $14,000 |
| **Total** | | **$53,201** | **$706,985** | **$760,186** |

---

## 3. Alerts

### 🔴 flx:COPPER Bleeding RESUMED — Day 4 (EXIT OVERDUE)

cumFunding on flx SHORT side moved from -$0.36 → **-$0.62** (-$0.26 new loss today). The brief pause on May 3 did not represent stabilization — bleeding has resumed:

| Date | flx cumFunding | Change | xyz cumFunding | Net Change |
|------|---------------|--------|---------------|------------|
| May 1 | $3.10 → $1.81 | -$1.29 | +n/a | — |
| May 2 | $1.81 → -$0.36 | -$2.17 | +$0.15 | -$2.02 |
| May 3 | -$0.36 → -$0.36 | flat | +$0.15 | +$0.15 |
| May 4 | -$0.36 → **-$0.62** | **-$0.26** | +$0.49 | +$0.23 |

Net position: cumFunding total = +$3.33 (xyz) - $0.62 (flx) = **+$2.71**. Positive overall, but the flx thesis is broken. xyz side is now EARNING more than expected (LONGs being paid = inverted funding on xyz). This is unusual.

COPPER thesis was: flx SHORT receives high positive funding. With flx paying negative, the trade is no longer working as intended. Exit has been recommended for 2+ sessions. The COPPER position now has net uPnL -$21.60 and cumFunding +$2.71.

**Action required:** Execute COPPER exit at next active session.

### 🔥 Major Rate Surge — HyperLend USDC +532bps, Felix USDT0 +363bps, Felix USDe +1089bps

Today's rate environment is dramatically improved:

| Protocol | 2026-05-03 | 2026-05-04 | Change | Impact |
|----------|-----------|-----------|--------|--------|
| HyperLend USDC | 6.01% | **11.33%** | **+532 bps ↑↑** | +$33.59/day |
| Felix USDT0 | 8.53% | **12.16%** | **+363 bps ↑↑** | +$10.97/day |
| Felix USDe | 6.87% | **17.76%** | **+1089 bps ↑↑** | +$1.07/day |
| FARTCOIN APR | 10.95% | **13.00%** | **+205 bps ↑↑** | +$0.68/day |
| Felix USDC | 8.48% | **8.20%** | -28 bps | -$0.96/day |

Net daily yield impact: **+$45.25/day** → from $153.43 → $197.16 (128% of target).

**HyperLend USDC is now the single largest yield contributor at $71.52/day**, surpassing Felix USDC ($79.05/day combined with today's slightly lower rate). This is driven by a large rate jump (6.01%→11.33%) on the $230K position.

### 🆕 New GOLD Position on Unified Wallet

A new spot-perp position was detected on the unified wallet:
- **Spot:** 0.1599 XAUT0 @ $4,586.25/oz = **$733**
- **Short:** 0.1728 xyz:GOLD SHORT @ $4,600 = **$795 notional**
- **uPnL:** +$2.32, cumFunding: $0.37
- **Delta:** slight net short (-8%). XAUT0 spot < GOLD short size by 0.0129 contracts.
- $737 USDC was used from unified wallet to purchase XAUT0 (unified USDC balance: $5,007 → $4,270).

Funding rate for xyz:GOLD is not available from standard HL API (builder dex only). The +$0.37 cumFunding suggests position is earning. Morning review agent to assess position health.

### 🟡 $18.5K Idle Capital (xyz 13 days + unified free cash)

| Location | Amount | Days Idle | Opportunity Cost |
|----------|--------|-----------|-----------------|
| xyz dex (spot-perp) | $6,300 | 13 days | $1.42/day @ 8.20% |
| Native spot (spot-perp) | $3,000 | moved today | $0.67/day @ 8.20% |
| Unified USDC (free) | $2,270 | ongoing | $0.51/day |
| Unified USDH (free) | $2,954 | ongoing | $0.66/day |
| **Total** | **$14,524** | | **$3.26/day opportunity cost** |

### Notable Rate Changes vs 2026-05-03

| Protocol | 2026-05-03 | 2026-05-04 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 8.48% | **8.20%** | -28 bps ↓ |
| Felix USDC Frontier | 7.99% | **8.24%** | +25 bps ↑ |
| Felix USDT0 | 8.53% | **12.16%** | **+363 bps ↑↑** |
| Felix USDe | 6.87% | **17.76%** | **+1089 bps ↑↑** |
| Felix USDH | 7.28% | **6.72%** | -56 bps ↓ |
| Felix USDH Frontier | 6.96% | **7.83%** | +87 bps ↑ |
| HyperLend USDC | 6.01% | **11.33%** | **+532 bps ↑↑** |
| HyperLend USDT | 5.40% | **5.49%** | +9 bps |
| HypurrFi USDT0 | 6.18% | **7.40%** | +122 bps ↑ |
| HypurrFi USDC | 6.77% | **5.02%** | -175 bps ↓ |
| HypurrFi USDH | 2.63% | **4.97%** | +234 bps ↑ |
| LINK funding | 10.95% | **10.95%** | flat |
| FARTCOIN funding | 10.95% | **13.00%** | **+205 bps ↑↑** |
| USDT0 spread | 3.20 bps | **2.00 bps** | -1.2 bps (tighter) |

> Three standout moves: HyperLend USDC +532bps, Felix USDT0 +363bps, Felix USDe +1089bps. These appear to be utilization-driven rate spikes. The sustained high deployment on HyperLend ($230K at 11.33%) is exceptional — if this rate holds tomorrow, daily yield will remain ~$197/day. USDT0 spread tightened to 2.0 bps (well within range).

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,800 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,385 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,200 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,090 | Active (funding 10.95%) |
| FARTCOIN spot-perp | $5,000 | $12,408 | Active (funding 13.0%) |
| COPPER | $10,000 | $3,924 | Active (EXIT OVERDUE — thesis broken) |
| GOLD | — | $1,528 | New position (assessment pending) |

**Progress:** Daily yield $197.16/day (+$43.73 from yesterday's $153.43). Massive rate surge across HyperLend USDC, Felix USDT0, and Felix USDe. HypurrFi USDT0 ($100K) and HyperLend USDT ($50K) remain at $0 deployed — 12 days overdue. COPPER exit remains unexecuted (Day 4 of negative flx funding).

---

*All data verified on-chain. Data pulled ~01:35 UTC 2026-05-04. Next update: morning-review agent.*
