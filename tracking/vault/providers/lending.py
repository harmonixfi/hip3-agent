"""Lending equity provider — reads harmonix-nav-platform PostgreSQL.

Equity = sum of latest per-vault `amount_underlying` for one account on ERC4626 hourly
snapshots (`raw.vault_erc4626_account_snapshot_hourly`), not the gold NAV view.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import List, Tuple

from .base import EquityProvider, StrategyEquity

log = logging.getLogger(__name__)

# Defaults match Harmonix raw snapshot filters (override via env or strategy config_json).
_DEFAULT_CHAIN_ID = 999
_DEFAULT_ERC4626_ACCOUNT = "0x0bdfcfbd77c0f3170ac5231480bbb1e45eeba9ae"
_DEFAULT_ERC4626_VAULTS = (
    "0x808F72b6Ff632fba005C88b49C2a76AB01CAB545",
    "0x274f854b2042DB1aA4d6C6E45af73588BEd4Fc9D",
)


class LendingProvider(EquityProvider):
    """Reads lending equity from harmonix-nav raw ERC4626 hourly snapshots."""

    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        del db  # lending uses external DB
        db_url = os.environ.get("HARMONIX_NAV_DB_URL", "").strip()
        if not db_url:
            log.warning("HARMONIX_NAV_DB_URL not set, returning zero equity for lending")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "HARMONIX_NAV_DB_URL not configured"},
            )

        try:
            import psycopg2  # type: ignore[import-untyped]

            con = psycopg2.connect(db_url)
            try:
                return self._query_lending_equity(con, strategy)
            finally:
                con.close()
        except ImportError:
            log.error("psycopg2 not installed. Run: pip install psycopg2-binary")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "psycopg2 not installed"},
            )
        except Exception as e:
            log.error("Failed to query harmonix-nav-platform: %s", e)
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": str(e)},
            )

    def _erc4626_params(self, strategy: dict) -> Tuple[int, str, List[str]]:
        chain = _DEFAULT_CHAIN_ID
        account = _DEFAULT_ERC4626_ACCOUNT
        vaults = list(_DEFAULT_ERC4626_VAULTS)

        env_chain = os.environ.get("HARMONIX_LENDING_CHAIN_ID", "").strip()
        if env_chain.isdigit():
            chain = int(env_chain)
        env_acct = os.environ.get("HARMONIX_LENDING_ERC4626_ACCOUNT", "").strip()
        if env_acct:
            account = env_acct
        env_vaults = os.environ.get("HARMONIX_LENDING_ERC4626_VAULTS", "").strip()
        if env_vaults:
            vaults = [v.strip() for v in env_vaults.split(",") if v.strip()]

        raw = strategy.get("config_json")
        if isinstance(raw, str) and raw.strip():
            try:
                cfg = json.loads(raw)
                if isinstance(cfg.get("erc4626_chain_id"), int):
                    chain = cfg["erc4626_chain_id"]
                elif isinstance(cfg.get("erc4626_chain_id"), str) and cfg["erc4626_chain_id"].strip().isdigit():
                    chain = int(cfg["erc4626_chain_id"].strip())
                ac = cfg.get("erc4626_account")
                if isinstance(ac, str) and ac.strip():
                    account = ac.strip()
                vlist = cfg.get("erc4626_vault_addresses") or cfg.get("erc4626_vaults")
                if isinstance(vlist, list) and vlist:
                    vaults = [str(x).strip() for x in vlist if str(x).strip()]
            except json.JSONDecodeError:
                pass

        return chain, account, vaults

    def _query_lending_equity(self, pg_con, strategy: dict) -> StrategyEquity:
        """Sum latest per-vault underlying amounts for one account (ERC4626 hourly raw)."""
        chain_id, account_address, vault_addresses = self._erc4626_params(strategy)
        if not vault_addresses:
            log.warning("Lending ERC4626: no vault addresses configured")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "no_erc4626_vaults"},
            )

        placeholders = ",".join(["%s"] * len(vault_addresses))
        sql = f"""
            WITH latest_per_vault AS (
                SELECT DISTINCT ON (lower(a.vault_address))
                    a.snapshot_ts,
                    lower(a.vault_address) AS vault_address,
                    (a.assets_est_raw_uint::numeric
                     / power(10, COALESCE(v.price_decimals, 18))) AS amount_underlying
                FROM raw.vault_erc4626_account_snapshot_hourly a
                LEFT JOIN raw.vault_erc4626_snapshot_hourly v
                    ON lower(a.vault_address) = lower(v.vault_address)
                    AND a.snapshot_ts = v.snapshot_ts
                WHERE a.chain_id = %s
                  AND lower(a.account_address) = lower(%s)
                  AND lower(a.vault_address) IN ({placeholders})
                ORDER BY lower(a.vault_address), a.snapshot_ts DESC
            )
            SELECT
                COALESCE(SUM(amount_underlying), 0),
                MAX(snapshot_ts),
                COALESCE(
                    jsonb_object_agg(vault_address, to_jsonb(amount_underlying))
                    FILTER (WHERE vault_address IS NOT NULL),
                    '{{}}'::jsonb
                )
            FROM latest_per_vault
        """
        cursor = pg_con.cursor()
        params = (chain_id, account_address, *[v.lower() for v in vault_addresses])
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "no_rows"},
            )

        total, latest_ts, per_vault_json = row[0], row[1], row[2]
        primary_val = float(total) if total is not None else 0.0

        ts_ms = int(time.time() * 1000)
        if latest_ts is not None:
            ts_ms = int(latest_ts.timestamp() * 1000)

        per_vault: dict = {}
        if per_vault_json:
            per_vault = {k: float(v) for k, v in per_vault_json.items()}

        return StrategyEquity(
            equity_usd=primary_val,
            breakdown=per_vault,
            timestamp_ms=ts_ms,
            meta={
                "source": "raw.vault_erc4626_account_snapshot_hourly",
                "chain_id": chain_id,
                "account_address": account_address,
                "vault_addresses": vault_addresses,
                "units": "underlying",
            },
        )
