# Delta-Neutral Rules - Hyperliquid Spot + Perp

Status: draft for operator use
Owner: Bean / Harmonix
Last updated: 2026-03-06

## 1) Strategy definition

This strategy is a **single-venue Hyperliquid** delta-neutral carry trade:

- long the spot asset
- short the perp of the same asset
- size both legs in **token units**
- hold only when expected funding carry remains positive after costs

The goal is boring carry, not directional PnL.

## 2) Candidate entry criteria

A symbol is eligible only if all of the following are true:

### Funding persistence

- `APR14 >= 20%`
- `APR7` does not materially contradict `APR14`
- `APR_latest` is not a one-print outlier against the trend

Interpretation:
- best case: `APR_latest`, `APR7`, and `APR14` all support the same carry regime
- weaker case: `APR_latest` softens, but `APR7` and `APR14` are still aligned -> smaller conviction
- reject: `APR_latest` flips hard against both `APR7` and `APR14`

### Freshness

- funding and position inputs must be fresh enough for same-day advisory
- if funding inputs are stale, the symbol cannot be promoted to a normal tradable recommendation

### Market quality

- liquidity must be adequate for Bean's intended size
- basis / spread cannot be so wide that the carry edge is fake
- weak-liquidity names can remain in watchlist / flagged sections, but not top recommendations

### Economics after costs

- estimated round-trip costs must be modeled before recommendation
- the trade must still have positive expected carry after:
  - trading fees
  - slippage
  - spread / basis drag

## 3) Stability score

Use this score only as a ranking aid, never as the sole entry rule:

`stability_score = 0.55 * APR14 + 0.30 * APR7 + 0.15 * APR_latest`

Interpretation:
- high score + fresh data + aligned regime = good candidate
- high score + stale inputs = flagged, not trusted
- high latest print with weak `APR7`/`APR14` = suspicious, not premium

## 4) Position lifecycle rules

### HOLD

Use `HOLD` when:
- current regime still broadly matches the historical regime
- realized funding remains positive net of fees
- no obvious hedge mismatch or operational issue exists

### MONITOR

Use `MONITOR` when:
- `APR_latest` weakens versus `APR14`
- net realized carry is still positive, but decelerating
- data quality is slightly degraded
- risk is still acceptable, but conviction fell

### EXIT

Use `EXIT` when one or more of these happen:
- realized economics turn unattractive after fees
- persistence breaks hard enough that the carry thesis is no longer intact
- the hedge is structurally broken or missing
- basis / execution conditions invalidate the expected edge
- data integrity is bad enough that holding becomes guesswork

### INCREASE SIZE

Use `INCREASE SIZE` only when:
- carry regime remains aligned across `APR_latest`, `APR7`, and `APR14`
- current realized economics are healthy
- the position already behaves cleanly
- margin buffer remains healthy after the increase

Never recommend a size increase into stale data or unstable funding.

## 5) Sizing guidance

- Keep leverage conservative: usually `2-3x`
- Maintain `30-50%` margin buffer
- Size in **token units**
- Prefer larger allocations only for cleaner, more liquid names
- Lower-liquidity names get smaller size even if the headline APR looks great

## 6) Recommendation policy

The agent may:
- rank candidates
- review active positions
- suggest `HOLD` / `MONITOR` / `EXIT` / `INCREASE SIZE`
- explain break-even logic and carry stability

The agent may not:
- auto-open positions
- auto-close positions
- change live risk settings without Bean

## 7) Daily report contract

The daily report must include:

1. Snapshot time and freshness state
2. Quick take
3. Current position review
4. Top new candidates
5. Flagged stale / unstable / low-confidence names
6. Explicit action list

Headline economics:
- realized funding
- trading fees
- net realized

Diagnostic context:
- unrealized mark-to-market

## 8) Failure modes

Degrade the report instead of bluffing when:
- funding inputs are stale
- position pulls fail
- cashflow ledger ingest fails
- one leg of a pair is missing

In degraded mode:
- say so near the top
- keep the flagged section
- avoid strong recommendations unless the surviving evidence is still clear
