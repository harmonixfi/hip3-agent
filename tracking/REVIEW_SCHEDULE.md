# Position Review Schedule

Last updated: 2026-03-25

---

## Active Reviews

| Position | Next Review | Action If Positive | Action If Negative | Notes |
|----------|-------------|--------------------|--------------------|-------|
| ORCL | **2026-03-27 (Fri)** | HOLD, reassess weekly | EXIT — 15d avg still negative | Reduced from 55.774 → 22.174 on 03-25 |
| MU | **2026-03-27 (Fri)** | HOLD, consider INCREASE if APR7 > 20% | EXIT — funding not recovering | Best 1d recovery in portfolio |
| CRCL | **2026-03-27 (Fri)** | HOLD if latest APR turns positive | EXIT — lock current profit (+$4.24) | System flagged EXIT on 03-25, overridden to HOLD |
| MSTR | **2026-03-25 21:30 ICT** | n/a | EXIT tonight at US market open | Dead money, $0.02/day funding |
| XAU/kinetiq | **2026-04-01 (post-open)** | HOLD | MONITOR — check if consistent | Pending open, ~$5k, APR14 18.7% |
| XAU/tradexyz | **2026-03-27 (Fri)** | SCALE if APR7 >15%, no 2 neg days | REDUCE if APR7 <10% or 2+ neg days | OPENED 03-25, 0.66 oz ~$2k, APR14 14.2%, 30% neg day rate |

---

## Friday 27 Mar Review Checklist

### Pre-Review (pull fresh data)
- [ ] `pull_loris_funding.py` — fresh funding snapshot
- [ ] `pull_hyperliquid_v3.py` — fresh market data
- [ ] `pull_positions_v3.py` — position state
- [ ] `pm_cashflows.py ingest` — realized cashflows
- [ ] `report_daily_funding_with_portfolio.py --section portfolio-summary`

### Per-Position Evaluation
- [ ] **ORCL**: Is 15d avg/day improving from -$1.89? Is 1d/2d trend sustaining?
- [ ] **MU**: Is 15d avg/day turning positive? Is 1d spike ($2.26) repeating or fading?
- [ ] **CRCL**: Has latest APR turned positive? Is lifetime PnL still positive?

### Decision Framework
- **HOLD criteria**: 2d APR > 5% AND 15d avg improving (less negative or positive)
- **EXIT criteria**: 15d avg still negative AND 1d/2d trend reversing back to negative
- **INCREASE criteria**: APR7 > 20% net AND stable trend (APR_latest > APR7 > APR14)

### Post-Review
- [ ] Update this file with new review dates
- [ ] Write journal entry (`tracking/journal/2026-03-27.md`)
- [ ] Update positions.json if any EXIT/rebalance decisions
- [ ] Sync to DB: `pm.py sync-registry`

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-03-25 | ORCL | Reduce size 55.774 → 22.174, HOLD | 15d avg -$1.89, too large for bleeding position |
| 2026-03-25 | MSTR | EXIT (scheduled 21:30 ICT) | Dead money, $0.02/day on $982 notional |
| 2026-03-25 | MU | HOLD to Fri review | Small loss, best 1d recovery |
| 2026-03-25 | CRCL | HOLD to Fri review (override EXIT signal) | Lifetime PnL still positive |
