# Top Candidates Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/candidates` page to the dashboard showing top rotation candidates split into General and Equities tabs, with an on-demand refresh button and a daily 7:00 AM GMT+7 cron job.

**Architecture:** A new FastAPI router reads `data/core_candidates_export.csv`, filters/sorts/splits, and serves JSON via two endpoints. The Next.js frontend adds a server-rendered `/candidates` page with a client tab-switcher component. The refresh button triggers the export script via a server action calling `POST /api/candidates/refresh`.

**Tech Stack:** Python 3.9, FastAPI, Pydantic v2, Next.js 14 App Router, TypeScript, Tailwind CSS

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `api/models/schemas.py` | Modify | Add `Candidate`, `CandidatesResponse` Pydantic models |
| `api/routers/candidates.py` | Create | `GET /api/candidates` + `POST /api/candidates/refresh` |
| `api/main.py` | Modify | Register candidates router |
| `tests/test_candidates_api.py` | Create | API tests for both endpoints |
| `frontend/lib/types.ts` | Modify | Add `Candidate`, `CandidatesResponse` TS interfaces |
| `frontend/lib/api.ts` | Modify | Add `getCandidates()`, `refreshCandidates()` |
| `frontend/app/candidates/page.tsx` | Create | Server component — fetches candidates on load |
| `frontend/components/CandidatesClient.tsx` | Create | Client component — tabs + refresh button |
| `frontend/components/NavSidebar.tsx` | Modify | Add "Candidates" nav link |
| `harmonix.cron` | Modify | Add 00:00 UTC daily export job |
| `docker/crontab` | Modify | Add 00:00 UTC daily export job |

---

## Task 1: Write failing API tests

**Files:**
- Create: `tests/test_candidates_api.py`

- [ ] **Step 1: Create the test file**

```python
#!/usr/bin/env python3
"""Tests for GET /api/candidates and POST /api/candidates/refresh."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_API_KEY = "test-key-12345"
os.environ["HARMONIX_API_KEY"] = TEST_API_KEY

from fastapi.testclient import TestClient


def _headers() -> dict:
    return {"X-API-Key": TEST_API_KEY}


def _make_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "symbol", "funding_venue", "tradeability_status", "pair_quality_score",
        "stability_score", "effective_apr_anchor", "oi_rank",
        "breakeven_estimate_days", "apr_latest", "apr_1d", "apr_3d",
        "apr_7d", "apr_14d", "spot_on_hyperliquid", "spot_on_felix",
        "freshness_hours", "flags",
    ]
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


SAMPLE_ROWS = [
    {
        "symbol": "HYPE", "funding_venue": "hyperliquid",
        "tradeability_status": "EXECUTABLE", "pair_quality_score": "80.0",
        "stability_score": "75.5", "effective_apr_anchor": "30.0",
        "oi_rank": "5", "breakeven_estimate_days": "8.0",
        "apr_latest": "55.0", "apr_1d": "50.0", "apr_3d": "45.0",
        "apr_7d": "38.0", "apr_14d": "35.0",
        "spot_on_hyperliquid": "True", "spot_on_felix": "False",
        "freshness_hours": "0.5", "flags": "",
    },
    {
        "symbol": "AAPL", "funding_venue": "hyperliquid",
        "tradeability_status": "EXECUTABLE", "pair_quality_score": "70.0",
        "stability_score": "60.0", "effective_apr_anchor": "25.0",
        "oi_rank": "10", "breakeven_estimate_days": "12.0",
        "apr_latest": "30.0", "apr_1d": "28.0", "apr_3d": "26.0",
        "apr_7d": "25.0", "apr_14d": "22.0",
        "spot_on_hyperliquid": "True", "spot_on_felix": "True",
        "freshness_hours": "0.5", "flags": "HIGH_BREAKEVEN",
    },
    {
        "symbol": "LOWRATE", "funding_venue": "hyperliquid",
        "tradeability_status": "NON_EXECUTABLE", "pair_quality_score": "40.0",
        "stability_score": "20.0", "effective_apr_anchor": "10.0",
        "oi_rank": "50", "breakeven_estimate_days": "30.0",
        "apr_latest": "10.0", "apr_1d": "10.0", "apr_3d": "10.0",
        "apr_7d": "10.0", "apr_14d": "10.0",   # below 20% floor
        "spot_on_hyperliquid": "False", "spot_on_felix": "False",
        "freshness_hours": "2.0", "flags": "MISSING_SPOT",
    },
]


def test_get_candidates_splits_general_and_equities():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    _make_csv(csv_path, SAMPLE_ROWS)

    with patch("api.routers.candidates.CSV_PATH", csv_path):
        from api.main import app
        client = TestClient(app)
        resp = client.get("/api/candidates", headers=_headers())

    csv_path.unlink(missing_ok=True)

    assert resp.status_code == 200
    data = resp.json()
    assert "general" in data
    assert "equities" in data
    assert "as_of" in data
    assert "total" in data

    symbols_general = [c["symbol"] for c in data["general"]]
    symbols_equities = [c["symbol"] for c in data["equities"]]

    assert "HYPE" in symbols_general
    assert "AAPL" in symbols_equities
    # LOWRATE has apr_14d=10 < 20, must be excluded
    assert "LOWRATE" not in symbols_general
    assert "LOWRATE" not in symbols_equities


def test_get_candidates_sorted_by_stability_score():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    rows = [
        {**SAMPLE_ROWS[0], "symbol": "LOW_STAB", "stability_score": "10.0", "spot_on_felix": "False"},
        {**SAMPLE_ROWS[0], "symbol": "HIGH_STAB", "stability_score": "90.0", "spot_on_felix": "False"},
    ]
    _make_csv(csv_path, rows)

    with patch("api.routers.candidates.CSV_PATH", csv_path):
        from api.main import app
        client = TestClient(app)
        resp = client.get("/api/candidates", headers=_headers())

    csv_path.unlink(missing_ok=True)

    assert resp.status_code == 200
    general = resp.json()["general"]
    assert general[0]["symbol"] == "HIGH_STAB"
    assert general[1]["symbol"] == "LOW_STAB"


def test_get_candidates_rank_is_1_based_per_tab():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    _make_csv(csv_path, SAMPLE_ROWS[:2])

    with patch("api.routers.candidates.CSV_PATH", csv_path):
        from api.main import app
        client = TestClient(app)
        resp = client.get("/api/candidates", headers=_headers())

    csv_path.unlink(missing_ok=True)

    data = resp.json()
    if data["general"]:
        assert data["general"][0]["rank"] == 1
    if data["equities"]:
        assert data["equities"][0]["rank"] == 1


def test_get_candidates_missing_csv_returns_503():
    missing = Path("/tmp/does_not_exist_candidates.csv")
    with patch("api.routers.candidates.CSV_PATH", missing):
        from api.main import app
        client = TestClient(app)
        resp = client.get("/api/candidates", headers=_headers())
    assert resp.status_code == 503


def test_refresh_candidates_calls_script(tmp_path):
    with patch("api.routers.candidates.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        from api.main import app
        client = TestClient(app)
        resp = client.post("/api/candidates/refresh", headers=_headers())

    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "elapsed_s" in data
    mock_run.assert_called_once()


def test_refresh_candidates_script_failure_returns_500():
    with patch("api.routers.candidates.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "script error"
        from api.main import app
        client = TestClient(app)
        resp = client.post("/api/candidates/refresh", headers=_headers())

    assert resp.status_code == 500
```

- [ ] **Step 2: Run tests — expect ImportError (router not yet created)**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_candidates_api.py -v 2>&1 | head -30
```

Expected: errors like `cannot import name 'candidates'` or `ModuleNotFoundError`.

---

## Task 2: Add Pydantic schemas

**Files:**
- Modify: `api/models/schemas.py`

- [ ] **Step 1: Append Candidate and CandidatesResponse to `api/models/schemas.py`**

Add at the end of the file:

```python
# ============================================================
# Candidates — GET /api/candidates
# ============================================================

class Candidate(BaseModel):
    rank: int
    symbol: str
    venue: str
    apr_14d: Optional[float]
    apr_7d: Optional[float]
    apr_1d: Optional[float]
    apr_3d: Optional[float]
    stability_score: Optional[float]
    flags: str
    tradeability_status: str


class CandidatesResponse(BaseModel):
    general: list[Candidate]
    equities: list[Candidate]
    as_of: str   # ISO 8601 — CSV file mtime
    total: int
```

---

## Task 3: Implement GET /api/candidates router

**Files:**
- Create: `api/routers/candidates.py`

- [ ] **Step 1: Create the router file**

```python
"""Candidates endpoints.

GET  /api/candidates         — read core_candidates_export.csv, filter/sort/split
POST /api/candidates/refresh — run export_core_candidates.py as subprocess
"""

from __future__ import annotations

import csv
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException

from api.config import ROOT
from api.models.schemas import Candidate, CandidatesResponse

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

CSV_PATH = ROOT / "data" / "core_candidates_export.csv"
SCRIPT_PATH = ROOT / "scripts" / "export_core_candidates.py"
PYTHON_BIN = ROOT / ".venv" / "bin" / "python"

APR14_FLOOR = 20.0


def _parse_float(value: str) -> Optional[float]:
    """Return float or None for empty/dash/non-numeric values."""
    v = value.strip()
    if not v or v == "-":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _load_candidates() -> tuple[list[Candidate], list[Candidate], str]:
    """Read CSV, filter, sort, split into general + equities.

    Returns (general, equities, as_of_iso).
    Raises HTTPException 503 if CSV is missing or unreadable.
    """
    if not CSV_PATH.exists():
        raise HTTPException(status_code=503, detail="Candidates data unavailable")

    try:
        mtime = CSV_PATH.stat().st_mtime
        as_of = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        rows: list[dict] = []
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except OSError as exc:
        raise HTTPException(status_code=503, detail="Candidates data unavailable") from exc

    # Filter: apr_14d >= floor
    filtered = [r for r in rows if (_parse_float(r.get("apr_14d", "")) or 0.0) >= APR14_FLOOR]

    # Sort: stability_score descending
    filtered.sort(key=lambda r: _parse_float(r.get("stability_score", "")) or 0.0, reverse=True)

    general: list[Candidate] = []
    equities: list[Candidate] = []

    for row in filtered:
        is_equity = row.get("spot_on_felix", "").strip().lower() == "true"
        target = equities if is_equity else general
        rank = len(target) + 1
        target.append(Candidate(
            rank=rank,
            symbol=row.get("symbol", ""),
            venue=row.get("funding_venue", ""),
            apr_14d=_parse_float(row.get("apr_14d", "")),
            apr_7d=_parse_float(row.get("apr_7d", "")),
            apr_1d=_parse_float(row.get("apr_1d", "")),
            apr_3d=_parse_float(row.get("apr_3d", "")),
            stability_score=_parse_float(row.get("stability_score", "")),
            flags=row.get("flags", ""),
            tradeability_status=row.get("tradeability_status", ""),
        ))

    return general, equities, as_of


@router.get("", response_model=CandidatesResponse)
def get_candidates() -> CandidatesResponse:
    """Return ranked candidates split into general and equities."""
    general, equities, as_of = _load_candidates()
    return CandidatesResponse(
        general=general,
        equities=equities,
        as_of=as_of,
        total=len(general) + len(equities),
    )


@router.post("/refresh")
def refresh_candidates() -> dict:
    """Run export_core_candidates.py and return elapsed time."""
    t0 = time.time()
    python = str(PYTHON_BIN) if PYTHON_BIN.exists() else "python"
    result = subprocess.run(
        [python, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    elapsed = round(time.time() - t0, 2)

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Export script failed: {result.stderr[:500]}",
        )

    return {"ok": True, "elapsed_s": elapsed}
```

- [ ] **Step 2: Export `ROOT` from `api/config.py`**

`ROOT` is already defined at module level in `api/config.py` as `ROOT = Path(__file__).parent.parent`. The import in the router uses `from api.config import ROOT` — verify this works by checking the existing definition:

```bash
grep "^ROOT" /Users/beannguyen/Development/OpenClawAgents/hip3-agent/api/config.py
```

Expected: `ROOT = Path(__file__).parent.parent`

---

## Task 4: Register the candidates router

**Files:**
- Modify: `api/main.py`

- [ ] **Step 1: Add import and include_router**

In `api/main.py`, find the router registration block (lines 94-99):

```python
from api.routers import portfolio, positions, cashflows, health  # noqa: E402

app.include_router(portfolio.router)
app.include_router(positions.router)
app.include_router(cashflows.router)
app.include_router(health.router)
```

Replace with:

```python
from api.routers import portfolio, positions, cashflows, health, candidates  # noqa: E402

app.include_router(portfolio.router)
app.include_router(positions.router)
app.include_router(cashflows.router)
app.include_router(health.router)
app.include_router(candidates.router)
```

- [ ] **Step 2: Run the tests — all should pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_candidates_api.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Commit**

```bash
git add api/models/schemas.py api/routers/candidates.py api/main.py tests/test_candidates_api.py
git commit -m "feat(api): add /api/candidates GET and POST /refresh endpoints"
```

---

## Task 5: Add frontend types and API client functions

**Files:**
- Modify: `frontend/lib/types.ts`
- Modify: `frontend/lib/api.ts`

- [ ] **Step 1: Add types to `frontend/lib/types.ts`**

Append at the end of the file:

```typescript
// ============================================================
// Candidates — GET /api/candidates
// ============================================================

export interface Candidate {
  rank: number;
  symbol: string;
  venue: string;
  apr_14d: number | null;
  apr_7d: number | null;
  apr_1d: number | null;
  apr_3d: number | null;
  stability_score: number | null;
  flags: string;
  tradeability_status: string;
}

export interface CandidatesResponse {
  general: Candidate[];
  equities: Candidate[];
  as_of: string;
  total: number;
}
```

- [ ] **Step 2: Add API functions to `frontend/lib/api.ts`**

Append after the `postManualCashflow` function:

```typescript
// ---- Candidates ----

export async function getCandidates(): Promise<CandidatesResponse> {
  return apiFetch<CandidatesResponse>("/api/candidates", {
    next: { revalidate: 0 },  // no ISR — fresh on each page load
  });
}

export async function refreshCandidates(): Promise<{ ok: boolean; elapsed_s: number }> {
  return apiFetch<{ ok: boolean; elapsed_s: number }>("/api/candidates/refresh", {
    method: "POST",
  });
}
```

Also add `CandidatesResponse` to the import at the top of `frontend/lib/api.ts`:

```typescript
import type {
  PortfolioOverview,
  Position,
  PositionDetail,
  FillsResponse,
  ClosedPosition,
  HealthStatus,
  ManualCashflowRequest,
  ManualCashflowResponse,
  CandidatesResponse,
} from "./types";
```

- [ ] **Step 3: Verify TypeScript compiles (no errors)**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output (clean compile).

- [ ] **Step 4: Commit**

```bash
git add frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(frontend): add Candidate types and API client functions"
```

---

## Task 6: Create the CandidatesClient component

**Files:**
- Create: `frontend/components/CandidatesClient.tsx`

- [ ] **Step 1: Create the client component**

```tsx
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Candidate, CandidatesResponse } from "@/lib/types";

function fmt(val: number | null, decimals = 1): string {
  if (val === null || val === undefined) return "—";
  return val.toFixed(decimals) + "%";
}

function TradeabilityBadge({ status }: { status: string }) {
  const isExecutable = status === "EXECUTABLE";
  return (
    <span
      className={`inline-block text-xs px-1.5 py-0.5 rounded font-medium ${
        isExecutable
          ? "bg-green-900/50 text-green-400"
          : "bg-gray-700 text-gray-400"
      }`}
    >
      {isExecutable ? "EXE" : "NON"}
    </span>
  );
}

function CandidateTable({ rows }: { rows: Candidate[] }) {
  if (rows.length === 0) {
    return <p className="text-gray-500 text-sm py-4">No candidates meet the filter criteria.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-400 border-b border-gray-800">
            <th className="pb-2 pr-3 font-medium w-8">#</th>
            <th className="pb-2 pr-3 font-medium">Symbol</th>
            <th className="pb-2 pr-3 font-medium">Venue</th>
            <th className="pb-2 pr-3 font-medium text-right">APR14</th>
            <th className="pb-2 pr-3 font-medium text-right">APR7</th>
            <th className="pb-2 pr-3 font-medium text-right">APR1d</th>
            <th className="pb-2 pr-3 font-medium text-right">APR3d</th>
            <th className="pb-2 pr-3 font-medium text-right">Stability</th>
            <th className="pb-2 font-medium">Flags</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-800/50">
          {rows.map((c) => (
            <tr key={`${c.symbol}-${c.rank}`} className="hover:bg-gray-800/30">
              <td className="py-2 pr-3 text-gray-500">{c.rank}</td>
              <td className="py-2 pr-3">
                <div className="flex items-center gap-2">
                  <span className="text-white font-medium">{c.symbol}</span>
                  <TradeabilityBadge status={c.tradeability_status} />
                </div>
              </td>
              <td className="py-2 pr-3 text-gray-400">{c.venue}</td>
              <td className="py-2 pr-3 text-right text-emerald-400">{fmt(c.apr_14d)}</td>
              <td className="py-2 pr-3 text-right text-emerald-400">{fmt(c.apr_7d)}</td>
              <td className="py-2 pr-3 text-right text-gray-300">{fmt(c.apr_1d)}</td>
              <td className="py-2 pr-3 text-right text-gray-300">{fmt(c.apr_3d)}</td>
              <td className="py-2 pr-3 text-right text-blue-400">{fmt(c.stability_score)}</td>
              <td className="py-2 text-xs text-gray-500 max-w-[200px] truncate">{c.flags || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type Tab = "general" | "equities";

interface Props {
  data: CandidatesResponse;
}

export default function CandidatesClient({ data }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("general");
  const [isPending, startTransition] = useTransition();
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const router = useRouter();

  function handleRefresh() {
    setRefreshError(null);
    startTransition(async () => {
      try {
        const res = await fetch("/api/candidates/refresh", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
        });
        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          setRefreshError(body.detail ?? "Refresh failed");
          return;
        }
        router.refresh();
      } catch {
        setRefreshError("Network error — could not reach API");
      }
    });
  }

  const rows = activeTab === "general" ? data.general : data.equities;

  return (
    <div className="space-y-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {(["general", "equities"] as Tab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
                activeTab === tab
                  ? "bg-gray-700 text-white"
                  : "text-gray-400 hover:text-white hover:bg-gray-800/50"
              }`}
            >
              {tab === "general" ? "General" : "Equities"}
              <span className="ml-1.5 text-xs text-gray-500">
                ({tab === "general" ? data.general.length : data.equities.length})
              </span>
            </button>
          ))}
        </div>

        <button
          onClick={handleRefresh}
          disabled={isPending}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-sm bg-gray-800 text-gray-300 hover:text-white hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isPending ? (
            <>
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Refreshing…
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </>
          )}
        </button>
      </div>

      {refreshError && (
        <p className="text-sm text-red-400">{refreshError}</p>
      )}

      <CandidateTable rows={rows} />
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

---

## Task 7: Create the candidates server page

**Files:**
- Create: `frontend/app/candidates/page.tsx`

- [ ] **Step 1: Create the directory and page**

```bash
mkdir -p /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend/app/candidates
```

```tsx
import { getCandidates } from "@/lib/api";
import CandidatesClient from "@/components/CandidatesClient";

export const revalidate = 0; // always fetch fresh on page load

export default async function CandidatesPage() {
  let data;
  let error: string | null = null;

  try {
    data = await getCandidates();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to fetch candidates";
  }

  if (error || !data) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Candidates</h1>
        <div className="card border-red-900">
          <p className="text-red-400">Failed to load candidates data</p>
          <p className="text-sm text-gray-500 mt-1">{error}</p>
          <p className="text-xs text-gray-600 mt-2">
            Run the export script or check the API connection.
          </p>
        </div>
      </div>
    );
  }

  const updatedAt = new Date(data.as_of).toLocaleString("en-US", {
    timeZone: "Asia/Ho_Chi_Minh",
    dateStyle: "medium",
    timeStyle: "short",
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Candidates</h1>
        <span className="text-xs text-gray-500">Last updated: {updatedAt} ICT</span>
      </div>

      <div className="card">
        <CandidatesClient data={data} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/CandidatesClient.tsx frontend/app/candidates/page.tsx frontend/lib/types.ts frontend/lib/api.ts
git commit -m "feat(frontend): add /candidates page with General/Equities tabs and refresh button"
```

---

## Task 8: Add Candidates link to the nav sidebar

**Files:**
- Modify: `frontend/components/NavSidebar.tsx`

- [ ] **Step 1: Add nav item and icon to `NavSidebar.tsx`**

Replace the `navItems` array (lines 7–11):

```typescript
const navItems = [
  { href: "/", label: "Dashboard", icon: "chart" },
  { href: "/candidates", label: "Candidates", icon: "star" },
  { href: "/closed", label: "Closed Positions", icon: "archive" },
  { href: "/settings", label: "Settings", icon: "gear" },
];
```

Add the `"star"` case inside `NavIcon` (before the `default` case):

```tsx
case "star":
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z" />
    </svg>
  );
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no output.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/NavSidebar.tsx
git commit -m "feat(frontend): add Candidates nav link to sidebar"
```

---

## Task 9: Add cron jobs for daily export

**Files:**
- Modify: `harmonix.cron`
- Modify: `docker/crontab`

- [ ] **Step 1: Add cron entry to `harmonix.cron`**

Append after the existing `Daily DB backup` line:

```cron
# Daily candidates export (7:00 AM GMT+7 = 00:00 UTC)
0 0 * * * cd /Users/harmonix/.openclaw/workspace-hip3-agent && source .arbit_env && .venv/bin/python scripts/export_core_candidates.py >> logs/export_core_candidates.log 2>&1
```

- [ ] **Step 2: Add cron entry to `docker/crontab`**

Append before the trailing empty line:

```cron
# Daily candidates export (7:00 AM GMT+7 = 00:00 UTC)
0 0 * * * cd /app && env $(cat /etc/environment | xargs) python scripts/export_core_candidates.py >> /app/logs/export_core_candidates.log 2>&1
```

- [ ] **Step 3: Commit**

```bash
git add harmonix.cron docker/crontab
git commit -m "chore: add daily candidates export cron at 00:00 UTC (7 AM GMT+7)"
```

---

## Task 10: End-to-end smoke test

- [ ] **Step 1: Start the API server**

```bash
source .arbit_env && .venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

- [ ] **Step 2: Hit GET /api/candidates**

In another terminal:

```bash
source .arbit_env && curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://localhost:8000/api/candidates | python -m json.tool | head -40
```

Expected: JSON with `general`, `equities`, `as_of`, `total` keys. If CSV exists and has rows with APR14 >= 20, non-empty lists.

- [ ] **Step 3: Start Next.js dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 4: Open http://localhost:3000/candidates in browser**

Verify:
- "Candidates" appears in sidebar
- Page loads with General tab active
- Table shows ranked rows with APR columns
- Clicking "Equities" switches the table
- Clicking "Refresh" shows spinner, then page reloads

---

## Self-Review Notes

- **Spec coverage:** All spec sections covered — GET endpoint, POST refresh, tab split, table columns (rank, symbol, venue, APR14, APR7, APR1d, APR3d, stability, flags), nav item, cron for both files.
- **apr_2d gap:** Documented in spec and omitted here — CSV has no apr_2d column.
- **Refresh API call:** `CandidatesClient` calls `/api/candidates/refresh` directly via `fetch`. In production this goes through the Next.js proxy — works because `API_BASE_URL` is set server-side only. The client must call via the Next.js route or a server action. **Correction needed:** The client component cannot use `API_BASE_URL` directly. The refresh call should hit the Next.js API route or use a server action.

### Fix: Add a Next.js API proxy route for refresh

**Files:**
- Create: `frontend/app/api/candidates/refresh/route.ts`

```typescript
import { NextResponse } from "next/server";
import { refreshCandidates } from "@/lib/api";

export async function POST() {
  try {
    const result = await refreshCandidates();
    return NextResponse.json(result);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Refresh failed";
    return NextResponse.json({ detail: msg }, { status: 500 });
  }
}
```

Update `CandidatesClient.tsx` — change the fetch URL from `/api/candidates/refresh` to the Next.js proxy:

```tsx
const res = await fetch("/api/candidates/refresh", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
});
```

This is already `/api/candidates/refresh` — but Next.js will intercept this because the route file at `frontend/app/api/candidates/refresh/route.ts` matches it. **No URL change needed in the client** — just add the route file.

Add this to Task 7 as an additional step:

- [ ] **Step 1b: Create Next.js proxy route for refresh**

Create `frontend/app/api/candidates/refresh/route.ts`:

```typescript
import { NextResponse } from "next/server";
import { refreshCandidates } from "@/lib/api";

export async function POST() {
  try {
    const result = await refreshCandidates();
    return NextResponse.json(result);
  } catch (e) {
    const msg = e instanceof Error ? e.message : "Refresh failed";
    return NextResponse.json({ detail: msg }, { status: 500 });
  }
}
```

Include this file in Task 7's commit.
