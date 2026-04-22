# Morning Review — 2026-04-22

**Data:** Vault pulse ~15:31 UTC | Journal from Day 1 deployment session

---

## 1. Portfolio Health

| Metric | Current | Target | Status |
|--------|---------|--------|--------|
| Deployed | $240k (30%) | $800k (100%) | RED — 70% idle |
| Daily yield (deployed only) | ~$30/day | $154/day | RED — 19% of target |
| Blended APY (deployed) | ~4.6% | 7.04% | RED — only HyperLend USDC earning |
| USDT0 exposure | $0 (0%) | $200k (25%) | N/A — not yet acquired |
| Largest protocol | HyperLend $230k (96% of deployed) | <50% | YELLOW — temporary, expected to diversify |

**Interpretation:** Day 1 of deployment. Only HyperLend USDC ($230k) is live. This is expected per the execution sequence — USDC lending first, then USDT0 swap, then USDT0 lending. The critical concern isn't the current state; it's the Felix USDC blocker (see below).

---

## 2. Position Status

| Position | Rate | Target | vs Target | Signal | Action |
|----------|------|--------|-----------|--------|--------|
| HyperLend USDC $230k | 4.75% live / 4.16% 7d avg | 4.36% | 7d avg 5% below target | YELLOW | HOLD — rate volatile in 3.0-4.6% range |
| HyperLend USDT $50k | 5.92% live / 3.29% 7d avg | 5.79% | 7d avg 43% BELOW target | RED | PENDING deploy — when deployed, use 3.29% for projections |
| Felix USDT0 $100k | 14.72% | 15.39% | -4% | GREEN | WAITING on USDT0 acquisition |
| HypurrFi USDT0 $100k | 6.37% | 6.36% | On target | GREEN | WAITING on USDT0 acquisition |
| Felix USDC $300k | **DOES NOT EXIST** | 6.86% | N/A | **RED** | **BLOCKER — see below** |
| LINK spot-perp ~$5k | 10.95% APR | 10.2% | +7% | GREEN | HOLD |
| FARTCOIN spot-perp ~$5k | 10.95% APR | 12.1% | -10% | GREEN | HOLD |
| COPPER $10k | ON HOLD | TBD | — | — | Pending macro research |

---

## 3. Trigger Check

| Trigger | Threshold | Current | Status |
|---------|-----------|---------|--------|
| Felix USDT0 < 8% | < 8% | 14.72% | GREEN |
| Felix USDC < 8% | < 8% | **POOL DOESN'T EXIST** | **RED — DATA GAP** |
| USDT0 depeg > 1% | > 1% | +0.035% | GREEN |
| USDT0 depeg > 3% | > 3% | +0.035% | GREEN |
| HyperLend USDC < 5% | < 5% | 4.75% (7d avg 4.16%) | **YELLOW — 7d avg already below 5%** |
| HyperLend USDC < 3% | < 3% | 4.75% | GREEN |
| HyperLend USDT < 5% | < 5% | 5.92% (7d avg 3.29%) | **YELLOW — 7d avg already below 5%** |
| Spot-perp LINK < 8% | < 8% | 10.95% | GREEN (cap rate regime) |
| Spot-perp FARTCOIN < 8% | < 8% | 10.95% | GREEN (cap rate regime) |

---

## 4. Yesterday -> Today

### From Journal (2026-04-22 — Day 1)

| Action Item | Status |
|-------------|--------|
| Close hyna:LINK leg | DONE |
| Close OIL_BRENTOIL spread | DONE |
| Deploy $230k USDC to HyperLend | DONE |
| Place $30k USDT0 maker buy | DONE — order live, 0% filled so far |
| Deploy $300k USDC to Felix USDC | **BLOCKED — pool doesn't exist** |
| Deploy $50k USDT to HyperLend USDT | PENDING |
| Update positions.json with lending positions | PENDING |

### Notable Changes
- Vault pulse confirms Felix has NO USDC vault — only USDT0, USDe, USDhl, HYPE vaults available
- This was already documented in `docs/lessons.md` lesson #4 but the deployment plan still includes it
- HyperLend USDC rate at 4.75% — slightly above the 7d avg of 4.16%, consistent with normal volatility

### Review Schedule — OVERDUE
- **All 4 reviews were due 2026-04-01** (FARTCOIN, HYPE, LINK, GOLD) — 21 days overdue
- HYPE and GOLD are now CLOSED, so those are moot
- LINK and FARTCOIN reviews still outstanding — both at cap rate so not urgent, but schedule needs updating

---

## 5. Today's Plan

### Priority #1 (RED): Resolve Felix USDC $300k Allocation

The single largest allocation in the plan ($300k, 37.5% of portfolio) has no valid destination. Felix doesn't offer USDC lending on HyperEVM. Options to evaluate:

| Option | Amount | Est. APY | Pro | Con |
|--------|--------|----------|-----|-----|
| More HyperLend USDC | +$300k | ~4.2% (7d avg) | Simple, immediate | Pushes HyperLend to $530k (66%) — breaks 50% protocol cap |
| Felix USDT0 (increase) | +$300k as USDT0 | 14.72% | High yield | USDT0 exposure jumps to $500k (62.5%) — way over 25% cap |
| Split: HyperLend USDC $150k + HypurrFi USDC | $150k + $150k | ~4.2% / ~20.7% | Diversified | HypurrFi USDC headroom check needed (lesson #9) |
| Hold in USDC, wait for new opportunities | $300k idle | 0% | No risk | Massive opportunity cost (~$45/day) |

**Recommendation:** Pull live HypurrFi USDC data (headroom, utilization) before deciding. If headroom allows $100-150k, split between HyperLend and HypurrFi. Otherwise, accept temporary HyperLend concentration while scouting alternatives.

### Priority #2: Deploy $50k USDT to HyperLend USDT
Straightforward, no blockers. But note: 7d avg rate is 3.29%, not the 5.79% live rate. At 3.29%, this $50k earns $4.50/day vs the $7.93 projected. Acceptable given small allocation.

### Priority #3: Monitor USDT0 order fill
$30k maker buy at 1.0002 — still 0% filled. The $4.8k pending order in vault pulse is at 1.0003 (different price). Check if the $30k order is still live or was cancelled/adjusted.

### Priority #4: Update positions.json
Add HyperLend USDC lending position. Remove closed positions or mark as CLOSED.

---

## 6. Challenger Questions

1. **Felix USDC is a phantom allocation.** The plan projects $56.38/day from a pool that doesn't exist (lesson #4 confirmed this). That's 37% of daily target yield. Without resolving this, the plan's 7.04% APR is fiction — real achievable APR is closer to **5.2-5.5%** with current alternatives. Are we OK with that, or does the strategy need redesign?

2. **HyperLend USDT at 5.92% live but 3.29% 7d average** (lesson #8). The deployment plan uses 5.79% — that's the spike, not the norm. At 3.29%, the $50k allocation earns $4.50/day, not $7.93. Small dollar impact ($3.43/day), but it signals we might be overestimating across the board. What's the HyperLend USDC 7d average telling us about sustainable yield?

3. **LINK and FARTCOIN are both at cap rate (10.95%).** Lesson #10 warns that cap rate data tells you nothing about normal behavior. When cap rate regime ends, these could drop to 2-3% overnight. What's the exit plan? The $10k is small, but the review schedule is 21 days overdue.

---

## 7. Risk Watch

### Scenario: Felix USDC Allocation Failure Cascades

**What:** The $300k earmarked for Felix USDC has no home. If rerouted entirely to HyperLend, protocol concentration hits 66%. If converted to USDT0 for Felix/HypurrFi, bridge exposure hits 50%+.

**Probability:** Already happening (100%) — this is today's #1 problem.

**Impact:** At best, $300k earns lower yield (~4.2% in HyperLend vs planned 6.86%), costing ~$22/day ($8k/yr). At worst, concentration risk means a single protocol exploit could hit >50% of portfolio.

**Trigger Signal:** Already triggered — vault pulse confirms no Felix USDC pool.

**Pre-planned Response:**
1. Check HypurrFi USDC headroom today (use `hypurrfi` skill)
2. If headroom >$150k: split $150k HypurrFi USDC + $150k HyperLend USDC
3. If headroom <$50k: deploy $200k more to HyperLend USDC (accept temporary 54% concentration) + $100k to HypurrFi USDT0 (if USDT0 acquired)
4. Revise deployment plan targets with realistic numbers
5. Set weekly rebalance check until diversification improves

---

*Review generated 2026-04-22. Next scheduled review: daily.*
