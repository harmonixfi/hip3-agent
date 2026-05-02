"""Unit tests for felix_order.py — no credentials, no network."""

from __future__ import annotations

import json
import pytest

from tracking.connectors.felix_order import (
    FelixOrderClient,
    _coerce_scalar,
    _coerce_struct,
    from_felix_symbol,
    sign_eip712_intent,
    to_felix_symbol,
)

# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------

class TestSymbolHelpers:
    def test_to_felix_symbol_plain(self):
        assert to_felix_symbol("TSLA") == "TSLAon"

    def test_to_felix_symbol_already_normalized(self):
        assert to_felix_symbol("TSLAon") == "TSLAon"

    def test_to_felix_symbol_strips_whitespace(self):
        assert to_felix_symbol("  AAPL  ") == "AAPLon"

    def test_from_felix_symbol(self):
        assert from_felix_symbol("TSLAon") == "TSLA"

    def test_from_felix_symbol_no_suffix(self):
        assert from_felix_symbol("TSLA") == "TSLA"


# ---------------------------------------------------------------------------
# EIP-712 type coercion
# ---------------------------------------------------------------------------

class TestCoerceScalar:
    def test_uint256_string(self):
        assert _coerce_scalar("uint256", "42") == 42

    def test_uint256_large_nonce(self):
        big = "85117725682671683225251272383736410733260124149709551369526744923939340210658"
        result = _coerce_scalar("uint256", big)
        assert result == int(big)

    def test_bytes_hex_string(self):
        result = _coerce_scalar("bytes", "0x095ea7b3")
        assert result == bytes.fromhex("095ea7b3")

    def test_bytes32(self):
        result = _coerce_scalar("bytes32", "0xdeadbeef" + "00" * 28)
        assert isinstance(result, bytes)

    def test_address_passthrough(self):
        addr = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
        assert _coerce_scalar("address", addr) == addr

    def test_string_passthrough(self):
        assert _coerce_scalar("string", "hello") == "hello"


CALL_TYPES = {
    "Call": [
        {"name": "target", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "callData", "type": "bytes"},
    ],
    "BatchExecuteData": [
        {"name": "calls", "type": "Call[]"},
        {"name": "deadline", "type": "uint256"},
        {"name": "nonce", "type": "uint256"},
        {"name": "token", "type": "address"},
        {"name": "amount", "type": "uint256"},
    ],
}

SAMPLE_MESSAGE = {
    "calls": [
        {
            "target": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
            "value": "0",
            "callData": "0x095ea7b3",
        },
    ],
    "deadline": "1777274708",
    "nonce": "85117725682671683225251272383736410733260124149709551369526744923939340210658",
    "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    "amount": "0",
}


class TestCoerceStruct:
    def test_scalar_fields_coerced(self):
        result = _coerce_struct(SAMPLE_MESSAGE, CALL_TYPES, "BatchExecuteData")
        assert result["deadline"] == 1777274708
        assert result["nonce"] == int(SAMPLE_MESSAGE["nonce"])
        assert result["amount"] == 0

    def test_nested_call_array_coerced(self):
        result = _coerce_struct(SAMPLE_MESSAGE, CALL_TYPES, "BatchExecuteData")
        call = result["calls"][0]
        assert call["value"] == 0
        assert isinstance(call["callData"], bytes)
        assert call["callData"] == bytes.fromhex("095ea7b3")

    def test_address_passthrough(self):
        result = _coerce_struct(SAMPLE_MESSAGE, CALL_TYPES, "BatchExecuteData")
        assert result["token"] == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


# ---------------------------------------------------------------------------
# EIP-712 signing (uses a test private key — no real funds)
# ---------------------------------------------------------------------------

# secp256k1 test key — deterministic, never used for real funds
_TEST_PK = "0x" + "aa" * 32

SAMPLE_EIP712 = {
    "domain": {
        "name": "FLX Executor",
        "version": "2",
        "chainId": 1,
        "verifyingContract": "0xaD0F4EcB5bbE32D080614018253FA5A40eF5df1D",
    },
    "types": CALL_TYPES,
    "message": SAMPLE_MESSAGE,
}


class TestSignEip712Intent:
    def test_returns_v_r_s(self):
        sig = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        assert set(sig.keys()) == {"v", "r", "s"}

    def test_v_is_27_or_28(self):
        sig = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        assert sig["v"] in (27, 28)

    def test_r_s_are_hex_strings(self):
        sig = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        assert sig["r"].startswith("0x")
        assert sig["s"].startswith("0x")

    def test_deterministic(self):
        # Same input + same key → same signature
        sig1 = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        sig2 = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        assert sig1 == sig2

    def test_pk_without_0x_prefix(self):
        pk_no_prefix = _TEST_PK[2:]
        sig = sign_eip712_intent(SAMPLE_EIP712, pk_no_prefix)
        assert sig["v"] in (27, 28)

    def test_different_pk_different_sig(self):
        other_pk = "0x" + "bb" * 32
        sig1 = sign_eip712_intent(SAMPLE_EIP712, _TEST_PK)
        sig2 = sign_eip712_intent(SAMPLE_EIP712, other_pk)
        assert sig1["r"] != sig2["r"]


# ---------------------------------------------------------------------------
# FelixOrderClient — validation only (no network)
# ---------------------------------------------------------------------------

_FAKE_SESSION_PK = "bb" * 32
_FAKE_SUB_ORG   = "d9b5db5f-2d5a-476a-a409-eccbbdc01a2a"


class TestFelixOrderClientValidation:
    def test_missing_jwt_raises(self):
        with pytest.raises(ValueError, match="JWT"):
            FelixOrderClient(jwt="", session_private_key_hex=_FAKE_SESSION_PK, sub_org_id=_FAKE_SUB_ORG)

    def test_missing_session_pk_raises(self):
        with pytest.raises(ValueError, match="session_private_key_hex"):
            FelixOrderClient(jwt="eyJ.fake.jwt", session_private_key_hex="", sub_org_id=_FAKE_SUB_ORG)

    def test_missing_sub_org_raises(self):
        with pytest.raises(ValueError, match="sub_org_id"):
            FelixOrderClient(jwt="eyJ.fake.jwt", session_private_key_hex=_FAKE_SESSION_PK, sub_org_id="")

    def test_buy_without_notional_raises(self):
        client = FelixOrderClient(jwt="eyJ.fake.jwt", session_private_key_hex=_FAKE_SESSION_PK, sub_org_id=_FAKE_SUB_ORG)
        with pytest.raises(ValueError, match="notional_usdc"):
            client.get_quote("TSLA", "BUY")

    def test_sell_without_token_amount_raises(self):
        client = FelixOrderClient(jwt="eyJ.fake.jwt", session_private_key_hex=_FAKE_SESSION_PK, sub_org_id=_FAKE_SUB_ORG)
        with pytest.raises(ValueError, match="token_amount"):
            client.get_quote("TSLA", "SELL")

    def test_invalid_side_raises(self):
        client = FelixOrderClient(jwt="eyJ.fake.jwt", session_private_key_hex=_FAKE_SESSION_PK, sub_org_id=_FAKE_SUB_ORG)
        with pytest.raises(ValueError, match="Invalid side"):
            client.get_quote("TSLA", "LONG", notional_usdc=50.0)
