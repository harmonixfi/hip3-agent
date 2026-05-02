# Portfolio State — 2026-05-02 (VERIFIED)

**Data:** All positions verified on-chain ~02:25 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,900 | **5.75%** | $55.44 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,311 | 5.58% | $35.18 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,100 | 5.85% | $17.64 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | **5.75%** | $1.70 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 7.84% | $0.77 | on-chain |
| | **Subtotal** | | | **$706,711** | **5.72%** | **$110.73** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,116 | **8.75%** | $27.83 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.93 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,344 | **10.95% APR** | native $22.18 / hyna $181.22 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** | $3,929 | n/a | xyz $2.69 / flx **-$0.36** |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

> COPPER: 329.6 xyz LONG (entry 6.063, mark 5.958, uPnL -$34.51) + 329.6 flx SHORT (entry 5.998, mark 5.962, uPnL +$11.99). Net uPnL: -$22.52. Total cumFunding: $2.33 ($2.69 xyz - $0.36 flx). ⚠️ **flx cumFunding NOW NEGATIVE (-$0.36, was +$1.81 yesterday) — flx:COPPER funding has flipped. Short position is PAYING not receiving. Day 2 of negative trend on flx side.** COPPER funding rate not available via HL API (custom dex symbol).

> FARTCOIN: Mark $0.2059 (was $0.1992 +3.4%). Large uPnL swings on short side (-$268.98 native, -$1,934.80 hyna) but delta neutral via spot. hyna:FARTCOIN cumFunding spike +$19.17 today vs $4.28/day expected — verify if funding rate spiked.

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate (11 days undeployed) |
| 11 | Idle USDC | USDC | unified L1 | $5,006 | $1,963 held as COPPER xyz margin. Free: $3,043 |
| 12 | Idle USDH | USDH | unified L1 | $4,965 | $2,011 held as COPPER flx margin. Free: $2,954 |
| 13 | Idle HYPE | HYPE | lending L1 | $0.82 | Dust (0.0199 HYPE @ $41.27) |
| 14 | Idle USDE | USDE | spot_perp L1 | $7.62 | Small balance — interest/dust |
| | **Subtotal** | | | **$19,279** | Free cash: $3,043 USDC + $2,954 USDH + $9,300 xyz |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$745,379** |
| Deployed (earning yield) | $706,711 (94.8%) |
| Trading positions | $19,389 (2.6%) |
| Idle | $19,279 (2.6%) |
| **Daily Yield** | **$115.18/day** |
| **Blended APY (deployed)** | **5.72%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **74.8% — ⚠️ BELOW TARGET** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,400 | 67.4% | $75.55 |
| HyperLend | $230,311 | 32.6% | $35.18 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $19,389 | — | $4.45 |
| Idle/Pending | $19,279 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.82 | $692,211 | $692,212 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $13,900 | $0 | $13,900 |
| **Total** | | **$53,001** | **$706,611** | **$759,612** |

---

## 3. Alerts

### 🔴 flx:COPPER cumFunding NOW NEGATIVE — Strategy Thesis Breaking Down

The flx:COPPER SHORT position has been paying funding for 2 consecutive days:
- May 1: cumFunding $3.10 → $1.81 (-$1.29)
- May 2: cumFunding $1.81 → **-$0.36** (-$2.17)
- Net loss on flx side: -$2.17 in 2 days

This directly contradicts the COPPER perp-perp strategy premise (flx:COPPER should have high positive funding for shorts). The xyz LONG side continues to accumulate normally (+$0.66 today, total $2.69). Combined net cumFunding: +$2.33. But if flx side continues negative, the net will turn negative quickly.

**Action required on next active session:** Verify flx:COPPER funding rate manually. If funding remains negative for shorts, evaluate position exit.

### 🔴 Felix USDC — Major Rate Decline

- Rate: 7.08% → **5.75%** (-133 bps) — largest single-day drop since tracking
- Balance: $351.9K (+$100 accrual)
- Daily yield impact: -$12.77/day ($68.24 → $55.44)
- Trigger headroom: 75 bps above 5% exit trigger (was 308 bps yesterday)
- Portfolio impact: -$12.77/day is the primary driver of today's overall yield drop
- Trigger rule: APR<5% for 3d. Rates need to check: Apr 28=6.89%, Apr 29=6.39%, May 1=7.08%, May 2=5.75% — all above 5%, counter not started. GREEN on trigger but deteriorating rapidly.

### 🟡 Felix USDT0 — Rate 5.85%, YELLOW Trigger (Day 5 of 14)

Felix USDT0 rate dropped again, moving away from 8% threshold:
- Position: $110,100 at 5.85% = $17.64/day
- Trigger rule: APR<8% for 2wk before exit
- Counter: Day 5 of 14. YELLOW.
- Rate trend: 13.38 → 6.08 → 6.48 → [stale] → 6.78 → **5.85** — declining again

### ⚠️ Daily Yield $115.18 — Below $154 Target (74.8%)

Yield dropped from $129.84 yesterday (-$14.66/day):
- Felix USDC: -$12.77/day (7.08%→5.75%, -133bps on $351.9K)
- Felix USDT0: -$2.80/day (6.78%→5.85%, -93bps on $110.1K)
- HyperLend USDC: +$1.45/day (5.35%→5.58%, +23bps on $230.3K)
- LINK funding: -$0.19/day (10.95%→8.75% APR on $3K notional)
- Net: -$14.31/day

Gap to $154 target: **$38.82/day**. Widest gap since tracking began. Two-day Felix rate compression is primary driver.

### ⚠️ LINK Funding Approaching 8% Trigger

LINK funding dropped from 10.95% to 8.75% APR — now only 75 bps above the 8% trigger threshold:
- Position: 342.13 LINK spot / 336 short, notional ~$3.1K
- At 8% trigger if LINK drops 1 funding interval: evaluate exit
- Not yet triggered (today 8.75% > 8%). GREEN on trigger but monitor.

### 🟡 $19.3K Idle Capital (11 days)

- $9,300 USDC on spot_perp xyz dex — no positions (11 days undeployed)
- $3,043 free USDC on unified (after $1,963 margin)
- $2,954 free USDH on unified (after $2,011 margin)
- Opportunity cost at 5.72% blended: ~$3.64/day

### Notable Rate Changes vs 2026-05-01

| Protocol | 2026-05-01 | 2026-05-02 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 7.08% | **5.75%** | **-133 bps ↓↓** |
| Felix USDC Frontier | 6.89% | **6.05%** | -84 bps ↓ |
| Felix USDT0 | 6.78% | **5.85%** | -93 bps ↓ |
| Felix USDe | 7.80% | **7.84%** | +4 bps |
| Felix USDH | 9.90% | **5.72%** | **-418 bps ↓↓** |
| Felix USDH Frontier | 10.16% | **6.85%** | -331 bps ↓ |
| HyperLend USDC | 5.35% | **5.58%** | +23 bps ↑ |
| HyperLend USDT | 6.06% | **5.17%** | -89 bps ↓ |
| HypurrFi USDT0 | 6.16% | **6.06%** | -10 bps |
| HypurrFi USDC | 6.06% | **2.91%** | **-315 bps ↓↓** |
| HypurrFi USDH | 9.78% | **2.31%** | **-747 bps ↓↓** |
| LINK funding | 10.95% | **8.75%** | **-220 bps ↓** |
| FARTCOIN funding | 10.95% | **10.95%** | flat |
| USDT0 spread | 2.90 bps | **2.50 bps** | -0.4 bps |

> Broad rate compression across all protocols today. USDH rates that spiked yesterday (Felix 9.90%, HypurrFi 9.78%) have fully reversed. HypurrFi USDC collapsed from 6.06% to 2.91%. These are short-lived rate spikes that we have no exposure to.

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,700 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,311 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,100 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,116 | Active (funding 8.75%) |
| FARTCOIN spot-perp | $5,000 | $12,344 | Active (funding 10.95%) |
| COPPER | $10,000 | $3,929 | Active (xyz LONG + flx SHORT — funding anomaly) |

**Progress:** Daily yield $115.18 (-$14.66 from yesterday's $129.84). Broad rate compression today: Felix USDC -133bps, Felix USDT0 -93bps, LINK funding -220bps. flx:COPPER funding flipped negative — cumFunding went -$0.36 (was +$1.81). HypurrFi USDT0 ($100K) and HyperLend USDT ($50K) remain at $0 deployed — 10 days overdue. No open orders on any wallet.

---

*All data verified on-chain. Data pulled ~02:25 UTC 2026-05-02. Next update: morning-review agent.*
