# Design: Open Positions — Windowed APR & Funding Columns

Date: 2026-03-31
Status: Approved

---

## Goal

Add two grouped columns to the **Open Positions** table in the dashboard UI:

1. **APR (realized)** — 1d / 3d / 7d / 14d annualized rates
2. **Funding ($) (realized)** — 1d / 3d / 7d / 14d cumulative cashflows

Both columns are derived from actual realized cashflows in `pm_cashflows`, not market rates.

---

## Architecture

**Option A** was chosen: compute windowed metrics directly in the API router using a single batched SQL query. No new files or shared modules required.

---

## Backend

### New Pydantic schema — `api/models/schemas.py`

```python
class WindowedMetrics(BaseModel):
    funding_1d:           float | None
    funding_3d:           float | None
    funding_7d:           float | None
    funding_14d:          float | None
    apr_1d:               float | None  # % annualized, None if incomplete_notional
    apr_3d:               float | None
    apr_7d:               float | None
    apr_14d:              float | None
    incomplete_notional:  bool          # True if any leg was skipped (price missing)
    missing_leg_ids:      list[str]     # leg_ids that were skipped
```

Add to `PositionSummary`:

```python
windowed: WindowedMetrics | None  # None if position has no cashflows yet
```

### New function — `api/routers/positions.py`

`_windowed_metrics(db, position_id, amount_usd, leg_rows, now_ms) -> WindowedMetrics`

**Step 1 — Detect incomplete notional.**

Iterate `leg_rows`. A leg is skipped if it has no `current_price`, no `avg_entry_price`, and no `entry_price`. Collect skipped `leg_id`s into `missing_leg_ids`. Set `incomplete_notional = len(missing_leg_ids) > 0`.

**Step 2 — Single batched funding query.**

```sql
SELECT
  SUM(CASE WHEN ts >= :ms_1d  THEN amount ELSE 0 END) AS funding_1d,
  SUM(CASE WHEN ts >= :ms_3d  THEN amount ELSE 0 END) AS funding_3d,
  SUM(CASE WHEN ts >= :ms_7d  THEN amount ELSE 0 END) AS funding_7d,
  SUM(CASE WHEN ts >= :ms_14d THEN amount ELSE 0 END) AS funding_14d
FROM pm_cashflows
WHERE position_id = ? AND cf_type = 'FUNDING'
```

Where `ms_Xd = now_ms - X * 86400 * 1000`.

**Step 3 — Derive APR.**

```
apr_Xd = (funding_Xd / X) * 365 / amount_usd * 100
```

- `amount_usd` is already total capital (sum of all legs' `abs(size * price)`).
- No `* 2` factor — unlike the report script which uses one-leg registry notional.
- If `incomplete_notional=True`, all `apr_*` fields are set to `None`. Funding `$` values are still returned as they are trustworthy regardless.
- If `amount_usd` is `None` or `<= 0`, all `apr_*` are `None`.
- If a window returns `0.0` funding (new position, no cashflows yet), `windowed` is still returned but funding and APR values are `None` for that window (rendered as `—` in the UI, not `0%`).

### Call site

`_windowed_metrics()` is called inside `_build_position_summary()`, after `leg_rows` and `amount_usd` are already resolved. Adds **1 SQL query** per position (up from 4 to 5 total).

---

## Frontend

### `frontend/lib/types.ts`

```typescript
export interface WindowedMetrics {
  funding_1d:          number | null;
  funding_3d:          number | null;
  funding_7d:          number | null;
  funding_14d:         number | null;
  apr_1d:              number | null;
  apr_3d:              number | null;
  apr_7d:              number | null;
  apr_14d:             number | null;
  incomplete_notional: boolean;
  missing_leg_ids:     string[];
}

// Add to Position:
windowed: WindowedMetrics | null;
```

### `frontend/components/PositionsTable.tsx`

Two new columns inserted after **Carry APR**:

**Column headers** use the existing `TooltipHeader` component:

- `APR (realized)` — tooltip: `"Realized APR from pm_cashflows.\nAnnualized from actual funding earned.\nNot a market rate."`
- `Funding $ (realized)` — tooltip: `"Realized funding cashflows from pm_cashflows.\n1d / 3d / 7d / 14d cumulative."`

**Cell layout** — stacked sub-values in a single `<td>`:

```
1d   3d   7d   14d
45%  42%  38%  35%
```

Rendered as a 4-column mini-grid inside the cell. Labels (`1d`, `3d`, `7d`, `14d`) are in `text-gray-500 text-xs`. Values use:

- APR: `pnlColor()` + `formatPct(v, 1)`
- Funding: `formatUSD(v)` (no color — cashflows are always cumulative positive for funded positions)

**Warning state** (`incomplete_notional=true`):

- APR cell: shows `⚠` icon in `text-yellow-400` with tooltip listing missing leg IDs: `"APR unavailable — spot leg price missing.\nAffected legs: [leg_id_1, ...]"`
- Funding cell: renders normally (values are trustworthy)

**Empty state** (`windowed=null` or all values null):

- Both cells show `—`

---

## APR Formula Notes

The report script (`_fmt_funding_apr`) uses:
```
apr = (funding / days) * 365 / (amount_usd * 2) * 100
```
because `amount_usd` in the registry is **one-leg notional**.

The API uses:
```
apr = (funding / days) * 365 / amount_usd * 100
```
because `amount_usd` in the API is already **total capital** (sum of all legs via `_gross_notional_usd_from_leg_rows`).

These will produce **different APR numbers** for the same position. The dashboard shows the more accurate figure.

---

## Files Changed

| File | Change |
|------|--------|
| `api/models/schemas.py` | Add `WindowedMetrics`, add `windowed` field to `PositionSummary` |
| `api/routers/positions.py` | Add `_windowed_metrics()`, call it in `_build_position_summary()` |
| `frontend/lib/types.ts` | Add `WindowedMetrics` interface, add `windowed` to `Position` |
| `frontend/components/PositionsTable.tsx` | Add 2 grouped columns with sub-value grid cells |

No new files. No changes to the report script.
