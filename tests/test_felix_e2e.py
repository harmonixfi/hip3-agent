"""E2E tests for Felix JWT authentication against real Turnkey API.

Requires FELIX_WALLET_PRIVATE_KEY and FELIX_WALLET_ADDRESS in env.
Skipped automatically when credentials are absent.

Run:
    source .arbit_env
    .venv/bin/python -m pytest tests/test_felix_e2e.py -v
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_auth import FelixSession, initial_login, refresh_session

_WALLET_PK = os.getenv("FELIX_WALLET_PRIVATE_KEY", "")
_WALLET_ADDR = os.getenv("FELIX_WALLET_ADDRESS", "")

pytestmark = pytest.mark.skipif(
    not _WALLET_PK or not _WALLET_ADDR,
    reason="Requires FELIX_WALLET_PRIVATE_KEY and FELIX_WALLET_ADDRESS in env",
)


def test_create_jwt_when_none_exists():
    """initial_login() creates a valid JWT from scratch."""
    session = initial_login(_WALLET_PK, _WALLET_ADDR)

    assert session.jwt, "JWT should not be empty"
    assert len(session.jwt) > 50
    assert session.jwt.count(".") >= 2, "JWT should have dot-separated parts (header.payload.sig)"

    # expires_at should be ~14 days from now
    now = int(time.time())
    assert session.expires_at >= now + 1_200_000, (
        f"Expected ~14-day expiry, got {session.expires_at - now}s from now"
    )
    assert session.sub_org_id, "sub_org_id must be populated"


def test_jwt_refresh_when_expired():
    """refresh_session() with a simulated-expired session returns a new valid JWT."""
    # Obtain a real session first
    session = initial_login(_WALLET_PK, _WALLET_ADDR)
    assert session.jwt

    # Simulate expiry
    expired = FelixSession(
        jwt=session.jwt,
        expires_at=int(time.time()) - 1,
        sub_org_id=session.sub_org_id,
    )
    assert expired.is_expired()

    # Refresh should issue a fresh token
    new_session = refresh_session(expired, _WALLET_PK)

    assert new_session.jwt, "Refreshed JWT should not be empty"
    assert not new_session.is_expired(), "Refreshed session should not be expired"
    assert new_session.jwt != session.jwt, "Refresh should issue a new token"
