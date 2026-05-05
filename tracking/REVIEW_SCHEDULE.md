# Position Review Schedule

Last updated: 2026-05-05

---

## Active Reviews

### Lending Positions (7-day cadence)

| Position | Amount | Current APY | Next Review | Trigger | Action If Triggered |
|----------|--------|-------------|-------------|---------|---------------------|
| Felix USDC Main | $352,000 | 8.20% ✅ | **2026-05-08 (Thu)** | APR < 5% for 3d (320 bps headroom — RESTORED) | Rotate $100-150K to HyperLend USDC. |
| HyperLend USDC | $230,385 | 11.33% ⚠️spike | **2026-05-06 (Tue)** — moved up due to spike | APR < 3% (833 bps headroom) | Exit to Felix/HypurrFi. **Per lesson #8 — use 7d avg ~5.5% for projections, not live 11.33%.** |
| Felix USDT0 | $110,200 | 12.16% ✅ | **2026-05-08 (Thu)** | APR < 8% for 2wk (counter RESET — was Day 5) | USDT0 vs USDC premium back to 396 bps. Bridge risk compensated. |
| Felix USDC (alt) | $10,800 | 8.20% | **2026-05-08 (Thu)** | — | Small, monitor with main |
| Felix USDe | $3,600 | 17.76% ⚠️spike | **2026-05-06 (Tue)** | — | Tiny, but spike noted. |

### Spot-Perp Positions

| Position | Notional | Current APR | Next Review | Trigger | Action If Triggered |
|----------|----------|-------------|-------------|---------|---------------------|
| FARTCOIN | $12,408 | 13.00% | **2026-05-08 (Thu)** | APR < 8% | Exit, redeploy to lending. hyna funding spike +$17.80 again today — verify pattern. |
| LINK | $3,090 | 10.95% | **2026-05-08 (Thu)** | APR < 8% (295 bps headroom — RESTORED) | Exit, redeploy to lending. |
| LINK hyna dust | $22 | n/a | **2026-04-29 (Tue)** ⏰ **7 DAYS OVERDUE** | — | Clean up 2.4 short (cumFunding -$5.91). |
| **GOLD (NEW)** | $1,528 | unknown (builder dex) | **2026-05-07 (Wed)** | APR < 8% (no automated check possible) | Builder dex — funding rate not visible from standard API. Manual verification required. Delta -8% (wider than spec). |

### Cross-Venue

| Position | Notional | Next Review | Notes |
|----------|----------|-------------|-------|
| COPPER | ~$3,924 | **2026-05-02 (Fri)** 🔴 **3 DAYS OVERDUE** | EXIT IMMEDIATELY. Day 5 of broken thesis. flx cumFunding -$0.62 and worsening. Net P&L -$18.89. 5th consecutive EXIT recommendation. |

### Pending Deployments

| Target | Amount | Status | Review By |
|--------|--------|--------|-----------|
| HyperLend USDT | $0 of $50k | ❗ **14 DAYS OVERDUE.** Rate 5.49%. **HARD DEADLINE TODAY (May 5). Default = DROP if no decision.** Options: A) Deploy $50K USDT. B) Redirect to HyperLend USDC. C) Drop, redirect to Felix USDC. | **2026-05-05 (Mon) — HARD DEADLINE TODAY** |
| HypurrFi USDT0 | $0 of $100k | Blocked — no idle USDT0. Rate 7.40%. USDT0 thesis recovered (Felix USDT0 at 12.16%). Reconsider after HyperLend USDT decision. | **2026-05-08 (Thu)** |
| Idle xyz USDC | $6,300 | ⏰ **14 days idle.** Deploy → Felix USDC (8.20%). +$1.42/day. | **OVERDUE — execute ASAP** |
| Idle USDH (unified) | $2,954 free + $2,014 post-COPPER = ~$4,968 | Deploy → Felix USDH (6.72% — recovered partially). | **Execute after COPPER exit** |
| Idle USDC (unified) | $2,270 free + $1,963 post-COPPER = ~$4,233 | Deploy → Felix USDC (8.20%). Note: $737 already consumed by GOLD position. | **Execute after COPPER exit** |

---

## Concentration Watch

| Protocol | Current | Cap | Status | Path to Reduce |
|----------|---------|-----|--------|----------------|
| Felix/Morpho | 67.4% ($476,600) | 50% | RED — 17pts over cap | HyperLend USDT $50K deploy (-5.9pts → 61.5%). Adding more USDC to HyperLend an option if 11.33% rate sustains 3+ days (currently spike per lesson #8). Structural — needs new protocol or larger HyperLend allocation. |
| USDT0 exposure | 14.8% ($110,200) | 25% ($200K) | GREEN | Premium recovered to 396 bps over USDC. Hold. |

---

## Completed Reviews

| Date | Position | Decision | Rationale |
|------|----------|----------|-----------|
| 2026-05-05 | COPPER | **EXIT (3 days overdue)** | Day 5 of broken thesis. flx cumFunding -$0.62. Net P&L -$18.89. 5th consecutive EXIT recommendation. |
| 2026-05-05 | HyperLend USDT $50K | **HARD DEADLINE** | 14 days overdue. Default to DROP (Option C) if no decision today. |
| 2026-05-05 | All triggers | GREEN (all rate triggers) | No trigger breaches. Felix USDT0 counter at 0. HyperLend USDC spike per lesson #8. |
| 2026-05-04 | Felix USDT0 | YELLOW counter RESET | Rate surged 8.53%→12.16% (+363bps). Day 5 of 14 cleared. USDT0/USDC premium back to 396 bps. |
| 2026-05-04 | Felix USDC | Trigger watch CLEARED | Rate recovered to 8.20%. 320 bps headroom (was 75 yesterday). |
| 2026-05-04 | LINK | Trigger watch CLEARED | Rate stable at 10.95%. 295 bps headroom (was 75 yesterday). |
| 2026-05-04 | COPPER | **EXIT (2 days overdue)** | Day 4 of broken thesis. flx bleeding resumed -$0.36→-$0.62. Net P&L -$18.89. xyz LONG paying funding (unusual). |
| 2026-05-03 | COPPER | **EXIT (1 day overdue)** | flx cumFunding negative day 2. Net P&L -$20.19. Thesis broken. |
| 2026-05-02 | COPPER | **EXIT (recommended)** | flx cumFunding decreased $3.10→$1.81 — short side paid funding, thesis broken. Net P&L: -$5.50. |
| 2026-05-01 | FARTCOIN | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (-0.4%). Next review May 8. |
| 2026-05-01 | LINK | HOLD | 10.95% cap rate, GREEN. 295 bps headroom. Delta neutral (1.1%). Next review May 8. |
| 2026-04-30 | Felix USDT0 | HOLD (day-3 review) | Rate 6.48%, still below 8% (YELLOW day 3). HypurrFi USDT0 rate (6.36%) lower — move not justified. HOLD until day 7 (May 4). |
| 2026-04-29 | COPPER | HOLD (reviewed) | cumFunding $3.64, uPnL -$11.72 net. Hard exit May 2 if not break-even. |
| 2026-04-29 | Felix USDT0 | WATCH (YELLOW day 2) | Rate partial recovery 6.08%→6.48%. Still below 8%. |
| 2026-04-29 | Felix USDC Main | WATCH (rate sliding) | Rate 6.39% — 3-day slide. 139 bps headroom vs 5% trigger. |
| 2026-04-28 | Felix USDC Main | HOLD (reviewed) | Rate 6.89% (GREEN, 189 bps above 5% trigger). |
| 2026-04-28 | HyperLend USDC | HOLD (reviewed) | Rate 5.61% (GREEN, 261 bps above 3% trigger). |
| 2026-04-28 | Felix USDT0 | WATCH (YELLOW day 1) | Rate crashed 13.38% → 6.08%. |
| 2026-04-27 | FARTCOIN | HOLD (recovered) | Funding recovered to 10.95% from 1.78%. |
| 2026-04-27 | LINK | HOLD (RED cleared) | Funding recovered to 10.95% from 7.59%. |
| 2026-04-27 | Felix USDT0 | HOLD (YELLOW cleared) | Rate surged to 13.38%. Idle USDT0 deployed. |
| 2026-04-25 | USDT0 swap order | CLOSED (completed) | ~$49.84k USDC swapped to USDT0. All deployed. |
| 2026-04-23 | LINK | HOLD (overrode EXIT signal) | Funding recovered from -8.04% to +10.95% overnight |
| 2026-04-22 | OIL_BRENTOIL | EXIT (CLOSED) | Per deployment plan — capital redeployed to lending |
| 2026-04-22 | hyna:LINK | EXIT (CLOSED) | Restructured to native-only. 2.4 dust remains. |
| 2026-03-30 | ALL | HOLD all, no changes | 3 days too early for rotation |
| 2026-03-28 | ORCL | EXIT (CLOSED) | 15d avg -$1.33, slow recovery |
| 2026-03-28 | MU | EXIT (CLOSED) | +$2.85 lifetime, rotated to crypto |
| 2026-03-28 | CRCL | EXIT (CLOSED) | +$5.47 lifetime, locked profit |
| 2026-03-25 | MSTR | EXIT (CLOSED) | Dead money, $0.02/day on $982 notional |
