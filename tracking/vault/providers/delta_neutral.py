"""Delta Neutral equity provider — reads pm_account_snapshots for strategy wallets."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots.

    Only includes wallets defined in strategies.json under delta_neutral.wallets.
    Felix and other external wallets are excluded — they belong to other strategies.
    """

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}
        counted_lower: set[str] = set()

        for wallet in wallets:
            # Prefer address directly from strategy config; fall back to resolver lookup
            address = wallet.get("address")
            venue = wallet.get("venue", "hyperliquid")
            label = wallet.get("label") or wallet.get("wallet_label", "main")

            if not address:
                accounts = resolve_venue_accounts(venue)
                address = accounts.get(label)

            if not address:
                continue

            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (address, venue),
            ).fetchone()

            vnorm = (venue or "").strip().lower()

            equity = 0.0
            if row and row[0] is not None:
                equity = float(row[0])

            # Felix: snapshot may be missing before puller runs — use open-leg notional (same as env fallback)
            if vnorm == "felix" and equity <= 1e-9:
                leg_usd = _felix_open_leg_notional_usd(db)
                if leg_usd > 1e-9:
                    equity = leg_usd

            # Non-Felix: only count wallets that have at least one snapshot (legacy behavior).
            # Felix: always show in breakdown when declared in strategies.json so DN total includes Felix.
            if vnorm == "felix" or row:
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}
                counted_lower.add(str(address).lower())

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
