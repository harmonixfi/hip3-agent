#!/usr/bin/env python3
"""Integration tests for the Harmonix API.

Uses FastAPI TestClient to exercise all endpoints without a real server.
Requires a populated arbit_v3.db with the monitoring schema applied.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_api.py -v
  or: source .arbit_env && .venv/bin/python tests/test_api.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

# Ensure repo root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Set a test API key before importing the app
TEST_API_KEY = "test-key-12345"
os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
# Override DB path for tests if needed
# os.environ["HARMONIX_DB_PATH"] = str(ROOT / "tracking" / "db" / "arbit_v3.db")

from fastapi.testclient import TestClient


def _headers() -> dict:
    return {"X-API-Key": TEST_API_KEY}


def _setup_test_db() -> Path:
    """Create a temporary SQLite DB with schema and test data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    # Apply pm_v3 schema
    schema_v3 = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"
    if schema_v3.exists():
        con.executescript(schema_v3.read_text())

    # Apply monitoring schema
    schema_mon = ROOT / "tracking" / "sql" / "schema_monitoring_v1.sql"
    if schema_mon.exists():
        con.executescript(schema_mon.read_text())

    now_ms = int(time.time() * 1000)
    day_ago_ms = now_ms - 86400 * 1000

    # Insert test position
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pos_test_BTC",
            "hyperliquid",
            "SPOT_PERP",
            "OPEN",
            day_ago_ms,
            now_ms,
            json.dumps({"base": "BTC", "strategy_type": "SPOT_PERP", "amount_usd": 10000.0}),
        ),
    )

    # Insert test legs
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, entry_price, current_price,
                             unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_SPOT", "pos_test_BTC", "hyperliquid", "BTC/USDC", "LONG", 0.1,
         60000.0, 60500.0, 50.0, "OPEN", day_ago_ms, "0xtest123"),
    )
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, entry_price, current_price,
                             unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_PERP", "pos_test_BTC", "hyperliquid", "BTC", "SHORT", 0.1,
         60050.0, 60500.0, -45.0, "OPEN", day_ago_ms, "0xtest123"),
    )

    # Insert test entry prices
    con.execute(
        """
        INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
                                     fill_count, first_fill_ts, last_fill_ts, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_SPOT", "pos_test_BTC", 60000.0, 0.1, 6000.0, 1, day_ago_ms, day_ago_ms, now_ms),
    )
    con.execute(
        """
        INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
                                     fill_count, first_fill_ts, last_fill_ts, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_PERP", "pos_test_BTC", 60050.0, 0.1, 6005.0, 1, day_ago_ms, day_ago_ms, now_ms),
    )

    # Insert test spread
    con.execute(
        """
        INSERT INTO pm_spreads (position_id, long_leg_id, short_leg_id,
                                entry_spread, long_avg_entry, short_avg_entry,
                                exit_spread, long_exit_price, short_exit_price,
                                spread_pnl_bps, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_SPOT", "pos_test_BTC_PERP",
         -0.0008, 60000.0, 60050.0,   # entry spread
         0.0005, 60500.0, 60470.0,     # exit spread
         13.0, now_ms),
    )

    # Insert test fills
    con.execute(
        """
        INSERT INTO pm_fills (venue, account_id, tid, inst_id, side, px, sz, fee, ts,
                              position_id, leg_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", "tid_001", "BTC/USDC", "BUY", 60000.0, 0.1,
         1.5, day_ago_ms, "pos_test_BTC", "pos_test_BTC_SPOT"),
    )
    con.execute(
        """
        INSERT INTO pm_fills (venue, account_id, tid, inst_id, side, px, sz, fee, ts,
                              position_id, leg_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", "tid_002", "BTC", "SELL", 60050.0, 0.1,
         1.2, day_ago_ms, "pos_test_BTC", "pos_test_BTC_PERP"),
    )

    # Insert test cashflows (funding + fee)
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
         now_ms - 3600000, "FUNDING", 5.25, "USDC"),
    )
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_SPOT", "hyperliquid", "0xtest123",
         day_ago_ms, "FEE", -1.5, "USDC"),
    )
    # 2nd funding payment: 3 hours ago (within 1d/3d/7d/14d)
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
         now_ms - 3 * 3600000, "FUNDING", 5.00, "USDC"),
    )
    # 3rd funding payment: 5 days ago (within 7d/14d but NOT 1d or 3d)
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
         now_ms - 5 * 86400000, "FUNDING", 25.00, "USDC"),
    )

    # Position with missing spot leg price (for incomplete_notional test)
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_ETH_WARN", "hyperliquid", "SPOT_PERP", "OPEN",
         day_ago_ms, now_ms,
         json.dumps({"base": "ETH", "strategy_type": "SPOT_PERP"})),
    )
    # Spot leg: size set but all prices are NULL
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                             entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_ETH_WARN_SPOT", "pos_test_ETH_WARN", "hyperliquid", "ETH/USDC",
         "LONG", 1.0, None, None, None, "OPEN", day_ago_ms, "0xtest123"),
    )
    # Perp leg: has price (so partial notional available)
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                             entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_ETH_WARN_PERP", "pos_test_ETH_WARN", "hyperliquid", "ETH",
         "SHORT", 1.0, 3000.0, 3100.0, -100.0, "OPEN", day_ago_ms, "0xtest123"),
    )
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_ETH_WARN", "pos_test_ETH_WARN_PERP", "hyperliquid", "0xtest123",
         now_ms - 3600000, "FUNDING", 10.0, "USDC"),
    )

    # Young position (2 days old) — for age-gating windowed metrics test
    two_days_ago_ms = now_ms - 2 * 86400 * 1000
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_YOUNG", "hyperliquid", "SPOT_PERP", "OPEN",
         two_days_ago_ms, now_ms,
         json.dumps({"base": "SOL", "strategy_type": "SPOT_PERP", "amount_usd": 5000.0})),
    )
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                             entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_YOUNG_SPOT", "pos_test_YOUNG", "hyperliquid", "SOL/USDC",
         "LONG", 10.0, 150.0, 152.0, 20.0, "OPEN", two_days_ago_ms, "0xtest123"),
    )
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                             entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_YOUNG_PERP", "pos_test_YOUNG", "hyperliquid", "SOL",
         "SHORT", 10.0, 150.5, 152.0, -15.0, "OPEN", two_days_ago_ms, "0xtest123"),
    )
    # Funding cashflow: 6 hours ago (within 1d window)
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_YOUNG", "pos_test_YOUNG_PERP", "hyperliquid", "0xtest123",
         now_ms - 6 * 3600000, "FUNDING", 8.0, "USDC"),
    )

    # Insert account snapshot
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES (?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", now_ms, 25000.50),
    )

    # Insert portfolio snapshot
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (ts, total_equity_usd, equity_by_account_json,
                                            total_unrealized_pnl, total_funding_today,
                                            total_funding_alltime, total_fees_alltime,
                                            daily_change_usd, cashflow_adjusted_change,
                                            apr_daily, tracking_start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (now_ms, 25000.50, json.dumps({"main": 25000.50}),
         5.0, 5.25, 120.50, -35.0,
         42.30, 42.30, 18.5, "2026-01-15"),
    )

    # Insert a closed position for /closed endpoint
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, closed_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pos_test_ETH",
            "hyperliquid",
            "SPOT_PERP",
            "CLOSED",
            day_ago_ms - 86400 * 7 * 1000,  # opened 8 days ago
            now_ms,
            now_ms,
            json.dumps({"base": "ETH", "strategy_type": "SPOT_PERP", "amount_usd": 5000.0}),
        ),
    )

    con.commit()
    con.close()
    return db_path


def _get_test_client(db_path: Path) -> TestClient:
    """Create a TestClient with the test DB."""
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    # Clear cached settings so it picks up the new DB path
    from api.config import get_settings
    get_settings.cache_clear()

    from api.main import app
    return TestClient(app)


# ===================================================================
# Tests
# ===================================================================

def test_auth_required():
    """Request without X-API-Key returns 401."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/health")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    response = client.get("/api/health", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

    # With correct key
    response = client.get("/api/health", headers=_headers())
    assert response.status_code == 200

    os.unlink(db_path)
    print("PASS: test_auth_required")


def test_health():
    """GET /api/health returns expected shape."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/health", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["db_size_mb"] >= 0
    assert data["open_positions"] >= 1
    assert data["uptime_seconds"] >= 0

    os.unlink(db_path)
    print("PASS: test_health")


def test_portfolio_overview():
    """GET /api/portfolio/overview returns aggregate metrics."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/portfolio/overview", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert "total_equity_usd" in data
    assert "equity_by_account" in data
    assert "daily_change_usd" in data
    assert "cashflow_adjusted_apr" in data
    assert "funding_today_usd" in data
    assert "funding_alltime_usd" in data
    assert "fees_alltime_usd" in data
    assert "open_positions_count" in data
    assert data["open_positions_count"] >= 1

    os.unlink(db_path)
    print("PASS: test_portfolio_overview")


def test_portfolio_overview_with_tracking_start():
    """GET /api/portfolio/overview?tracking_start=... overrides date."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/portfolio/overview?tracking_start=2026-03-01",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tracking_start_date"] == "2026-03-01"

    os.unlink(db_path)
    print("PASS: test_portfolio_overview_with_tracking_start")


def test_list_positions():
    """GET /api/positions returns open positions."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    pos = data[0]
    assert "position_id" in pos
    assert "base" in pos
    assert "legs" in pos
    assert "sub_pairs" in pos
    assert pos["status"] == "OPEN"
    # amount_usd for OPEN = sum abs(size * current_price) per leg (pm_legs has no total_balance)
    assert pos["amount_usd"] == 12100.0  # 0.1*60500 + 0.1*60500

    os.unlink(db_path)
    print("PASS: test_list_positions")


def test_list_positions_all():
    """GET /api/positions?status=ALL returns all positions."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions?status=ALL", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # OPEN + CLOSED

    os.unlink(db_path)
    print("PASS: test_list_positions_all")


def test_position_detail():
    """GET /api/positions/{id} returns full detail."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/pos_test_BTC", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["position_id"] == "pos_test_BTC"
    assert "fills_summary" in data
    assert "cashflows" in data
    assert "daily_funding_series" in data
    assert len(data["legs"]) == 2

    os.unlink(db_path)
    print("PASS: test_position_detail")


def test_position_not_found():
    """GET /api/positions/{id} returns 404 for nonexistent."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/nonexistent", headers=_headers())
    assert response.status_code == 404

    os.unlink(db_path)
    print("PASS: test_position_not_found")


def test_position_fills():
    """GET /api/positions/{id}/fills returns paginated fills."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/pos_test_BTC/fills", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["position_id"] == "pos_test_BTC"
    assert data["total"] == 2
    assert len(data["fills"]) == 2
    assert data["limit"] == 100
    assert data["offset"] == 0

    os.unlink(db_path)
    print("PASS: test_position_fills")


def test_position_fills_with_leg_filter():
    """GET /api/positions/{id}/fills?leg_id=... filters by leg."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/positions/pos_test_BTC/fills?leg_id=pos_test_BTC_SPOT",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["fills"][0]["leg_id"] == "pos_test_BTC_SPOT"

    os.unlink(db_path)
    print("PASS: test_position_fills_with_leg_filter")


def test_position_fills_pagination():
    """GET /api/positions/{id}/fills supports limit/offset."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/positions/pos_test_BTC/fills?limit=1&offset=0",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["fills"]) == 1

    response2 = client.get(
        "/api/positions/pos_test_BTC/fills?limit=1&offset=1",
        headers=_headers(),
    )
    data2 = response2.json()
    assert len(data2["fills"]) == 1
    assert data2["fills"][0]["fill_id"] != data["fills"][0]["fill_id"]

    os.unlink(db_path)
    print("PASS: test_position_fills_pagination")


def test_closed_positions():
    """GET /api/positions/closed returns closed P&L analysis."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/closed", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["status"] == "CLOSED"
    assert "net_pnl" in data[0]
    assert "duration_days" in data[0]

    os.unlink(db_path)
    print("PASS: test_closed_positions")


def test_manual_cashflow_deposit():
    """POST /api/cashflows/manual creates a deposit record."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    body = {
        "account_id": "0xtest123",
        "venue": "hyperliquid",
        "cf_type": "DEPOSIT",
        "amount": 5000.0,
        "currency": "USDC",
        "description": "Test deposit",
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert "cashflow_id" in data
    assert data["cashflow_id"] > 0

    # Verify it was stored with positive amount
    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT amount, cf_type, meta_json FROM pm_cashflows WHERE cashflow_id = ?",
        (data["cashflow_id"],),
    ).fetchone()
    assert row is not None
    assert row[0] == 5000.0  # positive for DEPOSIT
    assert row[1] == "DEPOSIT"
    meta = json.loads(row[2])
    assert meta["source"] == "manual"
    con.close()

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_deposit")


def test_manual_cashflow_withdraw():
    """POST /api/cashflows/manual with WITHDRAW stores negative amount."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    body = {
        "account_id": "0xtest123",
        "venue": "hyperliquid",
        "cf_type": "WITHDRAW",
        "amount": 2000.0,
        "currency": "USDC",
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 201
    data = response.json()

    # Verify negative amount
    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT amount FROM pm_cashflows WHERE cashflow_id = ?",
        (data["cashflow_id"],),
    ).fetchone()
    assert row[0] == -2000.0  # negative for WITHDRAW
    con.close()

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_withdraw")


def test_manual_cashflow_validation():
    """POST /api/cashflows/manual rejects invalid input."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    # Invalid cf_type
    body = {
        "account_id": "0xtest",
        "venue": "hyperliquid",
        "cf_type": "TRANSFER",
        "amount": 100.0,
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    # Zero amount
    body["cf_type"] = "DEPOSIT"
    body["amount"] = 0
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    # Negative amount
    body["amount"] = -100
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_validation")


def test_list_manual_cashflows_requires_auth():
    """GET /api/cashflows/manual without X-API-Key returns 401."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/cashflows/manual")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    os.unlink(db_path)
    print("PASS: test_list_manual_cashflows_requires_auth")


def test_options_preflight_skips_api_key():
    """CORS preflight OPTIONS must not require X-API-Key (browser sends no key on OPTIONS)."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.options(
        "/api/cashflows/manual?limit=50",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "content-type, x-api-key",
        },
    )
    assert response.status_code == 200, f"Expected 200 for OPTIONS, got {response.status_code}"

    os.unlink(db_path)
    print("PASS: test_options_preflight_skips_api_key")


def test_list_manual_cashflows_after_post():
    """POST manual cashflow then GET /api/cashflows/manual returns the row."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    ts_ms = int(time.time() * 1000)
    body = {
        "account_id": "0xmanual_list_test",
        "venue": "hyperliquid",
        "cf_type": "DEPOSIT",
        "amount": 1234.56,
        "currency": "USDC",
        "description": "list test",
        "ts": ts_ms,
    }
    post = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert post.status_code == 201
    cf_id = post.json()["cashflow_id"]

    get_resp = client.get("/api/cashflows/manual?limit=50", headers=_headers())
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["limit"] == 50
    assert isinstance(data["items"], list)
    match = next((x for x in data["items"] if x["cashflow_id"] == cf_id), None)
    assert match is not None
    assert match["ts"] == ts_ms
    assert match["cf_type"] == "DEPOSIT"
    assert match["amount"] == pytest.approx(1234.56)
    assert match["currency"] == "USDC"
    assert match["venue"] == "hyperliquid"
    assert match["account_id"] == "0xmanual_list_test"
    assert match["description"] == "list test"

    os.unlink(db_path)
    print("PASS: test_list_manual_cashflows_after_post")


def test_list_manual_cashflows_excludes_non_manual_meta():
    """DEPOSIT rows without meta source=manual are not listed."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    con = sqlite3.connect(str(db_path))
    now_ms = int(time.time() * 1000)
    con.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id, ts, cf_type, amount, currency,
            description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,
            None,
            "hyperliquid",
            "0xnonmanual",
            now_ms,
            "DEPOSIT",
            999.0,
            "USDC",
            "should not appear",
            json.dumps({"source": "other"}),
        ),
    )
    con.commit()
    con.close()

    post = client.post(
        "/api/cashflows/manual",
        json={
            "account_id": "0xmanual_only",
            "venue": "hyperliquid",
            "cf_type": "DEPOSIT",
            "amount": 100.0,
            "currency": "USDC",
        },
        headers=_headers(),
    )
    assert post.status_code == 201
    manual_id = post.json()["cashflow_id"]

    get_resp = client.get("/api/cashflows/manual?limit=100", headers=_headers())
    assert get_resp.status_code == 200
    items = get_resp.json()["items"]
    ids = {x["cashflow_id"] for x in items}
    assert manual_id in ids
    non_manual_ids = {x["cashflow_id"] for x in items if x["account_id"] == "0xnonmanual"}
    assert len(non_manual_ids) == 0

    os.unlink(db_path)
    print("PASS: test_list_manual_cashflows_excludes_non_manual_meta")


def test_root_endpoint():
    """GET / returns welcome message (no auth needed)."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/")
    assert response.status_code == 200
    assert "Harmonix" in response.json()["message"]

    os.unlink(db_path)
    print("PASS: test_root_endpoint")


# ===================================================================
# Pytest fixture for windowed metrics tests
# ===================================================================

@pytest.fixture
def client():
    db_path = _setup_test_db()
    os.environ["HARMONIX_DB_PATH"] = str(db_path)
    from api.config import get_settings
    get_settings.cache_clear()
    from api.main import app
    with TestClient(app) as c:
        yield c
    Path(db_path).unlink(missing_ok=True)


def test_positions_windowed_metrics_present(client: TestClient):
    """windowed field is present in /api/positions response."""
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    positions = resp.json()
    btc = next(p for p in positions if p["position_id"] == "pos_test_BTC")
    assert btc["windowed"] is not None
    w = btc["windowed"]
    assert "funding_1d" in w
    assert "funding_3d" in w
    assert "funding_7d" in w
    assert "funding_14d" in w
    assert "apr_1d" in w
    assert "apr_3d" in w
    assert "apr_7d" in w
    assert "apr_14d" in w
    assert "incomplete_notional" in w
    assert "missing_leg_ids" in w


def test_positions_windowed_funding_windows(client: TestClient):
    """Windowed funding sums respect time boundaries and age-gating.

    pos_test_BTC is ~1 day old (created_at_ms = now - 1d).
    Cashflows:
      - 5.25 at now - 1h   (in 1d window)
      - 5.00 at now - 3h   (in 1d window)
      - 25.0 at now - 5d   (before position creation — ignored by age-gate)

    Because position is ~1 day old, only 1d window is valid; 3d/7d/14d are age-gated to None.
    amount_usd_raw = 0.1 * 60500 + 0.1 * 60500 = 12100.0
    """
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    btc = next(p for p in resp.json() if p["position_id"] == "pos_test_BTC")
    w = btc["windowed"]

    assert w["incomplete_notional"] is False
    assert w["missing_leg_ids"] == []

    # 1d window: valid (position is ~1 day old)
    assert w["funding_1d"]  == pytest.approx(10.25, abs=0.01)   # 5.25 + 5.00

    # 3d/7d/14d: age-gated to None (position only ~1 day old)
    assert w["funding_3d"]  is None
    assert w["funding_7d"]  is None
    assert w["funding_14d"] is None

    # APR for 1d: (10.25 / 1) * 365 / 12100 * 100
    expected_apr_1d = (10.25 / 1) * 365 / 12100 * 100
    assert w["apr_1d"] == pytest.approx(expected_apr_1d, rel=0.001)

    # APR for 3d/7d/14d: age-gated
    assert w["apr_3d"]  is None
    assert w["apr_7d"]  is None
    assert w["apr_14d"] is None


def test_positions_windowed_incomplete_notional(client: TestClient):
    """incomplete_notional=True when a leg has no price; apr_* are None, funding_* still present."""
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    eth = next(p for p in resp.json() if p["position_id"] == "pos_test_ETH_WARN")
    w = eth["windowed"]

    assert w["incomplete_notional"] is True
    assert "pos_test_ETH_WARN_SPOT" in w["missing_leg_ids"]

    # APR fields must all be None when notional is incomplete
    assert w["apr_1d"]  is None
    assert w["apr_3d"]  is None
    assert w["apr_7d"]  is None
    assert w["apr_14d"] is None

    # Funding $ fields still populated (cashflows are trustworthy)
    assert w["funding_1d"] == pytest.approx(10.0, abs=0.01)


def test_positions_windowed_age_gating(client: TestClient):
    """Windows wider than position age are nulled out (2-day-old position has no 3d/7d/14d)."""
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    young = next(p for p in resp.json() if p["position_id"] == "pos_test_YOUNG")
    w = young["windowed"]

    assert w is not None

    # 1d window: position is 2 days old, so 1d is valid
    assert w["funding_1d"] == pytest.approx(8.0, abs=0.01)
    assert w["apr_1d"] is not None

    # 3d/7d/14d: position is only ~2 days old, these must be None
    assert w["funding_3d"] is None
    assert w["apr_3d"]     is None
    assert w["funding_7d"] is None
    assert w["apr_7d"]     is None
    assert w["funding_14d"] is None
    assert w["apr_14d"]     is None


# ===================================================================
# Runner
# ===================================================================

if __name__ == "__main__":
    tests = [
        test_auth_required,
        test_health,
        test_portfolio_overview,
        test_portfolio_overview_with_tracking_start,
        test_list_positions,
        test_list_positions_all,
        test_position_detail,
        test_position_not_found,
        test_position_fills,
        test_position_fills_with_leg_filter,
        test_position_fills_pagination,
        test_closed_positions,
        test_manual_cashflow_deposit,
        test_manual_cashflow_withdraw,
        test_manual_cashflow_validation,
        test_list_manual_cashflows_requires_auth,
        test_options_preflight_skips_api_key,
        test_list_manual_cashflows_after_post,
        test_list_manual_cashflows_excludes_non_manual_meta,
        test_root_endpoint,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed:
        sys.exit(1)
    print("All API tests passed!")
