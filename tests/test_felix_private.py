#!/usr/bin/env python3
"""Tests for Felix private connector — portfolio, orders, fills."""

from __future__ import annotations

import json
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import tracking.connectors.felix_private as felix_private_mod
from tracking.connectors.felix_private import (
    FelixPrivateConnector,
    _parse_portfolio_response,
    _parse_fills_response,
    _stablecoin_balance_usd,
    _normalize_felix_inst_id,
    felix_operator_hint_for_http_error,
    felix_operator_hint_for_error_message,
    recompute_felix_account_total_usd,
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


def test_parse_portfolio_production_shaped_without_account_value():
    """Roll up cash + notionals when ``accountValue`` is absent (spec §10)."""
    raw = {
        "stablecoinBalance": "1000.0",
        "positions": [
            {
                "symbol": "MSTRon",
                "qty": "2",
                "costBasisUsd": "500.0",
                "markPrice": "260.0",
                "unrealized_pnl": "20.0",
                "side": "LONG",
            },
        ],
    }
    result = _parse_portfolio_response(raw, "0xabc")
    # stable 1000 + 2 * 260 = 1520
    assert result["total_balance"] == 1520.0
    p0 = result["positions"][0]
    assert p0["inst_id"] == "MSTRon/USDC"
    assert p0["size"] == 2.0
    assert p0["entry_price"] == 250.0  # 500 / 2
    assert p0["current_price"] == 260.0


def test_parse_portfolio_felix_proxy_nested_stablecoin_no_live_mark():
    """Felix often omits currentPrice — parser must not use avg cost as a live mark."""
    raw = {
        "stablecoinBalance": {"amount": "11.177706", "usdValue": "11.177706"},
        "positions": [
            {
                "symbol": "MSTRon",
                "quantity": "39.082",
                "weightedAvgCostUsd": "127.60",
                "costBasisUsd": "4986.70",
            },
        ],
    }
    result = _parse_portfolio_response(raw, "0xb89e")
    assert _stablecoin_balance_usd(raw) == 11.177706
    assert result["positions"][0]["current_price"] is None
    # Fallback: stable + sum(costBasisUsd)
    assert abs(result["total_balance"] - (11.177706 + 4986.70)) < 0.01


def test_recompute_felix_account_total_uses_position_marks():
    """Account total uses leg marks, then cost basis when no MTM."""
    raw = {"stablecoinBalance": {"usdValue": "10"}}
    positions = [
        {"size": 2.0, "current_price": 400.0, "raw_json": {}},
        {"size": 1.0, "current_price": None, "raw_json": {"costBasisUsd": "100"}},
    ]
    t = recompute_felix_account_total_usd(raw, positions)
    assert abs(t - (10 + 2 * 400 + 100)) < 1e-6


def test_recompute_felix_prefers_hl_mtm_over_cost_when_configured():
    """HIP-3 mids (passed in) value the account total when Felix omits ``current_price``."""
    raw = {"stablecoinBalance": {"usdValue": "10"}}
    positions = [
        {
            "inst_id": "MUon/USDC",
            "size": 2.0,
            "current_price": None,
            "raw_json": {"costBasisUsd": "500"},
        },
    ]
    t = recompute_felix_account_total_usd(
        raw,
        positions,
        hl_marks_by_felix_inst_id={"MUon/USDC": 400.0},
    )
    assert abs(t - (10 + 2 * 400)) < 1e-6


def test_parse_portfolio_market_price_alias():
    """Common alias ``marketPrice`` populates ``current_price``."""
    raw = {
        "positions": [
            {"symbol": "MSTRon", "quantity": "2", "marketPrice": "131.25"},
        ],
    }
    result = _parse_portfolio_response(raw, "0xabc")
    assert result["positions"][0]["current_price"] == 131.25


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


def test_felix_connector_api_path_uses_api_account_ledger_for_account_id():
    """When api_account_address is set, /v1/portfolio/{api} is called; account_id stays ledger."""
    with patch.object(felix_private_mod, "_felix_get") as mock_get:
        mock_get.return_value = {
            "accountValue": "100.0",
            "availableBalance": "50",
            "positions": [],
        }
        c = FelixPrivateConnector(
            jwt="t",
            wallet_address="0xAAA",
            api_account_address="0xBBB",
        )
        snap = c.fetch_account_snapshot()
        path = mock_get.call_args[0][0]
        assert path == "/v1/portfolio/0xbbb"
        assert snap["account_id"] == "0xaaa"


def test_felix_operator_hint_helpers():
    err403 = urllib.error.HTTPError("https://x", 403, "Forbidden", hdrs=None, fp=None)
    assert "refresh" in felix_operator_hint_for_http_error(err403).lower()
    err401 = urllib.error.HTTPError("https://x", 401, "Unauthorized", hdrs=None, fp=None)
    assert "jwt" in felix_operator_hint_for_http_error(err401).lower()
    agg = "API call failed: HTTP Error 403: Forbidden"
    assert felix_operator_hint_for_error_message(agg)
    agg2 = "Cannot access another account's portfolio"
    assert "hyperliquid" in felix_operator_hint_for_error_message(agg2).lower()


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
