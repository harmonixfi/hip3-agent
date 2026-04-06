#!/usr/bin/env python3
"""Tests for spot symbol resolution via spotMeta."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.spot_meta import (
    build_spot_index_map,
    resolve_coin,
)


def test_build_spot_index_map():
    """spotMeta response is parsed into {index: 'SYMBOL/QUOTE'} map."""
    raw_response = {
        "tokens": [
            {"name": "USDC", "index": 0},
            {"name": "PURR", "index": 1},
            {"name": "HFUN", "index": 2},
            {"name": "HYPE", "index": 150},
        ],
        "universe": [
            {"name": "PURR/USDC", "tokens": [1, 0], "index": 0},
            {"name": "@1", "tokens": [2, 0], "index": 1},
            {"name": "HYPE/USDC", "tokens": [150, 0], "index": 107},
        ],
    }
    result = build_spot_index_map(raw_response)

    # Canonical pairs keep their name
    assert result[0] == "PURR/USDC"
    # Non-canonical pairs (@N) are resolved from tokens
    assert result[1] == "HFUN/USDC"
    # HYPE/USDC at universe index 107
    assert result[107] == "HYPE/USDC"


def test_resolve_coin_spot_index():
    """@107 resolves to HYPE/USDC."""
    cache = {107: "HYPE/USDC", 0: "PURR/USDC"}
    assert resolve_coin("@107", cache) == "HYPE/USDC"
    assert resolve_coin("@0", cache) == "PURR/USDC"


def test_resolve_coin_builder_dex_passthrough():
    """Builder dex coins pass through unchanged."""
    cache = {}
    assert resolve_coin("xyz:GOLD", cache) == "xyz:GOLD"
    assert resolve_coin("hyna:HYPE", cache) == "hyna:HYPE"


def test_resolve_coin_native_perp_passthrough():
    """Native perp coins pass through unchanged."""
    cache = {}
    assert resolve_coin("HYPE", cache) == "HYPE"
    assert resolve_coin("BTC", cache) == "BTC"


def test_resolve_coin_unknown_index_raises():
    """Unknown @index raises ValueError."""
    cache = {107: "HYPE/USDC"}
    try:
        resolve_coin("@999", cache)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "999" in str(e)


def main() -> int:
    test_build_spot_index_map()
    print("PASS: test_build_spot_index_map")
    test_resolve_coin_spot_index()
    print("PASS: test_resolve_coin_spot_index")
    test_resolve_coin_builder_dex_passthrough()
    print("PASS: test_resolve_coin_builder_dex_passthrough")
    test_resolve_coin_native_perp_passthrough()
    print("PASS: test_resolve_coin_native_perp_passthrough")
    test_resolve_coin_unknown_index_raises()
    print("PASS: test_resolve_coin_unknown_index_raises")
    print("\nAll spot_meta tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
