"""Helpers to read the tail of loris_funding_history.csv efficiently."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List


LORIS_HEADER = "timestamp_utc,exchange,symbol,oi_rank,funding_8h_scaled,funding_8h_rate"


def read_tail_lines(path: Path, max_bytes: int = 2_000_000) -> List[str]:
    """Read last max_bytes of a file and return splitlines."""
    if not path.exists():
        return []
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes), os.SEEK_SET)
            chunk = f.read().decode("utf-8", errors="ignore")
        lines = [ln for ln in chunk.splitlines() if ln.strip()]
        return lines
    except Exception:
        return []


def ensure_header(lines: List[str]) -> List[str]:
    # Find header in chunk; if absent, prepend expected header.
    for ln in lines[:5]:
        if ln.lower().startswith("timestamp_utc,"):
            return lines
    return [LORIS_HEADER] + lines
