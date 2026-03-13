#!/usr/bin/env python3
"""Focused regression checks for Loris historical timestamp parsing."""

from __future__ import annotations

import datetime as dt

from pull_loris_backfill_history import parse_hist_timestamp_utc


def main() -> int:
    naive = parse_hist_timestamp_utc("2026-02-08T00:00:00")
    zulu = parse_hist_timestamp_utc("2026-02-08T00:00:00Z")

    expected = dt.datetime(2026, 2, 8, 0, 0, 0, tzinfo=dt.timezone.utc)
    assert naive == expected, naive
    assert zulu == expected, zulu
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
