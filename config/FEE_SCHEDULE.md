# Fee Schedule Quick Reference

## Fee Schedule (Market/Taker Execution)

| Venue  | Product | Maker | Taker | Source |
|--------|---------|-------|-------|--------|
| OKX    | Spot    | 0.08% | 0.10% | [OKX Fee Schedule](https://www.okx.com/fees) |
| OKX    | Perp    | 0.02% | 0.05% | [OKX Fee Schedule](https://www.okx.com/fees) |
| Hyperliquid | Perp | -0.02% (rebate) | 0.05% | Hyperliquid fee schedule |
| Paradex | Perp   | 0.00% | 0.03% | Paradex default tier |
| Lighter | Perp    | 0.02% | 0.07% | Lighter default tier |
| Ethereal | Perp   | 0.00% | 0.03% | Bean confirmed |

## Roundtrip Fee Calculation

**Market Execution (Taker):**
```
Roundtrip Fee = (taker_fee_venue1 + taker_fee_venue2) × 2
```
- Entry: buy leg (pay taker) + sell leg (pay taker)
- Exit: sell leg (pay taker) + buy leg (pay taker)

**Examples:**
- Paradex ↔ Ethereal (both perp): (0.03% + 0.03%) × 2 = 0.12%
- OKX Perp ↔ Hyperliquid: (0.05% + 0.05%) × 2 = 0.20%
- OKX Spot ↔ OKX Perp: (0.10% + 0.05%) × 2 = 0.30%

**Limit Execution (Maker):**
```
Roundtrip Fee = (maker_fee_venue1 + maker_fee_venue2) × 2
```

## Spread Cost Calculation

**Cross-Spread (when bid/ask available):**
```
Spread Cost = (ask_long - bid_short) / mid_average × 100
```

**Proxy Fallback (when bid/ask unavailable):**
```
Spread Cost = proxy_slippage_bps / 100
```
Default proxy: 10 bps = 0.10%

## Total Cost Model

```
Cost Min = fee_cost_pct (fees only)
Cost Est = fee_cost_pct + spread_cost_pct (fees + spread/proxy)
Total Cost = Cost Est (used in PnL calculation)
```

## PnL Calculation

```
14D PnL% = net_funding_apr × (14/365) - cost_est_pct
Breakeven Days = cost_est_pct / (net_funding_apr / 365)
```
