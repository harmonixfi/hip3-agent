"""Multi-wallet account resolution.

Single source of truth: config/strategies.json.

Priority:
1. config/strategies.json → union of all strategies' wallets[] filtered by venue
2. Legacy single env var (HYPERLIQUID_ADDRESS etc.) → returns {"main": address}

HYPERLIQUID_ACCOUNTS_JSON is NO LONGER read. Delete it from .arbit_env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set


_LEGACY_ENV = {
    "hyperliquid": ["HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "paradex": ["PARADEX_ACCOUNT_ADDRESS"],
    "ethereal": ["ETHEREAL_ACCOUNT_ADDRESS", "ETHEREAL_SENDER"],
    "hyena": ["HYENA_ADDRESS"],
    "lighter": ["LIGHTER_L1_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "okx": ["OKX_API_KEY"],
}

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_STRATEGIES_PATH = _REPO_ROOT / "config" / "strategies.json"

# mtime-based cache: {"mtime": float, "strategies": list[dict]}
_CACHE: Dict[str, object] = {}


def _load_strategies_cached() -> List[dict]:
    """Load strategies.json with mtime-based cache invalidation.

    Returns list of strategy dicts (empty list if file missing/invalid).
    Validates that labels are globally unique across all wallets.

    Raises:
        ValueError: if duplicate labels found across strategies.
    """
    path = _STRATEGIES_PATH
    if not path.exists():
        return []

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []

    cached_mtime = _CACHE.get("mtime")
    if cached_mtime == mtime and "strategies" in _CACHE:
        return _CACHE["strategies"]  # type: ignore[return-value]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    strategies = data.get("strategies", []) if isinstance(data, dict) else []
    if not isinstance(strategies, list):
        strategies = []

    # Validate global label uniqueness
    seen_labels: Dict[str, str] = {}  # label -> strategy_id
    for s in strategies:
        if not isinstance(s, dict):
            continue
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            label = w.get("label")
            if not label:
                continue
            sid = s.get("strategy_id", "")
            if label in seen_labels and seen_labels[label] != sid:
                raise ValueError(
                    f"duplicate label '{label}' across strategies "
                    f"'{seen_labels[label]}' and '{sid}' — labels must be globally unique"
                )
            seen_labels[label] = sid

    _CACHE["mtime"] = mtime
    _CACHE["strategies"] = strategies
    return strategies


def resolve_venue_accounts(venue: str) -> Dict[str, str]:
    """Resolve wallet labels → addresses for a venue.

    Priority:
    1. config/strategies.json → union of all strategies' wallets for this venue
    2. Legacy single env var (HYPERLIQUID_ADDRESS etc.) → {"main": address}

    Returns:
        Dict mapping wallet_label -> address/credential.
        Empty dict if nothing configured.
    """
    strategies = _load_strategies_cached()

    result: Dict[str, str] = {}
    for s in strategies:
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            if (w.get("venue") or "").strip().lower() != venue.strip().lower():
                continue
            label = w.get("label")
            address = w.get("address")
            if label and address:
                result[str(label)] = str(address)

    if result:
        return result

    # Fallback: legacy single env var
    for env_key in _LEGACY_ENV.get(venue, []):
        val = os.environ.get(env_key, "").strip()
        if val:
            return {"main": val}

    return {}


def get_strategy_wallets(strategy_id: str) -> List[Dict[str, str]]:
    """Return list of wallets for a specific strategy.

    Returns list of dicts with keys: label, venue, address.
    Returns empty list if strategy has no wallets (e.g. lending reads from external NAV DB).

    Raises:
        KeyError: if strategy_id not found in strategies.json.
    """
    strategies = _load_strategies_cached()
    for s in strategies:
        if s.get("strategy_id") == strategy_id:
            wallets = s.get("wallets", []) or []
            return [
                {
                    "label": str(w.get("label")),
                    "venue": str(w.get("venue", "")),
                    "address": str(w.get("address")),
                }
                for w in wallets
                if isinstance(w, dict) and w.get("label") and w.get("address")
            ]
    raise KeyError(f"strategy not found: {strategy_id}")


def get_felix_wallet_address_from_env() -> Optional[str]:
    """Return normalized lower-case Felix wallet from ``FELIX_WALLET_ADDRESS``, or None."""
    raw = (os.environ.get("FELIX_WALLET_ADDRESS") or "").strip()
    return raw.lower() if raw else None


def get_delta_neutral_equity_account_ids() -> List[str]:
    """Account ids used for delta-neutral equity (``pm_account_snapshots`` / DN totals).

    Returns every non-empty ``address`` from ``get_strategy_wallets("delta_neutral")``.
    De-duplicates by lower-case so the same address is not double-counted.
    """
    try:
        dn = get_strategy_wallets("delta_neutral")
    except KeyError:
        dn = []

    seen_lower: Set[str] = set()
    out: List[str] = []

    for w in dn:
        a = (w.get("address") or "").strip()
        if not a:
            continue
        key = a.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        out.append(a)

    return out
