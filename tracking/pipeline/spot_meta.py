"""Spot symbol resolution via Hyperliquid spotMeta API.

Hyperliquid spot fills use @{index} format (e.g., @107) instead of human-readable
symbols. This module fetches the spotMeta endpoint to build an index-to-symbol map
and provides a resolver for fill coin fields.

Usage:
    cache = fetch_spot_index_map()
    inst_id = resolve_coin("@107", cache)  # -> "HYPE/USDC"
    inst_id = resolve_coin("xyz:GOLD", cache)  # -> "xyz:GOLD" (passthrough)
"""

from __future__ import annotations

from typing import Any, Dict


def build_spot_index_map(spot_meta: Dict[str, Any]) -> Dict[int, str]:
    """Build {universe_index: 'SYMBOL/QUOTE'} map from spotMeta response.

    The spotMeta response has two arrays:
    - tokens: [{name, index, ...}] — all tokens (USDC, PURR, HYPE, ...)
    - universe: [{name, tokens: [base_idx, quote_idx], index}] — spot pairs

    For canonical pairs, universe[].name is "PURR/USDC".
    For non-canonical pairs, universe[].name is "@N" — we resolve from tokens.
    """
    tokens = spot_meta.get("tokens", [])
    universe = spot_meta.get("universe", [])

    # Build token index -> name lookup
    token_names: Dict[int, str] = {}
    for tok in tokens:
        idx = tok.get("index")
        name = tok.get("name", "")
        if idx is not None:
            token_names[int(idx)] = name

    # Build universe index -> pair name
    result: Dict[int, str] = {}
    for pair in universe:
        uni_index = pair.get("index")
        if uni_index is None:
            continue
        uni_index = int(uni_index)

        pair_name = str(pair.get("name", ""))
        if "/" in pair_name and not pair_name.startswith("@"):
            # Canonical: "PURR/USDC" — use as-is
            result[uni_index] = pair_name
        else:
            # Non-canonical: "@1" — resolve from tokens array
            pair_tokens = pair.get("tokens", [])
            if len(pair_tokens) >= 2:
                base_name = token_names.get(int(pair_tokens[0]), "???")
                quote_name = token_names.get(int(pair_tokens[1]), "USDC")
                result[uni_index] = f"{base_name}/{quote_name}"

    return result


def resolve_coin(coin: str, spot_index_map: Dict[int, str]) -> str:
    """Resolve a fill's coin field to a canonical inst_id.

    Rules:
    - '@107' -> lookup in spot_index_map -> 'HYPE/USDC'
    - 'xyz:GOLD' -> passthrough (builder dex perp)
    - 'HYPE' -> passthrough (native perp)

    Raises ValueError for unknown @index.
    """
    coin = str(coin or "").strip()
    if not coin:
        raise ValueError("Empty coin field")

    if coin.startswith("@"):
        index = int(coin[1:])
        resolved = spot_index_map.get(index)
        if resolved is None:
            raise ValueError(f"Unknown spot index: {coin} (index={index})")
        return resolved

    # Builder dex (xyz:GOLD) or native perp (HYPE) — passthrough
    return coin


def fetch_spot_index_map() -> Dict[int, str]:
    """Fetch spotMeta from Hyperliquid API and build the index map.

    Makes one POST to https://api.hyperliquid.xyz/info with {"type": "spotMeta"}.
    """
    from tracking.connectors.hyperliquid_private import post_info

    raw = post_info({"type": "spotMeta"}, dex="")
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected spotMeta response type: {type(raw)}")
    return build_spot_index_map(raw)
