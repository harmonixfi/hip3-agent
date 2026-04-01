"""Delta Neutral equity provider — reads pm_account_snapshots for strategy wallets."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}

        for wallet in wallets:
            label = wallet.get("wallet_label", "main")
            venue = wallet.get("venue", "hyperliquid")
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

            if row:
                equity = float(row[0]) if row[0] is not None else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
