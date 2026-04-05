# Design: Manual Cashflows History (Settings)

Date: 2026-04-05  
Status: Draft (pending implementation plan)

---

## Goal

Expose a **read-only** history of **manual** portfolio deposits and withdrawals on **Settings**, backed by `pm_cashflows`. Users can confirm what was recorded via `POST /api/cashflows/manual` (and equivalent CLI paths that set the same metadata).

**Out of scope:** `vault_cashflows` / vault UI — unchanged unless a later spec merges views.

---

## Definitions

**Manual row:** A row in `pm_cashflows` where:

- `cf_type` ∈ `('DEPOSIT', 'WITHDRAW')`, and  
- `json_extract(meta_json, '$.source') = 'manual'`

This matches the metadata written by `POST /api/cashflows/manual` (`api/routers/cashflows.py`). Rows without `meta_json` or with a different `source` are excluded (strict manual-only).

---

## Backend

### Route

- **Method / path:** `GET /api/cashflows/manual`
- **Auth:** Same as all `/api/*` routes (`X-API-Key` middleware).
- **DB:** Read-only dependency `get_db()` (not `get_db_writable`).

### Query parameters

| Param   | Default | Max | Behavior                          |
|---------|---------|-----|-----------------------------------|
| `limit` | 50      | 100 | Clamp incoming value to `[1, max]` |

Optional `offset` is **not** in v1; add only if pagination is needed later.

### SQL

```sql
SELECT
  cashflow_id,
  ts,
  cf_type,
  amount,
  currency,
  venue,
  account_id,
  description
FROM pm_cashflows
WHERE cf_type IN ('DEPOSIT', 'WITHDRAW')
  AND json_extract(meta_json, '$.source') = 'manual'
ORDER BY ts DESC
LIMIT ?
```

### Response shape

Return a **JSON object** with a list and echo applied limit (consistent with paginated-style endpoints such as fills):

```json
{
  "items": [
    {
      "cashflow_id": 1,
      "ts": 1712345678901,
      "cf_type": "DEPOSIT",
      "amount": 1000.0,
      "currency": "USDC",
      "venue": "hyperliquid",
      "account_id": "0x...",
      "description": "optional text"
    }
  ],
  "limit": 50
}
```

- **`ts`:** Unix epoch **milliseconds** UTC (same convention as `pm_cashflows.ts`). The UI labels this as “time” / formats for display.
- **`amount`:** Signed as stored: **positive** for `DEPOSIT`, **negative** for `WITHDRAW` (matches insert logic in `record_manual_cashflow`).
- **`cf_type`:** Included so the table can show Deposit vs Withdraw without inferring from sign alone.
- **`description`:** May be `null` or empty string depending on DB; serialize consistently (prefer `null` when SQL returns NULL).

### Pydantic

Add models in `api/models/schemas.py`, e.g. `ManualCashflowListItem`, `ManualCashflowListResponse`, and use `response_model` on the route.

### Router

Implement in `api/routers/cashflows.py` next to the existing `POST /manual` handler.

---

## Frontend

### Placement

- **Page:** `frontend/app/settings/page.tsx`
- **Order:** Below the existing **Manual Deposit / Withdraw** form (`ManualCashflowForm`), above **System Information** (or directly under the form card — either a new card titled **Manual cashflows** or a subsection; prefer a **separate card** for visual separation).

### Behavior

- **Client component** for the table that:
  1. Calls `GET /api/cashflows/manual` via a new `getManualCashflows(limit?)` in `frontend/lib/api.ts`.
  2. **Refetches** the list after a **successful** submit from the manual form (so the new row appears without a full page reload). Implementation options: wrapper component with shared state/callback, or `onSuccess` prop on `ManualCashflowForm` — keep boundaries clear and minimal diff.

### UI

- Small **table**: columns — **Time** (local/UTC formatted from `ts`), **Type** (`cf_type`), **Amount** (formatted signed or absolute + type; must match user expectations — show signed amount with clear sign or absolute + type column), **Currency**, **Venue**, **Account** (truncate middle with `title` full address optional), **Description**, **ID** (`cashflow_id`).
- **Newest first** (API order); show up to **50** rows by default (or match API default).
- Loading and error states consistent with other dashboard tables.
- **Read-only** — no edit/delete in v1.

### Types

Add TypeScript interfaces in `frontend/lib/types.ts` mirroring the API response.

---

## Testing

- **API:** Extend `tests/test_api.py` (or the canonical API test module):  
  - `GET` without key → 401.  
  - `POST` manual cashflow, then `GET /api/cashflows/manual` → item present with expected fields.  
  - Optional: row with `DEPOSIT` but `meta_json` not manual → not listed.

---

## Self-review checklist

| Check            | Result |
|------------------|--------|
| Placeholders     | None   |
| Internal consistency | SQL filter matches “manual” definition; amount sign matches POST |
| Scope            | Single feature; vault excluded |
| Ambiguity        | `ts` vs display “time” — API uses `ts` ms; UI formats |

---

## Approval

Design approved in session: strict manual filter (**A**), `GET /api/cashflows/manual`, `ts` + `cf_type` in payload, client table with refetch after submit, limit default 50 max 100.
