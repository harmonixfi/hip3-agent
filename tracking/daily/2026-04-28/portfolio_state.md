# Portfolio State — 2026-04-28 (VERIFIED)

**Data:** All positions verified on-chain ~01:25 UTC via Morpho API, HyperLend API, HL API (with builder dex queries), HypurrFi API.

---

## 1. Position Register

### Lending Positions

| # | Protocol | Asset | Wallet | Amount | APY | Daily $ | Verified |
|---|----------|-------|--------|--------|-----|---------|----------|
| 1 | Felix USDC Main | USDC | lending (0x9653) | $351,700 | 6.89% | $66.34 | on-chain |
| 2 | HyperLend | USDC | lending (0x9653) | $230,175 | 5.61% | $35.39 | on-chain |
| 3 | Felix USDT0 | USDT0 | lending (0x9653) | $110,100 | 6.08% | $18.35 | on-chain |
| 4 | Felix USDC | USDC | spot_perp (0x3c2c) | $10,800 | 6.89% | $2.04 | on-chain |
| 5 | Felix USDe | USDe | spot_perp (0x3c2c) | $3,600 | 6.49% | $0.64 | on-chain |
| | **Subtotal** | | | **$706,375** | **6.58%** | **$122.76** | |

### Trading Positions

| # | Strategy | Asset | Wallet | Details | Notional | APR | Funding Earned |
|---|----------|-------|--------|---------|----------|-----|----------------|
| 6 | Spot-Perp | LINK | spot_perp | 342.13 spot / 336 short (native) | $3,194 | **10.95%** | $24.51 |
| 7 | Spot-Perp | LINK | spot_perp | 2.4 short (hyna dust) | $22 | n/a | -$5.95 |
| 8 | Spot-Perp | FARTCOIN | spot_perp | 59,944 spot / 8,590 short (native) + 51,590 short (hyna) | $12,034 | **10.95% APR** | native $20.32 / hyna $151.90 |
| 9 | Perp-Perp | COPPER | unified (0xd473) | **329.6 LONG (xyz) + 329.6 SHORT (flx)** ⚠️ REVERSED+5x | $3,991 | n/a (APR unavailable) | xyz $0.15 / flx $0.82 |
| | | | | FARTCOIN delta: 59,944 spot ≈ 60,180 short → **neutral** (-0.4%) | | | |
| | | | | LINK delta: 342.13 spot ≈ 338.4 short (336+2.4) → **neutral** (1.1%) | | | |

> ⚠️ **COPPER NOTE:** Positions reversed direction and scaled 5x since last snapshot (was 65.92 xyz SHORT + 65.92 flx LONG; now 329.6 xyz LONG + 329.6 flx SHORT). cumFunding reset ($0.15/$0.82) confirms these are new positions. Verify with Bean.

### Idle & Pending

| # | Type | Asset | Wallet | Amount | Notes |
|---|------|-------|--------|--------|-------|
| 10 | Idle margin | USDC | spot_perp xyz dex | $9,300 | No positions — redeploy candidate |
| 11 | Idle USDC | USDC | unified L1 | $5,050 | $107 held as COPPER xyz margin |
| 12 | Idle USDH | USDH | unified L1 | $4,945 | $90 held as COPPER flx margin |
| 13 | Idle HYPE | HYPE | lending L1 | $0.83 | Dust |
| 14 | Idle USDE | USDE | spot_perp L1 | $4.34 | Tiny balance — interest/dust |
| | **Subtotal** | | | **$19,300** | |

---

## 2. Portfolio Summary

| Metric | Value |
|--------|-------|
| **Total Portfolio** | **$744,894** |
| Deployed (earning yield) | $706,375 (94.8%) |
| Trading positions | $19,219 (2.6%) |
| Idle | $19,300 (2.6%) |
| **Daily Yield** | **$127.33/day** |
| **Blended APY (deployed)** | **6.58%** |
| Plan target | $154/day (7.04%) |
| Current vs target | **82.7% — ⚠️ BELOW TARGET** |

### By Protocol

| Protocol | Amount | % of Deployed | Daily $ |
|----------|--------|---------------|---------|
| Felix/Morpho | $476,200 | 67.4% | $87.37 |
| HyperLend | $230,175 | 32.6% | $35.39 |
| HypurrFi | $0 | 0.0% | $0.00 |
| Hyperliquid (trading) | $19,219 | — | $4.57 |
| Idle/Pending | $19,300 | — | $0.00 |

### By Wallet

| Wallet | Address | HL L1 | EVM | Total |
|--------|---------|-------|-----|-------|
| Lending | 0x9653...fEa | $0.83 | $691,975 | $691,976 |
| Spot-Perp | 0x3c2c...453 | $39,100 | $14,400 | $53,500 |
| Unified | 0xd473...210a | $10,200 | $0 | $10,200 |
| **Total** | | **$50,101** | **$706,375** | **$755,676** |

---

## 3. Alerts

### 🔴 Daily Yield $127.33 — Below $154 Target (82.7%)

Broad rate compression across Felix vaults today:
- Felix USDT0: 13.38% → **6.08%** (-730 bps) — single biggest impact
- Felix USDe: 15.00% → **6.49%** (-651 bps)
- Felix USDH: 11.31% → **6.21%** (-510 bps)
- Felix USDC: 7.44% → **6.89%** (-55 bps)

Impact on daily yield: -$28.18/day (USDT0: -$21.97, USDe: -$0.84, USDC: -$3.01)

### 🟡 Felix USDT0 — Rate 6.08%, YELLOW Trigger (Day 1 of 14)

Felix USDT0 crashed from 13.38% to 6.08% overnight — first day below 8% threshold again.
- Position: $110,100 at 6.08% = $18.35/day (was $40.32/day at 13.38%)
- Trigger rule: APR<8% for 2wk before exit
- Counter: Day 1 of 14. YELLOW. Monitor daily.
- Last time this dipped below 8%: 2026-04-25 (day 1) → recovered to 13.38% on 2026-04-27
- Rate was volatile; may recover

### ⚠️ COPPER Positions — Direction Reversed + 5x Scaled

COPPER perp-perp positions changed materially since 2026-04-27:
- **Old:** 65.92 xyz SHORT + 65.92 flx LONG (cumFunding: $0.70 / $2.26)
- **New:** 329.6 xyz LONG + 329.6 flx SHORT (cumFunding: $0.15 / $0.82)
- Size: 5x increase ($801 → $3,991 combined notional)
- Direction: reversed (xyz flipped from short to long)
- Low cumFunding confirms positions were opened recently
- APR still unavailable (COPPER not in public HL perp metadata)
- No action needed for pulse — for morning review to verify with Bean

### 🟡 $19.3K Idle Capital

- $9,300 USDC on spot_perp xyz dex — no positions, redeploy candidate
- $4,943 USDC free on unified (after $107 margin) — Felix USDH 6.21% or HypurrFi USDC 6.92%
- $4,854 USDH free on unified (after $90 margin) — Felix USDH 6.21%
- Opportunity cost at current blended rates: ~$3.50/day

### Notable Rate Changes vs 2026-04-27

| Protocol | 2026-04-27 | 2026-04-28 | Change |
|----------|-----------|-----------|--------|
| Felix USDC | 7.44% | **6.89%** | -55 bps ↓ |
| Felix USDC Frontier | 7.93% | **7.51%** | -42 bps ↓ |
| Felix USDT0 | 13.38% | **6.08%** | **-730 bps ↓↓** |
| Felix USDe | 15.00% | **6.49%** | **-651 bps ↓↓** |
| Felix USDH | 11.31% | **6.21%** | **-510 bps ↓↓** |
| Felix USDH Frontier | 9.00% | **6.82%** | -218 bps ↓ |
| HyperLend USDC | 5.56% | **5.61%** | +5 bps ↑ |
| HyperLend USDT | 5.39% | **5.26%** | -13 bps |
| HypurrFi USDT0 | 7.41% | **6.28%** | -113 bps ↓ |
| HypurrFi USDC | 8.30% | **6.92%** | -138 bps ↓ |
| HypurrFi USDH | 2.49% | **3.49%** | +100 bps ↑ |
| LINK funding | 10.95% | **10.95%** | flat |
| FARTCOIN funding | 10.95% | **10.95%** | flat |
| USDT0 spread | 2.00 bps | **1.00 bps** | -1 bps |

---

## 4. vs Deployment Plan

| Position | Target | Actual | % |
|----------|--------|--------|---|
| Felix USDC | $300,000 | $362,500 | 121% (includes $62K parked) |
| HyperLend USDC | $230,000 | $230,175 | 100% ✓ |
| Felix USDT0 | $100,000 | $110,100 | 110% ✓ |
| HypurrFi USDT0 | $100,000 | $0 | 0% |
| HyperLend USDT | $50,000 | $0 | 0% |
| LINK spot-perp | $5,000 | $3,194 | Active (funding 10.95%) |
| FARTCOIN spot-perp | $5,000 | $12,034 | Active (funding 10.95%) |
| COPPER | $10,000 | $3,991 | Test → scaled 5x, reversed direction |

**Progress:** Daily yield dropped from $155.51 to $127.33 due to broad Felix rate compression. Felix USDT0 back below 8% (YELLOW day 1). LINK+FARTCOIN funding stable at 10.95%. COPPER expanded significantly — verify intent with Bean. $9.3K xyz idle remains undeployed.

---

*All data verified on-chain. Data pulled ~01:25 UTC 2026-04-28. Next update: morning-review agent.*
