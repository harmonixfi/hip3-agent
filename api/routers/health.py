"""Health check endpoint.

GET /api/health — system status for monitoring.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from api.config import get_settings
from api.deps import get_db
from api.main import get_uptime
from api.models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


def _ts_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _latest_ts(db: sqlite3.Connection, table: str, ts_col: str = "ts") -> Optional[int]:
    """Get the latest timestamp from a table."""
    try:
        row = db.execute(f"SELECT MAX({ts_col}) FROM {table}").fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.OperationalError:
        return None


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: sqlite3.Connection = Depends(get_db),
):
    """Return system health status."""
    settings = get_settings()

    # DB file size
    db_size_mb = 0.0
    if settings.db_path.exists():
        db_size_mb = round(settings.db_path.stat().st_size / (1024 * 1024), 1)

    # Latest timestamps from key tables
    last_fill = _latest_ts(db, "pm_fills")
    last_position = _latest_ts(db, "pm_leg_snapshots")
    last_portfolio = _latest_ts(db, "pm_portfolio_snapshots")

    # Felix JWT expiry (from vault or env)
    felix_jwt_expires = None
    try:
        from vault.vault import get_secret

        jwt_expiry_str = get_secret("felix_jwt_expires_at")
        if jwt_expiry_str:
            felix_jwt_expires = jwt_expiry_str
    except Exception:
        pass

    # Open positions
    open_count = db.execute(
        "SELECT COUNT(*) FROM pm_positions WHERE status IN ('OPEN', 'PAUSED')"
    ).fetchone()[0]

    return HealthResponse(
        status="ok",
        db_size_mb=db_size_mb,
        last_fill_ingestion=_ts_to_iso(last_fill),
        last_price_pull=_ts_to_iso(last_portfolio),  # portfolio snapshot includes price data
        last_position_pull=_ts_to_iso(last_position),
        felix_jwt_expires_at=felix_jwt_expires,
        open_positions=open_count,
        uptime_seconds=round(get_uptime(), 1),
    )