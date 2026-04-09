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

APR14_FLOOR = 5.0
TOP_N = 20


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
        if len(target) >= TOP_N:
            continue
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
