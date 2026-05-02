"""Felix equity order placement.

Full order flow:
    1. check_limits(ticker, side)               → verify market open + max size
    2. get_quote(ticker, side, ...)             → quote_id + EIP-712 intent
    3. sign_via_turnkey(payloadHash, ...)       → {v, r, s}  (Turnkey signing API)
    4. submit_order(quote_id, intent_id, sig)   → order_id
    5. poll_order(order_id)                     → final order dict (FILLED / FAILED)

Signing uses Turnkey's sign_with_ecdsa API (not local key) because the Felix equity
account is a Turnkey-managed key in the user's sub-org. The session private key from
stamp_login authenticates the signing request.

Symbol format: Felix uses "TSLAon" (append "on"). Pass plain tickers (TSLA) here;
the module normalizes automatically.

Usage:
    from tracking.connectors.felix_order import FelixOrderClient

    client = FelixOrderClient(
        jwt="eyJ...",
        session_private_key_hex="...",   # from FelixSession.session_private_key_hex
        sub_org_id="d9b5db5f-...",       # from FelixSession.sub_org_id
    )
    result = client.place_order("TSLA", "BUY", notional_usdc=50.0)
    # result["status"] == "FILLED"
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

from eth_account import Account

log = logging.getLogger(__name__)

FELIX_PROXY_BASE = "https://spot-equities-proxy.white-star-bc1e.workers.dev"

_BROWSER_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://trade.usefelix.xyz",
    "Referer": "https://trade.usefelix.xyz/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
}

# EIP-712 domain type (standard — always required by eth_account)
_EIP712_DOMAIN_TYPE = [
    {"name": "name", "type": "string"},
    {"name": "version", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]

# Terminal order statuses — stop polling when reached
_TERMINAL_STATUSES = {"FILLED", "FAILED", "CANCELLED", "EXPIRED", "REJECTED"}


# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

def to_felix_symbol(ticker: str) -> str:
    """Convert plain ticker to Felix market symbol: TSLA → TSLAon."""
    s = ticker.strip()
    return s if s.endswith("on") else s + "on"


def from_felix_symbol(symbol: str) -> str:
    """Strip Felix 'on' suffix: TSLAon → TSLA."""
    return symbol[:-2] if symbol.endswith("on") else symbol


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _http_get(path: str, *, jwt: Optional[str] = None, timeout: int = 30) -> Any:
    url = FELIX_PROXY_BASE + path
    headers = dict(_BROWSER_HEADERS)
    headers["Accept"] = "application/json"
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = _read_body(e)
        raise RuntimeError(f"Felix GET {path} → HTTP {e.code}: {body[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Felix GET {path} → network error: {e.reason}") from e


def _http_post(path: str, payload: Any, *, jwt: str, timeout: int = 30) -> Any:
    url = FELIX_PROXY_BASE + path
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    headers = dict(_BROWSER_HEADERS)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    headers["Authorization"] = f"Bearer {jwt}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_err = _read_body(e)
        raise RuntimeError(f"Felix POST {path} → HTTP {e.code}: {body_err[:400]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Felix POST {path} → network error: {e.reason}") from e


def _read_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# EIP-712 signing
# ---------------------------------------------------------------------------

def _coerce_scalar(type_str: str, value: Any) -> Any:
    """Convert Felix API string values to Python types for eth_account."""
    if type_str.startswith("uint") or type_str.startswith("int"):
        return int(value)
    if type_str == "bytes" or (type_str.startswith("bytes") and len(type_str) > 5):
        if isinstance(value, str) and value.startswith("0x"):
            return bytes.fromhex(value[2:])
        return value
    # address, string, bool: pass through
    return value


def _coerce_struct(message: dict, types: dict, type_name: str) -> dict:
    """Recursively coerce struct fields to proper Python types."""
    fields = {f["name"]: f["type"] for f in types.get(type_name, [])}
    result = {}
    for name, value in message.items():
        type_str = fields.get(name, "")
        if type_str.endswith("[]"):
            inner = type_str[:-2]
            if inner in types:
                result[name] = [_coerce_struct(v, types, inner) for v in value]
            else:
                result[name] = [_coerce_scalar(inner, v) for v in value]
        elif type_str in types:
            result[name] = _coerce_struct(value, types, type_str)
        else:
            result[name] = _coerce_scalar(type_str, value)
    return result


def sign_eip712_intent(eip712: dict, wallet_private_key_hex: str) -> dict:
    """Sign a Felix EIP-712 BatchExecuteData intent locally.

    Kept for testing only. Production use calls sign_via_turnkey() instead,
    because the Felix equity account key is Turnkey-managed (not the auth wallet key).

    Args:
        eip712: the ``intent.eip712`` dict from a quote response
        wallet_private_key_hex: secp256k1 private key hex (32 bytes, with or without 0x)

    Returns:
        dict with keys ``v`` (int), ``r`` (hex str), ``s`` (hex str)
    """
    domain = eip712["domain"]
    types: dict = eip712["types"]
    message: dict = eip712["message"]

    coerced_message = _coerce_struct(message, types, "BatchExecuteData")

    full_message = {
        "types": {
            "EIP712Domain": _EIP712_DOMAIN_TYPE,
            **types,
        },
        "domain": domain,
        "primaryType": "BatchExecuteData",
        "message": coerced_message,
    }

    pk = wallet_private_key_hex.strip()
    if not pk.startswith("0x"):
        pk = "0x" + pk

    signed = Account.sign_typed_data(private_key=pk, full_message=full_message)

    return {
        "v": signed.v,
        "r": hex(signed.r),
        "s": hex(signed.s),
    }


# ---------------------------------------------------------------------------
# Turnkey signing (production path)
# ---------------------------------------------------------------------------

TURNKEY_API_BASE = "https://api.turnkey.com"


def sign_via_turnkey(
    payload_hash: str,
    account_address: str,
    sub_org_id: str,
    session_private_key_hex: str,
    *,
    timeout: int = 30,
) -> dict:
    """Sign a Felix intent hash via Turnkey's sign_with_ecdsa API.

    The Felix equity account is a Turnkey-managed key in the user's sub-org.
    Signing must go through Turnkey, authenticated with the session private key
    (ephemeral keypair from stamp_login).

    Args:
        payload_hash: hex hash from intent.payloadHash (e.g. "0xabc...")
        account_address: Felix account address to sign with (from quote.accountId)
        sub_org_id: Turnkey sub-org ID (from FelixSession.sub_org_id)
        session_private_key_hex: ephemeral session key (from FelixSession.session_private_key_hex)

    Returns:
        dict with keys ``v`` (int), ``r`` (hex str), ``s`` (hex str)
    """
    from tracking.connectors.felix_auth import build_x_stamp_header

    timestamp_ms = str(int(time.time() * 1000))
    body_dict = {
        "type": "ACTIVITY_TYPE_SIGN_RAW_PAYLOAD_V2",
        "timestampMs": timestamp_ms,
        "organizationId": sub_org_id,
        "parameters": {
            "signWith": account_address,
            "payload": payload_hash,
            "encoding": "PAYLOAD_ENCODING_HEXADECIMAL",
            "hashFunction": "HASH_FUNCTION_NO_OP",
        },
    }
    body_bytes = json.dumps(body_dict, separators=(",", ":")).encode("utf-8")
    stamp = build_x_stamp_header(session_private_key_hex, body_bytes)

    url = TURNKEY_API_BASE + "/public/v1/submit/sign_raw_payload"
    req = urllib.request.Request(
        url,
        data=body_bytes,
        headers={
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Origin": "https://trade.usefelix.xyz",
            "Referer": "https://trade.usefelix.xyz/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/147.0.0.0 Safari/537.36"
            ),
            "X-Stamp": stamp,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_err = _read_body(e)
        raise RuntimeError(
            f"Turnkey sign_raw_payload HTTP {e.code}: {body_err[:400]}"
        ) from e

    activity = data.get("activity", {})
    status = activity.get("status", "")
    if status != "ACTIVITY_STATUS_COMPLETED":
        raise RuntimeError(
            f"Turnkey signing failed: status={status} activity={activity.get('id')}"
        )

    result = activity.get("result", {}).get("signRawPayloadResult", {})
    r_hex = result.get("r", "")
    s_hex = result.get("s", "")
    v_val = result.get("v", "")

    if not r_hex or not s_hex:
        raise RuntimeError(f"Turnkey sign result missing r/s: {result}")

    # Ensure 0x prefix
    r_hex = r_hex if r_hex.startswith("0x") else "0x" + r_hex
    s_hex = s_hex if s_hex.startswith("0x") else "0x" + s_hex
    v_raw = int(v_val) if isinstance(v_val, str) else int(v_val)
    v_int = v_raw if v_raw >= 27 else v_raw + 27

    return {"v": v_int, "r": r_hex, "s": s_hex}


# ---------------------------------------------------------------------------
# FelixOrderClient
# ---------------------------------------------------------------------------

class FelixOrderClient:
    """Felix equity order placement client.

    Signs orders via Turnkey's sign_with_ecdsa API (not local key), because
    the Felix equity account is a Turnkey-managed key distinct from the auth wallet.

    Args:
        jwt: Valid Felix JWT from felix_auth.py (FelixSession.jwt)
        session_private_key_hex: Ephemeral session key from stamp_login
            (FelixSession.session_private_key_hex) — authenticates Turnkey signing
        sub_org_id: Turnkey sub-org ID (FelixSession.sub_org_id)
    """

    def __init__(
        self,
        *,
        jwt: str,
        session_private_key_hex: str,
        sub_org_id: str,
    ) -> None:
        if not jwt:
            raise ValueError("Felix JWT is required")
        if not session_private_key_hex:
            raise ValueError("session_private_key_hex is required for Turnkey signing")
        if not sub_org_id:
            raise ValueError("sub_org_id is required for Turnkey signing")
        self._jwt = jwt.strip()
        self._session_pk = session_private_key_hex.strip()
        self._sub_org_id = sub_org_id.strip()

    # ------------------------------------------------------------------
    # Market data
    # ------------------------------------------------------------------

    def fetch_all_prices(self) -> List[Dict[str, Any]]:
        """GET /v1/market/prices — all symbols. No auth required."""
        resp = _http_get("/v1/market/prices")
        return resp.get("data", [])

    def fetch_price(self, ticker: str) -> Dict[str, Any]:
        """GET /v1/market/prices/{symbol} — single symbol price.

        Returns dict with primaryMarket.price, underlyingMarket.price, timestamp.
        """
        symbol = to_felix_symbol(ticker)
        return _http_get(f"/v1/market/prices/{symbol}")

    # ------------------------------------------------------------------
    # Trading checks
    # ------------------------------------------------------------------

    def check_limits(self, ticker: str, side: str) -> Dict[str, Any]:
        """POST /v1/trading/limits — check market open + max position.

        Args:
            ticker: plain ticker, e.g. "TSLA"
            side: "BUY" or "SELL"

        Returns:
            dict with maxTokens, maxNotionalValue, isOpen, reason, remainingAttestations
        """
        symbol = to_felix_symbol(ticker)
        return _http_post(
            "/v1/trading/limits",
            {"symbol": symbol, "side": side.upper()},
            jwt=self._jwt,
        )

    # ------------------------------------------------------------------
    # Quote
    # ------------------------------------------------------------------

    def get_quote(
        self,
        ticker: str,
        side: str,
        *,
        notional_usdc: Optional[float] = None,
        token_amount: Optional[float] = None,
        stablecoin: str = "USDC",
    ) -> Dict[str, Any]:
        """POST /v1/trading/quote — get a price quote and EIP-712 intent.

        For BUY: pass notional_usdc (USD amount, e.g. 50.0)
        For SELL: pass token_amount (shares, e.g. 0.133021)

        Quote expires in ~30 seconds — sign and submit immediately.

        Returns:
            Full quote dict including id, estimatedShares, price, expiresAt,
            and intent.eip712 for signing.
        """
        side_upper = side.upper()
        symbol = to_felix_symbol(ticker)

        if side_upper == "BUY":
            if notional_usdc is None:
                raise ValueError("notional_usdc required for BUY orders")
            payload = {
                "symbol": symbol,
                "side": "BUY",
                "stablecoin": stablecoin,
                "notionalValue": str(notional_usdc),
            }
        elif side_upper == "SELL":
            if token_amount is None:
                raise ValueError("token_amount (shares) required for SELL orders")
            payload = {
                "symbol": symbol,
                "side": "SELL",
                "stablecoin": stablecoin,
                "tokenAmount": str(token_amount),
            }
        else:
            raise ValueError(f"Invalid side: {side!r}. Must be 'BUY' or 'SELL'")

        return _http_post("/v1/trading/quote", payload, jwt=self._jwt)

    # ------------------------------------------------------------------
    # Order submission
    # ------------------------------------------------------------------

    def submit_order(
        self,
        quote_id: str,
        intent_id: str,
        signature: Dict[str, Any],
    ) -> Dict[str, Any]:
        """POST /v1/trading/orders — submit signed order.

        Args:
            quote_id: from quote response .id
            intent_id: from quote response .intent.id
            signature: {v: int, r: hex_str, s: hex_str}

        Returns:
            Order dict with id, status (SUBMITTED_ONCHAIN), accountId, etc.
        """
        payload = {
            "quoteId": quote_id,
            "intentId": intent_id,
            "signature": signature,
        }
        return _http_post("/v1/trading/orders", payload, jwt=self._jwt)

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """GET /v1/trading/orders/{id} — get order status."""
        return _http_get(f"/v1/trading/orders/{order_id}", jwt=self._jwt)

    def poll_order(
        self,
        order_id: str,
        *,
        timeout: float = 90.0,
        poll_interval: float = 3.0,
    ) -> Dict[str, Any]:
        """Poll order until terminal state (FILLED / FAILED / CANCELLED / EXPIRED).

        Args:
            order_id: from submit_order response .id
            timeout: max seconds to wait (default 90)
            poll_interval: seconds between polls (default 3)

        Returns:
            Final order dict.

        Raises:
            TimeoutError: if order doesn't reach terminal state within timeout
        """
        deadline = time.monotonic() + timeout
        while True:
            order = self.get_order(order_id)
            status = order.get("status", "")
            log.debug("Felix order %s status=%s", order_id, status)

            if status in _TERMINAL_STATUSES:
                return order

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Felix order {order_id} still {status!r} after {timeout:.0f}s"
                )

            time.sleep(poll_interval)

    # ------------------------------------------------------------------
    # Full flow
    # ------------------------------------------------------------------

    def place_order(
        self,
        ticker: str,
        side: str,
        *,
        notional_usdc: Optional[float] = None,
        token_amount: Optional[float] = None,
        stablecoin: str = "USDC",
        check_limits_first: bool = True,
        poll: bool = True,
        poll_timeout: float = 90.0,
    ) -> Dict[str, Any]:
        """Execute a Felix equity order end-to-end.

        Flow: [check_limits →] get_quote → sign_via_turnkey → submit_order [→ poll]

        Args:
            ticker: plain ticker, e.g. "TSLA"
            side: "BUY" or "SELL"
            notional_usdc: USD amount for BUY (e.g. 50.0)
            token_amount: share count for SELL (e.g. 0.133)
            stablecoin: "USDC" (default and currently only supported)
            check_limits_first: verify market open before quoting (default True)
            poll: wait for FILLED/FAILED status (default True)
            poll_timeout: max poll seconds (default 90)

        Returns:
            If poll=True: final order dict (check status field for FILLED/FAILED)
            If poll=False: submitted order dict (status=SUBMITTED_ONCHAIN)
        """
        side_upper = side.upper()

        if check_limits_first:
            limits = self.check_limits(ticker, side_upper)
            if not limits.get("isOpen"):
                reason = limits.get("reason") or "market closed"
                raise RuntimeError(f"Felix market not open for {ticker} {side_upper}: {reason}")
            log.info(
                "Felix limits OK: %s %s maxNotional=%s remainingAttestations=%s",
                ticker, side_upper,
                limits.get("maxNotionalValue"), limits.get("remainingAttestations"),
            )

        log.info("Felix: getting quote %s %s", side_upper, ticker)
        quote = self.get_quote(
            ticker, side_upper,
            notional_usdc=notional_usdc,
            token_amount=token_amount,
            stablecoin=stablecoin,
        )

        quote_id = quote["id"]
        intent = quote["intent"]
        intent_id = intent["id"]
        payload_hash = intent["payloadHash"]
        account_address = quote["accountId"]
        expires_at = quote.get("expiresAt", "")
        log.info(
            "Felix: quote %s price=%s estimatedShares=%s expiresAt=%s",
            quote_id, quote.get("price"), quote.get("estimatedShares"), expires_at,
        )

        # Sign via Turnkey — must happen before quote expires (~30s)
        sig = sign_via_turnkey(
            payload_hash,
            account_address,
            self._sub_org_id,
            self._session_pk,
        )
        log.info("Felix: Turnkey signed intent %s v=%s", intent_id, sig["v"])

        order = self.submit_order(quote_id, intent_id, sig)
        order_id = order["id"]
        log.info("Felix: order %s submitted status=%s", order_id, order.get("status"))

        if not poll:
            return order

        final = self.poll_order(order_id, timeout=poll_timeout)
        log.info(
            "Felix: order %s final status=%s txHash=%s",
            order_id, final.get("status"), final.get("onchainTxHash"),
        )
        return final
