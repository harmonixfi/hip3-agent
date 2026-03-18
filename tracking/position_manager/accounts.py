"""Multi-wallet account resolution.

Resolves venue accounts from environment variables.
Supports {VENUE}_ACCOUNTS_JSON (multi-wallet) with legacy single-var fallback.
"""

from __future__ import annotations

import json
import os
from typing import Dict


_LEGACY_ENV = {
    "hyperliquid": ["HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "paradex": ["PARADEX_ACCOUNT_ADDRESS"],
    "ethereal": ["ETHEREAL_ACCOUNT_ADDRESS", "ETHEREAL_SENDER"],
    "hyena": ["HYENA_ADDRESS"],
    "lighter": ["LIGHTER_L1_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "okx": ["OKX_API_KEY"],
}


def resolve_venue_accounts(venue: str) -> Dict[str, str]:
    """Resolve wallet accounts for a venue.

    Priority:
    1. {VENUE}_ACCOUNTS_JSON env var (JSON object: label -> address)
    2. Legacy single env var with label "main"

    Returns:
        Dict mapping wallet_label -> address/credential.
        Empty dict if no config found.
    """
    venue_upper = venue.upper()
    json_var = f"{venue_upper}_ACCOUNTS_JSON"
    raw = os.environ.get(json_var, "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
            if isinstance(accounts, dict) and accounts:
                return {str(k): str(v) for k, v in accounts.items()}
        except (json.JSONDecodeError, TypeError):
            pass

    for env_key in _LEGACY_ENV.get(venue, []):
        val = os.environ.get(env_key, "").strip()
        if val:
            return {"main": val}

    return {}
