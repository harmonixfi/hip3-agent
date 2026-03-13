#!/usr/bin/env python3
"""Regression checks for Loris exchange normalization and OI-rank filtering."""

from __future__ import annotations

from pull_loris_backfill_history import normalize_target_exchanges as normalize_backfill_targets
from pull_loris_backfill_history import oi_rank_to_int
from pull_loris_funding import normalize_target_exchanges as normalize_live_targets


def main() -> int:
    raw = ["hyperliquid", "xyz", "felix", "kinetiq", "hyena", "tradexyz_perp", "HL"]
    expected = {"hyperliquid", "tradexyz", "felix", "kinetiq", "hyena"}

    assert normalize_live_targets(raw) == expected
    assert normalize_backfill_targets(raw) == expected

    assert oi_rank_to_int(None) == 9999
    assert oi_rank_to_int("") == 9999
    assert oi_rank_to_int("150+") == 150
    assert oi_rank_to_int("201") == 201

    oi_rank_max = 200
    keep_missing = oi_rank_to_int(None)
    assert keep_missing == 9999
    assert keep_missing == 9999 or keep_missing <= oi_rank_max
    assert oi_rank_to_int("180") <= oi_rank_max
    assert not (oi_rank_to_int("250") == 9999 or oi_rank_to_int("250") <= oi_rank_max)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
