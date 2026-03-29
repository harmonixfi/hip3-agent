# Phase 2: PERP_PERP Support

**Goal**: Full support for perp-long + perp-short positions
**Depends on**: Phase 1 complete

## Tasks

### 6.1 Fill Ingestion
- [ ] Fill ingester handles both legs of PERP_PERP (both are perp fills)
- [ ] Both legs mapped correctly by inst_id + account_id

### 6.2 Computation
- [ ] uPnL: long perp uses bid for exit, short perp uses ask for exit
- [ ] Entry price: VWAP per leg (same logic, both legs are perps)
- [ ] Spread: `long_perp_bid / short_perp_ask - 1`
- [ ] Funding: both legs accrue funding. Net = SUM(all funding for position)
- [ ] Carry APR accounts for net funding (long funding typically negative)

### 6.3 Frontend
- [ ] Position detail shows both perp legs with individual funding
- [ ] Dashboard handles PERP_PERP display (no "spot" label)

### 6.4 Testing
- [ ] Add sample PERP_PERP position to positions.json
- [ ] End-to-end: fill ingestion → metrics → API → UI display
- [ ] Verify net funding = long_funding + short_funding

## Acceptance Criteria
- PERP_PERP position displays correctly with dual funding
- uPnL signs correct for both legs
- Spread calculation works for perp/perp pair
