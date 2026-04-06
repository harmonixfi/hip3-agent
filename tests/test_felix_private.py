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
