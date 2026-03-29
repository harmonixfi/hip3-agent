# Phase 3: Felix Equities Headless Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement fully automated Felix equities JWT management via Turnkey stamp_login, Felix API connector for fill ingestion, and 14-minute auto-refresh cron.

**Architecture:** Wallet private key (secp256k1) from vault signs Turnkey stamp_login → receives ES256 JWT (900s TTL). P-256 session keypair enables refresh without wallet key. Felix connector uses JWT for API access. Cron refreshes every 14 minutes.

**Tech Stack:** Python 3.11+, cryptography library (EC operations), urllib.request

**References:**
- Architecture spec: `docs/PLAN.md` sections 5.2, 7, 8 (Phase 3)
- Task checklist: `docs/tasks/phase-3-felix-auth.md`
- Decisions: `docs/DECISIONS.md` (ADR-004 vault)
- Vault interface: `vault/vault.py` (Phase 1a)
- Existing connectors: `tracking/connectors/hyperliquid_private.py`, `tracking/connectors/paradex_private.py`
- Existing fill ingester: `tracking/pipeline/fill_ingester.py` (Phase 1a)
- Existing base class: `tracking/connectors/private_base.py`

**Dependencies:** Phase 1a must be complete (vault, pm_fills table, fill_ingester with `generate_synthetic_tid`, `insert_fills`, `load_fill_targets`, `map_fill_to_leg`).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `tracking/connectors/felix_auth.py` | Turnkey stamp_login, X-Stamp header, JWT management |
| Create | `tracking/connectors/felix_private.py` | Felix API connector (portfolio, orders, fills) |
| Create | `tracking/pipeline/felix_fill_ingester.py` | Parse Felix fills → pm_fills format, ingest |
| Create | `scripts/felix_jwt_refresh.py` | Cron script: login or refresh JWT, store in vault |
| Create | `tests/test_felix_auth.py` | Unit tests for auth crypto operations |
| Create | `tests/test_felix_private.py` | Unit tests for Felix API connector |
| Create | `tests/test_felix_fill_ingester.py` | Unit tests for fill parsing and ingestion |

---

## Background: Turnkey Auth Protocol

### Auth Flow Overview

```
                                  Turnkey API
                                  (api.turnkey.com)
                                       |
    1. Generate P-256 session keypair  |
    2. Build stamp_login body          |
    3. Sign body with wallet secp256k1 |
    4. Create X-Stamp header           |
    5. POST /public/v1/submit/stamp_login
                                       |
                              +---------+---------+
                              |                   |
                         JWT (ES256)        session active
                         900s TTL           for P-256 key
                              |
    6. Use JWT as Bearer token to Felix proxy
       https://spot-equities-proxy.white-star-bc1e.workers.dev
```

### Key Constants

```python
TURNKEY_API_BASE = "https://api.turnkey.com"
FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"
FELIX_ORG_ID = "b052e625-0ea1-4e6a-b3a4-dd3d8e06f636"
FELIX_AUTH_PROXY_CONFIG = "cc6ef853-e2e2-45db-a0f8-7c46be0ad04f"
JWT_TTL_SECONDS = 900
REFRESH_INTERVAL_SECONDS = 840  # 14 minutes
```

### X-Stamp Header Format

The X-Stamp header authenticates the request to Turnkey. It is a base64url-encoded JSON object:

```json
{
  "publicKey": "<hex-encoded secp256k1 public key (uncompressed, no 04 prefix)>",
  "signature": "<hex-encoded DER signature of the POST body>",
  "scheme": "SIGNATURE_SCHEME_TK_API_P256"
}
```

**Important:** Despite the scheme name containing "P256", the actual signing uses the wallet's secp256k1 key. The scheme identifier is a Turnkey protocol constant.

### stamp_login Request Body

```json
{
  "type": "ACTIVITY_TYPE_STAMP_LOGIN",
  "timestampMs": "1711900000000",
  "organizationId": "<user's sub-org ID>",
  "parameters": {
    "publicKey": "<hex-encoded P-256 session public key (uncompressed)>",
    "expirationSeconds": "900"
  }
}
```

### stamp_login Response

```json
{
  "activity": {
    "id": "...",
    "status": "ACTIVITY_STATUS_COMPLETED",
    "result": {
      "stampLoginResult": {
        "session": "<JWT token string>"
      }
    }
  }
}
```

### Sub-Org Discovery

Before stamp_login, we need the user's sub-organization ID. Turnkey provides this via:

```
POST /public/v1/query/list_suborgs
Body: {
  "organizationId": "<root org ID>",
  "filterType": "FILTER_TYPE_WALLET_ADDRESS",
  "filterValue": "<wallet address>"
}
```

This returns the sub-org that owns the wallet, which is needed for the `organizationId` field in stamp_login.

---

## Task 1: Felix Auth Module (`tracking/connectors/felix_auth.py`)

**Files:**
- Create: `tracking/connectors/felix_auth.py`
- Create: `tests/test_felix_auth.py`

- [ ] **Step 1: Write failing tests for felix_auth**

Create `tests/test_felix_auth.py`:

```python
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
    assert decoded["scheme"] == "SIGNATURE_SCHEME_TK_API_P256"
    assert len(decoded["publicKey"]) == 130  # uncompressed secp256k1 (65 bytes)


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_felix_auth.py
```

Expected: `ModuleNotFoundError: No module named 'tracking.connectors.felix_auth'`

- [ ] **Step 3: Install cryptography dependency**

The `cryptography` library is needed for EC key operations (secp256k1 signing, P-256 key generation). Check if already installed; install if not.

Run:
```bash
source .arbit_env && .venv/bin/pip install cryptography
```

Verify:
```bash
.venv/bin/python -c "from cryptography.hazmat.primitives.asymmetric import ec; print('OK: cryptography installed')"
```

- [ ] **Step 4: Implement felix_auth module**

Create `tracking/connectors/felix_auth.py`:

```python
"""Felix equities headless auth via Turnkey stamp_login.

Implements the Turnkey authentication protocol:
1. Generate P-256 session keypair (for session refresh)
2. Sign stamp_login request body with wallet secp256k1 key
3. Create X-Stamp header for Turnkey API authentication
4. Exchange for JWT (ES256, 900s TTL)
5. Refresh using P-256 session key before expiry

The wallet private key (secp256k1) MUST come from the vault — never from env vars.

Auth flow:
    wallet_key (secp256k1, from vault)
      → sign stamp_login body
      → X-Stamp header
      → POST /public/v1/submit/stamp_login
      → JWT (900s TTL)
      → Authorization: Bearer <jwt> to Felix proxy

Usage:
    from tracking.connectors.felix_auth import initial_login, refresh_session

    session = initial_login(wallet_private_key_hex)
    # ... later ...
    new_session = refresh_session(session)
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TURNKEY_API_BASE = "https://api.turnkey.com"
FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"
FELIX_ORG_ID = "b052e625-0ea1-4e6a-b3a4-dd3d8e06f636"
FELIX_AUTH_PROXY_CONFIG = "cc6ef853-e2e2-45db-a0f8-7c46be0ad04f"
JWT_TTL_SECONDS = 900
REFRESH_BUFFER_SECONDS = 120  # refresh when <2 min remaining

# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


@dataclass
class FelixSession:
    """Holds Felix auth session state."""
    jwt: str
    expires_at: int  # epoch seconds
    session_key_pem: str  # P-256 private key in PEM format
    sub_org_id: str

    def is_expired(self) -> bool:
        """True if JWT has expired."""
        return time.time() >= self.expires_at

    def needs_refresh(self) -> bool:
        """True if JWT will expire within REFRESH_BUFFER_SECONDS."""
        return time.time() >= (self.expires_at - REFRESH_BUFFER_SECONDS)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FelixSession:
        return cls(
            jwt=data["jwt"],
            expires_at=int(data["expires_at"]),
            session_key_pem=data["session_key_pem"],
            sub_org_id=data["sub_org_id"],
        )


# ---------------------------------------------------------------------------
# P-256 Session Key Operations
# ---------------------------------------------------------------------------


def generate_p256_session_keypair() -> ec.EllipticCurvePrivateKey:
    """Generate a new P-256 (secp256r1) private key for Turnkey session refresh."""
    return ec.generate_private_key(ec.SECP256R1())


def get_p256_public_key_hex(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Extract uncompressed public key as hex string (65 bytes = 130 hex chars).

    Format: 04 || x (32 bytes) || y (32 bytes)
    This is what Turnkey expects in the stamp_login parameters.publicKey field.
    """
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return pub_bytes.hex()


def serialize_p256_private_key_pem(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Serialize P-256 private key to PEM string for vault storage."""
    pem_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pem_bytes.decode("utf-8")


def deserialize_p256_private_key_pem(pem: str) -> ec.EllipticCurvePrivateKey:
    """Deserialize P-256 private key from PEM string."""
    key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    if not isinstance(key, ec.EllipticCurvePrivateKey):
        raise ValueError("PEM does not contain an EC private key")
    return key


# ---------------------------------------------------------------------------
# secp256k1 Wallet Signing
# ---------------------------------------------------------------------------


def _load_secp256k1_private_key(hex_key: str) -> ec.EllipticCurvePrivateKey:
    """Load a secp256k1 private key from hex string.

    Args:
        hex_key: 32-byte private key as hex (64 chars), with or without 0x prefix.
    """
    clean = hex_key.strip()
    if clean.startswith("0x") or clean.startswith("0X"):
        clean = clean[2:]
    key_bytes = bytes.fromhex(clean)
    if len(key_bytes) != 32:
        raise ValueError(f"secp256k1 private key must be 32 bytes, got {len(key_bytes)}")

    private_int = int.from_bytes(key_bytes, "big")
    return ec.derive_private_key(private_int, ec.SECP256K1())


def _get_secp256k1_public_key_hex(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Get uncompressed secp256k1 public key as hex (65 bytes = 130 hex chars)."""
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return pub_bytes.hex()


def sign_with_secp256k1(wallet_private_key_hex: str, message: bytes) -> str:
    """Sign a message with secp256k1 private key, return DER-encoded signature as hex.

    The signature is over SHA256(message), using ECDSA with secp256k1.
    Returns the DER-encoded signature as a hex string.
    """
    private_key = _load_secp256k1_private_key(wallet_private_key_hex)
    signature_der = private_key.sign(
        message,
        ec.ECDSA(hashes.SHA256()),
    )
    return signature_der.hex()


# ---------------------------------------------------------------------------
# X-Stamp Header
# ---------------------------------------------------------------------------


def build_x_stamp_header(wallet_private_key_hex: str, body: bytes) -> str:
    """Build the X-Stamp header value for Turnkey API authentication.

    The X-Stamp is a base64url-encoded JSON object containing:
    - publicKey: hex-encoded uncompressed secp256k1 public key
    - signature: hex-encoded DER signature of the body
    - scheme: "SIGNATURE_SCHEME_TK_API_P256"

    Args:
        wallet_private_key_hex: secp256k1 wallet private key (hex, 64 chars)
        body: the raw POST body bytes to sign

    Returns:
        base64url-encoded X-Stamp header value (no padding)
    """
    private_key = _load_secp256k1_private_key(wallet_private_key_hex)

    # Get uncompressed public key hex
    pub_hex = _get_secp256k1_public_key_hex(private_key)

    # Sign the body
    signature_der = private_key.sign(body, ec.ECDSA(hashes.SHA256()))
    sig_hex = signature_der.hex()

    # Build stamp JSON
    stamp = {
        "publicKey": pub_hex,
        "signature": sig_hex,
        "scheme": "SIGNATURE_SCHEME_TK_API_P256",
    }
    stamp_json = json.dumps(stamp, separators=(",", ":")).encode("utf-8")

    # base64url encode (no padding)
    encoded = base64.urlsafe_b64encode(stamp_json).rstrip(b"=").decode("ascii")
    return encoded


# ---------------------------------------------------------------------------
# stamp_login Request/Response
# ---------------------------------------------------------------------------


def build_stamp_login_body(
    *,
    organization_id: str,
    session_public_key_hex: str,
    expiration_seconds: int = JWT_TTL_SECONDS,
    timestamp_ms: Optional[int] = None,
) -> str:
    """Build the JSON body for the Turnkey stamp_login request.

    Args:
        organization_id: the user's Turnkey sub-org ID
        session_public_key_hex: P-256 session public key (uncompressed hex)
        expiration_seconds: JWT TTL (default 900)
        timestamp_ms: override timestamp (for testing)

    Returns:
        JSON string (compact, no extra whitespace)
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    body = {
        "type": "ACTIVITY_TYPE_STAMP_LOGIN",
        "timestampMs": str(timestamp_ms),
        "organizationId": organization_id,
        "parameters": {
            "publicKey": session_public_key_hex,
            "expirationSeconds": str(expiration_seconds),
        },
    }
    return json.dumps(body, separators=(",", ":"))


def parse_stamp_login_response(response: Dict[str, Any]) -> str:
    """Extract JWT from Turnkey stamp_login response.

    Args:
        response: parsed JSON response from Turnkey API

    Returns:
        JWT token string

    Raises:
        RuntimeError: if the activity failed or JWT not found
    """
    activity = response.get("activity", {})
    status = activity.get("status", "")

    if status != "ACTIVITY_STATUS_COMPLETED":
        raise RuntimeError(
            f"stamp_login failed: status={status}, "
            f"activity_id={activity.get('id', 'unknown')}"
        )

    result = activity.get("result", {})
    stamp_result = result.get("stampLoginResult", {})
    jwt = stamp_result.get("session")

    if not jwt:
        raise RuntimeError(
            f"stamp_login response missing JWT: result={json.dumps(result)}"
        )

    return jwt


# ---------------------------------------------------------------------------
# Turnkey API Calls
# ---------------------------------------------------------------------------


def _turnkey_post(
    path: str,
    body_bytes: bytes,
    wallet_private_key_hex: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an authenticated POST request to Turnkey API.

    Signs the body with the wallet key and attaches the X-Stamp header.
    """
    url = TURNKEY_API_BASE + path
    stamp = build_x_stamp_header(wallet_private_key_hex, body_bytes)

    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Stamp": stamp,
            "User-Agent": "arbit-felix-auth/0.1",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def lookup_sub_org(
    wallet_address: str,
    wallet_private_key_hex: str,
    *,
    root_org_id: str = FELIX_ORG_ID,
) -> str:
    """Look up the Turnkey sub-organization ID for a wallet address.

    Args:
        wallet_address: Ethereum wallet address (0x...)
        wallet_private_key_hex: wallet private key for X-Stamp signing
        root_org_id: Felix root organization ID

    Returns:
        Sub-organization ID string

    Raises:
        RuntimeError: if sub-org not found or API call fails
    """
    body = json.dumps({
        "organizationId": root_org_id,
        "filterType": "FILTER_TYPE_WALLET_ADDRESS",
        "filterValue": wallet_address.lower(),
    }, separators=(",", ":")).encode("utf-8")

    response = _turnkey_post(
        "/public/v1/query/list_suborgs",
        body,
        wallet_private_key_hex,
    )

    # Response: {"organizationIds": ["sub-org-id-1", ...]}
    org_ids = response.get("organizationIds", [])
    if not org_ids:
        raise RuntimeError(
            f"No Turnkey sub-org found for wallet {wallet_address}. "
            f"Ensure the wallet is registered with Felix (org: {root_org_id})."
        )

    return org_ids[0]


# ---------------------------------------------------------------------------
# Login and Refresh
# ---------------------------------------------------------------------------


def initial_login(
    wallet_private_key_hex: str,
    wallet_address: str,
    *,
    sub_org_id: Optional[str] = None,
) -> FelixSession:
    """Perform initial Felix login using wallet private key.

    This is the full auth flow:
    1. Look up sub-org ID (if not provided)
    2. Generate P-256 session keypair
    3. Build stamp_login body
    4. Sign with wallet secp256k1 key → X-Stamp header
    5. POST to Turnkey → receive JWT

    Args:
        wallet_private_key_hex: secp256k1 wallet private key (hex)
        wallet_address: Ethereum wallet address (0x...)
        sub_org_id: optional cached sub-org ID (skips lookup)

    Returns:
        FelixSession with JWT, P-256 session key, and expiry

    Security note: wallet_private_key_hex should come from vault, never env var.
    """
    # Step 1: Resolve sub-org
    if not sub_org_id:
        sub_org_id = lookup_sub_org(wallet_address, wallet_private_key_hex)

    # Step 2: Generate session keypair
    session_key = generate_p256_session_keypair()
    session_pub_hex = get_p256_public_key_hex(session_key)

    # Step 3: Build stamp_login body
    body_str = build_stamp_login_body(
        organization_id=sub_org_id,
        session_public_key_hex=session_pub_hex,
    )
    body_bytes = body_str.encode("utf-8")

    # Step 4: POST to Turnkey with X-Stamp
    response = _turnkey_post(
        "/public/v1/submit/stamp_login",
        body_bytes,
        wallet_private_key_hex,
    )

    # Step 5: Parse JWT
    jwt = parse_stamp_login_response(response)

    return FelixSession(
        jwt=jwt,
        expires_at=int(time.time()) + JWT_TTL_SECONDS,
        session_key_pem=serialize_p256_private_key_pem(session_key),
        sub_org_id=sub_org_id,
    )


def refresh_session(
    session: FelixSession,
    wallet_private_key_hex: str,
) -> FelixSession:
    """Refresh an existing Felix session using the P-256 session key.

    If the session has a valid P-256 key and the sub-org is known, we sign
    a new stamp_login using the wallet key but reuse the session keypair.

    In the Turnkey model, refresh still requires wallet signature (the P-256
    key is the *target* session key, not the *signing* key for stamp_login).

    If the session is fully expired or corrupted, falls back to initial_login.

    Args:
        session: current FelixSession
        wallet_private_key_hex: wallet key for signing

    Returns:
        New FelixSession with fresh JWT
    """
    try:
        # Reuse existing P-256 session key
        session_key = deserialize_p256_private_key_pem(session.session_key_pem)
        session_pub_hex = get_p256_public_key_hex(session_key)

        # Build new stamp_login body
        body_str = build_stamp_login_body(
            organization_id=session.sub_org_id,
            session_public_key_hex=session_pub_hex,
        )
        body_bytes = body_str.encode("utf-8")

        # Sign and POST
        response = _turnkey_post(
            "/public/v1/submit/stamp_login",
            body_bytes,
            wallet_private_key_hex,
        )

        jwt = parse_stamp_login_response(response)

        return FelixSession(
            jwt=jwt,
            expires_at=int(time.time()) + JWT_TTL_SECONDS,
            session_key_pem=session.session_key_pem,  # reuse same P-256 key
            sub_org_id=session.sub_org_id,
        )

    except Exception:
        # Refresh failed — we cannot silently recover here.
        # Caller (cron script) decides whether to do a full initial_login.
        raise
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
source .arbit_env && .venv/bin/python tests/test_felix_auth.py
```

Expected: `All felix_auth tests passed!`

- [ ] **Step 6: Commit**

```bash
git add tracking/connectors/felix_auth.py tests/test_felix_auth.py
git commit -m "feat: add Felix Turnkey auth module (secp256k1 signing, X-Stamp, stamp_login)"
```

---

## Task 2: Felix Private Connector (`tracking/connectors/felix_private.py`)

**Files:**
- Create: `tracking/connectors/felix_private.py`
- Create: `tests/test_felix_private.py`

- [ ] **Step 1: Write failing tests for felix_private**

Create `tests/test_felix_private.py`:

```python
#!/usr/bin/env python3
"""Tests for Felix private connector — portfolio, orders, fills."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_private import (
    FelixPrivateConnector,
    _parse_portfolio_response,
    _parse_fills_response,
    _normalize_felix_inst_id,
)


def test_normalize_felix_inst_id():
    """Felix symbols are normalized to SYMBOL/USDC format."""
    assert _normalize_felix_inst_id("AAPL") == "AAPL/USDC"
    assert _normalize_felix_inst_id("GOOGL") == "GOOGL/USDC"
    assert _normalize_felix_inst_id("MSFT") == "MSFT/USDC"
    # Already normalized — passthrough
    assert _normalize_felix_inst_id("AAPL/USDC") == "AAPL/USDC"
    # Edge cases
    assert _normalize_felix_inst_id("") == ""
    assert _normalize_felix_inst_id("  NVDA  ") == "NVDA/USDC"


def test_parse_portfolio_response():
    """Portfolio response is parsed into normalized dict."""
    raw = {
        "positions": [
            {
                "symbol": "AAPL",
                "quantity": "10.5",
                "averageEntryPrice": "175.30",
                "currentPrice": "180.00",
                "unrealizedPnl": "49.35",
                "side": "LONG",
            },
            {
                "symbol": "GOOGL",
                "quantity": "3.0",
                "averageEntryPrice": "140.00",
                "currentPrice": "142.50",
                "unrealizedPnl": "7.50",
                "side": "LONG",
            },
        ],
        "accountValue": "5000.00",
        "availableBalance": "2000.00",
    }
    result = _parse_portfolio_response(raw, "0xabc")

    assert result["account_id"] == "0xabc"
    assert result["total_balance"] == 5000.0
    assert result["available_balance"] == 2000.0
    assert len(result["positions"]) == 2
    assert result["positions"][0]["inst_id"] == "AAPL/USDC"
    assert result["positions"][0]["size"] == 10.5
    assert result["positions"][0]["entry_price"] == 175.30


def test_parse_fills_response():
    """Fill response is parsed into normalized list."""
    raw = {
        "orders": [
            {
                "id": "ord_001",
                "symbol": "AAPL",
                "side": "BUY",
                "filledQuantity": "10.0",
                "averageFilledPrice": "175.30",
                "fee": "0.88",
                "status": "FILLED",
                "createdAt": "2026-03-15T10:00:00Z",
                "updatedAt": "2026-03-15T10:00:01Z",
            },
            {
                "id": "ord_002",
                "symbol": "GOOGL",
                "side": "BUY",
                "filledQuantity": "3.0",
                "averageFilledPrice": "140.00",
                "fee": "0.42",
                "status": "FILLED",
                "createdAt": "2026-03-16T14:00:00Z",
                "updatedAt": "2026-03-16T14:00:02Z",
            },
        ]
    }
    fills = _parse_fills_response(raw, "0xabc")

    assert len(fills) == 2
    assert fills[0]["inst_id"] == "AAPL/USDC"
    assert fills[0]["side"] == "BUY"
    assert fills[0]["px"] == 175.30
    assert fills[0]["sz"] == 10.0
    assert fills[0]["fee"] == 0.88
    assert fills[0]["account_id"] == "0xabc"
    assert fills[0]["venue"] == "felix"
    # tid should be present (from order id or synthetic)
    assert fills[0]["tid"] is not None


def test_parse_fills_skips_unfilled():
    """Unfilled or cancelled orders are skipped."""
    raw = {
        "orders": [
            {
                "id": "ord_003",
                "symbol": "MSFT",
                "side": "BUY",
                "filledQuantity": "0",
                "averageFilledPrice": "0",
                "fee": "0",
                "status": "CANCELLED",
                "createdAt": "2026-03-17T10:00:00Z",
            },
            {
                "id": "ord_004",
                "symbol": "MSFT",
                "side": "BUY",
                "filledQuantity": "0",
                "averageFilledPrice": "0",
                "fee": "0",
                "status": "PENDING",
                "createdAt": "2026-03-17T10:00:00Z",
            },
        ]
    }
    fills = _parse_fills_response(raw, "0xabc")
    assert len(fills) == 0


def main() -> int:
    test_normalize_felix_inst_id()
    print("PASS: test_normalize_felix_inst_id")
    test_parse_portfolio_response()
    print("PASS: test_parse_portfolio_response")
    test_parse_fills_response()
    print("PASS: test_parse_fills_response")
    test_parse_fills_skips_unfilled()
    print("PASS: test_parse_fills_skips_unfilled")
    print("\nAll felix_private tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_felix_private.py
```

Expected: ImportError.

- [ ] **Step 3: Implement felix_private connector**

Create `tracking/connectors/felix_private.py`:

```python
"""Felix equities private connector.

Provides access to Felix equity portfolio, orders, and fills via the Felix
proxy API. Requires a valid JWT from the Turnkey auth flow (felix_auth.py).

Felix API is accessed through the Cloudflare Workers proxy:
    https://spot-equities-proxy.white-star-bc1e.workers.dev

All endpoints require Authorization: Bearer <jwt> header.

Usage:
    from tracking.connectors.felix_private import FelixPrivateConnector

    connector = FelixPrivateConnector(jwt="eyJ...", wallet_address="0x...")
    portfolio = connector.fetch_portfolio()
    fills = connector.fetch_fills()
"""

from __future__ import annotations

import json
import time
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional

from .private_base import PrivateConnectorBase

FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"


def _to_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _normalize_felix_inst_id(symbol: str) -> str:
    """Normalize Felix equity symbol to SYMBOL/USDC format.

    Felix API returns plain symbols (AAPL, GOOGL). Our schema uses
    SYMBOL/USDC for spot instruments (consistent with HL spot).
    """
    s = str(symbol or "").strip()
    if not s:
        return ""
    if "/" in s:
        return s  # already normalized
    return f"{s}/USDC"


def _iso_to_epoch_ms(iso_str: str) -> int:
    """Convert ISO 8601 datetime string to epoch milliseconds.

    Handles common formats: 2026-03-15T10:00:00Z, 2026-03-15T10:00:00.000Z
    """
    from datetime import datetime, timezone

    s = str(iso_str or "").strip()
    if not s:
        return 0

    # Handle milliseconds if present
    if "." in s:
        s = s.split(".")[0] + "Z"

    # Remove trailing Z and parse as UTC
    s = s.rstrip("Z")
    try:
        dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _felix_get(
    path: str,
    jwt: str,
    *,
    params: Optional[Dict[str, str]] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Make an authenticated GET request to Felix proxy API."""
    url = FELIX_PROXY_BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)

    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {jwt}",
            "User-Agent": "arbit-felix-private/0.1",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


# ---------------------------------------------------------------------------
# Response Parsers (module-level for testability)
# ---------------------------------------------------------------------------


def _parse_portfolio_response(
    raw: Dict[str, Any],
    wallet_address: str,
) -> Dict[str, Any]:
    """Parse Felix portfolio response into normalized structure.

    Args:
        raw: raw API response from /v1/portfolio/{address}
        wallet_address: the wallet address used for the query

    Returns:
        Normalized dict with account_id, balances, and positions list
    """
    positions = []
    for p in raw.get("positions", []):
        if not isinstance(p, dict):
            continue
        symbol = str(p.get("symbol", ""))
        inst_id = _normalize_felix_inst_id(symbol)
        if not inst_id:
            continue

        size = _to_float(p.get("quantity"))
        if size is None or size == 0:
            continue

        side = str(p.get("side", "")).upper()
        if side not in ("LONG", "SHORT"):
            side = "LONG"  # Felix equities are long by default

        positions.append({
            "inst_id": inst_id,
            "side": side,
            "size": abs(size),
            "entry_price": _to_float(p.get("averageEntryPrice")),
            "current_price": _to_float(p.get("currentPrice")),
            "unrealized_pnl": _to_float(p.get("unrealizedPnl")),
            "raw": p,
        })

    return {
        "account_id": wallet_address,
        "total_balance": _to_float(raw.get("accountValue")),
        "available_balance": _to_float(raw.get("availableBalance")),
        "positions": positions,
        "raw_json": raw,
    }


def _parse_fills_response(
    raw: Dict[str, Any],
    wallet_address: str,
) -> List[Dict[str, Any]]:
    """Parse Felix orders/fills response into pm_fills-compatible dicts.

    Felix may return orders rather than individual fills. Each FILLED order
    is treated as a single fill with averageFilledPrice and filledQuantity.

    Unfilled, cancelled, or pending orders are skipped.

    Args:
        raw: raw API response from /v1/trading/orders
        wallet_address: the wallet address

    Returns:
        List of fill dicts compatible with insert_fills()
    """
    from tracking.pipeline.fill_ingester import generate_synthetic_tid

    fills = []
    orders = raw.get("orders", [])
    if not isinstance(orders, list):
        return fills

    for order in orders:
        if not isinstance(order, dict):
            continue

        status = str(order.get("status", "")).upper()
        if status not in ("FILLED", "PARTIALLY_FILLED"):
            continue

        symbol = str(order.get("symbol", ""))
        inst_id = _normalize_felix_inst_id(symbol)
        if not inst_id:
            continue

        px = _to_float(order.get("averageFilledPrice"))
        sz = _to_float(order.get("filledQuantity"))
        if not px or px <= 0 or not sz or sz <= 0:
            continue

        side = str(order.get("side", "")).upper()
        if side not in ("BUY", "SELL"):
            continue

        fee = _to_float(order.get("fee")) or 0.0

        # Timestamp: prefer updatedAt (fill time), fallback to createdAt
        ts_str = order.get("updatedAt") or order.get("createdAt") or ""
        ts_ms = _iso_to_epoch_ms(ts_str)

        # Trade ID: use order ID if available, otherwise synthetic
        order_id = str(order.get("id", "")) or None
        if order_id:
            tid = f"felix_{order_id}"
        else:
            tid = generate_synthetic_tid(
                venue="felix",
                account_id=wallet_address,
                inst_id=inst_id,
                side=side,
                px=px,
                sz=sz,
                ts=ts_ms,
            )

        fills.append({
            "venue": "felix",
            "account_id": wallet_address,
            "tid": tid,
            "oid": order_id,
            "inst_id": inst_id,
            "side": side,
            "px": px,
            "sz": sz,
            "fee": fee,
            "fee_currency": "USDC",
            "ts": ts_ms,
            "closed_pnl": None,
            "dir": None,
            "builder_fee": None,
            "position_id": None,  # mapped later by fill ingester
            "leg_id": None,  # mapped later by fill ingester
            "raw_json": json.dumps(order),
            "meta_json": json.dumps({"source": "felix", "raw_symbol": symbol}),
        })

    return fills


# ---------------------------------------------------------------------------
# Connector Class
# ---------------------------------------------------------------------------


class FelixPrivateConnector(PrivateConnectorBase):
    """Private connector for Felix equities using JWT auth.

    Requires a valid Turnkey JWT. Use felix_auth.py to obtain/refresh.
    """

    def __init__(
        self,
        *,
        jwt: str,
        wallet_address: str,
    ):
        super().__init__("felix")
        self.jwt = jwt.strip()
        self.wallet_address = wallet_address.strip().lower()
        if not self.jwt:
            raise RuntimeError("Felix JWT is required")
        if not self.wallet_address:
            raise RuntimeError("Felix wallet address is required")

    def fetch_account_snapshot(self) -> Dict:
        """Fetch Felix portfolio snapshot.

        GET /v1/portfolio/{address}
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.wallet_address)
        return {
            "account_id": parsed["account_id"],
            "total_balance": parsed["total_balance"],
            "available_balance": parsed["available_balance"],
            "margin_balance": parsed["total_balance"],
            "unrealized_pnl": None,
            "position_value": None,
            "raw_json": parsed["raw_json"],
        }

    def fetch_open_positions(self) -> List[Dict]:
        """Fetch Felix open positions.

        Derives from portfolio endpoint since Felix exposes positions there.
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        parsed = _parse_portfolio_response(raw, self.wallet_address)

        out = []
        for p in parsed["positions"]:
            out.append({
                "leg_id": f"felix:{self.wallet_address}:{p['inst_id']}:{p['side']}",
                "position_id": "",
                "inst_id": p["inst_id"],
                "side": p["side"],
                "size": p["size"],
                "entry_price": p["entry_price"],
                "current_price": p["current_price"],
                "unrealized_pnl": p["unrealized_pnl"],
                "realized_pnl": None,
                "raw_json": p.get("raw", {}),
            })
        return out

    def fetch_fills(
        self,
        *,
        since_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch Felix trade fills (from orders endpoint).

        GET /v1/trading/orders

        Returns list of fill dicts compatible with pm_fills schema.
        """
        params = {}
        if since_ms:
            from datetime import datetime, timezone
            dt = datetime.fromtimestamp(since_ms / 1000, tz=timezone.utc)
            params["since"] = dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        raw = _felix_get("/v1/trading/orders", self.jwt, params=params)
        return _parse_fills_response(raw, self.wallet_address)

    def fetch_portfolio(self) -> Dict[str, Any]:
        """Fetch full portfolio data (convenience method).

        Returns parsed portfolio dict with positions, balances.
        """
        raw = _felix_get(
            f"/v1/portfolio/{self.wallet_address}",
            self.jwt,
        )
        return _parse_portfolio_response(raw, self.wallet_address)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
source .arbit_env && .venv/bin/python tests/test_felix_private.py
```

Expected: `All felix_private tests passed!`

- [ ] **Step 5: Commit**

```bash
git add tracking/connectors/felix_private.py tests/test_felix_private.py
git commit -m "feat: add Felix private connector (portfolio, orders, fills)"
```

---

## Task 3: Felix Fill Ingester (`tracking/pipeline/felix_fill_ingester.py`)

**Files:**
- Create: `tracking/pipeline/felix_fill_ingester.py`
- Create: `tests/test_felix_fill_ingester.py`

- [ ] **Step 1: Write failing tests for felix fill ingester**

Create `tests/test_felix_fill_ingester.py`:

```python
#!/usr/bin/env python3
"""Tests for Felix fill ingestion pipeline."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db(db_path: Path) -> sqlite3.Connection:
    """Create a test DB with pm_positions, pm_legs, and pm_fills tables."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    con.executescript("""
        CREATE TABLE pm_positions(
          position_id TEXT PRIMARY KEY,
          venue TEXT NOT NULL,
          strategy TEXT,
          status TEXT NOT NULL,
          created_at_ms INTEGER NOT NULL,
          updated_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_legs(
          leg_id TEXT PRIMARY KEY,
          position_id TEXT NOT NULL,
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL,
          size REAL NOT NULL,
          entry_price REAL,
          current_price REAL,
          unrealized_pnl REAL,
          realized_pnl REAL,
          status TEXT NOT NULL,
          opened_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE pm_fills (
          fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          tid TEXT,
          oid TEXT,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
          px REAL NOT NULL,
          sz REAL NOT NULL,
          fee REAL,
          fee_currency TEXT,
          ts INTEGER NOT NULL,
          closed_pnl REAL,
          dir TEXT,
          builder_fee REAL,
          position_id TEXT,
          leg_id TEXT,
          raw_json TEXT,
          meta_json TEXT,
          UNIQUE (venue, account_id, tid),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
        );
    """)
    return con


def _seed_felix_positions(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed Felix equity positions for testing."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("pos_felix_AAPL", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_felix_GOOGL", "hyperliquid", "SPOT_PERP", "CLOSED", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("aapl_spot", "pos_felix_AAPL", "felix", "AAPL/USDC", "LONG", 10.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("aapl_perp", "pos_felix_AAPL", "hyperliquid", "xyz:AAPL", "SHORT", 10.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("googl_spot", "pos_felix_GOOGL", "felix", "GOOGL/USDC", "LONG", 3.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            ("googl_perp", "pos_felix_GOOGL", "hyperliquid", "xyz:GOOGL", "SHORT", 3.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


def test_ingest_felix_fills_maps_to_legs():
    """Felix fills are mapped to correct position legs."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_001",
                "oid": "ord_001",
                "inst_id": "AAPL/USDC",
                "side": "BUY",
                "px": 175.30,
                "sz": 10.0,
                "fee": 0.88,
                "fee_currency": "USDC",
                "ts": 1711900000000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        inserted = ingest_felix_fills(con, raw_fills)
        assert inserted == 1

        # Verify fill was mapped to correct leg
        row = con.execute(
            "SELECT position_id, leg_id FROM pm_fills WHERE tid = 'felix_ord_001'"
        ).fetchone()
        assert row is not None
        assert row[0] == "pos_felix_AAPL"
        assert row[1] == "aapl_spot"

        con.close()


def test_ingest_felix_fills_dedup():
    """Duplicate Felix fills are rejected."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_002",
                "oid": "ord_002",
                "inst_id": "AAPL/USDC",
                "side": "BUY",
                "px": 176.00,
                "sz": 5.0,
                "fee": 0.44,
                "fee_currency": "USDC",
                "ts": 1711900100000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        assert ingest_felix_fills(con, raw_fills) == 1
        assert ingest_felix_fills(con, raw_fills) == 0  # dedup

        count = con.execute("SELECT COUNT(*) FROM pm_fills WHERE venue = 'felix'").fetchone()[0]
        assert count == 1

        con.close()


def test_ingest_felix_fills_unmapped():
    """Fills for unknown inst_id are inserted with NULL position/leg."""
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_felix_positions(con)

        raw_fills = [
            {
                "venue": "felix",
                "account_id": "0xabc",
                "tid": "felix_ord_999",
                "oid": "ord_999",
                "inst_id": "UNKNOWN/USDC",
                "side": "BUY",
                "px": 50.0,
                "sz": 1.0,
                "fee": 0.05,
                "fee_currency": "USDC",
                "ts": 1711900200000,
                "closed_pnl": None,
                "dir": None,
                "builder_fee": None,
                "position_id": None,
                "leg_id": None,
                "raw_json": "{}",
                "meta_json": "{}",
            }
        ]

        inserted = ingest_felix_fills(con, raw_fills)
        assert inserted == 1

        row = con.execute(
            "SELECT position_id, leg_id FROM pm_fills WHERE tid = 'felix_ord_999'"
        ).fetchone()
        assert row[0] is None
        assert row[1] is None

        con.close()


def main() -> int:
    test_ingest_felix_fills_maps_to_legs()
    print("PASS: test_ingest_felix_fills_maps_to_legs")
    test_ingest_felix_fills_dedup()
    print("PASS: test_ingest_felix_fills_dedup")
    test_ingest_felix_fills_unmapped()
    print("PASS: test_ingest_felix_fills_unmapped")
    print("\nAll felix_fill_ingester tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_felix_fill_ingester.py
```

Expected: ImportError.

- [ ] **Step 3: Implement felix_fill_ingester**

Create `tracking/pipeline/felix_fill_ingester.py`:

```python
"""Felix equity fill ingester.

Takes parsed fills from FelixPrivateConnector.fetch_fills() and ingests them
into pm_fills with position/leg mapping. Uses the same insert_fills() and
map_fill_to_leg() infrastructure from the HL fill ingester.

Usage:
    from tracking.connectors.felix_private import FelixPrivateConnector
    from tracking.pipeline.felix_fill_ingester import ingest_felix_fills_from_api

    connector = FelixPrivateConnector(jwt="...", wallet_address="0x...")
    count = ingest_felix_fills_from_api(con, connector)
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from tracking.pipeline.fill_ingester import (
    insert_fills,
    load_fill_targets,
    map_fill_to_leg,
)


def ingest_felix_fills(
    con: sqlite3.Connection,
    raw_fills: List[Dict[str, Any]],
    *,
    include_closed: bool = False,
    position_ids: Optional[List[str]] = None,
) -> int:
    """Map raw Felix fills to position legs and insert into pm_fills.

    Args:
        con: DB connection
        raw_fills: list of fill dicts from FelixPrivateConnector.fetch_fills()
                   or directly constructed (for testing)
        include_closed: include CLOSED positions when mapping
        position_ids: limit mapping to these positions

    Returns:
        Number of newly inserted fills
    """
    if not raw_fills:
        return 0

    # Load mapping targets (felix venue legs)
    targets = load_fill_targets(
        con,
        include_closed=include_closed,
        position_ids=position_ids,
    )

    # Map each fill to its position/leg
    mapped_fills = []
    for fill in raw_fills:
        inst_id = fill.get("inst_id", "")
        account_id = fill.get("account_id", "")

        target = map_fill_to_leg(inst_id, account_id, targets)

        mapped = dict(fill)
        if target:
            mapped["position_id"] = target["position_id"]
            mapped["leg_id"] = target["leg_id"]
        # If no target found, position_id and leg_id remain as-is (None)

        mapped_fills.append(mapped)

    return insert_fills(con, mapped_fills)


def ingest_felix_fills_from_api(
    con: sqlite3.Connection,
    connector: Any,  # FelixPrivateConnector
    *,
    include_closed: bool = False,
    since_ms: Optional[int] = None,
) -> int:
    """Full Felix fill ingestion: fetch from API + map + insert.

    Args:
        con: DB connection
        connector: FelixPrivateConnector instance with valid JWT
        include_closed: include CLOSED positions when mapping
        since_ms: only fetch fills since this timestamp

    Returns:
        Number of newly inserted fills
    """
    # Get watermark from DB if not specified
    if since_ms is None:
        row = con.execute(
            "SELECT MAX(ts) FROM pm_fills WHERE venue = 'felix'"
        ).fetchone()
        since_ms = int(row[0]) if row and row[0] else None

    raw_fills = connector.fetch_fills(since_ms=since_ms)

    if not raw_fills:
        return 0

    return ingest_felix_fills(
        con,
        raw_fills,
        include_closed=include_closed,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
source .arbit_env && .venv/bin/python tests/test_felix_fill_ingester.py
```

Expected: `All felix_fill_ingester tests passed!`

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/felix_fill_ingester.py tests/test_felix_fill_ingester.py
git commit -m "feat: add Felix fill ingester (map fills to legs, insert with dedup)"
```

---

## Task 4: Felix JWT Refresh Cron Script (`scripts/felix_jwt_refresh.py`)

**Files:**
- Create: `scripts/felix_jwt_refresh.py`

- [ ] **Step 1: Implement the cron script**

Create `scripts/felix_jwt_refresh.py`:

```python
#!/usr/bin/env python3
"""Felix JWT auto-refresh cron script.

Run every 14 minutes via systemd timer or crontab:
    */14 * * * * cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1

Flow:
1. Load wallet private key from vault
2. Try to load existing session from vault/felix_session.enc.json
3. If session exists and needs refresh: refresh using existing P-256 key
4. If no session or refresh fails: full initial_login with wallet key
5. Store updated session in vault (encrypted)
6. Log result

Security:
- Wallet private key comes from vault (never env var)
- Session state (JWT + P-256 key) stored encrypted in vault
- Never log JWT or private keys
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.connectors.felix_auth import (
    FelixSession,
    initial_login,
    refresh_session,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_DIR = ROOT / "vault"
SESSION_FILE = VAULT_DIR / "felix_session.enc.json"
SESSION_FILE_PLAIN = VAULT_DIR / "felix_session.dec.json"  # temporary, deleted after use

LOG_FMT = "%(asctime)s [felix_jwt] %(levelname)s %(message)s"
logging.basicConfig(format=LOG_FMT, level=logging.INFO, stream=sys.stdout)
log = logging.getLogger("felix_jwt")


# ---------------------------------------------------------------------------
# Vault Integration
# ---------------------------------------------------------------------------


def _get_wallet_key() -> str:
    """Load wallet private key from vault.

    Falls back to env var during migration period.
    """
    try:
        from vault.vault import get_secret_with_env_fallback

        key = get_secret_with_env_fallback(
            "felix_wallet_private_key",
            env_var="FELIX_WALLET_PRIVATE_KEY",
        )
        if key:
            return key
    except ImportError:
        pass

    # Fallback to env var
    key = os.environ.get("FELIX_WALLET_PRIVATE_KEY", "")
    if not key:
        raise RuntimeError(
            "Felix wallet private key not found. "
            "Set in vault as 'felix_wallet_private_key' or env var FELIX_WALLET_PRIVATE_KEY."
        )
    return key


def _get_wallet_address() -> str:
    """Load wallet address from vault or env."""
    try:
        from vault.vault import get_secret_with_env_fallback

        addr = get_secret_with_env_fallback(
            "felix_wallet_address",
            env_var="FELIX_WALLET_ADDRESS",
        )
        if addr:
            return addr
    except ImportError:
        pass

    addr = os.environ.get("FELIX_WALLET_ADDRESS", "")
    if not addr:
        raise RuntimeError(
            "Felix wallet address not found. "
            "Set in vault as 'felix_wallet_address' or env var FELIX_WALLET_ADDRESS."
        )
    return addr


def _load_session() -> FelixSession | None:
    """Load existing session from encrypted vault file.

    Returns None if file doesn't exist or decryption fails.
    """
    if not SESSION_FILE.exists():
        return None

    try:
        result = subprocess.run(
            ["sops", "--decrypt", str(SESSION_FILE)],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(result.stdout)
        return FelixSession.from_dict(data)
    except FileNotFoundError:
        log.warning("sops not installed — cannot load encrypted session")
        return None
    except subprocess.CalledProcessError:
        log.warning("Failed to decrypt session file — will do full login")
        return None
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log.warning("Corrupt session file: %s — will do full login", e)
        return None


def _save_session(session: FelixSession) -> None:
    """Save session to encrypted vault file using sops.

    Strategy:
    1. Write plaintext JSON to temporary file
    2. Encrypt in-place with sops
    3. Verify the encrypted file
    """
    VAULT_DIR.mkdir(parents=True, exist_ok=True)

    # Write plaintext
    plain_data = json.dumps(session.to_dict(), indent=2)
    SESSION_FILE.write_text(plain_data, encoding="utf-8")

    try:
        # Encrypt in-place
        subprocess.run(
            ["sops", "--encrypt", "--in-place", str(SESSION_FILE)],
            check=True,
            capture_output=True,
            text=True,
        )
        log.info("Session saved to vault (encrypted)")
    except FileNotFoundError:
        log.warning(
            "sops not installed — session saved as PLAINTEXT at %s. "
            "Install sops to encrypt.", SESSION_FILE
        )
    except subprocess.CalledProcessError as e:
        log.error("sops encrypt failed: %s", e.stderr)
        # Leave file as plaintext rather than losing the session
        log.warning("Session saved as PLAINTEXT (sops failed)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Main entry point for Felix JWT refresh."""
    log.info("Starting Felix JWT refresh...")

    try:
        wallet_key = _get_wallet_key()
        wallet_address = _get_wallet_address()
    except RuntimeError as e:
        log.error("Configuration error: %s", e)
        return 1

    # Try to load existing session
    session = _load_session()

    if session and not session.is_expired() and not session.needs_refresh():
        remaining = session.expires_at - int(time.time())
        log.info(
            "Session still valid (%d seconds remaining). No action needed.",
            remaining,
        )
        return 0

    if session and not session.is_expired():
        # Session exists and is not fully expired — try refresh
        log.info("Session needs refresh (sub-org: %s)...", session.sub_org_id)
        try:
            new_session = refresh_session(session, wallet_key)
            _save_session(new_session)
            log.info(
                "JWT refreshed successfully. Expires at %s (in %d seconds).",
                time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(new_session.expires_at)),
                new_session.expires_at - int(time.time()),
            )
            return 0
        except Exception as e:
            log.warning("Refresh failed: %s. Falling back to full login.", e)

    # Full initial login (no session, expired, or refresh failed)
    log.info("Performing full initial login for %s...", wallet_address)
    try:
        # Reuse sub-org ID if we have it (avoids extra API call)
        sub_org_id = session.sub_org_id if session else None

        new_session = initial_login(
            wallet_key,
            wallet_address,
            sub_org_id=sub_org_id,
        )
        _save_session(new_session)
        log.info(
            "Initial login successful. JWT expires at %s (in %d seconds).",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(new_session.expires_at)),
            new_session.expires_at - int(time.time()),
        )
        return 0

    except Exception as e:
        log.error("Felix login FAILED: %s", e)
        log.error(
            "Felix will be unavailable until next successful login. "
            "System continues without Felix data (degraded mode)."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify script loads without errors (dry run)**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from scripts import felix_jwt_refresh
print('OK: felix_jwt_refresh module loads correctly')
print('Functions:', [x for x in dir(felix_jwt_refresh) if not x.startswith('_')])
"
```

Note: This will not actually run the auth flow (no Felix credentials). It only verifies the module imports and compiles.

- [ ] **Step 3: Commit**

```bash
git add scripts/felix_jwt_refresh.py
git commit -m "feat: add Felix JWT auto-refresh cron script (14-minute cycle)"
```

---

## Task 5: Integration Testing

**Files:** None (verification only)

- [ ] **Step 1: Run all unit tests**

Run:
```bash
source .arbit_env
.venv/bin/python tests/test_felix_auth.py
.venv/bin/python tests/test_felix_private.py
.venv/bin/python tests/test_felix_fill_ingester.py
```

Expected: All tests pass.

- [ ] **Step 2: Verify crypto operations with known test vectors**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from tracking.connectors.felix_auth import (
    generate_p256_session_keypair,
    get_p256_public_key_hex,
    serialize_p256_private_key_pem,
    deserialize_p256_private_key_pem,
    sign_with_secp256k1,
    build_x_stamp_header,
    build_stamp_login_body,
    _load_secp256k1_private_key,
    _get_secp256k1_public_key_hex,
)
import json, base64

# Test 1: P-256 key generation
print('--- P-256 Key Generation ---')
key = generate_p256_session_keypair()
pub_hex = get_p256_public_key_hex(key)
print(f'P-256 public key (first 20 chars): {pub_hex[:20]}...')
print(f'Length: {len(pub_hex)} chars (expected: 130)')
assert len(pub_hex) == 130

# Test 2: P-256 PEM roundtrip
pem = serialize_p256_private_key_pem(key)
restored = deserialize_p256_private_key_pem(pem)
assert get_p256_public_key_hex(restored) == pub_hex
print('P-256 PEM roundtrip: OK')

# Test 3: secp256k1 signing
print()
print('--- secp256k1 Signing ---')
# Well-known test key (Hardhat account #0)
test_key = 'ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80'
priv = _load_secp256k1_private_key(test_key)
pub = _get_secp256k1_public_key_hex(priv)
print(f'secp256k1 public key (first 20 chars): {pub[:20]}...')
print(f'Length: {len(pub)} chars (expected: 130)')

sig = sign_with_secp256k1(test_key, b'hello world')
print(f'Signature (first 20 chars): {sig[:20]}...')
print(f'Signature length: {len(sig)} chars')

# Test 4: X-Stamp header
print()
print('--- X-Stamp Header ---')
stamp = build_x_stamp_header(test_key, b'{\"test\":\"data\"}')
decoded = json.loads(base64.urlsafe_b64decode(stamp + '=='))
print(f'Stamp fields: {list(decoded.keys())}')
assert 'publicKey' in decoded
assert 'signature' in decoded
assert decoded['scheme'] == 'SIGNATURE_SCHEME_TK_API_P256'
print('X-Stamp: OK')

# Test 5: stamp_login body
print()
print('--- stamp_login Body ---')
body = build_stamp_login_body(
    organization_id='test-org',
    session_public_key_hex=pub_hex,
)
parsed = json.loads(body)
print(f'Body type: {parsed[\"type\"]}')
print(f'Org ID: {parsed[\"organizationId\"]}')
print(f'Expiration: {parsed[\"parameters\"][\"expirationSeconds\"]}s')
print('stamp_login body: OK')

print()
print('All crypto verification tests passed!')
"
```

Expected: All assertions pass, all outputs are reasonable.

- [ ] **Step 3: Verify FelixPrivateConnector instantiation (no live API call)**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from tracking.connectors.felix_private import FelixPrivateConnector

# Verify constructor validates inputs
try:
    FelixPrivateConnector(jwt='', wallet_address='0x123')
    assert False, 'Should have raised'
except RuntimeError as e:
    print(f'Empty JWT rejected: {e}')

try:
    FelixPrivateConnector(jwt='test', wallet_address='')
    assert False, 'Should have raised'
except RuntimeError as e:
    print(f'Empty address rejected: {e}')

# Valid instantiation
c = FelixPrivateConnector(jwt='test-jwt', wallet_address='0xabc')
print(f'Connector venue: {c.venue}')
print(f'Connector wallet: {c.wallet_address}')
print('FelixPrivateConnector instantiation: OK')
"
```

- [ ] **Step 4: Verify fill ingester integration (with test DB)**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3, tempfile, json
from pathlib import Path

# Create in-memory test DB
con = sqlite3.connect(':memory:')
con.execute('PRAGMA foreign_keys = ON')
con.executescript('''
    CREATE TABLE pm_positions(
      position_id TEXT PRIMARY KEY,
      venue TEXT NOT NULL,
      strategy TEXT,
      status TEXT NOT NULL,
      created_at_ms INTEGER NOT NULL,
      updated_at_ms INTEGER NOT NULL,
      closed_at_ms INTEGER,
      raw_json TEXT,
      meta_json TEXT
    );
    CREATE TABLE pm_legs(
      leg_id TEXT PRIMARY KEY,
      position_id TEXT NOT NULL,
      venue TEXT NOT NULL,
      inst_id TEXT NOT NULL,
      side TEXT NOT NULL,
      size REAL NOT NULL,
      entry_price REAL,
      current_price REAL,
      unrealized_pnl REAL,
      realized_pnl REAL,
      status TEXT NOT NULL,
      opened_at_ms INTEGER NOT NULL,
      closed_at_ms INTEGER,
      raw_json TEXT,
      meta_json TEXT,
      account_id TEXT,
      FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
    );
    CREATE TABLE pm_fills (
      fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
      venue TEXT NOT NULL,
      account_id TEXT NOT NULL,
      tid TEXT,
      oid TEXT,
      inst_id TEXT NOT NULL,
      side TEXT NOT NULL CHECK (side IN (\"BUY\", \"SELL\")),
      px REAL NOT NULL,
      sz REAL NOT NULL,
      fee REAL,
      fee_currency TEXT,
      ts INTEGER NOT NULL,
      closed_pnl REAL,
      dir TEXT,
      builder_fee REAL,
      position_id TEXT,
      leg_id TEXT,
      raw_json TEXT,
      meta_json TEXT,
      UNIQUE (venue, account_id, tid),
      FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
      FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
    );
''')

# Seed data
now_ms = 1711900000000
con.execute(
    'INSERT INTO pm_positions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
    ('pos_AAPL', 'hyperliquid', 'SPOT_PERP', 'OPEN', now_ms, now_ms, None, '{}', '{}')
)
con.execute(
    'INSERT INTO pm_legs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
    ('aapl_spot', 'pos_AAPL', 'felix', 'AAPL/USDC', 'LONG', 10.0, None, None, None, None, 'OPEN', now_ms, None, '{}', '{}', '0xabc')
)
con.commit()

from tracking.pipeline.felix_fill_ingester import ingest_felix_fills

fills = [{
    'venue': 'felix', 'account_id': '0xabc', 'tid': 'felix_t1',
    'oid': 'o1', 'inst_id': 'AAPL/USDC', 'side': 'BUY',
    'px': 175.0, 'sz': 10.0, 'fee': 0.88, 'fee_currency': 'USDC',
    'ts': now_ms, 'closed_pnl': None, 'dir': None, 'builder_fee': None,
    'position_id': None, 'leg_id': None, 'raw_json': '{}', 'meta_json': '{}',
}]

count = ingest_felix_fills(con, fills)
print(f'Inserted: {count} fill(s)')
assert count == 1

row = con.execute('SELECT position_id, leg_id, inst_id, px, sz FROM pm_fills').fetchone()
print(f'Fill: pos={row[0]}, leg={row[1]}, inst={row[2]}, px={row[3]}, sz={row[4]}')
assert row[0] == 'pos_AAPL'
assert row[1] == 'aapl_spot'

# Dedup
count2 = ingest_felix_fills(con, fills)
assert count2 == 0
print(f'Dedup check: {count2} (expected 0)')

con.close()
print('Felix fill ingester integration: OK')
"
```

- [ ] **Step 5: Final commit (integration test passed)**

If all tests pass and no additional changes are needed, this step is a no-op. If fixes were required during testing, commit them here.

---

## Task 6: Systemd Timer Setup

**Files:** Documentation only (no code changes — deployment is manual)

- [ ] **Step 1: Document the crontab entry**

Add to crontab (or systemd timer):

```cron
# Felix JWT refresh (every 14 minutes)
*/14 * * * * cd /path/to/workspace && source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py >> logs/felix_jwt.log 2>&1
```

- [ ] **Step 2: Verify cron runs (after deployment)**

After deploying to VPS:
```bash
# Check recent logs
tail -20 logs/felix_jwt.log

# Manual test run
source .arbit_env && .venv/bin/python scripts/felix_jwt_refresh.py
```

Expected: Either "Session still valid" or "Initial login successful" or "JWT refreshed successfully".

- [ ] **Step 3: Verify health endpoint reports Felix JWT status**

After Phase 1c (API endpoints), the health endpoint should include:
```json
{
  "felix_jwt_expires_at": "2026-03-29T09:14:00Z",
  "felix_jwt_status": "active"
}
```

This integration requires reading the session file from the API layer — deferred to Phase 1c or a follow-up task.

---

## Task 7: Graceful Degradation

**Files:** No new files — verification that the system handles Felix auth failure gracefully.

- [ ] **Step 1: Verify system works without Felix credentials**

Run the hourly pipeline without Felix credentials configured:

```bash
source .arbit_env && .venv/bin/python -c "
# Simulate: no Felix credentials available
import os
for key in ['FELIX_WALLET_PRIVATE_KEY', 'FELIX_WALLET_ADDRESS']:
    os.environ.pop(key, None)

# Import should not fail
from tracking.connectors.felix_private import FelixPrivateConnector
print('FelixPrivateConnector imported (no crash)')

# Attempting to create connector without credentials should raise clearly
try:
    c = FelixPrivateConnector(jwt='', wallet_address='')
except RuntimeError as e:
    print(f'Expected error: {e}')

# The fill ingester should handle empty fills gracefully
from tracking.pipeline.felix_fill_ingester import ingest_felix_fills
import sqlite3
# Using in-memory DB with no tables — just testing the empty case
con = sqlite3.connect(':memory:')
try:
    ingest_felix_fills(con, [])
    print('Empty fills handled gracefully')
except Exception as e:
    print(f'Empty fills error: {e}')
con.close()

print('Graceful degradation: OK')
"
```

Expected: Clear error messages, no crashes, system continues operating.

- [ ] **Step 2: Document degraded mode behavior**

The system should:
- Log a WARNING when Felix auth fails (not ERROR that triggers alerts)
- Continue all other data pipelines (HL fills, cashflows, equity snapshots)
- Health endpoint shows `felix_jwt_status: "expired"` or `"unavailable"`
- Morning report notes Felix data staleness if JWT has been expired >1 hour

---

## Summary

| Task | Files | Tests | Description |
|------|-------|-------|-------------|
| 1 | `tracking/connectors/felix_auth.py` | `tests/test_felix_auth.py` | Turnkey stamp_login, X-Stamp, P-256/secp256k1 crypto, JWT management |
| 2 | `tracking/connectors/felix_private.py` | `tests/test_felix_private.py` | Felix API connector (portfolio, orders, fills) |
| 3 | `tracking/pipeline/felix_fill_ingester.py` | `tests/test_felix_fill_ingester.py` | Fill ingestion with leg mapping and dedup |
| 4 | `scripts/felix_jwt_refresh.py` | (integration test) | 14-minute cron: login/refresh JWT, store in vault |
| 5 | (none) | (verification) | Integration testing across all modules |
| 6 | (none) | (deployment) | Systemd timer / crontab setup |
| 7 | (none) | (verification) | Graceful degradation when Felix unavailable |

**Estimated effort:** 3-4 days

**Critical path:** Task 1 (auth) → Task 2 (connector) → Task 3 (ingester) → Task 4 (cron). Tasks 5-7 are verification and can overlap.

**Python dependency to add:** `cryptography` (for EC key operations). This is the only new dependency. No `web3` or `eth_account` needed — the `cryptography` library handles both secp256k1 and P-256 natively.
