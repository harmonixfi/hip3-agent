# Fund Utilization Report — Design Spec

**Date:** 2026-04-02
**Goal:** Add fund utilization metrics to the dashboard so the user can answer: How leveraged are we? How much capital is available to deploy? How concentrated is each position?

## Summary

Three changes:
1. **API** — Add `fund_utilization` field to `GET /api/portfolio/overview`
2. **Frontend — Fund Utilization card** — New card showing leverage, deployed/available capital, per-account breakdown
3. **Frontend — Allocation column** — New "Alloc %" column in positions table

## 1. Data Model & API

### New Pydantic models

```python
class AccountUtilization(BaseModel):
    label: str              # "main", "alt"
    venue: str              # "hyperliquid"
    equity_usd: float       # total balance
    margin_used_usd: float  # margin in use
    available_usd: float    # free margin (from exchange)
    position_value_usd: float  # total notional on this account
    leverage: float         # position_value / equity

class FundUtilization(BaseModel):
    total_equity_usd: float
    total_notional_usd: float       # sum notional all OPEN positions
    total_deployed_usd: float       # = total_notional
    total_available_usd: float      # sum available_balance across accounts
    leverage: float                 # total_notional / total_equity
    deployed_pct: float             # total_notional / total_equity * 100
    accounts: list[AccountUtilization]
```

### Endpoint change

Extend `PortfolioOverview` response with:
```python
fund_utilization: FundUtilization
```

### Computation logic

- `leverage` = `total_notional / total_equity` (e.g., 15k/10k = 1.5x)
- `total_notional` = sum of `abs(size * current_price)` from all OPEN/PAUSED/EXITING legs — reuse existing `_gross_notional_usd_from_leg_rows` logic
- `available_usd` = sum of `available_balance` from `pm_account_snapshots` (latest row per account)
- Per-account `position_value_usd` = sum notional of legs belonging to that account
- Per-account `leverage` = `position_value_usd / equity_usd`
- Edge case: if `equity == 0`, leverage = 0.0 (avoid division by zero)

### Data sources (all existing, no schema changes)

- `pm_account_snapshots` — `total_balance`, `available_balance`, `margin_balance`, `position_value` (latest per account)
- `pm_legs` + `pm_entry_prices` / `prices_v3` — for notional calculation

### Multi-venue extensibility

Logic queries account data dispatched by `venue` field. Currently only Hyperliquid adapter exists. Adding a new venue requires implementing the same query interface for that venue's account snapshot data.

## 2. Frontend — Fund Utilization Card

### Layout

New card in the top summary row, alongside Equity / Wallet Breakdown / Funding Summary.

```
┌─────────────────────────────────┐
│  FUND UTILIZATION               │
│                                 │
│  Leverage        1.5x           │
│  Deployed        $28,580  83%   │
│  Available       $5,711         │
│                                 │
│  ┌──────────────────────────┐   │
│  │ main   $67    0.04x      │   │
│  │ alt    $34,223  1.48x    │   │
│  └──────────────────────────┘   │
└─────────────────────────────────┘
```

### Metrics displayed

| Metric | Source | Description |
|--------|--------|-------------|
| Leverage | `fund_utilization.leverage` | Total notional / total equity, formatted as "1.5x" |
| Deployed | `fund_utilization.total_deployed_usd` + `deployed_pct` | Dollar amount + percentage |
| Available | `fund_utilization.total_available_usd` | Free margin across all accounts |
| Per-account rows | `fund_utilization.accounts[]` | Label, equity, leverage per account |

### Color coding for leverage

| Range | Color | Meaning |
|-------|-------|---------|
| < 1x | Green | Conservative |
| 1-2x | White | Normal |
| 2-3x | Yellow | Warning |
| > 3x | Red | Danger |

## 3. Frontend — Positions Table Allocation Column

### Column spec

- **Header:** "Alloc %"
- **Position:** After "Amount" column
- **Sortable:** Yes
- **Computation:** `position_amount_usd / sum(all_open_position_amount_usd) * 100`
- **Computed in:** Frontend (no API change needed — `amount_usd` already available)

### Color coding

| Range | Color | Meaning |
|-------|-------|---------|
| < 40% | White | Normal distribution |
| 40-50% | Yellow | Concentrated |
| > 50% | Red | Over-concentrated |

## Scope exclusions

- No historical leverage tracking (can add later via snapshot cron — Approach C)
- No schema migrations
- No changes to existing cron jobs
- No alerts/notifications for leverage thresholds (future feature)
