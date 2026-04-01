# Top Candidates Dashboard — Design Spec

**Date:** 2026-04-01
**Branch:** feat/monitoring-system
**Status:** Approved

---

## Overview

Add a `/candidates` page to the dashboard that displays the top rotation candidates ranked by stability score, split into two tabs: General and Equities (Felix). Includes an on-demand refresh button and a daily scheduled export at 7:00 AM GMT+7.

---

## Architecture & Data Flow

```
data/core_candidates_export.csv   ← written by export_core_candidates.py (cron + on-demand)
        ↓
GET /api/candidates               ← FastAPI reads CSV, splits by spot_on_felix, returns JSON
POST /api/candidates/refresh      ← FastAPI subprocess.run(export_core_candidates.py)
        ↓
/candidates page (Next.js)        ← server fetch on load, tab client component
        ├── Tab: General          ← spot_on_felix = False
        └── Tab: Equities         ← spot_on_felix = True
```

**Candidate source:** `data/core_candidates_export.csv` — output artifact of `scripts/export_core_candidates.py`. No DB schema changes required.

**Scheduled job:** `0 0 * * *` UTC (= 7:00 AM GMT+7) added to both `harmonix.cron` and `docker/crontab`.

---

## API

### `GET /api/candidates`

Reads `data/core_candidates_export.csv`, applies the WORKFLOW candidate floor filter, sorts, and splits.

**Filters:** `apr_14d >= 20`

**Sort:** `stability_score` descending

**Split:** `spot_on_felix = True` → equities list; else → general list

**Response:**
```json
{
  "general": [...],
  "equities": [...],
  "as_of": "2026-04-01T00:00:00Z",
  "total": 42
}
```

**Candidate row shape:**
```json
{
  "rank": 1,
  "symbol": "HYPE",
  "venue": "hyperliquid",
  "apr_14d": 45.2,
  "apr_7d": 38.1,
  "apr_1d": 52.3,
  "apr_3d": 41.0,
  "stability_score": 88.4,
  "flags": "LOW_LIQUIDITY_CONFIDENCE",
  "tradeability_status": "EXECUTABLE"
}
```

Note: `apr_2d` is not available in the CSV source — the table shows 1d/3d only, not 1d/2d/3d as listed in WORKFLOW.

**Error handling:** If CSV is missing or unreadable, return 503 with `{"detail": "Candidates data unavailable"}`.

---

### `POST /api/candidates/refresh`

Runs `scripts/export_core_candidates.py` as a subprocess with a 120s timeout.

**Success response:**
```json
{ "ok": true, "elapsed_s": 4.2 }
```

**Error response (500):** Script non-zero exit or timeout.

**Implementation:** `api/routers/candidates.py` — new router registered in `api/main.py`.

---

## Frontend

### Files changed / created

| File | Action |
|------|--------|
| `frontend/components/NavSidebar.tsx` | Add "Candidates" nav item |
| `frontend/app/candidates/page.tsx` | New server component — fetches GET /api/candidates |
| `frontend/components/CandidatesClient.tsx` | New client component — tab switcher + refresh button |
| `frontend/lib/api.ts` | Add `getCandidates()` and `refreshCandidates()` |
| `frontend/lib/types.ts` | Add `Candidate`, `CandidatesResponse` types |

### Nav

Add "Candidates" link to `NavSidebar.tsx` between Dashboard and Closed Positions. Use a star/sparkle SVG icon.

### Page layout

```
[ Candidates ]                         [ Refresh ] button (top-right, triggers POST)
Last updated: 2026-04-01 07:00 ICT

[ General | Equities ]   ← tab switcher

Table:
  # | Symbol | Venue | APR14 | APR7 | APR1d | APR3d | Stability | Flags
```

### Tab behavior

`CandidatesClient.tsx` receives both `general` and `equities` arrays as props from the server component. Tab switch is pure client-side state — no additional fetch. Rank column is 1-based within each tab independently.

### Refresh button

- Calls server action wrapping `POST /api/candidates/refresh`
- Shows loading spinner during execution (~4s)
- On success: calls `router.refresh()` to re-run server component data fetch
- On error: shows inline error message

### Table details

- Rows sorted by stability score (API pre-sorts)
- `tradeability_status` shown as a colored badge: green for `EXECUTABLE`, gray for `NON_EXECUTABLE`
- `flags` shown as small muted text (truncated if long)
- No hard row cut — full list rendered, matching full candidate pool beyond top 10

---

## Cron Schedule

Add to **both** `harmonix.cron` and `docker/crontab`:

```cron
# Daily candidates export (7:00 AM GMT+7 = 00:00 UTC)
0 0 * * * cd <workspace> && source .arbit_env && .venv/bin/python scripts/export_core_candidates.py >> logs/export_core_candidates.log 2>&1
```

Use workspace path appropriate to each file's convention.

---

## Out of Scope

- Filtering/sorting controls on the page (static ranked view only)
- Persisting candidates to DB
- Rotation Cost Analysis integration (on-demand only, per WORKFLOW)
- Auto-refresh / polling
