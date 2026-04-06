# Position Review Schedule

Last updated: 2026-03-30

---

## Active Reviews

| Position | Next Review | Action If Positive | Action If Negative | Notes |
|----------|-------------|--------------------|--------------------|-------|
| FARTCOIN | **2026-04-01 (Wed)** | HOLD, consider INCREASE | MONITOR if APR7 drops below 20% | Opened 03-27, 3d APR 41.9%, top performer |
| HYPE | **2026-04-01 (Wed)** | HOLD | MONITOR if APR7 drops below 15% | Opened 03-27, 3d APR 25.4%, consistent |
| LINK | **2026-04-01 (Wed)** | HOLD if APR7 > 5% | EXIT — redeploy capital | Opened 03-27, 3d APR 0.9%, 1d recovering 8.9% |
| GOLD | **2026-04-01 (Wed)** | HOLD | EXIT if APR7 < 3% sustained | Reopened 03-25, avg $0.38/d, 4.7% APR |

---

## Wednesday 01 Apr Review Checklist

### Pre-Review (pull fresh data)
- [ ] `pull_loris_funding.py` — fresh funding snapshot
- [ ] `pull_hyperliquid_v3.py` — fresh market data
- [ ] `pull_positions_v3.py` — position state
- [ ] `pm_cashflows.py ingest` — realized cashflows

### Per-Position Evaluation
- [ ] **FARTCOIN**: Is 7d APR still > 20%? Is 1d trend sustaining above 15%?
- [ ] **HYPE**: Is 7d APR still > 15%? Any negative funding spikes?
- [ ] **LINK**: Has 7d APR improved above 5%? If not → EXIT candidate
- [ ] **GOLD**: Is avg/day improving from $0.38? APR trend direction?

### Decision Framework
- **HOLD criteria**: 7d APR > 10% AND trend stable or improving
- **EXIT criteria**: 7d APR < 5% AND no recovery trend in 1d/3d
- **INCREASE criteria**: 7d APR > 20% AND stable (1d ≈ 3d ≈ 7d)

### Post-Review
- [ ] Update this file with new review dates
- [ ] Write journal entry (`tracking/journal/2026-04-01.md`)
- [ ] Update positions.json if any changes
- [ ] Sync to DB: `pm.py sync-registry`

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-03-30 | ALL | HOLD all, no changes | 3 days too early for rotation. FARTCOIN/HYPE strong, LINK/GOLD weak but monitoring |
| 2026-03-28 | ORCL | EXIT (CLOSED) | 15d avg -$1.33, slow recovery, rotated to crypto |
| 2026-03-28 | MU | EXIT (CLOSED) | +$2.85 lifetime, rotated to crypto |
| 2026-03-28 | CRCL | EXIT (CLOSED) | +$5.47 lifetime, locked profit |
| 2026-03-25 | ORCL | Reduce size 55.774 → 22.174, HOLD | 15d avg -$1.89, too large for bleeding position |
| 2026-03-25 | MSTR | EXIT (CLOSED) | Dead money, $0.02/day on $982 notional |
| 2026-03-25 | MU | HOLD to Fri review | Small loss, best 1d recovery |
| 2026-03-25 | CRCL | HOLD to Fri review (override EXIT signal) | Lifetime PnL still positive |
