# MEMORY.md - Harmonix Long-Term Memory

Last updated: 2026-03-06

## Core strategy defaults

- Strategy type: Hyperliquid `spot + perp` same-asset delta-neutral carry.
- Agent role: advisory/orchestration only.
- Entry floor: `APR14 >= 20%`.
- Stability score:
  - `0.55 * APR14`
  - `0.30 * APR7`
  - `0.15 * APR_latest`
- Daily report channel/time: Telegram at `09:00` Asia/Ho_Chi_Minh.

## Reporting rules

- Headline economics = realized funding - trading fees.
- Unrealized MTM is diagnostic detail only.
- Every report must include a flagged section for stale, weak-confidence, or structurally broken names.
- Never send raw data dumps to chat.

## Portfolio / schema invariants

- One logical position = one asset-level pair.
- Legs = one spot leg + one perp leg.
- Position sizes are in **token units**, not USD.
- DB timestamps are in **milliseconds**.
- **Funding Summary** metrics (Funding Today, all-time sums vs `tracking_start_date`) use **UTC+0** calendar boundaries for “today” / date ranges — not local timezone.
- `cf_type` values are uppercase.

## Risk defaults

- Margin buffer target: `30-50%`
- Preferred leverage: `2-3x`
- Freshness is the first gate. If data is stale, the report is degraded.

## Reuse policy

- The local runtime tree (`scripts/`, `tracking/`, `config/`) was cloned from Arbit on `2026-03-06`.
- Generated state copied from Arbit was reset the same day so Harmonix starts with empty positions, empty alert/cashflow state, and no inherited equity/report artifacts.
- `config/strategy.json` was narrowed to Hyperliquid-only spot-perp defaults the same day so the local runtime no longer advertises Arbit's multi-exchange scope.
- Reuse the cloned PM DB patterns where possible.
- Do not invent new workflows if the current local tooling already covers the need.
