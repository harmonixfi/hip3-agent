# Funding Arbitrage Trading Plan

**Date**: 2026-03-13
**Type**: Operational trading plan (document only, no code changes)
**Target**: Rolling 14d AVG portfolio APR >= 7%

---

## 1. Portfolio Structure & Tier Definitions

### 1.1 Three-Tier Architecture

| Tier | Weight | Venue | Strategy | Min Effective APR | OI Rank | Hold Period | Max Pairs |
|------|--------|-------|----------|-------------------|---------|-------------|-----------|
| **Core** | 60% | Hyperliquid (spot+perp, builder-dex) | SPOT_PERP | 5% | <= 100 | > 30 days | 2-4 |
| **Satellite** | 25% | Hyperliquid ecosystem | SPOT_PERP | 10% | <= 250 | 7-14 days | 2-3 |
| **Cross-venue** | 15% | Paradex, Lighter, OKX... | PERP_PERP | 20% | N/A | 7-10 days | 1-2 |

### 1.2 APR Convention

> **Critical distinction**:
> - **Pair APR** = funding rate APR of the perp symbol (observable on Loris/exchange)
> - **Effective APR** = yield on total deployed capital
>   - SPOT_PERP: Effective APR = Pair APR / 2 (only 50% capital earns funding)
>   - PERP_PERP: Effective APR = Combined APR from both legs (100% capital earns/pays)

### 1.3 Position Sizing Rules

- Max 40% portfolio per single pair (across all tiers)
- Min $1,000 USDC per position
- Total portfolio target: rolling 14d AVG APR >= 7%

### 1.4 Example Allocation ($10,000 portfolio)

| Tier | Capital | Pairs | Per-pair size |
|------|---------|-------|--------------|
| Core | $6,000 | 2-3 pairs | $2,000-$3,000 |
| Satellite | $2,500 | 2 pairs | $1,250 |
| Cross-venue | $1,500 | 1 pair | $1,500 |

---

## 2. Entry Rules

### 2.1 Core Tier Entry Criteria

| Criteria | Threshold | Rationale |
|----------|-----------|-----------|
| **Pair APR14** | >= 10% | Effective APR >= 5% on total capital |
| **Funding consistency** | Daily APR > 0 at least 90% of last 30 days | Avoid pairs with high spikes followed by deeply negative funding |
| **APR7 vs APR14 deviation** | <= 30% | `\|APR7 - APR14\| / APR14 <= 0.3` — consistency check |
| **OI rank** | <= 100 | Ensures sufficient liquidity |
| **Funding history** | >= 14 days positive | Established track record required |
| **Stability score** | Top 20% of universe | Formula: `0.55 x APR14 + 0.30 x APR7 + 0.15 x APR_latest` |
| **Breakeven time** | <= 7 days | Total fees for both legs (spot entry/exit + perp entry/exit) |

### 2.2 Satellite Tier Entry Criteria

| Criteria | Threshold | Rationale |
|----------|-----------|-----------|
| **Pair APR14** | >= 20% | Effective APR >= 10% |
| **OI rank** | <= 250 | Allows smaller-cap pairs |
| **Funding history** | >= 7 days positive | Shorter track record acceptable |
| **Breakeven time** | <= 7 days | Must cover fees within hold period |
| **No duplicate base** | with Core tier | Diversification — no double-up on same asset |

### 2.3 Cross-venue Tier Entry Criteria (PERP_PERP)

| Criteria | Threshold | Rationale |
|----------|-----------|-----------|
| **Combined APR14** | >= 20% | 100% capital earns — sum of funding from both legs |
| **Breakeven time** | <= 7 days | Cross-venue fees are typically higher |
| **Venue stability** | Established venue | Do not trade on newly launched venues |

> **Cross-venue APR Calculation:**
>
> Since PERP_PERP uses 100% capital (long perp on venue A + short perp on venue B), the combined APR
> is the sum of funding received from both legs.
>
> **Example 1:**
> - Long Paradex (funding -100%) => long receives funding = +100%
> - Short Lighter (funding +10%) => short receives funding = +10%
> - Combined APR = 100% + 10% = **110%**
>
> **Example 2:**
> - Long Paradex (funding -100%) => long receives funding = +100%
> - Short Lighter (funding -20%) => short pays funding = -20%
> - Combined APR = 100% - 20% = **80%**

### 2.4 Portfolio Construction Process

1. **Pull data**: Run `pull_loris_funding.py` + `report_daily_funding_with_portfolio.py`
2. **Filter universe**: Filter by OI rank & APR thresholds for each tier
3. **Rank candidates**: Sort by stability score (descending)
4. **Check constraints**: Max 40% per pair, min $1,000, no duplicate base assets across tiers
5. **Calculate breakeven**: Use cost_model_v3 to verify breakeven <= 7 days
6. **Deploy**: Fill Core first, then Satellite, then Cross-venue

### 2.5 Portfolio Target Verification

| Tier | Strategy | Weight | Min Effective APR | Contribution |
|------|----------|--------|-------------------|-------------|
| Core | SPOT_PERP | 60% | 5% (pair >= 10%) | 3.0% |
| Satellite | SPOT_PERP | 25% | 10% (pair >= 20%) | 2.5% |
| Cross-venue | PERP_PERP | 15% | 20% (combined) | 3.0% |
| **Portfolio** | | **100%** | | **>= 8.5%** |

> Buffer of +1.5% above the 7% target. Provides headroom for periods when not fully
> deployed or when pairs earn near minimum thresholds.

---

## 3. Exit & Rotation Rules

> **Key principle**: Use APR7 (not APR14) for exit signals — APR14 is too laggy for crypto
> markets where funding can flip and erode earned carry quickly.

### 3.1 Core Tier Exit Rules

| Signal | Condition | Persistence | Action |
|--------|-----------|-------------|--------|
| **WARN** | Pair APR7 < 10% (effective < 5%) | Immediate | Flag for monitoring, do not exit |
| **REDUCE** | Pair APR7 < 8% (effective < 4%) | > 48h continuous | Reduce 50% size, reallocate to Satellite/Cross-venue |
| **EXIT** | Pair APR3d < 6% (effective < 3%) | > 72h continuous | Close entire position |
| **EXIT** | Funding flip negative | > 24h continuous | Close entire position |
| **EXIT** | Funding consistency < 70% in last 14d | Checked each review | Pair is deteriorating, exit early |

### 3.2 Satellite Tier Exit Rules

| Signal | Condition | Persistence | Action |
|--------|-----------|-------------|--------|
| **WARN** | Pair APR7 < 20% (effective < 10%) | Immediate | Monitor |
| **EXIT** | Pair APR7 < 14% (effective < 7%) | > 24h continuous | Close position |
| **EXIT** | Funding flip negative | > 12h continuous | Close position |
| **EXIT** | Hold > 14 days + APR declining | Each review | Pair lost momentum, rotate |

### 3.3 Cross-venue Tier Exit Rules

| Signal | Condition | Persistence | Action |
|--------|-----------|-------------|--------|
| **WARN** | Combined APR7 < 20% | Immediate | Monitor |
| **EXIT** | Combined APR7 < 12% | > 24h | Close both legs |
| **EXIT** | Venue downtime/issue on either side | Immediate | Close both legs (risk of losing delta-neutral) |

### 3.4 Portfolio-Level Rules

| Rule | Condition | Action |
|------|-----------|--------|
| **Portfolio APR floor** | Rolling 7d portfolio APR < 5% | Emergency review: exit worst performers, reallocate |
| **Max idle capital** | > 30% capital undeployed > 3 days | Actively seek new entries, or temporarily lower tier thresholds |
| **Margin buffer** | Excess margin < 30% per account | Reduce largest positions until buffer restored |
| **Liquidation distance** | < 50% buffer to liquidation price | Immediate size reduction |
| **Concentration** | Single pair > 40% portfolio | Rebalance down to <= 40% |

### 3.5 Rotation Process

When exiting a position:

1. **Close position**: Unwind both legs (spot sell + perp close, or close both perps for cross-venue)
2. **Assess freed capital**: Determine which tier the capital belonged to
3. **Check candidates**: Run screener, filter by entry criteria of that tier
4. **Compare**: Best candidate must meet entry criteria AND have stability score > the exited pair
5. **Deploy**: If candidate qualifies, deploy. If not, hold capital idle (max 3 days), then consider allocating to another tier
6. **Log**: Record exit reason, realized PnL, new entry details

---

## 4. Risk Management & Operational Procedures

### 4.1 Delta Risk Management

| Check | Threshold | Frequency | Action |
|-------|-----------|-----------|--------|
| **Delta drift** | Spot vs Perp notional deviation > 2% | Each review (2-3x/week) | Rebalance legs to match |
| **Critical drift** | Deviation > 4% | Immediately upon detection | Rebalance immediately or reduce size |
| **Cross-venue delta** (PERP_PERP) | Long vs Short notional deviation > 3% | Each review | Adjust size on one leg |

### 4.2 Margin & Liquidation

| Check | Threshold | Action |
|-------|-----------|--------|
| **Excess margin** | < 30% on each account | Reduce largest position(s) |
| **Liquidation buffer** | < 50% distance to liquidation | Immediate size reduction |
| **Cross-venue margin** | Monitor separately per venue | Each venue has different margin models — check independently |

### 4.3 Operational Checklist (2-3x per week, ~15-20 min)

**Data pull:**

```bash
# 1. Public data pulls
scripts/pull_loris_funding.py
scripts/pull_hyperliquid_v3.py

# 2. Position/account sync
scripts/pull_positions_v3.py --venues hyperliquid

# 3. Realized cashflows
scripts/pm_cashflows.py ingest --venues hyperliquid
```

**Review:**

```bash
# Generate report
scripts/report_daily_funding_with_portfolio.py --top 10
```

- Check portfolio APR7 rolling — target >= 7%
- Check per-position advisory signals (HOLD / WARN / EXIT)
- Check delta drift & margin buffers
- Review rotation candidates if any EXIT signals

**Action (if needed):**

- Exit positions with EXIT signal
- Deploy freed capital into best candidates
- Log actions taken, reasons, timestamps

### 4.4 Venue-Specific Risks

| Venue | Risk | Mitigation |
|-------|------|------------|
| **Hyperliquid** | Smart contract risk, DEX downtime | Max 85% total portfolio |
| **Builder-dex** (xyz, felix...) | Lower liquidity, wider spreads | May be used in Core or Satellite, but apply Satellite-tier sizing (smaller positions) regardless of tier |
| **Paradex** | Newer venue, liquidity risk | Max 10% portfolio per cross-venue position |
| **Lighter** | Newer venue | Max 10% portfolio per cross-venue position |
| **Cross-venue general** | Settlement mismatch, different margin models | Always close both legs simultaneously |

### 4.5 Emergency Procedures

| Scenario | Action |
|----------|--------|
| **Venue outage** | If one leg is stuck, hedge on another venue if possible, or accept risk until venue recovers |
| **Flash crash / negative funding spike** | Do not panic close — check APR7 persistence rules, only exit if threshold is met |
| **Portfolio APR < 3%** (severe underperformance) | Full portfolio review, consider closing all and rebuilding from scratch |
| **Capital < min size** on a position | Close that position, consolidate capital into remaining positions |

---

## 5. Summary: Decision Flowchart

### Entry Decision

```
Pull data → Filter by tier criteria → Rank by stability score
→ Check constraints (size, concentration, no duplicates)
→ Verify breakeven <= 7 days → Deploy (Core first, then Satellite, then Cross-venue)
```

### Exit Decision

```
Review APR7 per position:
  → APR7 meets WARN threshold? → Monitor, no action
  → APR7 meets REDUCE threshold + persistence? → Reduce 50%
  → APR7 meets EXIT threshold + persistence? → Close position
  → Funding flip negative + persistence? → Close position
  → Funding consistency degraded? → Close position
```

### Rotation Decision

```
Position exited → Check candidates for same tier
  → Candidate meets entry criteria + stability > exited pair? → Deploy
  → No candidate qualifies within 3 days? → Allocate to another tier
```
