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
    organization_id: str,
    wallet_private_key_hex: str,
    expiration_seconds: int = JWT_TTL_SECONDS,
    timestamp_ms: Optional[int] = None,
) -> str:
    """Build the JSON body for the Turnkey stamp_login request.

    Uses the wallet's compressed secp256k1 pubkey as the session identity,
    matching @turnkey/wallet-stamper browser behavior.

    Args:
        organization_id: Turnkey sub-org ID
        wallet_private_key_hex: secp256k1 wallet private key (hex, 64 chars); pubkey used as session identity
        expiration_seconds: JWT TTL in seconds (default 1209600 = 14 days)
        timestamp_ms: override for testing

    Returns:
        compact JSON string for the request body
    """
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)

    private_key = _load_secp256k1_private_key(wallet_private_key_hex)
    wallet_pub_hex = _get_secp256k1_public_key_hex_compressed(private_key)

    body = {
        "type": "ACTIVITY_TYPE_STAMP_LOGIN",
        "timestampMs": str(timestamp_ms),
        "organizationId": organization_id,
        "parameters": {
            "publicKey": wallet_pub_hex,
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
            "Accept": "application/json",
            "X-Stamp": stamp,
            "User-Agent": "arbit-felix-auth/0.1",
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

    log.info(
        "Felix auth: Turnkey list_suborgs (root_org=%s, wallet=%s)",
        root_org_id,
        wallet_address,
    )
    response = _turnkey_post(
        "/public/v1/query/list_suborgs",
        body,
        wallet_private_key_hex,
    )

    # Response: {"organizationIds": ["sub-org-id-1", ...]}
    org_ids = response.get("organizationIds", [])
    log.info(
        "Felix auth: list_suborgs returned %d sub-org id(s)",
        len(org_ids),
    )
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
    wallet_address: str = "",
    *,
    sub_org_id: Optional[str] = None,
) -> FelixSession:
    """Perform initial Felix login using wallet private key.

    Flow:
    1. Look up sub-org ID (if not provided)
    2. Build stamp_login body (wallet's compressed pubkey as session identity)
    3. Sign with wallet secp256k1 key -> X-Stamp header
    4. POST to Turnkey -> receive JWT
    """
    # Step 1: Resolve sub-org
    if not sub_org_id:
        if not wallet_address:
            raise ValueError(
                "wallet_address is required when sub_org_id is not provided"
            )
        sub_org_id = lookup_sub_org(wallet_address, wallet_private_key_hex)

    # Step 2: Build stamp_login body
    body_str = build_stamp_login_body(
        organization_id=sub_org_id,
        wallet_private_key_hex=wallet_private_key_hex,
    )
    body_bytes = body_str.encode("utf-8")

    # Step 3: POST to Turnkey with X-Stamp
    log.info("Felix auth: Turnkey stamp_login (sub_org_id=%s)", sub_org_id)
    response = _turnkey_post(
        "/public/v1/submit/stamp_login",
        body_bytes,
        wallet_private_key_hex,
    )

    # Step 4: Parse JWT
    jwt_token = parse_stamp_login_response(response)

    return FelixSession(
        jwt=jwt_token,
        expires_at=int(time.time()) + JWT_TTL_SECONDS,
        sub_org_id=sub_org_id,
    )


def refresh_session(
    session: FelixSession,
    wallet_private_key_hex: str,
) -> FelixSession:
    """Refresh Felix session by re-running stamp_login with the wallet key."""
    log.info("Felix auth: Turnkey stamp_login refresh (sub_org_id=%s)", session.sub_org_id)
    return initial_login(
        wallet_private_key_hex,
        sub_org_id=session.sub_org_id,
    )
