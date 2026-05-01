# Portfolio State — 2026-05-01 (VERIFIED)

**Data:** All positions verified on-chain ~01:15 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,800 | **7.08%** | $68.24 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,276 | 5.35% | $33.78 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,100 | 6.78% | $20.45 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | **7.08%** | $2.09 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 7.80% | $0.77 | on-chain |
| | **Subtotal** | | | **$706,576** | **6.71%** | **$125.33** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,121 | **10.95%** | $26.90 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.93 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $11,936 | **10.95% APR** | native $21.60 / hyna $162.05 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** | $3,965 | n/a (APR unavailable) | xyz $2.03 / flx $1.81 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

> COPPER: 329.6 xyz LONG (entry 6.063, mark 6.035, uPnL -$9.23) + 329.6 flx SHORT (entry 5.998, mark 5.999, uPnL -$0.11). Net uPnL: -$9.34 (improved from -$11.72 yesterday — COPPER price recovering). Total cumFunding: $3.84 ($2.03 xyz + $1.81 flx). ⚠️ flx cumFunding DECREASED $3.10→$1.81 — unusual, verify. COPPER funding rate not available via HL API (custom dex symbol).

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate (still undeployed) |
| 11 | Idle USDC | USDC | unified L1 | $5,032 | $1,989 held as COPPER xyz margin. Free: $3,043 |
| 12 | Idle USDH | USDH | unified L1 | $4,955 | $2,001 held as COPPER flx margin. Free: $2,954 |
| 13 | Idle HYPE | HYPE | lending L1 | $0.80 | Dust (0.0199 HYPE @ $40.25) |
| 14 | Idle USDE | USDE | spot_perp L1 | $6.93 | Small balance — interest/dust (up from $5.21) |
| | **Subtotal** | | | **$19,295** | Free cash: $3,043 USDC + $2,954 USDH + $9,300 xyz |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$744,911** |
| Deployed (earning yield) | $706,576 (94.9%) |
| Trading positions | $19,040 (2.6%) |
| Idle | $19,295 (2.6%) |
| **Daily Yield** | **$129.84/day** |
| **Blended APY (deployed)** | **6.71%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **84.3% — ⚠️ BELOW TARGET** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,300 | 67.4% | $91.55 |
| HyperLend | $230,276 | 32.6% | $33.78 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $19,040 | — | $4.51 |
| Idle/Pending | $19,295 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.80 | $692,176 | $692,177 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $14,000 | $0 | $14,000 |
| **Total** | | **$53,101** | **$706,576** | **$759,677** |

---

## 3. Alerts

### ✅ Felix USDC Recovered — 6.39% → 7.08% (+69 bps)

Significant recovery on the portfolio's largest position:
- Rate: 6.39% → **7.08%** (+69 bps) — best level since Apr 28
- Balance: $351.7K → $351.8K (+$100 interest accrual)
- Daily yield impact: +$6.65/day ($61.57 → $68.24)
- Trigger headroom: 139 bps → **308 bps above 5% exit trigger** (GREEN, comfortable)

### 🟡 Felix USDT0 — Rate 6.78%, YELLOW Trigger (Day 4 of 14)

Felix USDT0 continued gradual recovery but remains below 8% threshold.
- Position: $110,100 at 6.78% = $20.45/day (target was $40+/day at 13.38%)
- Trigger rule: APR<8% for 2wk before exit
- Counter: Day 4 of 14. YELLOW. Counter started Apr 28.
- Rate trend: 13.38 → 6.08 → 6.48 → [stale Apr 30] → 6.78 — gradual recovery but lower high vs 13.38%
- Rate still needs to recover to 8%+ to clear trigger.

### ⚠️ Daily Yield $129.84 — Below $154 Target (84.3%)

Yield improved from $123.87 yesterday (+$5.97) driven by Felix USDC rate recovery:
- Felix USDC: +$6.65/day (rate recovery +69bps on $352K)
- Felix USDT0: +$0.91/day (rate recovery +30bps on $110K)
- HyperLend: -$1.77/day (rate drop -28bps on $230K)
- Net improvement: +$5.79/day vs yesterday

Gap to $154 target: $24.16/day. Path to close gap requires either rate recovery or new deployments (HypurrFi USDT0 $100K + HyperLend USDT $50K still at $0 — 9 days overdue).

### ⚠️ COPPER flx cumFunding Decreased — $3.10 → $1.81

Unusual: cumFunding on flx:COPPER SHORT decreased from $3.10 to $1.81 (-$1.29). Normal behavior is monotonically increasing for long-term positions. Possible causes: funding rate went negative on flx:COPPER (short paid longs), API accounting reset, or data artifact. xyz side accumulated normally ($0.54 → $2.03, +$1.49). Verify manually on next active session.

COPPER mark prices recovering:
- xyz LONG: 5.971 → 6.035 (+1.1%) → uPnL improved -$30.33 → -$9.23
- flx SHORT: 5.942 → 5.999 (+1.0%) → uPnL converged +$18.61 → -$0.11
- Net uPnL: -$11.72 → -$9.34 (improving)

### 🟡 $19.3K Idle Capital

- $9,300 USDC on spot_perp xyz dex — no positions (10 days undeployed)
- $3,043 free USDC on unified (after $1,989 margin)
- $2,954 free USDH on unified (after $2,001 margin)
- Opportunity cost at current blended rates: ~$3.55/day

### Notable Rate Changes vs 2026-04-29

| Protocol | 2026-04-29 | 2026-05-01 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 6.39% | **7.08%** | **+69 bps ↑** |
| Felix USDC Frontier | 6.69% | **6.89%** | +20 bps ↑ |
| Felix USDT0 | 6.48% | **6.78%** | +30 bps ↑ |
| Felix USDe | 7.83% | **7.80%** | -3 bps |
| Felix USDH | 7.22% | **9.90%** | **+268 bps ↑** |
| Felix USDH Frontier | 7.01% | **10.16%** | **+315 bps ↑** |
| HyperLend USDC | 5.63% | **5.35%** | -28 bps ↓ |
| HyperLend USDT | 6.27% | **6.06%** | -21 bps ↓ |
| HypurrFi USDT0 | 6.36% | **6.16%** | -20 bps ↓ |
| HypurrFi USDC | 6.85% | **6.06%** | -79 bps ↓ |
| HypurrFi USDH | 4.56% | **9.78%** | **+522 bps ↑** |
| LINK funding | 10.95% | **10.95%** | flat |
| FARTCOIN funding | 10.95% | **10.95%** | flat |
| USDT0 spread | 2.00 bps | **2.90 bps** | +0.9 bps |

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,600 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,276 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,100 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,121 | Active (funding 10.95%) |
| FARTCOIN spot-perp | $5,000 | $11,936 | Active (funding 10.95%) |
| COPPER | $10,000 | $3,965 | Active (xyz LONG + flx SHORT) |

**Progress:** Daily yield $129.84 (+$5.97 from yesterday's $123.87). Felix USDC recovery (+69bps) was the main driver. Felix USDT0 continuing gradual recovery. LINK+FARTCOIN funding flat at 10.95%. COPPER mark prices recovering — net uPnL improved to -$9.34. HypurrFi USDT0 ($100K) and HyperLend USDT ($50K) remain at $0 deployed — 9 days overdue. No open orders on any wallet. Felix USDH rate surged to 9.90% (notable opportunity — no current exposure).

---

*All data verified on-chain. Data pulled ~01:15 UTC 2026-05-01. Next update: morning-review agent.*
