#!/usr/bin/env python3
"""Tests for Felix Turnkey auth — crypto operations and header generation."""

from __future__ import annotations

import base64
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_auth import (
    sign_with_secp256k1,
    build_x_stamp_header,
    build_stamp_login_body,
    parse_stamp_login_response,
    FelixSession,
)


def test_sign_with_secp256k1():
    """secp256k1 signing produces a DER-encoded signature."""
    # Use a known test private key (DO NOT use in production)
    test_key_hex = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    message = b'{"type":"ACTIVITY_TYPE_STAMP_LOGIN","timestampMs":"1234567890"}'

    signature_der_hex = sign_with_secp256k1(test_key_hex, message)

    # DER signature is variable length but typically 70-72 bytes (140-144 hex chars)
    assert len(signature_der_hex) >= 128
    assert len(signature_der_hex) <= 148

    # Should be valid hex
    bytes.fromhex(signature_der_hex)


def test_build_x_stamp_header():
    """X-Stamp header is base64url-encoded JSON with correct fields."""
    test_key_hex = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    body = b'{"test":"data"}'

    stamp = build_x_stamp_header(test_key_hex, body)

    # Decode and verify structure
    # X-Stamp is base64url-encoded JSON
    decoded = json.loads(base64.urlsafe_b64decode(stamp + "=="))
    assert "publicKey" in decoded
    assert "signature" in decoded
    assert decoded["scheme"] == "SIGNATURE_SCHEME_TK_API_SECP256K1_EIP191"
    # Turnkey expects compressed secp256k1 (33 bytes = 66 hex chars, prefix 02/03)
    assert len(decoded["publicKey"]) == 66
    assert decoded["publicKey"][:2] in ("02", "03")
    # DER ECDSA signature (variable length, typically ~70–72 bytes hex ~140–144)
    assert len(decoded["signature"]) >= 128


def test_build_stamp_login_body():
    """stamp_login body uses wallet's compressed secp256k1 pubkey as session identity."""
    test_key_hex = "ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
    org_id = "test-org-123"

    body = build_stamp_login_body(
        organization_id=org_id,
        wallet_private_key_hex=test_key_hex,
    )

    parsed = json.loads(body)
    assert parsed["type"] == "ACTIVITY_TYPE_STAMP_LOGIN"
    assert parsed["organizationId"] == org_id
    pub_key = parsed["parameters"]["publicKey"]
    assert len(pub_key) == 66, "publicKey must be compressed secp256k1 (33 bytes = 66 hex)"
    assert pub_key[:2] in ("02", "03"), "compressed pubkey has 02/03 prefix"
    assert parsed["parameters"]["expirationSeconds"] == "1209600"
    assert "timestampMs" in parsed
    ts = int(parsed["timestampMs"])
    assert abs(ts - int(time.time() * 1000)) < 5000


def test_parse_stamp_login_response_success():
    """Successful stamp_login response is parsed to JWT."""
    response = {
        "activity": {
            "id": "act_123",
            "status": "ACTIVITY_STATUS_COMPLETED",
            "result": {
                "stampLoginResult": {
                    "session": "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"
                }
            }
        }
    }
    jwt = parse_stamp_login_response(response)
    assert jwt == "eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"


def test_parse_stamp_login_response_failure():
    """Failed stamp_login response raises RuntimeError."""
    response = {
        "activity": {
            "id": "act_456",
            "status": "ACTIVITY_STATUS_FAILED",
            "result": {}
        }
    }
    with pytest.raises(RuntimeError, match="FAILED|stamp_login"):
        parse_stamp_login_response(response)


def test_felix_session_is_expired():
    """FelixSession correctly reports expiry."""
    session = FelixSession(
        jwt="token",
        expires_at=int(time.time()) - 10,  # 10 seconds ago
        sub_org_id="org_123",
    )
    assert session.is_expired()

    session2 = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 600,  # 10 minutes from now
        sub_org_id="org_123",
    )
    assert not session2.is_expired()


def test_felix_session_needs_refresh():
    """FelixSession reports needing refresh when <24 hours remain."""
    session = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 3600,  # 1 hour from now — needs refresh since 3600 < 86400
        sub_org_id="org_123",
    )
    assert session.needs_refresh()

    session2 = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 90000,  # >86400s — no refresh needed
        sub_org_id="org_123",
    )
    assert not session2.needs_refresh()


def test_felix_session_serialization():
    """FelixSession survives JSON serialization roundtrip."""
    session = FelixSession(
        jwt="eyJ.test.sig",
        expires_at=1711900000,
        sub_org_id="org_abc",
    )
    data = session.to_dict()
    assert isinstance(data, dict)
    assert data["jwt"] == "eyJ.test.sig"

    restored = FelixSession.from_dict(data)
    assert restored.jwt == session.jwt
    assert restored.expires_at == session.expires_at
    assert restored.sub_org_id == session.sub_org_id


def main() -> int:
    test_sign_with_secp256k1()
    print("PASS: test_sign_with_secp256k1")
    test_build_x_stamp_header()
    print("PASS: test_build_x_stamp_header")
    test_build_stamp_login_body()
    print("PASS: test_build_stamp_login_body")
    test_parse_stamp_login_response_success()
    print("PASS: test_parse_stamp_login_response_success")
    test_parse_stamp_login_response_failure()
    print("PASS: test_parse_stamp_login_response_failure")
    test_felix_session_is_expired()
    print("PASS: test_felix_session_is_expired")
    test_felix_session_needs_refresh()
    print("PASS: test_felix_session_needs_refresh")
    test_felix_session_serialization()
    print("PASS: test_felix_session_serialization")
    print("\nAll felix_auth tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
