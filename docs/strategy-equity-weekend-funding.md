# Equity Funding Strategy & Weekend Flip Mechanics

---

## Section 1: Equity Funding Arbitrage — How It Works

### Background

Hyperliquid builder dexes (tradexyz, kinetiq, felix) list **tokenized equity perpetual contracts** — synthetic perps that track US stock prices (AAPL, TSLA, NVDA, MSFT, etc.). These perps use the same funding rate mechanism as crypto perps: every hour, one side pays the other based on the deviation between perp mark price and the oracle/index price.

### Why Equity Perps Have Predictable Funding

During US trading hours (Mon–Fri), the underlying stock market is open and the oracle price tracks real-time stock price. Perp traders skew long (bullish bias on popular tech stocks), pushing the perp mark price above oracle. This creates **positive funding** — longs pay shorts.

The key insight: **equity perps inherit the directional bias of the underlying stock market, but amplify it through leverage and thin liquidity.** On builder dexes with small open interest, even modest long-biased flow creates funding rates of 10–40% APR.

### Strategy: Delta-Neutral Spot-Perp Carry

**Setup:**
- LONG equity spot token (e.g., buy AAPLon on Hyperliquid spot market)
- SHORT equity perp on a builder dex (e.g., short xyz:AAPL)

**P&L components:**
| Component | Effect |
|-----------|--------|
| Spot price change | +/- (offset by perp leg) |
| Perp price change | -/+ (offset by spot leg) |
| Funding received (short) | + (main income) |
| Trading fees (entry + exit) | - (cost) |
| Spread slippage (spot vs perp price gap) | - (cost, often dominant) |

**Net P&L = cumulative funding received − fees − slippage**

The position is market-neutral: if AAPL goes up $5, the spot leg gains ~$5 and the perp leg loses ~$5. The only real income is funding.

### Strategy: Cross-Venue Perp-Perp Spread

When no spot token exists (or liquidity is better on perps), use two perp venues:

**Setup:**
- LONG perp on venue with lower/more-negative funding (e.g., kinetiq)
- SHORT perp on venue with higher/more-positive funding (e.g., tradexyz)

**Net funding = short-venue funding received − long-venue funding paid**

If kinetiq funding is -5% (shorts pay longs → your long receives) and tradexyz funding is +15% (longs pay shorts → your short receives), net APR = 20%.

### Venue Fee Structure (as of Mar 2026)

| Venue | Taker Fee | Roundtrip (entry + exit) | Notes |
|-------|-----------|--------------------------|-------|
| tradexyz (xyz) | 0.0086% | 0.0172% | Lowest fees |
| felix (flx) | 0.0078% | 0.0156% | Very low |
| kinetiq (km) | 0.0431% | 0.0862% | ~5x higher than xyz/flx |
| OKX (reference) | 0.1000% | 0.2000% | CEX comparison |

**Fees are NOT the bottleneck.** On a $2,500 leg, roundtrip fees are $0.43 (xyz) to $2.16 (km). The real cost is **price slippage** — the price gap between your long and short entry fills. In the NVDA/TSLA weekend arb (Mar 27–30), slippage cost $2–4 per $2,500 leg per weekend, dwarfing the $0.74 fee.

### Tier Classification for Equity Perps

| Tier | Characteristics | Sizing | Hold Period |
|------|----------------|--------|-------------|
| Tier 1 (Core) | Consistent funding >10% APR, OI rank < 50, deep order book | Up to $10k per leg | Days to weeks |
| Tier 2 (Opportunistic) | Spikey funding, thin OI, newer listing | $2–5k per leg | Hours to days |
| Weekend-only | Exploit weekend flip pattern (see Section 2) | $2–5k per leg | Fri close → Mon open |

---

## Section 2: Weekend Funding Rate Flip — Why It Happens

### The Pattern

Every Friday after US market close (~21:00 UTC), equity perp funding rates on Hyperliquid builder dexes **flip deeply negative** and stay negative until Monday when the US market reopens.

Observed magnitudes:
- ORCL: -86% to -125% APR over weekends (Feb–Mar 2026)
- AAPL, TSLA, NVDA: similarly deep negative funding on weekends
- The flip is consistent and structural, not random

### Root Cause: No Spot Market Anchor

**During the week (market open):**
```
Oracle price = real-time stock price (from NYSE/NASDAQ via data feed)
Perp mark price ≈ oracle price (arbitrageurs keep them in line)
Funding = f(mark − oracle) → depends on trader positioning
```

Arbitrageurs and market makers keep the perp price close to oracle because they can hedge in the real stock market. If perp trades at premium, they short perp + buy real stock → convergence.

**Over the weekend (market closed):**
```
Oracle price = FROZEN at Friday's closing price
Perp mark price = free-floating (only perp traders setting price)
No real stock market → no hedging → no arbitrage anchor
```

With the oracle frozen and no spot market to arbitrage against:

1. **Liquidity evaporates.** Market makers who hedge via stocks pull out — they can't hedge over the weekend.
2. **Perp price drifts below oracle.** Without buy-side flow from arbitrageurs, the perp naturally trades at a discount to the frozen oracle.
3. **Discount = negative funding.** When mark < oracle, funding flips negative → shorts pay longs.
4. **Self-reinforcing loop.** Negative funding → shorts close or reduce → less selling pressure → but also less liquidity → price stays at discount → funding stays negative.

### The Mechanics in Detail

```
Funding Rate = (mark_price − oracle_price) / oracle_price × time_factor

Weekend:
  oracle_price = FROZEN (Friday close)
  mark_price   = DRIFTING BELOW oracle (no buy-side flow)
  
  → mark < oracle
  → funding rate < 0
  → shorts PAY longs
```

On Hyperliquid, funding settles every hour. Over a full weekend (~48 hours from Fri close to Mon pre-market), the negative funding compounds:

**Example (ORCL, Weekend of Feb 15–17, 2026):**
- Friday close oracle: $168.43
- Weekend avg perp mark: ~$167.80 (0.37% discount)
- Hourly funding rate: ~-0.015%
- 48 hours × -0.015% = -0.72% over the weekend
- Annualized: -0.72% × (365/2) ≈ -131% APR

### How to Exploit This Pattern

**The trade:**
- LONG perp on venue with most negative weekend funding (historically: kinetiq)
- SHORT perp on venue with least negative weekend funding (historically: felix, sometimes tradexyz)

**Timing:**
| Event | Time (ICT/UTC+7) | Action |
|-------|-------------------|--------|
| US market closes Friday | 04:00 Sat ICT (21:00 Fri UTC) | Open spread position |
| Weekend | Sat–Sun | Hold, collect net funding |
| US pre-market opens Monday | 21:30 Mon ICT (14:30 Mon UTC) | Close spread position |

**Entry window:** Open after US market close Friday, when oracle freezes and funding begins flipping.

**Exit window:** Close before or shortly after US pre-market opens Monday, when oracle begins updating again and funding normalizes.

### Venue Ranking (Weekend Funding, Most Negative First)

Based on 3-weekend analysis (W1: Mar 14–17, W2: Mar 21–24, W3: Mar 28–31):

| Rank | Venue | Typical Weekend APR | Role |
|------|-------|---------------------|------|
| 1 | kinetiq (km) | -80% to -130% | LONG leg (receive funding) |
| 2 | tradexyz (xyz) | -30% to -80% | LONG leg (alt) or SHORT leg |
| 3 | felix (flx) | -10% to -30% | SHORT leg (pay least) |

**Best pairing: L:km + S:xyz** or **L:km + S:flx**

The spread between kinetiq and felix/tradexyz is the income. Kinetiq being the most negative means your long leg receives the most funding; felix being the least negative means your short leg pays the least.

### Entry Criteria

| Criteria | Minimum Threshold | Rationale |
|----------|-------------------|-----------|
| Projected net APR spread | > 30% | Safety margin for slippage (lesson from NVDA loss) |
| Historical win rate | > 60% over 3+ weekends | Enough sample to confirm pattern |
| Avg net profit per weekend | > $3 per $2,500 leg | Must cover slippage + fees |
| Price slippage budget | < $4 per leg | Main cost — monitor execution quality |

### Risk Factors

1. **Price slippage is the dominant cost.** Entry price gap between long and short fills ($0.09–$0.15/share on $2,500 legs) creates unrealized PnL drag much larger than trading fees. Use limit orders and simultaneous execution to minimize.

2. **Oracle update timing.** When the US market reopens, the oracle price updates rapidly. If you're slow to exit, a price jump can create directional P&L that overwhelms funding gains.

3. **Funding is not guaranteed.** While the pattern is structural (driven by market closure), individual weekends can vary. Some weekends have lighter negative funding if pre-weekend positioning was already balanced.

4. **Thin liquidity.** Weekend equity perp OI is low. Position sizes above $5k per leg may face significant market impact.

5. **Symbol selection matters more than venue selection.** The TSLA vs NVDA weekend arb showed this clearly: same venues (km + flx), same fees, but TSLA earned 9x more funding than NVDA. High-funding symbols with strong weekday carry tend to have stronger weekend flips.

### Lessons From Live Trades (Mar 27–30 Weekend Arb)

| | NVDA (L:km S:flx) | TSLA (L:km S:flx) |
|---|---|---|
| Notional per leg | $2,495 | $2,413 |
| Funding earned | +$0.68 | +$6.07 |
| Price slippage | -$4.07 | -$2.10 |
| Fees (roundtrip) | -$0.74 | -$0.74 |
| **Net P&L** | **-$4.12** | **+$3.22** |
| **APR** | **-20.1%** | **+16.2%** |

**Key takeaway:** NVDA's funding ($0.68) couldn't cover slippage ($4.07) → loss. TSLA's funding ($6.07) easily covered slippage ($2.10) + fees ($0.74) → profit. Always validate that the **projected funding exceeds expected slippage by at least 2x**.

### Decision Flowchart

```
1. Thursday: Pull weekend funding projection for all equity symbols
   └─ Use 3-weekend historical avg as baseline

2. Friday pre-close: Rank pairs by projected net APR
   └─ Filter: net APR > 30%, historical win rate > 60%

3. Friday 21:00 UTC: Open spread
   └─ Limit orders preferred (reduce slippage)
   └─ Long leg on most-negative-funding venue
   └─ Short leg on least-negative-funding venue

4. Saturday–Sunday: Monitor (no action needed)
   └─ Funding accumulates hourly

5. Monday 14:30 UTC: Close spread
   └─ Exit both legs simultaneously
   └─ Record actual funding vs projected
   └─ Journal the trade
```

---

## Appendix: Glossary

| Term | Definition |
|------|-----------|
| **Funding rate** | Periodic payment between long and short holders, based on mark vs oracle price deviation |
| **Positive funding** | Mark > oracle → longs pay shorts (bullish market bias) |
| **Negative funding** | Mark < oracle → shorts pay longs (bearish/discount) |
| **Oracle price** | External reference price (stock exchange price for equities) |
| **Mark price** | Current trading price on the perp venue |
| **Builder dex** | Third-party perpetual trading venues built on Hyperliquid (xyz, km, flx, hyna) |
| **Delta neutral** | Position with zero net directional exposure (long + short cancel out) |
| **Slippage** | Price difference between intended and actual execution price |
| **OI (Open Interest)** | Total outstanding contracts — proxy for liquidity and market depth |
