"""Tests for LendingProvider three-source equity (ERC4626 + HyperLend + HypurrFi)."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class _FakeCursor:
    def __init__(self) -> None:
        self._mode: str | None = None

    def execute(self, sql, params=None) -> None:
        s = sql if isinstance(sql, str) else str(sql)
        if "vault_erc4626_account_snapshot_hourly" in s:
            self._mode = "erc4626"
        elif "aave_user_reserve_snapshot_hourly" in s:
            self._mode = "aave"

    def fetchone(self):
        if self._mode == "erc4626":
            return (
                100.0,
                None,
                {"0x808f72b6ff632fba005c88b49c2a76ab01cab545": 100.0},
            )
        return None

    def fetchall(self):
        if self._mode == "aave":
            # GROUP BY protocol_code: (protocol_code, total_usdc, max_ts)
            return [
                ("HYPERLEND", 1.5, None),
                ("HYPURRFI", 2.5, None),
            ]
        return []


class _FakeConn:
    def cursor(self):
        return _FakeCursor()


def test_lending_total_is_erc4626_plus_aave_legs():
    from tracking.vault.providers.lending import LendingProvider

    p = LendingProvider()
    se = p._query_lending_equity(_FakeConn(), {})
    assert se.equity_usd == pytest.approx(104.0)
    assert se.breakdown["HYPERLEND"] == pytest.approx(1.5)
    assert se.breakdown["HYPURRFI"] == pytest.approx(2.5)
    assert "0x808f72b6ff632fba005c88b49c2a76ab01cab545" in se.breakdown
    assert se.meta.get("sources") == ["erc4626", "aave_hyperlend", "aave_hypurrfi"]
    assert se.meta.get("usdc_decimals") == 6
    assert isinstance(se.meta.get("account_addresses"), list)
    assert len(se.meta["account_addresses"]) >= 1


def test_lending_partial_aave_one_protocol():
    """One Aave protocol missing → amount 0 for that key, total still defined."""

    class CursorOneAave(_FakeCursor):
        def fetchall(self):
            if self._mode == "aave":
                return [("HYPERLEND", 3.0, None)]
            return []

    class Conn:
        def cursor(self):
            return CursorOneAave()

    from tracking.vault.providers.lending import LendingProvider

    p = LendingProvider()
    se = p._query_lending_equity(Conn(), {})
    assert se.breakdown.get("HYPURRFI") == 0.0
    assert se.equity_usd == pytest.approx(103.0)


def test_get_equity_skips_pg_when_no_db_url():
    from tracking.vault.providers.lending import LendingProvider

    with patch.dict(os.environ, {"HARMONIX_NAV_DB_URL": ""}, clear=False):
        p = LendingProvider()
        se = p.get_equity({}, None)
    assert se.equity_usd == 0.0
    assert "error" in se.meta


def test_lending_account_addresses_from_unified_env():
    from tracking.vault.providers.lending import LendingProvider

    with patch.dict(
        os.environ,
        {"HARMONIX_LENDING_ACCOUNT_ADDRESSES": "0xaaa,0xbbb"},
        clear=False,
    ):
        p = LendingProvider()
        addrs = p._lending_account_addresses({})
    assert addrs == ["0xaaa", "0xbbb"]


def test_two_addresses_passed_to_sql_params():
    """ERC4626 and Aave queries use ANY(%s) with two lowered addresses."""
    from tracking.vault.providers.lending import LendingProvider

    class Cursor:
        def execute(self, sql, params=None) -> None:
            s = sql if isinstance(sql, str) else str(sql)
            if "vault_erc4626_account_snapshot_hourly" in s:
                assert len(params[1]) == 2
                assert params[1] == ["0xaaa", "0xbbb"]
            elif "aave_user_reserve_snapshot_hourly" in s:
                assert len(params[3]) == 2
                assert params[3] == ["0xaaa", "0xbbb"]

        def fetchone(self):
            return (50.0, None, {"0xv": 50.0})

        def fetchall(self):
            return [("HYPERLEND", 25.0, None), ("HYPURRFI", 25.0, None)]

    class Conn:
        def cursor(self):
            return Cursor()

    with patch.dict(
        os.environ,
        {"HARMONIX_LENDING_ACCOUNT_ADDRESSES": "0xAAA,0xbBb"},
        clear=False,
    ):
        p = LendingProvider()
        se = p._query_lending_equity(Conn(), {})
    assert se.equity_usd == pytest.approx(100.0)
    assert se.meta["account_addresses"] == ["0xAAA", "0xbBb"]
