"""Tests for pure aggregation + spread + P&L math in trades.py.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_aggregate.py -v
"""
from __future__ import annotations
import pytest

from tracking.pipeline.trades import (
    aggregate_fills,
    compute_spread_bps,
    compute_realized_pnl_bps,
    side_for,
    FillRow,
)


def test_aggregate_fills_vwap_and_fees():
    fills = [
        FillRow(fill_id=1, px=100.0, sz=2.0, fee=0.10),
        FillRow(fill_id=2, px=102.0, sz=3.0, fee=0.15),
    ]
    agg = aggregate_fills(fills)
    assert agg.size == pytest.approx(5.0)
    assert agg.notional == pytest.approx(506.0)
    assert agg.avg_px == pytest.approx(101.2)
    assert agg.fees == pytest.approx(0.25)
    assert agg.fill_count == 2


def test_aggregate_fills_empty_returns_zeroed():
    agg = aggregate_fills([])
    assert agg.size == 0.0
    assert agg.notional == 0.0
    assert agg.avg_px is None
    assert agg.fees == 0.0
    assert agg.fill_count == 0


def test_aggregate_fills_single():
    agg = aggregate_fills([FillRow(fill_id=1, px=50.0, sz=1.0, fee=None)])
    assert agg.avg_px == 50.0
    assert agg.fees == 0.0


def test_compute_spread_bps_positive():
    assert compute_spread_bps(101.0, 100.0) == pytest.approx(100.0)


def test_compute_spread_bps_negative():
    assert compute_spread_bps(99.0, 100.0) == pytest.approx(-100.0)


def test_compute_spread_bps_zero_denominator_raises():
    with pytest.raises(ValueError, match="zero short"):
        compute_spread_bps(100.0, 0.0)


def test_compute_spread_bps_none_leg_returns_none():
    assert compute_spread_bps(None, 100.0) is None
    assert compute_spread_bps(100.0, None) is None


def test_compute_realized_pnl_bps_single_open_single_close():
    opens = [(50.0, 10.0)]
    assert compute_realized_pnl_bps(opens, close_spread_bps=30.0) == pytest.approx(20.0)


def test_compute_realized_pnl_bps_multi_open_weighted_avg():
    opens = [(60.0, 10.0), (40.0, 30.0)]
    assert compute_realized_pnl_bps(opens, close_spread_bps=20.0) == pytest.approx(25.0)


def test_compute_realized_pnl_bps_no_opens_raises():
    with pytest.raises(ValueError, match="no FINALIZED OPEN"):
        compute_realized_pnl_bps([], close_spread_bps=30.0)


def test_compute_realized_pnl_bps_zero_size_open_skipped():
    opens = [(50.0, 0.0), (30.0, 10.0)]
    assert compute_realized_pnl_bps(opens, close_spread_bps=20.0) == pytest.approx(10.0)


def test_side_for_open_long_is_buy():
    assert side_for("OPEN", "LONG") == "BUY"


def test_side_for_open_short_is_sell():
    assert side_for("OPEN", "SHORT") == "SELL"


def test_side_for_close_long_is_sell():
    assert side_for("CLOSE", "LONG") == "SELL"


def test_side_for_close_short_is_buy():
    assert side_for("CLOSE", "SHORT") == "BUY"


def test_side_for_invalid_type_raises():
    with pytest.raises(ValueError):
        side_for("ADD", "LONG")
    with pytest.raises(ValueError):
        side_for("OPEN", "BOTH")


# ---------------------------------------------------------------------------
# A3: Trade ID + window overlap tests
# ---------------------------------------------------------------------------

from tracking.pipeline.trades import (
    resolve_trade_id,
    overlaps,
    TradeWindow,
)
from datetime import datetime, timezone


def test_resolve_trade_id_basic():
    ts_ms = int(datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    existing = set()
    assert resolve_trade_id("GOOGL", "OPEN", ts_ms, existing) == "trd_GOOGL_202604171000_open"


def test_resolve_trade_id_collision_suffixed():
    ts_ms = int(datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    existing = {"trd_GOOGL_202604171000_open"}
    assert resolve_trade_id("GOOGL", "OPEN", ts_ms, existing) == "trd_GOOGL_202604171000_open_2"


def test_resolve_trade_id_close_type():
    ts_ms = int(datetime(2026, 4, 17, 11, 30, tzinfo=timezone.utc).timestamp() * 1000)
    assert resolve_trade_id("MSFT", "CLOSE", ts_ms, set()) == "trd_MSFT_202604171130_close"


def test_overlaps_disjoint_false():
    a = TradeWindow(start_ts=100, end_ts=200)
    b = TradeWindow(start_ts=300, end_ts=400)
    assert overlaps(a, b) is False


def test_overlaps_touching_edge_false():
    a = TradeWindow(start_ts=100, end_ts=200)
    b = TradeWindow(start_ts=200, end_ts=300)
    # end of a == start of b is NOT overlap (half-open intervals)
    assert overlaps(a, b) is False


def test_overlaps_contained_true():
    a = TradeWindow(start_ts=100, end_ts=400)
    b = TradeWindow(start_ts=200, end_ts=300)
    assert overlaps(a, b) is True


def test_overlaps_partial_true():
    a = TradeWindow(start_ts=100, end_ts=250)
    b = TradeWindow(start_ts=200, end_ts=300)
    assert overlaps(a, b) is True


def test_resolve_trade_id_double_collision():
    ts_ms = int(datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    existing = {
        "trd_GOOGL_202604171000_open",
        "trd_GOOGL_202604171000_open_2",
    }
    assert resolve_trade_id("GOOGL", "OPEN", ts_ms, existing) == "trd_GOOGL_202604171000_open_3"


def test_resolve_trade_id_invalid_trade_type_raises():
    ts_ms = int(datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    with pytest.raises(ValueError, match="invalid trade_type"):
        resolve_trade_id("GOOGL", "ADD", ts_ms, set())


def test_resolve_trade_id_invalid_base_raises():
    ts_ms = int(datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc).timestamp() * 1000)
    with pytest.raises(ValueError, match="invalid base"):
        resolve_trade_id("BTC_USD", "OPEN", ts_ms, set())  # underscore disallowed
    with pytest.raises(ValueError, match="invalid base"):
        resolve_trade_id("", "OPEN", ts_ms, set())
    with pytest.raises(ValueError, match="invalid base"):
        resolve_trade_id("BTC/USD", "OPEN", ts_ms, set())  # slash disallowed


def test_overlaps_identical_windows_true():
    w = TradeWindow(start_ts=100, end_ts=200)
    assert overlaps(w, w) is True


def test_overlaps_zero_width_window_false():
    a = TradeWindow(start_ts=100, end_ts=200)
    b = TradeWindow(start_ts=150, end_ts=150)  # zero-width → empty set
    assert overlaps(a, b) is False
