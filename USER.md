# USER.md - About Bean

- **Name:** Bean
- **What to call them:** Bean
- **Timezone:** Asia/Ho_Chi_Minh (GMT+7)
- **Role:** Busy trader who wants operator-grade advisory, not noise.

## What Bean needs from this agent

- Ongoing monitoring of Hyperliquid delta-neutral carry positions.
- A stable daily report that is easy to scan on Telegram.
- Clear recommendations with reasons, not raw data dumps.
- Confidence that costs, freshness, and risk were checked before any recommendation.

## Strategy-specific preferences

- Strategy focus: Hyperliquid `spot + perp` same-asset delta-neutral carry.
- Entry floor: `APR14 >= 20%`.
- Leverage: conservative, normally `2-3x`.
- Universe bias: higher-liquidity assets first; weaker liquidity means smaller size.
- Bean cares about:
  - break-even hold time after costs,
  - stability of carry,
  - whether the regime is strengthening or decaying,
  - whether current positions still deserve capital.

## Reporting expectations

- Delivery time: `09:00` local time every day.
- Channel: Telegram.
- Headline economics: realized funding minus fees.
- Diagnostic detail: unrealized MTM shown separately.
- Position actions must use one of:
  - `HOLD`
  - `MONITOR`
  - `EXIT`
  - `INCREASE SIZE`

## Operating constraints

- Advisory only. Bean approves actions.
- No silent assumptions about missing data.
- If the report quality is degraded, say so in the first screen.
