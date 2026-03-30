"""Unit tests for Hyperliquid fee row attribution (dex guard + spot index resolution)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.hl_cashflow_attribution import (  # noqa: E402
    hl_fee_target_from_fill_coin,
    hl_resolve_fee_fill_target,
)


def test_fee_fill_target_spot_index_maps_to_spot_leg():
    targets = {"HYPE/USDC": {"leg_id": "spot_a", "inst_id": "HYPE/USDC"}}
    m = {107: "HYPE/USDC"}
    t = hl_fee_target_from_fill_coin("@107", targets, m)
    assert t is not None
    assert t["leg_id"] == "spot_a"


def test_fee_fill_target_builder_perp():
    targets = {"GOLD": {"leg_id": "perp_b", "inst_id": "xyz:GOLD"}}
    m = {}
    t = hl_fee_target_from_fill_coin("xyz:GOLD", targets, m)
    assert t is not None
    assert t["leg_id"] == "perp_b"


def test_resolve_fee_fill_target_skips_dex_mismatch():
    targets = {"HYPE": {"leg_id": "perp"}}
    m = {}
    assert hl_resolve_fee_fill_target("hyna:HYPE", "", targets, m) is None
