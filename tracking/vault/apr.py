"""Unified cashflow-adjusted APR calculator.

Same formula as design spec and portfolio daily APR scale (see tracking/pipeline/portfolio.py):
organic_change = (current - prior) - net_cashflows
apr = (organic_change / prior_equity) / period_days * 365
"""

from __future__ import annotations


def cashflow_adjusted_apr(
    current_equity: float,
    prior_equity: float,
    net_external_cashflows: float,
    period_days: float,
) -> float:
    """Compute annualized return adjusted for external cashflows.

    Returns:
        Same units as portfolio ``apr_daily``: e.g. ~3.65 means ~3.65% annualized
        from a 1-day move of ~1%; multi-day windows scale by ``period_days``.
    """
    if prior_equity <= 0 or period_days <= 0:
        return 0.0
    organic_change = (current_equity - prior_equity) - net_external_cashflows
    return (organic_change / prior_equity) / period_days * 365.0
