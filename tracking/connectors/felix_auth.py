"""Felix equities headless auth via Turnkey stamp_login.

Auth flow:
    wallet_key (secp256k1, from vault)
      → compressed pubkey used as session identity (parameters.publicKey)
      → sign stamp_login body with EIP-191 (X-Stamp header)
      → POST /public/v1/submit/stamp_login
      → JWT (14-day TTL)
      → Authorization: Bearer <jwt> to Felix proxy
"""

from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from eth_account import Account
from eth_account.messages import encode_defunct

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TURNKEY_API_BASE = "https://api.turnkey.com"
FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"
FELIX_ORG_ID = "b052e625-0ea1-4e6a-b3a4-dd3d8e06f636"
FELIX_AUTH_PROXY_CONFIG = "cc6ef853-e2e2-45db-a0f8-7c46be0ad04f"
JWT_TTL_SECONDS = 1209600      # 14 days — matches browser signin
REFRESH_BUFFER_SECONDS = 86400  # refresh 1 day before expiry

# EVM wallets use EIP-191 over the raw POST body (matches @turnkey/wallet-stamper).
TURNKEY_STAMP_SCHEME_SECP256K1_EIP191 = "SIGNATURE_SCHEME_TK_API_SECP256K1_EIP191"

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Session dataclass
# ---------------------------------------------------------------------------


@dataclass
class FelixSession:
    """Holds Felix auth session state."""
    jwt: str
    expires_at: int  # epoch seconds
    sub_org_id: str
    session_private_key_hex: str = ""  # ephemeral session key for Turnkey signing API

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
            sub_org_id=data["sub_org_id"],
            session_private_key_hex=data.get("session_private_key_hex", ""),
        )


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


def _get_secp256k1_public_key_hex_compressed(private_key: ec.EllipticCurvePrivateKey) -> str:
    """Get compressed secp256k1 public key as hex (33 bytes = 66 hex chars).

    Used as both the X-Stamp publicKey and stamp_login parameters.publicKey,
    matching @turnkey/wallet-stamper browser behavior.
    """
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint,
    )
    return pub_bytes.hex()


def sign_with_secp256k1(wallet_private_key_hex: str, message: bytes) -> str:
    """Sign message with secp256k1 private key, return DER-encoded signature as hex.

    Uses SHA256+ECDSA. This is NOT used for Turnkey stamp auth (which uses EIP-191
    via eth_account). Retained as a utility for direct signing use cases.
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

    EVM wallets must match `@turnkey/wallet-stamper`: EIP-191 sign the UTF-8 POST
    body, DER-encode the (r,s) signature, compressed secp256k1 pubkey, scheme
    SIGNATURE_SCHEME_TK_API_SECP256K1_EIP191 (not TK_API_P256).

    Args:
        wallet_private_key_hex: secp256k1 wallet private key (hex, 64 chars)
        body: the raw POST body bytes (same bytes sent in the HTTP body)

    Returns:
        base64url-encoded X-Stamp header value (no padding)
    """
    private_key = _load_secp256k1_private_key(wallet_private_key_hex)
    pub_hex = _get_secp256k1_public_key_hex_compressed(private_key)

    # EIP-191 personal_sign equivalent (matches viem hashMessage + wallet sign)
    k = wallet_private_key_hex.strip()
    if not k.startswith(("0x", "0X")):
        k = "0x" + k
    acct = Account.from_key(k)
    signable = encode_defunct(primitive=body)
    signed_msg = acct.sign_message(signable)
    der_sig = encode_dss_signature(signed_msg.r, signed_msg.s)
    sig_hex = der_sig.hex()

    stamp = {
        "publicKey": pub_hex,
        "signature": sig_hex,
        "scheme": TURNKEY_STAMP_SCHEME_SECP256K1_EIP191,
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
    session_public_key_hex: str,
    expiration_seconds: int = JWT_TTL_SECONDS,
    timestamp_ms: Optional[int] = None,
) -> str:
    """Build the JSON body for the Turnkey stamp_login request.

    Args:
        session_public_key_hex: compressed secp256k1 pubkey of ephemeral session keypair
        expiration_seconds: JWT TTL (default 1209600 = 14 days)
        timestamp_ms: override for testing

    Returns:
        compact JSON string
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    body = {
        "type": "ACTIVITY_TYPE_STAMP_LOGIN",
        "timestampMs": str(timestamp_ms),
        "organizationId": FELIX_ORG_ID,  # always ROOT org, Turnkey routes to sub-org via X-Stamp
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

_MAX_ERR_BODY_LOG = 6000


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
            "Accept": "*/*",
            "Origin": "https://trade.usefelix.xyz",
            "Referer": "https://trade.usefelix.xyz/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "X-Stamp": stamp,
            "x-client-version": "@turnkey/core@1.11.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            log.debug("Turnkey POST %s -> HTTP %s", path, resp.status)
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        if len(err_body) > _MAX_ERR_BODY_LOG:
            err_body = err_body[:_MAX_ERR_BODY_LOG] + "...(truncated)"
        log.error(
            "Turnkey POST %s failed: HTTP %s %s. Response body: %s",
            path,
            e.code,
            e.reason,
            err_body,
        )
        raise RuntimeError(
            f"Turnkey HTTP {e.code} on {path}: {e.reason}. Body: {err_body[:800]}"
        ) from e
    except urllib.error.URLError as e:
        log.error("Turnkey POST %s failed: network error %s", path, e.reason)
        raise


def lookup_sub_org(wallet_private_key_hex: str) -> str:
    """Look up the Turnkey sub-organization ID via Felix auth proxy.

    Uses authproxy.turnkey.com/v1/account with PUBLIC_KEY filter.
    No authentication required — the auth proxy handles routing.
    """
    private_key = _load_secp256k1_private_key(wallet_private_key_hex)
    compressed_pubkey = _get_secp256k1_public_key_hex_compressed(private_key)

    body = json.dumps(
        {"filterType": "PUBLIC_KEY", "filterValue": compressed_pubkey},
        separators=(",", ":"),
    ).encode("utf-8")

    url = "https://authproxy.turnkey.com/v1/account"
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://trade.usefelix.xyz",
            "Referer": "https://trade.usefelix.xyz/",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "x-auth-proxy-config-id": FELIX_AUTH_PROXY_CONFIG,
        },
        method="POST",
    )

    log.info("Felix auth: auth proxy account lookup (pubkey=%s...)", compressed_pubkey[:12])
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            org_id = data.get("organizationId")
            if not org_id:
                raise RuntimeError(
                    f"No organizationId in auth proxy response: {raw[:400]}"
                )
            log.info("Felix auth: resolved sub_org_id=%s", org_id)
            return org_id
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        log.error("Auth proxy lookup failed: HTTP %s. Body: %s", e.code, err_body[:800])
        raise RuntimeError(
            f"Auth proxy HTTP {e.code}: {err_body[:800]}"
        ) from e
    except urllib.error.URLError as e:
        log.error("Auth proxy lookup failed: network error %s", e.reason)
        raise


# ---------------------------------------------------------------------------
# Login and Refresh
# ---------------------------------------------------------------------------


def initial_login(
    wallet_private_key_hex: str,
    wallet_address: str = "",
    *,
    sub_org_id: Optional[str] = None,
) -> FelixSession:
    """Perform initial Felix login using wallet private key.

    Flow:
    1. Look up sub-org ID via Felix auth proxy (PUBLIC_KEY lookup, no auth)
    2. Generate ephemeral secp256k1 session keypair
    3. Build stamp_login body (ROOT org ID, session pubkey as identity)
    4. Sign body with wallet key via EIP-191 → X-Stamp header
    5. POST to Turnkey → receive JWT
    """
    # Step 1: Resolve sub-org
    if not sub_org_id:
        sub_org_id = lookup_sub_org(wallet_private_key_hex)

    # Step 2: Generate ephemeral secp256k1 session keypair
    session_key = ec.generate_private_key(ec.SECP256K1())
    session_pub_hex = session_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint,
    ).hex()
    # Serialize session private key for Turnkey signing API authentication
    session_key_hex = session_key.private_numbers().private_value.to_bytes(32, "big").hex()

    # Step 3: Build stamp_login body (ROOT org, ephemeral session pubkey)
    body_str = build_stamp_login_body(session_public_key_hex=session_pub_hex)
    body_bytes = body_str.encode("utf-8")

    # Step 4: POST to Turnkey with wallet X-Stamp
    log.info("Felix auth: Turnkey stamp_login (sub_org_id=%s)", sub_org_id)
    response = _turnkey_post(
        "/public/v1/submit/stamp_login",
        body_bytes,
        wallet_private_key_hex,
    )

    # Step 5: Parse JWT
    jwt_token = parse_stamp_login_response(response)

    return FelixSession(
        jwt=jwt_token,
        expires_at=int(time.time()) + JWT_TTL_SECONDS,
        sub_org_id=sub_org_id,
        session_private_key_hex=session_key_hex,
    )


def refresh_session(
    session: FelixSession,
    wallet_private_key_hex: str,
) -> FelixSession:
    """Refresh Felix session by re-running stamp_login with a new ephemeral keypair.

    After P-256 removal, refresh = initial_login with cached sub_org_id (skips lookup).
    """
    log.info("Felix auth: Turnkey stamp_login refresh (sub_org_id=%s)", session.sub_org_id)
    # refresh_session re-runs stamp_login with cached sub_org_id (no lookup)
    return initial_login(
        wallet_private_key_hex,
        sub_org_id=session.sub_org_id,
    )
