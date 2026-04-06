#!/usr/bin/env python3
"""Tests for GET /api/candidates and POST /api/candidates/refresh."""

from __future__ import annotations

import csv
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

TEST_API_KEY = "test-key-12345"
os.environ["HARMONIX_API_KEY"] = TEST_API_KEY

from api.main import app  # noqa: E402
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
        "apr_latest": "1.0", "apr_1d": "1.0", "apr_3d": "1.0",
        "apr_7d": "1.0", "apr_14d": "1.0",   # below 5% floor
        "spot_on_hyperliquid": "False", "spot_on_felix": "False",
        "freshness_hours": "2.0", "flags": "MISSING_SPOT",
    },
]


def test_get_candidates_splits_general_and_equities():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
        csv_path = Path(f.name)
    _make_csv(csv_path, SAMPLE_ROWS)

    with patch("api.routers.candidates.CSV_PATH", csv_path):
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
        client = TestClient(app)
        resp = client.get("/api/candidates", headers=_headers())
    assert resp.status_code == 503


def test_refresh_candidates_calls_script():
    with patch("api.routers.candidates.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
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
        client = TestClient(app)
        resp = client.post("/api/candidates/refresh", headers=_headers())

    assert resp.status_code == 500
