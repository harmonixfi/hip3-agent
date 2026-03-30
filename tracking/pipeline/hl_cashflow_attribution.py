"""Shared Hyperliquid cashflow attribution for dex-scoped API rows.

Used by ``scripts/pm_cashflows.py`` and ``scripts/hl_reset_backfill.py`` so funding/fees
share the same dex-vs-coin namespace rules and fee fills use the same coin resolution as
``fill_ingester`` (including @{index} spot symbols).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from tracking.connectors.hyperliquid_private import strip_coin_namespace
from tracking.pipeline.spot_meta import resolve_coin


def hl_norm_dex(d: str) -> str:
    return str(d or "").strip().lower()


def hl_row_dex_from_coin(raw_coin: str) -> str:
    """Dex namespace in HL coin strings: 'hyna:LINK' -> 'hyna', 'LINK' / '@107' -> '' (native)."""
    raw = str(raw_coin or "").strip()
    if ":" in raw:
        return raw.split(":", 1)[0].strip().lower()
    return ""


def hl_fee_target_from_fill_coin(
    raw_coin: str,
    coin_targets: Dict[str, Any],
    spot_index_map: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    """Resolve ``raw_coin`` to a target using the same rules as fill ingester (after dex guard passes).

    ``coin_targets`` is the inner map for one (account, dex) slot: perp base coin or spot ``inst_id``.
    """
    try:
        resolved = resolve_coin(raw_coin, spot_index_map)
    except (ValueError, TypeError, KeyError):
        return None
    if "/" in resolved:
        return coin_targets.get(resolved)
    coin = strip_coin_namespace(resolved)
    if not coin:
        return None
    return coin_targets.get(coin)


def hl_resolve_fee_fill_target(
    raw_coin: str,
    request_dex: str,
    coin_targets: Dict[str, Any],
    spot_index_map: Dict[int, str],
) -> Optional[Dict[str, Any]]:
    """Map a userFillsByTime row to a fee target, or None (dex mismatch, unknown @index, or no leg)."""
    if hl_norm_dex(request_dex) != hl_row_dex_from_coin(raw_coin):
        return None
    return hl_fee_target_from_fill_coin(raw_coin, coin_targets, spot_index_map)
