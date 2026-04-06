"""Lending equity provider — reads harmonix-nav-platform PostgreSQL.

Equity = ERC4626 latest per-(account,vault) underlying summed across a shared address list
+ HyperLend + HypurrFi USDC a_token supply (same addresses; fixed 6 decimals).
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base import EquityProvider, StrategyEquity

log = logging.getLogger(__name__)

# Defaults match Harmonix raw snapshot filters (override via env or strategy config_json).
_DEFAULT_CHAIN_ID = 999
_DEFAULT_ERC4626_ACCOUNT = "0x0bdfcfbd77c0f3170ac5231480bbb1e45eeba9ae"
_DEFAULT_ERC4626_VAULTS = (
    "0x808F72b6Ff632fba005C88b49C2a76AB01CAB545",
    "0x274f854b2042DB1aA4d6C6E45af73588BEd4Fc9D",
)
# HyperEVM USDC (Harmonix lending spec default)
_DEFAULT_USDC_ADDRESS = "0xb88339CB7199b77E23DB6E890353E22632Ba630f"
_AAVE_PROTOCOL_CODES = ("HYPERLEND", "HYPURRFI")
_USDC_DECIMALS = 6


class LendingProvider(EquityProvider):
    """Reads lending equity from harmonix-nav raw ERC4626 + Aave-style hourly snapshots."""

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

    def _chain_and_vaults(self, strategy: dict) -> Tuple[int, List[str]]:
        chain = _DEFAULT_CHAIN_ID
        vaults = list(_DEFAULT_ERC4626_VAULTS)

        env_chain = os.environ.get("HARMONIX_LENDING_CHAIN_ID", "").strip()
        if env_chain.isdigit():
            chain = int(env_chain)
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
                vlist = cfg.get("erc4626_vault_addresses") or cfg.get("erc4626_vaults")
                if isinstance(vlist, list) and vlist:
                    vaults = [str(x).strip() for x in vlist if str(x).strip()]
            except json.JSONDecodeError:
                pass

        return chain, vaults

    def _lending_account_addresses(self, strategy: dict) -> List[str]:
        """Single ordered list for ERC4626 + Aave legs (length >= 1)."""
        raw = strategy.get("config_json")
        if isinstance(raw, str) and raw.strip():
            try:
                cfg = json.loads(raw)
                la = cfg.get("lending_accounts")
                if isinstance(la, list) and la:
                    out = [str(x).strip() for x in la if str(x).strip()]
                    if out:
                        return out
            except json.JSONDecodeError:
                pass

        env_accounts = os.environ.get("HARMONIX_LENDING_ACCOUNT_ADDRESSES", "").strip()
        if env_accounts:
            return [x.strip() for x in env_accounts.split(",") if x.strip()]

        if isinstance(raw, str) and raw.strip():
            try:
                cfg = json.loads(raw)
                ac = cfg.get("erc4626_account")
                if isinstance(ac, str) and ac.strip():
                    return [x.strip() for x in ac.split(",") if x.strip()]
            except json.JSONDecodeError:
                pass

        return [_DEFAULT_ERC4626_ACCOUNT]

    def _usdc_address(self, strategy: dict) -> str:
        env_u = os.environ.get("HARMONIX_LENDING_USDC_ADDRESS", "").strip()
        if env_u:
            return env_u
        raw = strategy.get("config_json")
        if isinstance(raw, str) and raw.strip():
            try:
                cfg = json.loads(raw)
                u = cfg.get("lending_usdc_address") or cfg.get("harmonix_lending_usdc_address")
                if isinstance(u, str) and u.strip():
                    return u.strip()
            except json.JSONDecodeError:
                pass
        return _DEFAULT_USDC_ADDRESS

    def _query_erc4626_equity(
        self,
        pg_con: Any,
        chain_id: int,
        account_addresses: Sequence[str],
        vault_addresses: List[str],
    ) -> Tuple[float, Dict[str, float], Optional[datetime]]:
        """Latest per (account, vault); sum per vault across accounts; empty vault list → zeros."""
        if not vault_addresses:
            return 0.0, {}, None

        acct_lower = [a.lower() for a in account_addresses]
        placeholders = ",".join(["%s"] * len(vault_addresses))
        sql = f"""
            WITH latest_per AS (
                SELECT DISTINCT ON (lower(a.account_address), lower(a.vault_address))
                    a.snapshot_ts,
                    lower(a.vault_address) AS vault_address,
                    (a.assets_est_raw_uint::numeric
                     / power(10, COALESCE(v.price_decimals, 18))) AS amount_underlying
                FROM raw.vault_erc4626_account_snapshot_hourly a
                LEFT JOIN raw.vault_erc4626_snapshot_hourly v
                    ON lower(a.vault_address) = lower(v.vault_address)
                    AND a.snapshot_ts = v.snapshot_ts
                WHERE a.chain_id = %s
                  AND lower(a.account_address) = ANY(%s)
                  AND lower(a.vault_address) IN ({placeholders})
                ORDER BY lower(a.account_address), lower(a.vault_address), a.snapshot_ts DESC
            ),
            by_vault AS (
                SELECT vault_address,
                       SUM(amount_underlying) AS amount_underlying,
                       MAX(snapshot_ts) AS max_ts
                FROM latest_per
                GROUP BY vault_address
            )
            SELECT
                COALESCE(SUM(amount_underlying), 0),
                MAX(max_ts),
                COALESCE(
                    jsonb_object_agg(vault_address, to_jsonb(amount_underlying))
                    FILTER (WHERE vault_address IS NOT NULL),
                    '{{}}'::jsonb
                )
            FROM by_vault
        """
        cursor = pg_con.cursor()
        params: Tuple[Any, ...] = (chain_id, acct_lower, *[v.lower() for v in vault_addresses])
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return 0.0, {}, None

        total, latest_ts, per_vault_json = row[0], row[1], row[2]
        primary_val = float(total) if total is not None else 0.0

        per_vault: Dict[str, float] = {}
        if per_vault_json:
            per_vault = {k: float(v) for k, v in per_vault_json.items()}

        return primary_val, per_vault, latest_ts

    def _query_aave_usdc_by_protocol(
        self,
        pg_con: Any,
        chain_id: int,
        account_addresses: Sequence[str],
        usdc_address: str,
    ) -> Tuple[Dict[str, float], Optional[datetime]]:
        """Latest per (account, protocol); sum per protocol across accounts."""
        acct_lower = [a.lower() for a in account_addresses]
        sql = """
            WITH latest_per AS (
                SELECT DISTINCT ON (lower(ur.account_address), p.protocol_code)
                    p.protocol_code,
                    ur.snapshot_ts,
                    (COALESCE(ur.a_token_balance_raw_uint, 0)::numeric
                     / power(10::numeric, %s)) AS amount_usdc
                FROM raw.aave_user_reserve_snapshot_hourly ur
                JOIN raw.aave_reserve r ON r.reserve_id = ur.reserve_id
                JOIN raw.aave_pool p ON p.pool_id = r.pool_id
                WHERE p.chain_id = %s
                  AND p.protocol_code IN ('HYPERLEND', 'HYPURRFI')
                  AND ur.chain_id = %s
                  AND lower(ur.account_address) = ANY(%s)
                  AND lower(r.underlying_token_address) = lower(%s)
                ORDER BY lower(ur.account_address), p.protocol_code, ur.snapshot_ts DESC
            )
            SELECT
                protocol_code,
                COALESCE(SUM(amount_usdc), 0) AS total_usdc,
                MAX(snapshot_ts) AS max_ts
            FROM latest_per
            GROUP BY protocol_code
        """
        cursor = pg_con.cursor()
        cursor.execute(
            sql,
            (_USDC_DECIMALS, chain_id, chain_id, acct_lower, usdc_address),
        )
        rows = cursor.fetchall()
        amounts: Dict[str, float] = {}
        latest_ts: Optional[datetime] = None
        for protocol_code, total_usdc, max_ts in rows:
            if protocol_code:
                amounts[str(protocol_code)] = float(total_usdc) if total_usdc is not None else 0.0
                if max_ts is not None:
                    if latest_ts is None or max_ts > latest_ts:
                        latest_ts = max_ts

        found = set(amounts.keys())
        for code in _AAVE_PROTOCOL_CODES:
            if code not in found:
                log.debug(
                    "Lending Aave: no snapshot row for protocol %s (treating as 0)",
                    code,
                )

        return amounts, latest_ts

    def _query_lending_equity(self, pg_con: Any, strategy: dict) -> StrategyEquity:
        chain_id, vault_addresses = self._chain_and_vaults(strategy)
        account_addresses = self._lending_account_addresses(strategy)
        if not account_addresses:
            log.warning("Lending: no account addresses configured")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "no_lending_accounts"},
            )

        usdc_address = self._usdc_address(strategy)

        erc4626_total, per_vault, erc4626_ts = self._query_erc4626_equity(
            pg_con, chain_id, account_addresses, vault_addresses
        )
        aave_amounts, aave_ts = self._query_aave_usdc_by_protocol(
            pg_con, chain_id, account_addresses, usdc_address
        )

        hl = float(aave_amounts.get("HYPERLEND", 0.0))
        hf = float(aave_amounts.get("HYPURRFI", 0.0))
        aave_sum = hl + hf
        total = erc4626_total + aave_sum

        breakdown: Dict[str, Any] = dict(per_vault)
        breakdown["HYPERLEND"] = hl
        breakdown["HYPURRFI"] = hf

        ts_candidates = [t for t in (erc4626_ts, aave_ts) if t is not None]
        ts_ms = int(time.time() * 1000)
        if ts_candidates:
            latest = max(ts_candidates)
            ts_ms = int(latest.timestamp() * 1000)

        meta: Dict[str, Any] = {
            "sources": ["erc4626", "aave_hyperlend", "aave_hypurrfi"],
            "usdc_decimals": _USDC_DECIMALS,
            "account_addresses": list(account_addresses),
            "underlying_token": usdc_address,
            "protocol_codes": list(_AAVE_PROTOCOL_CODES),
            "chain_id": chain_id,
            "vault_addresses": vault_addresses,
            "mixed_units_note": (
                "equity_usd is a product scalar combining ERC4626 underlying amounts "
                "and USDC-denominated Aave supply; not a single FX-unified USD."
            ),
            "erc4626_source": "raw.vault_erc4626_account_snapshot_hourly",
            "aave_source": "raw.aave_user_reserve_snapshot_hourly",
            "units": "mixed",
        }

        return StrategyEquity(
            equity_usd=total,
            breakdown=breakdown,
            timestamp_ms=ts_ms,
            meta=meta,
        )
