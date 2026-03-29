# Phase 1b: Computation Layer

**Goal**: Avg entry price, uPnL, spread calculations, portfolio metrics
**Depends on**: Phase 1a (fills must exist in DB)

## Tasks

### 2.1 Entry Price Computer
- [ ] Create `tracking/pipeline/entry_price.py`
- [ ] VWAP calculation: `avg_entry = SUM(px * sz) / SUM(sz)` for opening fills
- [ ] Opening fill identification: BUY for LONG legs, SELL for SHORT legs
- [ ] Write results to `pm_entry_prices` (INSERT OR REPLACE on leg_id PK)
- [ ] Update `pm_legs.entry_price` column
- [ ] Handle partial close + re-open: FIFO cost basis
- [ ] Manual check: compute avg entry for pos_xyz_GOLD by hand, compare

### 2.2 uPnL Calculator
- [ ] Create `tracking/pipeline/upnl.py`
- [ ] Per-leg uPnL: LONG uses bid, SHORT uses ask from prices_v3
- [ ] Fallback: if bid/ask unavailable, use mid/last with quality flag
- [ ] Position-level uPnL = SUM(leg uPnLs)
- [ ] Update `pm_legs.unrealized_pnl` and `pm_legs.current_price`
- [ ] Sign verification: spot long below entry → negative uPnL ✓

### 2.3 Spread Calculator
- [ ] Create `tracking/pipeline/spreads.py`
- [ ] Entry spread: `long_avg_entry / short_avg_entry - 1`
- [ ] Exit spread: `long_exit_bid / short_exit_ask - 1`
- [ ] Spread P&L in bps: `(exit - entry) * 10000`
- [ ] Sub-pair generation: for split-leg positions, each short leg pairs with the long leg
- [ ] Write to `pm_spreads` (INSERT OR REPLACE on UNIQUE constraint)
- [ ] Verify: entry spread for a known position matches manual calculation

### 2.4 Portfolio Aggregator
- [ ] Create `tracking/pipeline/portfolio.py`
- [ ] Total equity from latest `pm_account_snapshots`
- [ ] Cashflow-adjusted APR: `(equity_change - net_deposits) / prior_equity / days * 365`
- [ ] Funding today: SUM(FUNDING cashflows WHERE ts >= today_start)
- [ ] Funding all-time: SUM(FUNDING cashflows WHERE ts >= tracking_start_date)
- [ ] Write hourly snapshot to `pm_portfolio_snapshots`

### 2.5 Metric Computation Orchestrator
- [ ] Create `scripts/pipeline_hourly.py`
- [ ] Orchestration order: pull fills → pull prices → compute entry prices → compute uPnL → compute spreads → compute portfolio snapshot
- [ ] Log summary: N new fills, N entries recomputed, portfolio equity
- [ ] Error handling: partial failure should not block other steps

## Acceptance Criteria
- All OPEN positions have computed avg entry prices matching manual verification
- uPnL signs are correct (spot down = negative for long)
- Spread values match manual calculation for at least 2 positions
- Portfolio snapshot written hourly with correct equity and APR
