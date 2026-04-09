"""Delta Neutral equity provider — reads pm_account_snapshots for strategy wallets."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import get_felix_wallet_address_from_env, resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


def _felix_open_leg_notional_usd(db: sqlite3.Connection) -> float:
    """Sum qty × mark (fallback entry) for OPEN Felix legs — used when account snapshot total is 0."""
    row = db.execute(
        """
        SELECT COALESCE(SUM(
            ABS(l.size) * COALESCE(
                NULLIF(l.current_price, 0),
                ep.avg_entry_price,
                NULLIF(l.entry_price, 0),
                0
            )
        ), 0.0)
        FROM pm_legs l
        INNER JOIN pm_positions p ON p.position_id = l.position_id
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        WHERE l.venue = 'felix'
          AND p.status IN ('OPEN', 'PAUSED', 'EXITING')
        """,
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots."""

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

        felix_addr = get_felix_wallet_address_from_env()
        felix_lower = felix_addr.lower() if felix_addr else ""
        if felix_addr and felix_lower not in counted_lower:
            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = 'felix'
                ORDER BY ts DESC LIMIT 1
                """,
                (felix_addr,),
            ).fetchone()
            equity = float(row[0]) if row and row[0] is not None else 0.0
            if equity <= 1e-9:
                leg_usd = _felix_open_leg_notional_usd(db)
                if leg_usd > 1e-9:
                    equity = leg_usd
            total_equity += equity
            breakdown["felix"] = {
                "address": felix_addr,
                "equity_usd": equity,
                "venue": "felix",
            }

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
