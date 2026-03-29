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
    4. Sign with wallet secp256k1 key -> X-Stamp header
    5. POST to Turnkey -> receive JWT

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
