# Vault strategy page: equity history table (design)

**Date:** 2026-04-07  
**Status:** Approved approach — implementation pending  
**Related:** `2026-03-31-vault-multi-strategy-tracking-design.md`

## Goal

Show a **read-only table of historical equity snapshots** on each vault strategy detail page (e.g. `/vault/strategies/delta_neutral`), using data already stored in `vault_strategy_snapshots` and exposed by the API.

## Current state

- **DB:** `vault_strategy_snapshots` — daily rows per `strategy_id` (`ts`, `equity_usd`, APR fields).
- **API:** `GET /api/vault/strategies/{strategy_id}/snapshots` — query params `limit` (1–365, default 30), optional `from` / `to` (epoch ms). Response: `StrategySnapshot[]` with `ts`, `equity_usd`, `apr_since_inception`, `apr_30d`, `apr_7d`.
- **UI:** `frontend/app/vault/strategies/[id]/page.tsx` loads only `GET /api/vault/strategies/{id}` (latest snapshot for summary cards). No history table.

## Decision: Approach A — server-rendered table

- **Rendering:** Next.js **server component** on the strategy detail route: fetch strategy detail **and** snapshot history in parallel (same pattern as `frontend/app/vault/page.tsx` using `Promise.all`).
- **No new API** for v1 unless we later need per-row `equity_breakdown` (not in `StrategySnapshot` today).
- **No client-side pagination** in v1; optional follow-up if lists grow uncomfortable.

## Default window

- Request **`limit=90`** on the snapshots endpoint from the page (explicit in code; overrides API default 30).
- **Rationale:** Balances useful history vs. payload size without extra UI. Changeable in one constant if product prefers 30 or 365.

## Table content

| Column        | Source field              | Format                          |
|---------------|---------------------------|---------------------------------|
| Date          | `ts`                      | Local or UTC date string — **use same convention as vault overview / cashflows pages** (match existing `format` helpers). |
| Equity        | `equity_usd`              | `formatUSD`                     |
| APR inception | `apr_since_inception`     | `formatPct` or `—` if null      |
| 30d / 7d APR  | `apr_30d`, `apr_7d`       | Same as summary row on page     |

- **Sort:** Newest first (API already returns `ORDER BY ts DESC`).
- **Empty state:** Short message when zero rows (e.g. no daily snapshot run yet for this strategy).

## Frontend implementation sketch

1. **`frontend/lib/types.ts`:** Add `StrategySnapshot` interface aligned with API (mirror `StrategySnapshot` in `api/models/vault_schemas.py`).
2. **`frontend/lib/api.ts`:** Add `fetchVaultStrategySnapshots(strategyId: string, limit?: number)` → `GET /api/vault/strategies/{id}/snapshots?limit=...`.
3. **`frontend/app/vault/strategies/[id]/page.tsx`:** `Promise.all([fetchVaultStrategyDetail(id), fetchVaultStrategySnapshots(id, 90)])`; render existing cards unchanged; add a **card** section “Equity history” with an HTML table using existing `card` / typography patterns (consistent with `StrategyTable` / vault pages).

## Testing

- **Manual:** Load `/vault/strategies/<id>` with API running; table shows rows when DB has snapshots.
- **Automated (optional):** API tests for `strategy_snapshots` already exist in `tests/test_api.py`; extend only if a regression is likely from client contract changes (not required for a pure UI read).

## Out of scope (v1)

- Charts, CSV export, per-day equity breakdown in the table.
- Paginated or “load more” UI.
- Editing snapshot data from the UI.

## Self-review

- **Placeholders:** None.
- **Consistency:** Aligns with existing vault API and RSC data fetching.
- **Scope:** Single page + types + one API helper.
- **Ambiguity:** Date formatting defers to existing app convention (see table note).
