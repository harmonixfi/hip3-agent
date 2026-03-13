#!/usr/bin/env python3
"""Unit tests for funding sign convention.

Funding sign convention (exchange funding rate):
- funding > 0: long pays, short receives
- funding < 0: long receives, short pays

Position PnL (APR terms):
- pnl_long = -funding_apr
- pnl_short = +funding_apr
"""


def pnl_long(funding_apr_pct: float) -> float:
    return -funding_apr_pct


def pnl_short(funding_apr_pct: float) -> float:
    return funding_apr_pct


def test_cases():
    # funding positive
    assert pnl_long(+10.0) == -10.0
    assert pnl_short(+10.0) == +10.0

    # funding negative
    assert pnl_long(-10.0) == +10.0
    assert pnl_short(-10.0) == -10.0


def main() -> int:
    test_cases()
    print("OK: funding sign convention tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
