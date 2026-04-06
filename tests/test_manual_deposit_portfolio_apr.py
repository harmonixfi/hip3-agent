"""Readable tests for manual DEPOSIT / WITHDRAW vs portfolio cashflow-adjusted APR.

Story (see docs/guide-manual-deposit-and-apr.md):
- Equity comes from pm_account_snapshots (venue balance).
- Manual DEPOSIT / WITHDRAW rows in pm_cashflows do not change balances; they feed
  net_deposits_24h (sum of signed amounts) so raw equity moves are not mistaken
  for trading performance.

These tests freeze time and use round numbers so the math is obvious.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.portfolio import compute_portfolio_snapshot


# Fixed "now" so 24h / 26h windows are predictable.
NOW_MS = 1_700_000_000_000
# Prior snapshot must sit in [now-28h, now-24h] for _get_prior_equity (24h lookback, 4h tolerance).
TS_PRIOR_SNAPSHOT = NOW_MS - 26 * 3600 * 1000  # 26 hours ago
# Manual flow row inside the last 24h window (deposit or withdraw).
TS_FLOW = NOW_MS - 1 * 3600 * 1000  # 1 hour ago


def _minimal_db() -> sqlite3.Connection:
    """Only tables used by compute_portfolio_snapshot + unrealized PnL query."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(
        """
        CREATE TABLE pm_positions (
          position_id TEXT PRIMARY KEY,
          venue TEXT NOT NULL,
          strategy TEXT,
          status TEXT NOT NULL,
          created_at_ms INTEGER NOT NULL,
          updated_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_legs (
          leg_id TEXT PRIMARY KEY,
          position_id TEXT NOT NULL,
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL,
          size REAL NOT NULL,
          entry_price REAL,
          current_price REAL,
          unrealized_pnl REAL,
          realized_pnl REAL,
          status TEXT NOT NULL,
          opened_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE pm_account_snapshots (
          snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          total_balance REAL
        );
        CREATE TABLE pm_portfolio_snapshots (
          snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts INTEGER NOT NULL,
          total_equity_usd REAL NOT NULL,
          equity_by_account_json TEXT,
          total_unrealized_pnl REAL,
          total_funding_today REAL,
          total_funding_alltime REAL,
          total_fees_alltime REAL,
          daily_change_usd REAL,
          cashflow_adjusted_change REAL,
          apr_daily REAL,
          tracking_start_date TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_cashflows (
          cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
          position_id TEXT,
          leg_id TEXT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          cf_type TEXT NOT NULL,
          amount REAL NOT NULL,
          currency TEXT NOT NULL,
          description TEXT,
          raw_json TEXT,
          meta_json TEXT
        );
        """
    )
    return con


def _seed_baseline_equity_story(con: sqlite3.Connection) -> None:
    """~24h ago the book was $50k; today the venue shows $60k (one wallet)."""
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (
          ts, total_equity_usd, equity_by_account_json,
          total_unrealized_pnl, total_funding_today, total_funding_alltime,
          total_fees_alltime, daily_change_usd, cashflow_adjusted_change, apr_daily,
          tracking_start_date
        ) VALUES (?, 50000.0, '{}', 0, 0, 0, 0, NULL, NULL, NULL, '2000-01-01')
        """,
        (TS_PRIOR_SNAPSHOT,),
    )
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES ('hyperliquid', '0xwallets', ?, 60000.0)
        """,
        (NOW_MS,),
    )
    con.commit()


def _seed_withdraw_equity_story(con: sqlite3.Connection) -> None:
    """~24h ago the book was $60k; today the venue shows $50k after $10k left."""
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (
          ts, total_equity_usd, equity_by_account_json,
          total_unrealized_pnl, total_funding_today, total_funding_alltime,
          total_fees_alltime, daily_change_usd, cashflow_adjusted_change, apr_daily,
          tracking_start_date
        ) VALUES (?, 60000.0, '{}', 0, 0, 0, 0, NULL, NULL, NULL, '2000-01-01')
        """,
        (TS_PRIOR_SNAPSHOT,),
    )
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES ('hyperliquid', '0xwallets', ?, 50000.0)
        """,
        (NOW_MS,),
    )
    con.commit()


@pytest.fixture
def frozen_portfolio_time():
    """Freeze 'now' and 'start of day' so funding windows stay stable."""
    with (
        patch("tracking.pipeline.portfolio._now_ms", return_value=NOW_MS),
        patch("tracking.pipeline.portfolio._today_start_ms", return_value=NOW_MS - 43_200_000),
    ):
        yield


def test_deposit_logged__cashflow_adjusted_change_is_zero(frozen_portfolio_time):
    """If equity jumps $10k and you logged a $10k deposit, organic change is ~0.

    daily_change = 60k - 50k = 10k
    net_deposits_24h = +10k  →  adjusted = 10k - 10k = 0  →  apr_daily = 0
    """
    con = _minimal_db()
    _seed_baseline_equity_story(con)
    con.execute(
        """
        INSERT INTO pm_cashflows (
          position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, meta_json
        ) VALUES (NULL, NULL, 'hyperliquid', '0xwallets', ?, 'DEPOSIT', 10000.0, 'USDC', 'test', '{"source":"manual"}')
        """,
        (TS_FLOW,),
    )
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] == pytest.approx(10000.0)
    assert snap["cashflow_adjusted_change"] == pytest.approx(0.0)
    assert snap["apr_daily"] == pytest.approx(0.0)


def test_deposit_not_logged__apr_looks_like_huge_return(frozen_portfolio_time):
    """Same equity path but no DEPOSIT row: the whole $10k move counts as 'organic'.

    apr_daily = (10000 / 50000) * 365 = 73.0  (same units as pipeline)
    """
    con = _minimal_db()
    _seed_baseline_equity_story(con)
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] == pytest.approx(10000.0)
    assert snap["cashflow_adjusted_change"] == pytest.approx(10000.0)
    assert snap["apr_daily"] == pytest.approx(73.0)


def test_withdraw_logged__cashflow_adjusted_change_is_zero(frozen_portfolio_time):
    """Equity drops $10k and you logged a $10k WITHDRAW (stored negative): organic change ~0.

    daily_change = 50k - 60k = -10k
    net_deposits_24h = -10k  →  adjusted = -10k - (-10k) = 0  →  apr_daily = 0
    """
    con = _minimal_db()
    _seed_withdraw_equity_story(con)
    con.execute(
        """
        INSERT INTO pm_cashflows (
          position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, description, meta_json
        ) VALUES (NULL, NULL, 'hyperliquid', '0xwallets', ?, 'WITHDRAW', -10000.0, 'USDC', 'test', '{"source":"manual"}')
        """,
        (TS_FLOW,),
    )
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] == pytest.approx(-10000.0)
    assert snap["cashflow_adjusted_change"] == pytest.approx(0.0)
    assert snap["apr_daily"] == pytest.approx(0.0)


def test_withdraw_not_logged__apr_looks_like_big_loss(frozen_portfolio_time):
    """Same equity path but no WITHDRAW row: the full -$10k counts as 'organic'.

    apr_daily = (-10000 / 60000) * 365
    """
    con = _minimal_db()
    _seed_withdraw_equity_story(con)
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] == pytest.approx(-10000.0)
    assert snap["cashflow_adjusted_change"] == pytest.approx(-10000.0)
    expected_apr = (-10000.0 / 60000.0) * 365.0
    assert snap["apr_daily"] == pytest.approx(expected_apr)


def test_huge_negative_move_without_withdraw__circuit_breaker_nulls_apr(frozen_portfolio_time):
    """>50% drop vs prior with no DEPOSIT/WITHDRAW rows: suppress APR (unrecorded flow)."""
    con = _minimal_db()
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (
          ts, total_equity_usd, equity_by_account_json,
          total_unrealized_pnl, total_funding_today, total_funding_alltime,
          total_fees_alltime, daily_change_usd, cashflow_adjusted_change, apr_daily,
          tracking_start_date
        ) VALUES (?, 60000.0, '{}', 0, 0, 0, 0, NULL, NULL, NULL, '2000-01-01')
        """,
        (TS_PRIOR_SNAPSHOT,),
    )
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES ('hyperliquid', '0xwallets', ?, 20000.0)
        """,
        (NOW_MS,),
    )
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] is None
    assert snap["cashflow_adjusted_change"] is None
    assert snap["apr_daily"] is None


def test_huge_move_without_deposit__circuit_breaker_nulls_apr(frozen_portfolio_time):
    """If equity jumps >50% vs prior and net_deposits is 0, APR fields are suppressed.

    This matches the 'probably an unrecorded deposit' guard in portfolio.py.
    """
    con = _minimal_db()
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (
          ts, total_equity_usd, equity_by_account_json,
          total_unrealized_pnl, total_funding_today, total_funding_alltime,
          total_fees_alltime, daily_change_usd, cashflow_adjusted_change, apr_daily,
          tracking_start_date
        ) VALUES (?, 50000.0, '{}', 0, 0, 0, 0, NULL, NULL, NULL, '2000-01-01')
        """,
        (TS_PRIOR_SNAPSHOT,),
    )
    # +60% equity move: 50k -> 80k with no logged deposit
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES ('hyperliquid', '0xwallets', ?, 80000.0)
        """,
        (NOW_MS,),
    )
    con.commit()

    snap = compute_portfolio_snapshot(con, tracking_start_date="2000-01-01")

    assert snap["daily_change_usd"] is None
    assert snap["cashflow_adjusted_change"] is None
    assert snap["apr_daily"] is None
