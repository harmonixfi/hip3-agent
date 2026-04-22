# Cross-Venue Perp-Perp Spread Playbook

## Strategy Overview

Capture **funding rate differentials** between two perpetual contract venues on the same underlying asset. One venue (the "high-funding" venue) has structurally or periodically higher funding; the other (the "low-funding" venue) serves as the hedge leg.

**Core mechanic:**
- SHORT on high-funding venue → receive funding when positive
- LONG on low-funding venue → pay funding (ideally low/negative = we also receive)
- Net P&L = cumulative net funding ± price spread change at exit

This is NOT delta-neutral in the traditional sense — price spread between venues can diverge. Spread risk is the primary risk.

---

## When to Use This Strategy

**Good conditions:**
- One venue consistently has 3x+ higher funding than the other on the same asset
- Funding spikes are frequent (>2x/week) and last multiple hours
- Price spread between venues is mean-reverting (observable range)
- Net funding differential is positive >70% of the time

**Avoid when:**
- Funding is high on BOTH venues (no differential to capture)
- Price spread is trending (not mean-reverting) — you'll get locked in
- OI on either venue is too thin (oi_rank 9999, low volume)
- No historical data to establish funding regime (< 7 days of data)

---

## Pre-Trade Evaluation Checklist

### 1. Funding Analysis (quantitative)

| Metric | Minimum threshold | How to compute |
|--------|------------------|----------------|
| Net APR 7d | > 10% | `(avg_short_venue_rate - avg_long_venue_rate) × 1095 × 100` |
| Net positive hours | > 65% | Hours where short-venue rate > long-venue rate |
| Spike frequency | > 2/week | Count of hours where short-venue rate > 3× baseline |
| Max negative streak | < 24h | Longest consecutive run of negative net funding |
| Trend | STABLE or ACCELERATING | Compare 3d vs 7d net APR |

### 2. Spread Analysis

| Metric | What to check |
|--------|---------------|
| Current spread | Mark price difference between venues as % |
| 3d rolling avg spread | Where is the spread "normally"? |
| Spread range (7d) | Min and max observed |
| Entry zone | Current spread near low end of range (favorable exit optionality) |
| Spread-funding correlation | Do high funding periods coincide with wide spreads? |

### 3. Liquidity Gate

| Metric | Minimum |
|--------|---------|
| OI on each venue | > $500k per venue |
| 24h volume | Target entry < 10% of daily volume |
| Order book depth | Sufficient for target size without >0.1% slippage |

### 4. Macro/Model Context

Before entering, answer:
- WHY is funding persistently higher on venue A vs venue B?
- Is this structural (different user base, market maker incentives) or temporary (news-driven)?
- What would cause the regime to flip?

---

## Entry Protocol

### Step 1: Observe (minimum 2-3 days)

- Log hourly funding rates for both venues
- Track price spread every 4-8 hours
- Identify the spread range and mean
- Confirm funding differential persists across different market conditions

### Step 2: Choose entry timing

- Enter when price spread is at or below the rolling 3d average
- NEVER enter when spread is at the high end — you'll be locked into a bad exit
- Prefer entering during low-volatility periods (not around funding spikes, as spread may be temporarily wide)

### Step 3: Execute

- Open both legs within a narrow time window (< 5 minutes apart)
- Record exact fill prices for both legs → this determines your entry spread
- Use limit orders where possible to reduce fee drag

### Step 4: Record

Create a trade log entry (see Trade Log Template below).

---

## Position Management

### Daily monitoring

- Check net funding earned (both legs)
- Check current price spread vs entry spread
- Check if funding regime is intact (no sustained flip)

### Warning signals

| Signal | Action |
|--------|--------|
| Net funding negative for > 6 consecutive hours | Evaluate exit |
| Price spread widens > 1% beyond entry | Evaluate exit (spread loss eating funding gains) |
| Funding regime flip (both venues similar) | Exit — no edge |
| OI dropping on either venue | Reduce size or exit |

### Exit triggers

| Trigger | Priority |
|---------|----------|
| Funding flips negative for > 12h | EXIT immediately |
| Spread loss exceeds 3 days of expected funding | EXIT — cut loss |
| Target holding period reached with profit | EXIT — take profit |
| Better opportunity identified | Rotate capital |

---

## Risk Framework

### Risk 1: Funding flip

Funding can flip from positive to negative suddenly. When this happens:
- The short leg starts paying instead of receiving
- Often coincides with spread widening (double whammy)
- Mitigation: strict exit rules on consecutive negative hours

### Risk 2: Spread divergence

Price spread between venues is NOT guaranteed to mean-revert. It can:
- Trend in one direction due to venue-specific events
- Gap on weekends (some venues pause trading)
- Widen during high volatility
- Mitigation: enter at low spread, size appropriately

### Risk 3: Liquidity trap

Thin books on either venue can mean:
- Can't exit at desired price
- Slippage exceeds funding gains
- Mitigation: size < 5% of daily volume on the thinner venue

### Risk 4: Weekend gaps

Some venues (tradexyz, felix) don't trade weekends for certain assets.
- Funding may still accrue on one leg but not the other
- Price can gap on Monday open
- Mitigation: either close Friday or accept weekend risk with smaller size

---

## Breakeven Formula

```
Breakeven days = (entry_spread_cost + total_fees) / daily_net_funding

Where:
  entry_spread_cost = notional × |entry_spread - expected_exit_spread|
  total_fees = notional × (entry_fee_rate + exit_fee_rate) × 2 legs
  daily_net_funding = notional × net_APR / 365
```

**Example:**
- $10k notional, entry spread 1.05%, expected exit 0.5%
- Spread cost: $10k × 0.55% = $55
- Fees: $10k × 0.0134% × 2 legs × 2 (entry+exit) = $5.36
- Daily net funding at 80% APR: $10k × 80% / 365 = $21.92
- Breakeven: ($55 + $5.36) / $21.92 = **2.8 days**

---

## Sizing Guidelines

| Confidence level | Max allocation | When |
|-----------------|---------------|------|
| Observation phase | $0 (paper trade) | First 2-3 days |
| Initial test | $10-20k | After funding + spread confirmed |
| Validated | $20-50k | After 1+ week of positive P&L |
| Scaled | $50-100k | After 2+ weeks, with clear regime understanding |

Never size more than 10% of total active trading capital in a single cross-venue spread.

---

## Trade Log Template

Each trade should be logged separately for post-analysis. Use `tracking/trades/cross-venue/` directory.

```markdown
# Trade: {SYMBOL} Cross-Venue Spread — {date_opened}

## Setup
- Short: {venue}:{symbol} @ {entry_price}
- Long: {venue}:{symbol} @ {entry_price}
- Entry spread: {spread_pct}%
- Notional: ${amount}
- Thesis: {why this trade now}

## Daily Log
| Date | Net funding ($) | Cumulative ($) | Spread (%) | Notes |
|------|----------------|----------------|------------|-------|

## Exit
- Date: {date_closed}
- Exit spread: {spread_pct}%
- Total funding earned: ${amount}
- Spread P&L: ${amount}
- Net P&L: ${amount}
- Holding period: {days}
- Annualized return: {apr}%

## Lessons
- What worked:
- What didn't:
- Would I take this trade again:
```

---

## Venue Mapping Reference

| Loris exchange | Short name | Funding frequency | Weekend trading |
|---------------|------------|-------------------|-----------------|
| `felix` | flx | Per-sample (~30min) | Check per-asset |
| `tradexyz` | xyz | Per-sample (~30min) | Check per-asset |
| `hyperliquid` | HL native | Hourly | Yes |
| `hyena` | hyna | Hourly | Yes |
| `kinetiq` | ktq | Per-sample | Check per-asset |
