"""Tests for unified cashflow-adjusted APR calculator."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.vault.apr import cashflow_adjusted_apr


def test_positive_return_no_cashflows():
    # 1% over 10 days → (0.01/10)*365 = 0.365
    apr = cashflow_adjusted_apr(
        current_equity=10100.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    assert abs(apr - 0.365) < 0.0001


def test_deposit_excluded_from_return():
    apr = cashflow_adjusted_apr(
        current_equity=15100.0,
        prior_equity=10000.0,
        net_external_cashflows=5000.0,
        period_days=10.0,
    )
    assert abs(apr - 0.365) < 0.0001


def test_withdrawal_excluded_from_return():
    apr = cashflow_adjusted_apr(
        current_equity=5100.0,
        prior_equity=10000.0,
        net_external_cashflows=-5000.0,
        period_days=10.0,
    )
    assert abs(apr - 0.365) < 0.0001


def test_negative_return():
    apr = cashflow_adjusted_apr(
        current_equity=9900.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    assert abs(apr - (-0.365)) < 0.0001


def test_zero_prior_equity():
    apr = cashflow_adjusted_apr(
        current_equity=100.0,
        prior_equity=0.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    assert apr == 0.0


def test_zero_period():
    apr = cashflow_adjusted_apr(
        current_equity=10100.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=0.0,
    )
    assert apr == 0.0
