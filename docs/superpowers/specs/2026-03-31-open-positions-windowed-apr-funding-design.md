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
    apr_1d:               float | None  # percent form e.g. 38.5 means 38.5%. None if incomplete_notional.
    apr_3d:               float | None
    apr_7d:               float | None
    apr_14d:              float | None
    incomplete_notional:  bool          # True if any leg was skipped (missing price or size)
    missing_leg_ids:      list[str]     # leg_ids that were skipped
```

Add to `PositionSummary`:

```python
windowed: WindowedMetrics | None  # None only if amount_usd is unavailable at call time
```

`PositionDetail` extends `PositionSummary`, so `windowed` propagates automatically. The detail page (`/positions/{id}`) will receive it — no UI change needed there, the field is simply available.

### New function — `api/routers/positions.py`

Signature: `_windowed_metrics(db, position_id, amount_usd_raw, leg_rows, now_ms) -> WindowedMetrics | None`

- `amount_usd_raw`: the **raw unrounded** float from `_gross_notional_usd_from_leg_rows()`, not the `round(..., 2)` value stored in `PositionSummary`. Pass it before rounding to avoid precision loss on small positions.
- `now_ms`: caller computes `int(datetime.now(timezone.utc).timestamp() * 1000)` once at the top of `_build_position_summary()` and passes it in. `_windowed_metrics` does not call `datetime.now()` internally.
- Returns `None` if `amount_usd_raw` is `None` or `<= 0`.

**Step 1 — Detect incomplete notional.**

Mirror the skip logic of `_gross_notional_usd_from_leg_rows()` exactly. A leg is skipped (and added to `missing_leg_ids`) if:
- `size` is `None`, **or**
- all three price fields are `None`: `current_price`, `avg_entry_price`, and `entry_price`

Set `incomplete_notional = len(missing_leg_ids) > 0`.

**Step 2 — Single batched funding query.**

Use positional `?` placeholders to match the rest of `positions.py`:

```sql
SELECT
  SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_1d,
  SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_3d,
  SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_7d,
  SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_14d
FROM pm_cashflows
WHERE position_id = ? AND cf_type = 'FUNDING'
```

Parameters: `(now_ms - 1*86400*1000, now_ms - 3*86400*1000, now_ms - 7*86400*1000, now_ms - 14*86400*1000, position_id)`

The query always returns one row. `SUM(CASE WHEN ... ELSE 0 END)` returns `0.0` both when no rows exist and when rows net to zero — these cases are treated identically: treat `0.0` as no data and set the field to `None` (rendered as `—` in UI, not `0%`). This accepts a minor semantic imprecision (positive + negative cashflows summing to exactly zero is indistinguishable from no cashflows) which is an acceptable edge case in practice.

**Step 3 — Derive APR.**

APR values are in **percent form** (e.g. `38.5` means 38.5%):

```
apr_Xd = (funding_Xd / X) * 365 / amount_usd_raw * 100
```

- `amount_usd_raw` is already total capital (sum of all legs' `abs(size * price)`). No `* 2`.
- If `incomplete_notional=True`, all `apr_*` are `None`. Funding `$` values are still returned.
- If `funding_Xd` is `None` or `0.0`, `apr_Xd` is `None`.

### Call site

Inside `_build_position_summary()`, after `leg_rows` and the raw `amount_usd` are resolved, before rounding:

```python
now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
windowed = _windowed_metrics(db, position_id, amount_usd, leg_rows, now_ms)
# ... then round amount_usd for PositionSummary
```

Adds **1 SQL query** per position (4 → 5 total).

---

## Frontend

### `frontend/lib/types.ts`

```typescript
export interface WindowedMetrics {
  funding_1d:          number | null;
  funding_3d:          number | null;
  funding_7d:          number | null;
  funding_14d:         number | null;
  apr_1d:              number | null;  // percent form, e.g. 38.5
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

Final column order (10 total):
**Base | Status | Amount | uPnL | Funding | Carry APR | APR (realized) | Funding $ (realized) | Exit Spread | Spread P&L**

Two new columns inserted after **Carry APR**, before **Exit Spread**.

**Column headers** use the existing `TooltipHeader` component:

- `APR (realized)` — tooltip: `"Realized APR from pm_cashflows.\nAnnualized from actual funding earned.\nNot a market rate."`
- `Funding $ (realized)` — tooltip: `"Realized funding cashflows from pm_cashflows.\n1d / 3d / 7d / 14d cumulative."`

**Cell layout** — stacked sub-values in a single `<td>`:

```
1d   3d   7d   14d
45%  42%  38%  35%
```

Rendered as a 4-column mini-grid inside the cell. Labels (`1d`, `3d`, `7d`, `14d`) in `text-gray-500 text-xs`. Values:

- APR: `pnlColor()` + `formatPct(v, 1)`. Values are already in percent form from the API (e.g. `38.5`), so pass directly to `formatPct` without multiplying by 100.
- Funding: `formatUSD(v)` (no color)

**Warning state** (`incomplete_notional=true`):

- APR cell: use an SVG warning icon (match existing SVG icon style from `TooltipHeader`) in `text-yellow-400` with tooltip: `"APR unavailable — spot leg price missing.\nAffected legs: [leg_id_1, ...]"`
- Funding cell: renders normally

**Empty state** (`windowed=null` or individual value `null`):

- Show `—` per sub-value

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

These produce **different APR numbers** for the same position. The dashboard shows the more accurate figure.

---

## Files Changed

| File | Change |
|------|--------|
| `api/models/schemas.py` | Add `WindowedMetrics`, add `windowed` field to `PositionSummary` |
| `api/routers/positions.py` | Add `_windowed_metrics()`, call it in `_build_position_summary()` |
| `frontend/lib/types.ts` | Add `WindowedMetrics` interface, add `windowed` to `Position` |
| `frontend/components/PositionsTable.tsx` | Add 2 grouped columns with sub-value grid cells |

No new files. No changes to the report script.
