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
        Percent form: e.g. 4.77 means 4.77% annualized.
        Consistent with position carry_apr and candidate APR (all use * 100).
    """
    if prior_equity <= 0 or period_days <= 0:
        return 0.0
    organic_change = (current_equity - prior_equity) - net_external_cashflows
    return (organic_change / prior_equity) / period_days * 365.0 * 100.0
