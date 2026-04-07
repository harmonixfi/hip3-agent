"""Depeg equity provider — reads pm_account_snapshots for the depeg wallet."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DepegProvider(EquityProvider):
    """Reads depeg wallet equity from pm_account_snapshots (same source as DN)."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}

        for wallet in wallets:
            address = wallet.get("address")
            venue = wallet.get("venue", "hyperliquid")
            label = wallet.get("label") or wallet.get("wallet_label", "depeg")

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

            if row:
                equity = float(row[0]) if row[0] is not None else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
