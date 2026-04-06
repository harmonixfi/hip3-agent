"""Integration tests for vault API endpoints."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMA_PM = Path(__file__).parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = Path(__file__).parent.parent / "tracking" / "sql" / "schema_vault.sql"

TEST_API_KEY = "test-key-123"


def _setup_test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())

    now_ms = int(time.time() * 1000)

    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            config_json, created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "lending",
            "Lending",
            "LENDING",
            "ACTIVE",
            '[{"wallet_label":"lending"}]',
            50.0,
            '{"vault_name":"Test Vault"}',
            now_ms,
            now_ms,
        ),
    )
    con.execute(
        """
        INSERT INTO vault_strategies(
            strategy_id, name, type, status, wallets_json, target_weight_pct,
            config_json, created_at_ms, updated_at_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            "delta_neutral",
            "DN",
            "DELTA_NEUTRAL",
            "ACTIVE",
            '[{"wallet_label":"alt"}]',
            45.0,
            '{"vault_name":"Test Vault"}',
            now_ms,
            now_ms,
        ),
    )

    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("lending", now_ms, 50000.0, 4.0, 3.8, 4.2),
    )
    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d
        ) VALUES (?,?,?,?,?,?)
        """,
        ("delta_neutral", now_ms, 45000.0, 18.0, 15.0, 20.0),
    )

    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d,
            net_deposits_alltime
        ) VALUES (?,?,?,?,?,?,?)
        """,
        (
            now_ms,
            95000.0,
            '{"lending":52.6,"delta_neutral":47.4}',
            10.5,
            9.0,
            11.5,
            80000.0,
        ),
    )

    con.commit()
    con.close()
    return db_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = _setup_test_db(tmp_path)
    monkeypatch.setenv("HARMONIX_DB_PATH", str(db_path))
    monkeypatch.setenv("HARMONIX_API_KEY", TEST_API_KEY)

    from api.config import get_settings

    get_settings.cache_clear()

    from api.main import app

    return TestClient(app)


def _headers():
    return {"X-API-Key": TEST_API_KEY}


def test_vault_overview(client):
    resp = client.get("/api/vault/overview", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_equity_usd"] == 95000.0
    assert len(data["strategies"]) == 2
    assert data["strategies"][0]["equity_usd"] is not None


def test_vault_strategies_list(client):
    resp = client.get("/api/vault/strategies", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_strategy_detail(client):
    resp = client.get("/api/vault/strategies/lending", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy_id"] == "lending"
    assert data["equity_usd"] == 50000.0


def test_strategy_not_found(client):
    resp = client.get("/api/vault/strategies/nonexistent", headers=_headers())
    assert resp.status_code == 404


def test_create_cashflow(client):
    resp = client.post(
        "/api/vault/cashflows",
        headers=_headers(),
        json={
            "cf_type": "DEPOSIT",
            "amount": 5000.0,
            "strategy_id": "lending",
            "description": "test deposit",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["cashflow_id"] > 0
    assert "DEPOSIT" in data["message"]


def test_list_cashflows(client):
    client.post(
        "/api/vault/cashflows",
        headers=_headers(),
        json={"cf_type": "DEPOSIT", "amount": 1000.0, "strategy_id": "lending"},
    )
    resp = client.get("/api/vault/cashflows", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_vault_snapshots(client):
    resp = client.get("/api/vault/snapshots?limit=10", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["total_equity_usd"] == 95000.0
