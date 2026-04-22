# Lessons Learned — Trading Analysis & Portfolio Construction

Mistakes, corrections, and insights from portfolio planning sessions. Read this before any new analysis to avoid repeating errors.

---

## 1. Liquidity Assessment: Volume + OI, Not Just Order Book Depth

**Mistake:** Checked HL spot order book depth snapshot and concluded BNB/AVAX were "impossible" to trade at $25-30k. Recommended dropping them entirely.

**Correction (Bean):** Order book depth is an instantaneous snapshot. Market makers replenish levels after fills. The correct assessment uses:

| Metric | What it tells you |
|--------|------------------|
| **24h Volume** | Daily throughput — how much flows through the market over time |
| **Open Interest** | Market depth — how much capital is already positioned |
| **Order book depth** | Instant fill capacity — how much can execute in one shot |
| **Participation rate** | Our share of daily flow — target <5% to avoid impact |

**Formula:** `daily_deploy_capacity = 24h_volume × participation_rate`

**Example:** BNB spot 24h vol = $7.2k. At 5% participation = $360/day. Can deploy $5k in 14 days via limit orders. Cannot deploy $30k in any reasonable timeframe. Size positions to match spot throughput, not perp capacity.

**Key insight:** A thin book with decent daily volume = executable with patience. A thin book with zero volume = truly dead. Check BOTH.

---

## 2. APR Calculation: funding_8h_rate × 1095, NOT × 8760

**Mistake:** Computed APR as `avg(funding_8h_rate) × 8760 × 100` which inflated rates 8x (BNB showed 87.5% instead of 10.9%).

**Correction:** `funding_8h_rate` from Loris is already per-8h period. There are 1095 eight-hour periods per year (365 × 3).

```
APR = avg(funding_8h_rate) × 1095 × 100
```

Verify: 0.0001 × 1095 × 100 = 10.95% — matches screener output.

---

## 3. Operational Constraints Come First

**Mistake:** Proposed bridging BNB from Binance to HyperEVM as execution path for spot-perp positions.

**Correction (Bean):** Operational constraint — only Hyperliquid and HyperCore. No CEX bridging. Always ask about operational constraints before proposing execution paths.

**Rule:** Before recommending any execution strategy, confirm:
- Which venues/chains are available?
- Can we bridge between venues?
- What wallets/accounts do we have access to?

---

## 4. Felix Has No USDC Pools on HyperEVM

**Mistake:** Original plan allocated $400k to "Felix USDC Main" at 4.98%.

**Finding:** Felix/Morpho on HyperEVM only has USDT0, USDe, and USDhl vaults. No USDC lending pools exist on Felix. The USDC lending need is served by HyperLend (Aave V3 fork).

**Rule:** Verify pool existence via on-chain data before allocating. Don't assume pools exist because they sound reasonable.

---

## 5. HL Spot Tokens Are Bridged — Check Availability Separately

**Mistake:** Assumed BNB, AVAX, LINK have native spot markets on HL. Tried fetching `BNB/USDC` — failed.

**Finding:** HL spot uses bridged tokens with different names: BNB0, AVAX0, LINK0. Must query `spotMeta` API first to find the correct token index and use `@{index}` format for order book queries.

**Token format:** Perp = `BNB`, Spot = `BNB0/USDC` (coin = `@277`)

---

## 6. Concentration Risk — Cap Single Protocol Exposure

**Mistake (v1):** 69% of $800k portfolio on Felix/Morpho. Accepted with "no alternative available."

**Correction (Frank review):** Alternatives DO exist (HyperLend, HypurrFi). The real issue was not checking. Every protocol can fail — Euler lost $197M after being "audited and battle-tested."

**Rule:** No single lending protocol should exceed ~45% of portfolio. If no alternative exists, that's a signal to keep more in reserve, not to concentrate harder.

---

## 7. Staged Deployment Must Actually Be Staged

**Mistake (v1):** Plan said "start $20k USDT0, scale to $150k" as risk mitigation. But execution sequence placed a $130k limit order on Day 1 that would fill within hours.

**Correction (Frank):** That's not staged — it's full deployment with a brief delay. Real staging means:
- Week 1: $20k
- Week 2: +$50-100k (if no issues)
- Week 3: remaining

The yield loss during staging (~$200) is cheap insurance.

---

## 8. HyperLend Rates Are Volatile — Use 7d Average

**Finding:** HyperLend USDT showed 5.79% live APR but 7d average was only 3.29% (range 1.4-5.9%). USDC was more stable: live 4.36%, 7d avg 4.16%, range 3.0-4.6%.

**Rule:** For allocation projections, use 7d average, not live rate. Flag when live rate is >50% above 7d average — it's likely a utilization spike, not sustainable.

---

## 9. HypurrFi High APY Pools — Check Headroom

**Finding:** HypurrFi USDC Pooled showed 25.34% APY but only $239k headroom at 89% utilization. Looks amazing in a screener but can't absorb meaningful capital.

**Rule:** Always check: (1) supply cap, (2) current utilization, (3) available headroom. A pool at 25% APY with $239k headroom is useless for a $100k+ allocation.

---

## 10. Cap Rate Regime — 14 Days of Data Is Thin

**Finding:** All HL perps were at cap rate (10.9% APR) for the entire 14d observation window. AAVE had std=0.000 — every sample identical. This means we had zero information about behavior in normal conditions.

**Rule:** When all data comes from a single regime (e.g., cap rate), the data tells you about that regime, not about the asset. Correlation numbers, stability scores, and std dev are all artifacts of the regime, not the underlying fundamentals.

**What to do:** Note the regime in the analysis. Size conservatively. Add explicit triggers for "cap rate regime ends → reassess all positions."

---

## 11. Cross-Venue Spread: Entry Spread Is Critical

**Context:** COPPER (XCU) cross-venue spread analysis.

**Key learning:** When funding spikes on the short venue, the price spread between venues also widens. If you enter when spread is at the high end (chasing the funding spike), you're locked into a bad exit price. The funding you earn gets eaten by spread loss on exit.

**Rule:** Enter when price spread is at or below the rolling 3d average. Never chase entries when spread is at the high end of its range. See `docs/playbook-cross-venue-spread.md` for the full framework.

---

## 12. Frozen/Capped Pools Show Misleading Rates

**Finding:** HyperLend showed USR at 65.7% APR and USDe at 21.2% APR — both FROZEN (no new deposits). USDHL at 58.6% APR — supply cap = 1 token.

**Rule:** Always check pool status (active/frozen) and supply cap before considering a rate. Screeners and dashboards show rates for pools you can't actually deposit into.

---

## Process Lessons

### Always Use Skills for Protocol Data

HyperLend, HypurrFi, and Felix/Morpho all have dedicated skills (`hyperlend`, `hypurrfi`, `morpho`) that can pull live on-chain data. Use these instead of trying to scrape web UIs (which are all client-rendered SPAs that return empty HTML).

### Subagents for Parallel Data Pulls

When comparing multiple protocols, launch parallel subagents — one per protocol. Each uses the relevant skill. Results come back simultaneously instead of sequentially.

### Frank Mode Review

After writing any deployment plan, run a subagent with the Challenger Framework from CLAUDE.md. It consistently finds blind spots: concentration risk, fake staging, thin data, missing stress tests.
