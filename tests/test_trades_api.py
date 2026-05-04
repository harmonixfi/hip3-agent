"""E2E tests for /api/trades router using FastAPI TestClient + in-memory DB.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_api.py -v
"""
from __future__ import annotations
import os
import sqlite3

# Set API key before importing the app (middleware reads it at module-import time
# via get_settings(), which is lru_cache'd).
TEST_API_KEY = "test-trades-key"
os.environ["HARMONIX_API_KEY"] = TEST_API_KEY

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_db, get_db_writable


_INLINE_SCHEMA = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


@pytest.fixture
def client():
    # Ensure settings cache is cleared so our test API key is picked up,
    # even if another test module has already cached get_settings().
    from api.config import get_settings
    get_settings.cache_clear()

    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(_INLINE_SCHEMA)
    con.execute("INSERT INTO pm_positions (position_id,venue,status,created_at_ms,updated_at_ms,base,strategy_type) VALUES ('pos_X','hyperliquid','OPEN',0,0,'GOOGL','SPOT_PERP')")
    con.execute("INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_X_SPOT','pos_X','hyperliquid','GOOGL','LONG',0,'OPEN',0,'0xMAIN')")
    con.execute("INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_X_PERP','pos_X','hyperliquid','xyz:GOOGL','SHORT',0,'OPEN',0,'0xMAIN')")
    con.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL","BUY",100.0,2.0,0.05,1100,"pos_X_SPOT","pos_X"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0,2.0,0.04,1200,"pos_X_PERP","pos_X"),
        ],
    )
    con.commit()

    def _override_db():
        yield con

    # Override both read-only and writable DB dependencies
    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_db_writable] = _override_db
    with TestClient(app) as c:
        # Inject API key into every request made through this client
        c.headers.update({"X-API-Key": TEST_API_KEY})
        yield c
    app.dependency_overrides.clear()
    con.close()


def test_preview_then_create_then_finalize(client):
    # Preview
    r = client.post("/api/trades/preview", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    assert r.status_code == 200, r.text
    assert r.json()["long_size"] == pytest.approx(2.0)

    # Preview must NOT persist
    r2 = client.get("/api/trades")
    assert r2.json()["total"] == 0

    # Create
    r3 = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    assert r3.status_code == 201, r3.text
    tid = r3.json()["trade_id"]

    # Finalize
    r4 = client.post(f"/api/trades/{tid}/finalize")
    assert r4.status_code == 200, r4.text
    assert r4.json()["state"] == "FINALIZED"


def test_create_rejects_invalid_input(client):
    # Unknown position
    r = client.post("/api/trades", json={
        "position_id": "pos_MISSING", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    assert r.status_code == 422
    # Invalid window
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 2000, "end_ts": 1000,
    })
    assert r.status_code == 422


def test_edit_draft_updates_window(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]

    r2 = client.patch(f"/api/trades/{tid}", json={"end_ts": 1150})
    assert r2.status_code == 200, r2.text
    # Only the spot fill at ts=1100 falls in [1000, 1150)
    assert r2.json()["long_fill_count"] == 1


def test_edit_rejects_on_finalized(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    client.post(f"/api/trades/{tid}/finalize")
    r2 = client.patch(f"/api/trades/{tid}", json={"end_ts": 1500})
    assert r2.status_code == 409


def test_edit_empty_patch_returns_400(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    r2 = client.patch(f"/api/trades/{tid}", json={})
    assert r2.status_code == 400


def test_reopen_finalized(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    client.post(f"/api/trades/{tid}/finalize")

    r2 = client.post(f"/api/trades/{tid}/reopen")
    assert r2.status_code == 200
    assert r2.json()["state"] == "DRAFT"


def test_reopen_draft_returns_409(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    r2 = client.post(f"/api/trades/{tid}/reopen")
    assert r2.status_code == 409


def test_recompute(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    r2 = client.post(f"/api/trades/{tid}/recompute")
    assert r2.status_code == 200


def test_delete_draft_returns_204(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    r2 = client.delete(f"/api/trades/{tid}")
    assert r2.status_code == 204
    r3 = client.get(f"/api/trades/{tid}")
    assert r3.status_code == 404


def test_delete_unknown_returns_404(client):
    r = client.delete("/api/trades/trd_missing")
    assert r.status_code == 404


def test_list_filters(client):
    client.post("/api/trades", json={"position_id":"pos_X","trade_type":"OPEN","start_ts":1000,"end_ts":2000})
    r = client.get("/api/trades?trade_type=OPEN&state=DRAFT")
    assert r.status_code == 200
    assert r.json()["total"] == 1
    # Filter that matches nothing
    r2 = client.get("/api/trades?state=FINALIZED")
    assert r2.json()["total"] == 0


def test_get_detail_includes_linked_fills(client):
    r = client.post("/api/trades", json={"position_id":"pos_X","trade_type":"OPEN","start_ts":1000,"end_ts":2000})
    tid = r.json()["trade_id"]
    r2 = client.get(f"/api/trades/{tid}")
    assert r2.status_code == 200
    body = r2.json()
    assert len(body["fills"]) == 2
    # fills is list of LinkedFillItem
    long_fill = next(f for f in body["fills"] if f["leg_side"] == "LONG")
    assert long_fill["side"] == "BUY"
    assert long_fill["inst_id"] == "GOOGL"


def test_get_unknown_returns_404(client):
    r = client.get("/api/trades/trd_missing")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# On-demand fill sync tests
# ---------------------------------------------------------------------------

def _make_db_and_client(schema, setup_sql: list[str]):
    """Helper: in-memory DB + TestClient with overridden deps."""
    from api.config import get_settings
    get_settings.cache_clear()

    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(schema)
    for sql in setup_sql:
        con.execute(sql)
    con.commit()

    def _override():
        yield con

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_db_writable] = _override
    c = TestClient(app)
    c.headers.update({"X-API-Key": TEST_API_KEY})
    return con, c


def test_preview_calls_on_demand_sync(monkeypatch):
    """preview_trade triggers on-demand sync and finds fills even if DB was empty."""
    con, c = _make_db_and_client(
        _INLINE_SCHEMA,
        [
            "INSERT INTO pm_positions (position_id,venue,status,created_at_ms,updated_at_ms,base,strategy_type) VALUES ('pos_sync','hyperliquid','OPEN',0,0,'SYNC','SPOT_PERP')",
            "INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_sync_SPOT','pos_sync','hyperliquid','SYNC/USDC','LONG',0,'OPEN',0,'0xACCT')",
            "INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_sync_PERP','pos_sync','hyperliquid','xyz:SYNC','SHORT',0,'OPEN',0,'0xACCT')",
        ],
    )

    # Override the stub from conftest with one that actually inserts fills
    import api.routers.trades as trades_router

    def _mock_sync(db, position_id, start_ts):
        db.execute("INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES ('hyperliquid','0xACCT','SYNC/USDC','BUY',100.0,1.0,0.01,1100,'pos_sync_SPOT','pos_sync')")
        db.execute("INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES ('hyperliquid','0xACCT','xyz:SYNC','SELL',101.0,1.0,0.01,1150,'pos_sync_PERP','pos_sync')")
        db.commit()
        return 2

    monkeypatch.setattr(trades_router, "sync_fills_for_position_window", _mock_sync)

    try:
        r = c.post("/api/trades/preview", json={
            "position_id": "pos_sync",
            "trade_type": "OPEN",
            "start_ts": 1000,
            "end_ts": 2000,
        })
    finally:
        app.dependency_overrides.clear()
        con.close()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["long_fill_count"] == 1
    assert body["short_fill_count"] == 1
    assert body["spread_bps"] == pytest.approx((100.0 / 101.0 - 1) * 10_000, abs=0.01)

    # Preview must NOT persist the trade draft
    # (fills were already committed before savepoint, but the trade row itself was rolled back)


def test_preview_returns_422_on_missing_account_id():
    """preview_trade returns 422 with a clear message when a leg has no account_id."""
    con, c = _make_db_and_client(
        _INLINE_SCHEMA,
        [
            "INSERT INTO pm_positions (position_id,venue,status,created_at_ms,updated_at_ms,base,strategy_type) VALUES ('pos_noacct','hyperliquid','OPEN',0,0,'X','SPOT_PERP')",
            "INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_noacct_SPOT','pos_noacct','hyperliquid','X/USDC','LONG',0,'OPEN',0,'')",
            "INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_noacct_PERP','pos_noacct','hyperliquid','xyz:X','SHORT',0,'OPEN',0,'')",
        ],
    )

    try:
        r = c.post("/api/trades/preview", json={
            "position_id": "pos_noacct",
            "trade_type": "OPEN",
            "start_ts": 1000,
            "end_ts": 2000,
        })
    finally:
        app.dependency_overrides.clear()
        con.close()

    assert r.status_code == 422
    assert "account_id" in r.json()["detail"]


def test_create_position_resolves_account_id(monkeypatch):
    """create_position must populate account_id from wallet_label via resolve_venue_accounts."""
    import tracking.position_manager.accounts as accts_mod

    monkeypatch.setattr(
        accts_mod, "resolve_venue_accounts",
        lambda venue: {"main": "0xWALLET_MAIN", "alt": "0xWALLET_ALT"},
    )

    from api.config import get_settings
    get_settings.cache_clear()

    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(_INLINE_SCHEMA)
    con.commit()

    def _override():
        yield con

    app.dependency_overrides[get_db] = _override
    app.dependency_overrides[get_db_writable] = _override

    try:
        c = TestClient(app)
        c.headers.update({"X-API-Key": TEST_API_KEY})

        r = c.post("/api/positions", json={
            "position_id": "pos_wallettest",
            "base": "TEST",
            "strategy_type": "SPOT_PERP",
            "venue": "hyperliquid",
            "long_leg": {
                "leg_id": "pos_wallettest_SPOT",
                "venue": "hyperliquid",
                "inst_id": "TEST/USDC",
                "side": "LONG",
                "wallet_label": "main",
            },
            "short_leg": {
                "leg_id": "pos_wallettest_PERP",
                "venue": "hyperliquid",
                "inst_id": "xyz:TEST",
                "side": "SHORT",
                "wallet_label": "alt",
            },
        })
        assert r.status_code == 201, r.text

        rows = {
            r["leg_id"]: r["account_id"]
            for r in con.execute(
                "SELECT leg_id, account_id FROM pm_legs WHERE position_id = 'pos_wallettest'"
            ).fetchall()
        }
    finally:
        app.dependency_overrides.clear()
        con.close()

    assert rows["pos_wallettest_SPOT"] == "0xWALLET_MAIN"
    assert rows["pos_wallettest_PERP"] == "0xWALLET_ALT"
