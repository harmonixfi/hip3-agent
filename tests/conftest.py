"""Shared pytest fixtures and autouse mocks for all unit/API tests."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _mock_fill_sync(monkeypatch):
    """Prevent live Hyperliquid API calls in unit tests.

    Replaces sync_fills_for_position_window with a local stub that:
    - Raises ValueError when any leg has an empty account_id (same guard as real code)
    - Returns 0 without making any network call otherwise

    Individual tests that need the sync to insert fills can override this
    by calling monkeypatch.setattr(api.routers.trades,
    "sync_fills_for_position_window", their_mock) inside the test body.
    """
    import api.routers.trades as trades_router

    def _stub_sync(con, position_id, start_ts):
        rows = con.execute(
            "SELECT leg_id, account_id FROM pm_legs WHERE position_id = ?",
            (position_id,),
        ).fetchall()
        if not rows:
            raise ValueError(f"position {position_id!r} has no legs")
        missing = [r[0] for r in rows if not (r[1] or "").strip()]
        if missing:
            raise ValueError(
                f"legs {missing} have no account_id — "
                "recreate the position with a valid wallet_label "
                "or patch pm_legs.account_id directly"
            )
        return 0  # no fills added (no network I/O in unit tests)

    monkeypatch.setattr(trades_router, "sync_fills_for_position_window", _stub_sync)
