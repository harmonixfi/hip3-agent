# Portfolio State — 2026-05-03 (VERIFIED)

**Data:** All positions verified on-chain ~01:10 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $352,000 | **8.48%** | $81.78 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,348 | 6.01% | $37.93 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,200 | **8.53%** | $25.75 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | **8.48%** | $2.51 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 6.87% | $0.68 | on-chain |
| | **Subtotal** | | | **$706,948** | **7.67%** blended | **$148.65** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,066 | **10.95%** | $28.64 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.92 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,297 | **10.95% APR** | native $23.44 / hyna $205.10 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** | $3,929 | n/a | xyz $2.84 / flx **-$0.36** |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

> COPPER: 329.6 xyz LONG (entry 6.063, mark 5.961, uPnL -$33.42) + 329.6 flx SHORT (entry 5.998, mark 5.960, uPnL +$12.71). Net uPnL: -$20.71. Total cumFunding: +$2.48 ($2.84 xyz - $0.36 flx). **flx:COPPER cumFunding UNCHANGED at -$0.36** — no new losses today vs yesterday. Bleeding stopped but cumulative flx loss persists. Day 3 of negative/stagnant flx side. xyz side gained +$0.15 today.

> FARTCOIN: Mark $0.2053 (was $0.2059 -0.3%). cumFunding spike from hyna side: $205.10 (was $181.22 +$23.88 today — high vs $4.28/day baseline). Large uPnL swings on short side (-$263.83 native, -$1,910.04 hyna) but delta neutral via spot.

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate (12 days undeployed). Felix USDC now 8.48% opportunity cost. |
| 11 | Idle USDC | USDC | unified L1 | $5,007 | $1,964 held as COPPER xyz margin. Free: $3,043 |
| 12 | Idle USDH | USDH | unified L1 | $4,966 | $2,011 held as COPPER flx margin. Free: $2,955 |
| 13 | Idle HYPE | HYPE | lending L1 | $0.82 | Dust (0.0199 HYPE @ $41.15) |
| 14 | Idle USDE | USDE | spot_perp L1 | $8.30 | Small balance — interest/dust (up from $7.62) |
| | **Subtotal** | | | **$19,282** | Free cash: $3,043 USDC + $2,955 USDH + $9,300 xyz |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$745,601** |
| Deployed (earning yield) | $706,948 (94.8%) |
| Trading positions | $19,371 (2.6%) |
| Idle | $19,282 (2.6%) |
| **Daily Yield** | **$153.43/day** |
| **Blended APY (deployed)** | **7.92%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **99.6% — near target** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,600 | 67.4% | $110.72 |
| HyperLend | $230,348 | 32.6% | $37.93 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $19,371 | — | $4.78 |
| Idle/Pending | $19,282 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.82 | $692,548 | $692,549 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $13,900 | $0 | $13,900 |
| **Total** | | **$53,001** | **$706,948** | **$759,949** |

---

## 3. Alerts

### ⚠️ flx:COPPER cumFunding Stagnant at -$0.36 (Day 3)

No new losses today — cumFunding held at -$0.36 (same as yesterday), but the cumulative loss from the flx side persists:
- May 1: cumFunding $3.10 → $1.81 (-$1.29)
- May 2: cumFunding $1.81 → -$0.36 (-$2.17)
- May 3: cumFunding -$0.36 → **-$0.36** (flat — bleeding stopped)

The xyz LONG side accumulated +$0.15 today (total $2.84). Net combined cumFunding: +$2.48. The COPPER thesis (flx:COPPER high positive funding for shorts) has not been restored — funding was either zero or negligible on the flx side today. Requires manual verification of flx:COPPER funding rate.

**Action required on next active session:** Verify if flx:COPPER funding has stabilized or if today was a one-day pause before resuming negative.

### ✅ Major Rate Recovery — All Alerts Resolved

All rate triggers from yesterday have fully resolved:

| Position | May 2 | May 3 | Change | Status |
|----------|-------|-------|--------|--------|
| Felix USDC | 5.75% | **8.48%** | +273bps ↑↑ | GREEN |
| Felix USDT0 | 5.85% | **8.53%** | +268bps ↑↑ | GREEN (counter RESET) |
| LINK funding | 8.75% | **10.95%** | +220bps ↑↑ | GREEN |
| HypurrFi USDC | 2.91% | **6.77%** | +386bps ↑↑ | (no position) |
| HyperLend USDC | 5.58% | **6.01%** | +43bps ↑ | GREEN |

**Felix USDT0 YELLOW counter RESET** — Rate climbed from 5.85% to 8.53% (+268bps), breaking the 5-day streak below 8%. Counter resets to 0. No active YELLOW trigger today.

### 🟡 $19.3K Idle Capital (12 days on xyz)

- $9,300 USDC on spot_perp xyz dex — no positions (12 days undeployed)
- $3,043 free USDC on unified (after $1,964 margin)
- $2,955 free USDH on unified (after $2,011 margin)
- Opportunity cost at 7.92% blended: ~$4.19/day

With Felix USDC now at 8.48%, the xyz idle margin opportunity cost has increased significantly vs yesterday.

### Notable Rate Changes vs 2026-05-02

| Protocol | 2026-05-02 | 2026-05-03 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 5.75% | **8.48%** | **+273 bps ↑↑** |
| Felix USDC Frontier | 6.05% | **7.99%** | +194 bps ↑↑ |
| Felix USDT0 | 5.85% | **8.53%** | **+268 bps ↑↑** |
| Felix USDe | 7.84% | **6.87%** | -97 bps ↓ |
| Felix USDH | 5.72% | **7.28%** | +156 bps ↑ |
| Felix USDH Frontier | 6.85% | **6.96%** | +11 bps |
| HyperLend USDC | 5.58% | **6.01%** | +43 bps ↑ |
| HyperLend USDT | 5.17% | **5.40%** | +23 bps ↑ |
| HypurrFi USDT0 | 6.06% | **6.18%** | +12 bps |
| HypurrFi USDC | 2.91% | **6.77%** | **+386 bps ↑↑** |
| HypurrFi USDH | 2.31% | **2.63%** | +32 bps |
| LINK funding | 8.75% | **10.95%** | **+220 bps ↑↑** |
| FARTCOIN funding | 10.95% | **10.95%** | flat |
| USDT0 spread | 2.50 bps | **3.20 bps** | +0.7 bps |

> Strong broad rate recovery across all Felix/Morpho vaults today. The crash on May 2 (Felix USDC -133bps, Felix USDT0 -93bps) fully reversed. Daily yield recovered from $115.18 to $153.43 (+$38.25/day) — now at 99.6% of the $154 target.

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,800 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,348 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,200 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,066 | Active (funding 10.95%) |
| FARTCOIN spot-perp | $5,000 | $12,297 | Active (funding 10.95%) |
| COPPER | $10,000 | $3,929 | Active (xyz LONG + flx SHORT — flx funding stagnant) |

**Progress:** Daily yield $153.43 (+$38.25 from yesterday's $115.18). Rates fully recovered from May 2 compression. Felix USDT0 YELLOW counter reset — rate climbed from 5.85% back to 8.53%. HypurrFi USDT0 ($100K) and HyperLend USDT ($50K) remain at $0 deployed — 11 days overdue. No open orders on any wallet.

---

*All data verified on-chain. Data pulled ~01:10 UTC 2026-05-03. Next update: morning-review agent.*
