#!/usr/bin/env python3
"""Tests for Felix Turnkey auth — crypto operations and header generation."""

from __future__ import annotations

import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_auth import (
    generate_p256_session_keypair,
    get_p256_public_key_hex,
    serialize_p256_private_key_pem,
    deserialize_p256_private_key_pem,
    sign_with_secp256k1,
    build_x_stamp_header,
    build_stamp_login_body,
    parse_stamp_login_response,
    FelixSession,
)


def test_generate_p256_keypair():
    """P-256 keypair generation produces valid key objects."""
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = generate_p256_session_keypair()
    assert isinstance(private_key, ec.EllipticCurvePrivateKey)
    assert isinstance(private_key.curve, ec.SECP256R1)

    # Public key should be extractable
    pub = private_key.public_key()
    assert isinstance(pub, ec.EllipticCurvePublicKey)


def test_p256_public_key_hex():
    """P-256 public key hex is uncompressed format (65 bytes = 130 hex chars)."""
    private_key = generate_p256_session_keypair()
    hex_str = get_p256_public_key_hex(private_key)

    # Uncompressed P-256 public key: 04 || x (32 bytes) || y (32 bytes) = 65 bytes
    assert len(hex_str) == 130
    assert hex_str.startswith("04")


def test_p256_key_serialization_roundtrip():
    """P-256 private key survives PEM serialization roundtrip."""
    original = generate_p256_session_keypair()
    pem = serialize_p256_private_key_pem(original)

    assert isinstance(pem, str)
    assert "BEGIN EC PRIVATE KEY" in pem

    restored = deserialize_p256_private_key_pem(pem)
    # Verify same public key
    assert get_p256_public_key_hex(original) == get_p256_public_key_hex(restored)


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
    """stamp_login body has correct structure."""
    p256_key = generate_p256_session_keypair()
    p256_pub_hex = get_p256_public_key_hex(p256_key)
    org_id = "test-org-123"

    body = build_stamp_login_body(
        organization_id=org_id,
        session_public_key_hex=p256_pub_hex,
        expiration_seconds=900,
    )

    parsed = json.loads(body)
    assert parsed["type"] == "ACTIVITY_TYPE_STAMP_LOGIN"
    assert parsed["organizationId"] == org_id
    assert parsed["parameters"]["publicKey"] == p256_pub_hex
    assert parsed["parameters"]["expirationSeconds"] == "900"
    assert "timestampMs" in parsed
    # timestampMs should be a string of current-ish epoch ms
    ts = int(parsed["timestampMs"])
    assert abs(ts - int(time.time() * 1000)) < 5000  # within 5 seconds


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
    try:
        parse_stamp_login_response(response)
        assert False, "Should have raised RuntimeError"
    except RuntimeError as e:
        assert "FAILED" in str(e) or "stamp_login" in str(e).lower()


def test_felix_session_is_expired():
    """FelixSession correctly reports expiry."""
    session = FelixSession(
        jwt="token",
        expires_at=int(time.time()) - 10,  # 10 seconds ago
        session_key_pem="-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----",
        sub_org_id="org_123",
    )
    assert session.is_expired()

    session2 = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 600,  # 10 minutes from now
        session_key_pem="-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----",
        sub_org_id="org_123",
    )
    assert not session2.is_expired()


def test_felix_session_needs_refresh():
    """FelixSession reports needing refresh when <2 minutes remain."""
    session = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 60,  # 1 minute from now — needs refresh
        session_key_pem="-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----",
        sub_org_id="org_123",
    )
    assert session.needs_refresh()

    session2 = FelixSession(
        jwt="token",
        expires_at=int(time.time()) + 600,  # 10 minutes — no refresh needed
        session_key_pem="-----BEGIN EC PRIVATE KEY-----\ntest\n-----END EC PRIVATE KEY-----",
        sub_org_id="org_123",
    )
    assert not session2.needs_refresh()


def test_felix_session_serialization():
    """FelixSession survives JSON serialization roundtrip."""
    session = FelixSession(
        jwt="eyJ.test.sig",
        expires_at=1711900000,
        session_key_pem="-----BEGIN EC PRIVATE KEY-----\nABC\n-----END EC PRIVATE KEY-----",
        sub_org_id="org_abc",
    )
    data = session.to_dict()
    assert isinstance(data, dict)
    assert data["jwt"] == "eyJ.test.sig"

    restored = FelixSession.from_dict(data)
    assert restored.jwt == session.jwt
    assert restored.expires_at == session.expires_at
    assert restored.session_key_pem == session.session_key_pem
    assert restored.sub_org_id == session.sub_org_id


def main() -> int:
    test_generate_p256_keypair()
    print("PASS: test_generate_p256_keypair")
    test_p256_public_key_hex()
    print("PASS: test_p256_public_key_hex")
    test_p256_key_serialization_roundtrip()
    print("PASS: test_p256_key_serialization_roundtrip")
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
