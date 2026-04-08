"""Hourly Pipeline Orchestrator.

Orchestrates all computation steps in order:
1. Fetch spot_meta (symbol resolution cache)
2. Ingest fills from Hyperliquid
3. Compute entry prices (VWAP)
4. Compute unrealized PnL (bid/ask)
5. Compute entry/exit spreads
6. Compute portfolio snapshot (pm_portfolio_snapshots — health / PM overview)
7. Vault snapshot (vault_snapshots + vault_strategy_snapshots — dashboard ``/api/vault/overview``)

Errors in one step do not block subsequent steps.

Usage:
    source .arbit_env
    .venv/bin/python scripts/pipeline_hourly.py
    .venv/bin/python scripts/pipeline_hourly.py --skip-ingest
    .venv/bin/python scripts/pipeline_hourly.py --since-hours 48
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"
DEFAULT_SINCE_HOURS = 504  # 21 days


# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _log(step: str, msg: str) -> None:
    """Log a pipeline step message with UTC timestamp."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] [{step}] {msg}", flush=True)


def _run_step(step_name: str, fn: Callable, *args, **kwargs) -> Any:
    """Run a pipeline step, catching and logging exceptions without blocking subsequent steps."""
    _log(step_name, "starting...")
    t0 = time.time()
    try:
        result = fn(*args, **kwargs)
        elapsed = time.time() - t0
        _log(step_name, f"OK ({elapsed:.2f}s) → {result!r}")
        return result
    except Exception as exc:
        elapsed = time.time() - t0
        _log(step_name, f"ERROR ({elapsed:.2f}s): {exc}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Step functions
# ---------------------------------------------------------------------------

def step_fetch_spot_meta() -> dict:
    """Fetch spot index map from Hyperliquid spotMeta API."""
    from tracking.pipeline.spot_meta import fetch_spot_index_map
    spot_index_map = fetch_spot_index_map()
    return spot_index_map


def step_ingest_fills(con: sqlite3.Connection, spot_index_map: dict, since_ms: Optional[int] = None) -> int:
    """Ingest fills from Hyperliquid for all managed wallets."""
    from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills
    kwargs = {}
    if since_ms is not None:
        kwargs["since_ms"] = since_ms
    count = ingest_hyperliquid_fills(con, spot_index_map, **kwargs)
    return count


def step_entry_prices(con: sqlite3.Connection) -> list:
    """Compute VWAP entry prices from fills."""
    from tracking.pipeline.entry_price import compute_entry_prices
    results = compute_entry_prices(con)
    return results


def step_unrealized_pnl(con: sqlite3.Connection) -> list:
    """Compute unrealized PnL using bid/ask prices."""
    from tracking.pipeline.upnl import compute_unrealized_pnl
    results = compute_unrealized_pnl(con)
    return results


def step_spreads(con: sqlite3.Connection) -> list:
    """Compute entry/exit spreads."""
    from tracking.pipeline.spreads import compute_spreads
    results = compute_spreads(con)
    return results


def step_portfolio_snapshot(con: sqlite3.Connection) -> dict:
    """Compute and write portfolio-level snapshot."""
    from tracking.pipeline.portfolio import compute_portfolio_snapshot
    result = compute_portfolio_snapshot(con)
    return result


def step_vault_snapshot(con: sqlite3.Connection) -> dict:
    """Refresh vault_snapshots so the main dashboard (GET /api/vault/overview) updates."""
    from tracking.vault.snapshot import run_daily_snapshot
    return run_daily_snapshot(con)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_pipeline(
    *,
    db_path: Path = DEFAULT_DB,
    skip_ingest: bool = False,
    since_hours: int = DEFAULT_SINCE_HOURS,
    skip_vault: bool = False,
) -> None:
    _log(
        "orchestrator",
        f"starting pipeline (skip_ingest={skip_ingest}, since_hours={since_hours}, skip_vault={skip_vault})",
    )

    con = sqlite3.connect(str(db_path), timeout=60)
    con.execute("PRAGMA journal_mode=WAL")

    # Step 1: Fetch spot meta (needed for fill ingestion)
    spot_index_map = _run_step("spot_meta", step_fetch_spot_meta)

    # Step 2: Ingest fills (optional, can be skipped for recompute-only runs)
    if skip_ingest:
        _log("fill_ingest", "SKIPPED (--skip-ingest flag)")
    else:
        since_ms = None
        if since_hours:
            since_ms = int((time.time() - since_hours * 3600) * 1000)
        _run_step(
            "fill_ingest",
            step_ingest_fills,
            con,
            spot_index_map if spot_index_map is not None else {},
            since_ms,
        )

    # Step 3: Entry prices (VWAP)
    _run_step("entry_prices", step_entry_prices, con)

    # Step 4: Unrealized PnL
    _run_step("unrealized_pnl", step_unrealized_pnl, con)

    # Step 5: Spreads
    _run_step("spreads", step_spreads, con)

    # Step 6: Portfolio snapshot
    _run_step("portfolio_snapshot", step_portfolio_snapshot, con)

    # Step 7: Vault overview (dashboard total equity / strategy weights / as_of)
    if skip_vault:
        _log("vault_snapshot", "SKIPPED (--skip-vault flag)")
    else:
        _run_step("vault_snapshot", step_vault_snapshot, con)

    con.close()
    _log("orchestrator", "pipeline complete")


# ---------------------------------------------------------------------------
# CLI entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hourly pipeline orchestrator for the monitoring computation layer.",
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to SQLite database (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "--skip-ingest",
        action="store_true",
        default=False,
        help="Skip fill ingestion — recompute only (entry prices, uPnL, spreads, portfolio)",
    )
    parser.add_argument(
        "--since-hours",
        type=int,
        default=DEFAULT_SINCE_HOURS,
        help=f"Fill lookback window in hours when forcing since_ms (default: {DEFAULT_SINCE_HOURS} = 21 days). "
             "Only applies when not using watermark-based ingestion.",
    )
    parser.add_argument(
        "--skip-vault",
        action="store_true",
        default=False,
        help="Skip vault_snapshots refresh (GET /api/vault/overview will stay stale until scripts/vault_daily_snapshot.py)",
    )
    args = parser.parse_args()

    run_pipeline(
        db_path=args.db,
        skip_ingest=args.skip_ingest,
        since_hours=args.since_hours,
        skip_vault=args.skip_vault,
    )


if __name__ == "__main__":
    main()
