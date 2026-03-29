#!/usr/bin/env python3
"""Tests for PERP_PERP position support.

Verifies that fill ingestion, uPnL, spreads, and portfolio aggregation
all work correctly for perp-long + perp-short positions.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared test DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE pm_positions(
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
            account_id TEXT NOT NULL,
            raw_json TEXT,
            meta_json TEXT
        );
        CREATE TABLE pm_fills (
            fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue TEXT NOT NULL,
            account_id TEXT NOT NULL,
            tid TEXT NOT NULL,
            oid TEXT,
            inst_id TEXT NOT NULL,
            side TEXT NOT NULL,
            px REAL NOT NULL,
            sz REAL NOT NULL,
            fee REAL,
            fee_currency TEXT,
            ts INTEGER NOT NULL,
            closed_pnl REAL,
            dir TEXT,
            builder_fee REAL,
            position_id TEXT,
            leg_id TEXT,
            raw_json TEXT,
            meta_json TEXT,
            UNIQUE(venue, account_id, tid)
        );
        CREATE TABLE pm_entry_prices (
            leg_id TEXT NOT NULL PRIMARY KEY,
            position_id TEXT NOT NULL,
            avg_entry_price REAL NOT NULL,
            total_filled_qty REAL NOT NULL,
            total_cost REAL NOT NULL,
            fill_count INTEGER NOT NULL,
            first_fill_ts INTEGER,
            last_fill_ts INTEGER,
            computed_at_ms INTEGER NOT NULL,
            method TEXT NOT NULL DEFAULT 'VWAP',
            meta_json TEXT
        );
        CREATE TABLE pm_cashflows(
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
    """)
    return con


def _seed_perp_perp_position(con: sqlite3.Connection) -> None:
    """Seed a PERP_PERP position: long hyna:HYPE (0xdef) + short HYPE (0xabc)."""
    now_ms = 1711900000000
    con.executemany(
        """INSERT INTO pm_positions
           (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("pos_hype_pp", "hyperliquid", "PERP_PERP", "OPEN", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        """INSERT INTO pm_legs
           (leg_id, position_id, venue, inst_id, side, size, entry_price,
            current_price, unrealized_pnl, realized_pnl, status, opened_at_ms,
            closed_at_ms, account_id, raw_json, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            # Long leg: hyna:HYPE on Hyena, account 0xdef
            ("hype_long_hyna", "pos_hype_pp", "hyena", "hyna:HYPE", "LONG",
             100.0, None, None, None, 0.0, "OPEN", now_ms, None, "0xdef", "{}", "{}"),
            # Short leg: HYPE on HL native, account 0xabc
            ("hype_short_hl", "pos_hype_pp", "hyperliquid", "HYPE", "SHORT",
             100.0, None, None, None, 0.0, "OPEN", now_ms, None, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


# ---------------------------------------------------------------------------
# 1. Fill Ingestion Tests
# ---------------------------------------------------------------------------

def test_perp_perp_fill_mapping_long_leg():
    """Long perp fill maps to long leg by (inst_id, account_id)."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        result = map_fill_to_leg("hyna:HYPE", "0xdef", targets)

        assert result is not None
        assert result["leg_id"] == "hype_long_hyna"
        assert result["side"] == "LONG"

        con.close()


def test_perp_perp_fill_mapping_short_leg():
    """Short perp fill maps to short leg by (inst_id, account_id)."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        result = map_fill_to_leg("HYPE", "0xabc", targets)

        assert result is not None
        assert result["leg_id"] == "hype_short_hl"
        assert result["side"] == "SHORT"

        con.close()


def test_perp_perp_no_cross_account_mapping():
    """Fill from wrong account does not match even if inst_id matches."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        # HYPE fill but wrong account — should not match
        result = map_fill_to_leg("HYPE", "0xdef", targets)
        assert result is None

        con.close()


# ---------------------------------------------------------------------------
# 2. uPnL Tests
# ---------------------------------------------------------------------------

def test_perp_perp_upnl_long_uses_bid():
    """Long perp uPnL is computed using bid price."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Long perp: entry at 25.00, current bid 26.00, size 100
    # Expected: (26.00 - 25.00) * 100 = +100.0
    pnl = compute_leg_upnl(side="LONG", avg_entry=25.00, exit_price=26.00, size=100.0)
    assert pnl == 100.0


def test_perp_perp_upnl_short_uses_ask():
    """Short perp uPnL is computed using ask price."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Short perp: entry at 25.00, current ask 24.00, size 100
    # Expected: -(24.00 - 25.00) * 100 = +100.0
    pnl = compute_leg_upnl(side="SHORT", avg_entry=25.00, exit_price=24.00, size=100.0)
    assert pnl == 100.0


def test_perp_perp_upnl_net_negative_when_spread_moves_against():
    """Net uPnL is negative when spread moves against position."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Long at 25.00, now bid is 24.50 (moved down) -> -50
    long_pnl = compute_leg_upnl(side="LONG", avg_entry=25.00, exit_price=24.50, size=100.0)
    # Short at 25.00, now ask is 25.50 (moved up, bad for short) -> -50
    short_pnl = compute_leg_upnl(side="SHORT", avg_entry=25.00, exit_price=25.50, size=100.0)
    assert long_pnl == -50.0
    assert short_pnl == -50.0
    assert long_pnl + short_pnl == -100.0  # net loss when spread widens against you


# ---------------------------------------------------------------------------
# 3. Spread Tests
# ---------------------------------------------------------------------------

def test_perp_perp_entry_spread():
    """Entry spread = long_avg_entry / short_avg_entry - 1."""
    from tracking.pipeline.spreads import entry_spread

    # Long entered at 25.00, short at 25.50
    # Spread = 25.00 / 25.50 - 1 = -0.01961... (long at discount to short)
    spread = entry_spread(long_avg_entry=25.00, short_avg_entry=25.50)
    assert abs(spread - (25.00 / 25.50 - 1.0)) < 1e-9


def test_perp_perp_exit_spread():
    """Exit spread = long_perp_bid / short_perp_ask - 1."""
    from tracking.pipeline.spreads import exit_spread

    # Long leg bid: 25.20, Short leg ask: 25.30
    # Spread = 25.20 / 25.30 - 1 = -0.00395...
    spread = exit_spread(long_exit_bid=25.20, short_exit_ask=25.30)
    assert abs(spread - (25.20 / 25.30 - 1.0)) < 1e-9


def test_perp_perp_spread_pnl_bps():
    """Spread P&L in bps: positive means spread tightened (favorable for long/short)."""
    from tracking.pipeline.spreads import spread_pnl_bps

    entry = 25.00 / 25.50 - 1.0   # ~-196 bps
    exit_ = 25.20 / 25.10 - 1.0   # ~+40 bps — spread flipped to long premium
    bps = spread_pnl_bps(entry, exit_)
    # exit > entry => bps > 0 => favorable
    assert bps > 0


# ---------------------------------------------------------------------------
# 4. Net Funding Tests
# ---------------------------------------------------------------------------

def test_perp_perp_net_funding_sums_both_legs():
    """Net funding = long_funding + short_funding (long is typically negative)."""
    from tracking.pipeline.portfolio import compute_position_net_funding

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        now_ms = 1711900000000
        # Long leg funding: -15 USDC (pays funding, negative)
        # Short leg funding: +40 USDC (receives funding, positive)
        con.executemany(
            """INSERT INTO pm_cashflows
               (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms - 3600000, "FUNDING", -15.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms - 3600000, "FUNDING", +40.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms,           "FUNDING", -12.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms,           "FUNDING", +38.0, "USDC", "{}"),
            ],
        )
        con.commit()

        net = compute_position_net_funding(con, "pos_hype_pp")
        # Expected: -15 + 40 + -12 + 38 = +51
        assert abs(net - 51.0) < 1e-9

        con.close()


def test_perp_perp_long_funding_reduces_carry():
    """Long funding (negative) reduces carry vs SPOT_PERP which has no long funding cost."""
    from tracking.pipeline.portfolio import compute_position_net_funding

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        now_ms = 1711900000000
        con.executemany(
            """INSERT INTO pm_cashflows
               (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms, "FUNDING", -20.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms, "FUNDING", +60.0, "USDC", "{}"),
            ],
        )
        con.commit()

        net = compute_position_net_funding(con, "pos_hype_pp")
        # Net = +40 (not +60 — long funding cost reduces carry)
        assert abs(net - 40.0) < 1e-9

        con.close()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_perp_perp_fill_mapping_long_leg,
        test_perp_perp_fill_mapping_short_leg,
        test_perp_perp_no_cross_account_mapping,
        test_perp_perp_upnl_long_uses_bid,
        test_perp_perp_upnl_short_uses_ask,
        test_perp_perp_upnl_net_negative_when_spread_moves_against,
        test_perp_perp_entry_spread,
        test_perp_perp_exit_spread,
        test_perp_perp_spread_pnl_bps,
        test_perp_perp_net_funding_sums_both_legs,
        test_perp_perp_long_funding_reduces_carry,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print(f"\nAll {len(tests)} PERP_PERP tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
