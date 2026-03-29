# Phase 1b: Computation Layer -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement VWAP entry price, unrealized PnL (bid/ask), entry/exit spreads, and portfolio aggregation from raw fills and prices.

**Architecture:** Five Python modules under tracking/pipeline/ that read from pm_fills + prices_v3, compute metrics, and write to pm_entry_prices + pm_spreads + pm_portfolio_snapshots + pm_legs.

**Tech Stack:** Python 3.11+, SQLite3 (stdlib)

**References:**
- Architecture spec: `docs/PLAN.md` sections 3.2-3.4, 4.3
- Decisions: `docs/DECISIONS.md` (ADR-001 bid/ask pricing, ADR-008 spread definition, ADR-009 PERP_PERP schema)
- Schema: `tracking/sql/schema_pm_v3.sql` (pm_legs, pm_positions, pm_cashflows, pm_account_snapshots)
- Schema: `tracking/sql/schema_monitoring_v1.sql` (pm_fills, pm_entry_prices, pm_spreads, pm_portfolio_snapshots)
- Schema: `tracking/sql/schema_v3.sql` (prices_v3 table)
- Phase 1a plan: `docs/superpowers/plans/2026-03-29-phase-1a-backend-foundation.md` (fill_ingester, spot_meta signatures)
- Existing carry: `tracking/position_manager/carry.py` (pattern reference)
- Existing cashflows: `scripts/pm_cashflows.py` (pattern reference)
- Position config: `config/positions.json` (live positions)

**Depends on:** Phase 1a (pm_fills table must exist and contain fills)

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `tracking/pipeline/entry_price.py` | VWAP entry price computation from fills |
| Create | `tracking/pipeline/upnl.py` | Per-leg unrealized PnL using bid/ask from prices_v3 |
| Create | `tracking/pipeline/spreads.py` | Entry/exit spread computation per sub-pair |
| Create | `tracking/pipeline/portfolio.py` | Portfolio-level aggregation and snapshot writer |
| Create | `scripts/pipeline_hourly.py` | Orchestrator cron script |
| Create | `tests/test_entry_price.py` | Unit tests for VWAP computation |
| Create | `tests/test_upnl.py` | Unit tests for uPnL computation |
| Create | `tests/test_spreads.py` | Unit tests for spread computation |

---

## Key Formulas (from ADR-001, ADR-008)

These are the authoritative formulas. All code must match exactly.

```
# Entry price (VWAP of opening fills)
avg_entry = SUM(px * sz) / SUM(sz)
  Opening fill = BUY for LONG leg, SELL for SHORT leg

# Unrealized PnL (ADR-001: bid/ask, not mark)
LONG uPnL  = (current_bid - avg_entry) * size
SHORT uPnL = -(current_ask - avg_entry) * size

# Spread (ADR-008)
entry_spread = long_avg_entry / short_avg_entry - 1
exit_spread  = long_exit_bid / short_exit_ask - 1
spread_pnl_bps = (exit_spread - entry_spread) * 10000

# Portfolio APR
organic_change = (current_equity - prior_equity) - net_deposits
apr = (organic_change / prior_equity) / period_days * 365
```

---

## Key Schema Context

**prices_v3** (from `tracking/sql/schema_v3.sql`):
```sql
CREATE TABLE IF NOT EXISTS prices_v3 (
  venue TEXT NOT NULL,
  inst_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  bid REAL, ask REAL, last REAL, mid REAL, mark REAL, index_price REAL,
  source TEXT, quality_flags TEXT,
  PRIMARY KEY (venue, inst_id, ts)
);
```

**pm_fills** (from `tracking/sql/schema_monitoring_v1.sql`):
```sql
-- Key columns: fill_id, venue, account_id, tid, inst_id, side (BUY/SELL),
--              px, sz, fee, ts, dir, position_id, leg_id
-- UNIQUE (venue, account_id, tid)
```

**pm_entry_prices** (from `tracking/sql/schema_monitoring_v1.sql`):
```sql
-- PK: leg_id
-- Columns: leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
--          fill_count, first_fill_ts, last_fill_ts, computed_at_ms, method, meta_json
```

**pm_spreads** (from `tracking/sql/schema_monitoring_v1.sql`):
```sql
-- UNIQUE (position_id, long_leg_id, short_leg_id)
-- Columns: position_id, long_leg_id, short_leg_id, entry_spread,
--          long_avg_entry, short_avg_entry, exit_spread,
--          long_exit_price, short_exit_price, spread_pnl_bps,
--          computed_at_ms, meta_json
```

**pm_portfolio_snapshots** (from `tracking/sql/schema_monitoring_v1.sql`):
```sql
-- Columns: ts, total_equity_usd, equity_by_account_json,
--          total_unrealized_pnl, total_funding_today, total_funding_alltime,
--          total_fees_alltime, daily_change_usd, cashflow_adjusted_change,
--          apr_daily, tracking_start_date, meta_json
-- UNIQUE INDEX on CAST(ts / 3600000 AS INTEGER) (one per hour)
```

**Inst_id naming conventions** (critical for price lookups):
- Spot legs: `HYPE/USDC`, `XAUT0/USDC`, `LINK0/USDC`, `UFART/USDC`
- Native perps: `HYPE`, `FARTCOIN`, `LINK`
- Builder dex perps: `xyz:GOLD`, `hyna:HYPE`, `hyna:FARTCOIN`, `hyna:LINK`
- prices_v3 uses venue-specific inst_id (may differ from pm_legs). Must check and map.

**Live positions** (from `config/positions.json`):
- `pos_xyz_GOLD`: XAUT0/USDC (LONG) + xyz:GOLD (SHORT) -- alt wallet
- `pos_hyna_HYPE`: HYPE/USDC (LONG) + hyna:HYPE (SHORT) + HYPE (SHORT) -- alt wallet, split-leg
- `pos_hyna_FARTCOIN`: UFART/USDC (LONG) + hyna:FARTCOIN (SHORT) + FARTCOIN (SHORT) -- alt wallet, split-leg
- `pos_multi_LINK`: LINK0/USDC (LONG) + LINK (SHORT) + hyna:LINK (SHORT) -- alt wallet, split-leg

---

## Task 1: Entry Price Computer

**Files:**
- Create: `tracking/pipeline/entry_price.py`
- Create: `tests/test_entry_price.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_entry_price.py`**

```python
#!/usr/bin/env python3
"""Tests for VWAP entry price computation."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db() -> sqlite3.Connection:
    """Create an in-memory test DB with required tables."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")

    con.executescript("""
        CREATE TABLE pm_positions (
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
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE pm_fills (
          fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          tid TEXT,
          oid TEXT,
          inst_id TEXT NOT NULL,
          side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
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
          UNIQUE (venue, account_id, tid),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
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
          meta_json TEXT,
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
    """)
    return con


def _seed_positions(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed test positions and legs."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms),
            ("pos_hyna_HYPE", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms),
            ("pos_closed", "hyperliquid", "SPOT_PERP", "CLOSED", now_ms, now_ms),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 0.6608, "OPEN", now_ms, "0xalt"),
            ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 0.6608, "OPEN", now_ms, "0xalt"),
            ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE/USDC", "LONG", 126.98, "OPEN", now_ms, "0xalt"),
            ("hype_perp_hyna", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 89.48, "OPEN", now_ms, "0xalt"),
            ("hype_perp_native", "pos_hyna_HYPE", "hyperliquid", "HYPE", "SHORT", 37.50, "OPEN", now_ms, "0xalt"),
            ("closed_spot", "pos_closed", "hyperliquid", "GOOGL/USDC", "LONG", 3.0, "CLOSED", now_ms, "0xmain"),
            ("closed_perp", "pos_closed", "hyperliquid", "xyz:GOOGL", "SHORT", 3.0, "CLOSED", now_ms, "0xmain"),
        ],
    )
    con.commit()


def test_vwap_single_fill():
    """Single fill: avg_entry = fill price."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)

    # One BUY fill for LONG spot leg
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t001", "XAUT0/USDC", "BUY", 3050.0, 0.6608, 1711900000000, "pos_xyz_GOLD", "gold_spot"),
    )
    con.commit()

    results = compute_entry_prices(con)
    assert len(results) >= 1

    gold_spot = next((r for r in results if r["leg_id"] == "gold_spot"), None)
    assert gold_spot is not None
    assert abs(gold_spot["avg_entry_price"] - 3050.0) < 0.001
    assert gold_spot["fill_count"] == 1
    assert abs(gold_spot["total_filled_qty"] - 0.6608) < 0.0001

    # Verify written to pm_entry_prices
    row = con.execute("SELECT avg_entry_price, fill_count FROM pm_entry_prices WHERE leg_id = 'gold_spot'").fetchone()
    assert row is not None
    assert abs(row[0] - 3050.0) < 0.001
    assert row[1] == 1

    # Verify pm_legs.entry_price updated
    ep = con.execute("SELECT entry_price FROM pm_legs WHERE leg_id = 'gold_spot'").fetchone()[0]
    assert abs(ep - 3050.0) < 0.001

    con.close()


def test_vwap_multiple_fills():
    """Multiple fills: avg_entry = SUM(px * sz) / SUM(sz)."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)

    # Two BUY fills for LONG spot leg at different prices
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t001", "XAUT0/USDC", "BUY", 3000.0, 0.3, 1711900000000, "pos_xyz_GOLD", "gold_spot"),
    )
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t002", "XAUT0/USDC", "BUY", 3100.0, 0.3608, 1711900100000, "pos_xyz_GOLD", "gold_spot"),
    )
    con.commit()

    # Hand calculation:
    # total_cost = 3000 * 0.3 + 3100 * 0.3608 = 900.0 + 1118.48 = 2018.48
    # total_qty = 0.3 + 0.3608 = 0.6608
    # avg_entry = 2018.48 / 0.6608 = 3054.63...
    expected_avg = (3000.0 * 0.3 + 3100.0 * 0.3608) / (0.3 + 0.3608)

    results = compute_entry_prices(con)
    gold_spot = next((r for r in results if r["leg_id"] == "gold_spot"), None)
    assert gold_spot is not None
    assert abs(gold_spot["avg_entry_price"] - expected_avg) < 0.01
    assert gold_spot["fill_count"] == 2

    con.close()


def test_vwap_short_leg_uses_sell_fills():
    """SHORT leg: opening fills are SELL side only."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)

    # SELL fill for SHORT perp leg (opening fill)
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t010", "xyz:GOLD", "SELL", 3055.0, 0.6608, 1711900000000, "pos_xyz_GOLD", "gold_perp"),
    )
    # BUY fill for SHORT perp leg (closing fill -- should be IGNORED)
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t011", "xyz:GOLD", "BUY", 3020.0, 0.1, 1711900100000, "pos_xyz_GOLD", "gold_perp"),
    )
    con.commit()

    results = compute_entry_prices(con)
    gold_perp = next((r for r in results if r["leg_id"] == "gold_perp"), None)
    assert gold_perp is not None
    assert abs(gold_perp["avg_entry_price"] - 3055.0) < 0.001
    assert gold_perp["fill_count"] == 1  # Only the SELL fill counts

    con.close()


def test_no_fills_skipped():
    """Legs with no fills are skipped (no entry in pm_entry_prices)."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)
    # No fills inserted

    results = compute_entry_prices(con)
    assert len(results) == 0

    # No rows in pm_entry_prices
    count = con.execute("SELECT COUNT(*) FROM pm_entry_prices").fetchone()[0]
    assert count == 0

    con.close()


def test_includes_closed_positions():
    """CLOSED positions also get entry prices computed (for historical analysis)."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)

    # Fill for closed position
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xmain", "t020", "GOOGL/USDC", "BUY", 175.0, 3.0, 1711900000000, "pos_closed", "closed_spot"),
    )
    con.commit()

    results = compute_entry_prices(con)
    closed = next((r for r in results if r["leg_id"] == "closed_spot"), None)
    assert closed is not None
    assert abs(closed["avg_entry_price"] - 175.0) < 0.001

    con.close()


def test_recompute_overwrites():
    """Running compute_entry_prices twice overwrites (INSERT OR REPLACE)."""
    from tracking.pipeline.entry_price import compute_entry_prices

    con = _create_test_db()
    _seed_positions(con)

    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t001", "XAUT0/USDC", "BUY", 3000.0, 0.5, 1711900000000, "pos_xyz_GOLD", "gold_spot"),
    )
    con.commit()

    compute_entry_prices(con)

    # Add another fill
    con.execute(
        "INSERT INTO pm_fills(venue, account_id, tid, inst_id, side, px, sz, ts, position_id, leg_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "0xalt", "t002", "XAUT0/USDC", "BUY", 3100.0, 0.1608, 1711900100000, "pos_xyz_GOLD", "gold_spot"),
    )
    con.commit()

    results = compute_entry_prices(con)
    gold_spot = next((r for r in results if r["leg_id"] == "gold_spot"), None)
    assert gold_spot is not None
    assert gold_spot["fill_count"] == 2

    # Only 1 row in pm_entry_prices (overwritten, not duplicated)
    count = con.execute("SELECT COUNT(*) FROM pm_entry_prices WHERE leg_id = 'gold_spot'").fetchone()[0]
    assert count == 1

    con.close()


def main() -> int:
    test_vwap_single_fill()
    print("PASS: test_vwap_single_fill")
    test_vwap_multiple_fills()
    print("PASS: test_vwap_multiple_fills")
    test_vwap_short_leg_uses_sell_fills()
    print("PASS: test_vwap_short_leg_uses_sell_fills")
    test_no_fills_skipped()
    print("PASS: test_no_fills_skipped")
    test_includes_closed_positions()
    print("PASS: test_includes_closed_positions")
    test_recompute_overwrites()
    print("PASS: test_recompute_overwrites")
    print("\nAll entry_price tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: Run tests to verify they fail

- [ ] **Run:**

```bash
.venv/bin/python tests/test_entry_price.py
```

Expected: `ModuleNotFoundError: No module named 'tracking.pipeline.entry_price'`

### Step 3: Implement entry_price module

- [ ] **Create `tracking/pipeline/entry_price.py`**

```python
"""VWAP entry price computation from fills.

Computes average entry price per leg using opening fills only:
- LONG legs: opening fills are side='BUY'
- SHORT legs: opening fills are side='SELL'

Formula: avg_entry = SUM(px * sz) / SUM(sz)

Writes results to pm_entry_prices (INSERT OR REPLACE on leg_id PK)
and updates pm_legs.entry_price.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any, Dict, List, Optional


def _now_ms() -> int:
    return int(time.time() * 1000)


def _opening_side(leg_side: str) -> str:
    """Return the fill side that constitutes an 'opening' fill for this leg.

    LONG leg opened by BUY fills.
    SHORT leg opened by SELL fills.
    """
    return "BUY" if leg_side == "LONG" else "SELL"


def compute_entry_prices(
    con: sqlite3.Connection,
    *,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Compute VWAP entry prices for all legs that have fills.

    Reads from pm_fills, writes to pm_entry_prices and pm_legs.entry_price.
    Processes ALL positions (including CLOSED) for historical analysis.

    Args:
        con: SQLite connection (must have pm_fills, pm_legs, pm_entry_prices tables)
        position_ids: Optional filter -- only compute for these positions

    Returns:
        List of result dicts: {leg_id, position_id, avg_entry_price, total_filled_qty,
                               total_cost, fill_count, first_fill_ts, last_fill_ts}
    """
    # Load legs (all statuses -- closed positions need entry prices too)
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        legs = con.execute(
            f"""
            SELECT l.leg_id, l.position_id, l.side
            FROM pm_legs l
            WHERE l.position_id IN ({placeholders})
            """,
            position_ids,
        ).fetchall()
    else:
        legs = con.execute(
            "SELECT leg_id, position_id, side FROM pm_legs"
        ).fetchall()

    if not legs:
        return []

    now = _now_ms()
    results: List[Dict[str, Any]] = []

    for leg_id, position_id, side in legs:
        opening_side = _opening_side(side)

        # Aggregate opening fills for this leg
        row = con.execute(
            """
            SELECT SUM(px * sz), SUM(sz), COUNT(*), MIN(ts), MAX(ts)
            FROM pm_fills
            WHERE leg_id = ? AND side = ?
            """,
            (leg_id, opening_side),
        ).fetchone()

        total_cost = row[0]
        total_qty = row[1]
        fill_count = row[2] or 0
        first_ts = row[3]
        last_ts = row[4]

        if fill_count == 0 or total_qty is None or total_qty <= 0:
            continue

        avg_entry = total_cost / total_qty

        # Write to pm_entry_prices (INSERT OR REPLACE on leg_id PK)
        con.execute(
            """
            INSERT OR REPLACE INTO pm_entry_prices
              (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
               fill_count, first_fill_ts, last_fill_ts, computed_at_ms, method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'VWAP')
            """,
            (leg_id, position_id, avg_entry, total_qty, total_cost,
             fill_count, first_ts, last_ts, now),
        )

        # Update pm_legs.entry_price
        con.execute(
            "UPDATE pm_legs SET entry_price = ? WHERE leg_id = ?",
            (avg_entry, leg_id),
        )

        results.append({
            "leg_id": leg_id,
            "position_id": position_id,
            "avg_entry_price": avg_entry,
            "total_filled_qty": total_qty,
            "total_cost": total_cost,
            "fill_count": fill_count,
            "first_fill_ts": first_ts,
            "last_fill_ts": last_ts,
        })

    con.commit()
    return results
```

### Step 4: Run tests to verify they pass

- [ ] **Run:**

```bash
.venv/bin/python tests/test_entry_price.py
```

Expected:
```
PASS: test_vwap_single_fill
PASS: test_vwap_multiple_fills
PASS: test_vwap_short_leg_uses_sell_fills
PASS: test_no_fills_skipped
PASS: test_includes_closed_positions
PASS: test_recompute_overwrites

All entry_price tests passed!
```

### Step 5: Commit

- [ ] **Commit:**

```bash
git add tracking/pipeline/entry_price.py tests/test_entry_price.py
git commit -m "feat: add VWAP entry price computation from fills (Phase 1b)"
```

---

## Task 2: Unrealized PnL Calculator

**Files:**
- Create: `tracking/pipeline/upnl.py`
- Create: `tests/test_upnl.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_upnl.py`**

```python
#!/usr/bin/env python3
"""Tests for unrealized PnL computation using bid/ask (ADR-001)."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db() -> sqlite3.Connection:
    """Create an in-memory test DB with required tables."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")

    con.executescript("""
        CREATE TABLE pm_positions (
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
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
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
          meta_json TEXT,
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE instruments_v3 (
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          symbol_key TEXT,
          symbol_base TEXT,
          PRIMARY KEY (venue, inst_id)
        );
        CREATE TABLE prices_v3 (
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          bid REAL,
          ask REAL,
          last REAL,
          mid REAL,
          mark REAL,
          index_price REAL,
          source TEXT,
          quality_flags TEXT,
          PRIMARY KEY (venue, inst_id, ts),
          FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
        );
    """)
    return con


def _seed_data(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed positions, legs, entry prices, and live prices."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        [
            ("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, entry_price, status, opened_at_ms, account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 0.6608, 3050.0, "OPEN", now_ms, "0xalt"),
            ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 0.6608, 3055.0, "OPEN", now_ms, "0xalt"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_entry_prices(leg_id, position_id, avg_entry_price, total_filled_qty, total_cost, fill_count, computed_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("gold_spot", "pos_xyz_GOLD", 3050.0, 0.6608, 3050.0 * 0.6608, 1, now_ms),
            ("gold_perp", "pos_xyz_GOLD", 3055.0, 0.6608, 3055.0 * 0.6608, 1, now_ms),
        ],
    )

    # Instruments required for FK in prices_v3
    con.executemany(
        "INSERT INTO instruments_v3(venue, inst_id) VALUES (?, ?)",
        [
            ("hyperliquid", "XAUT0/USDC"),
            ("hyperliquid", "xyz:GOLD"),
        ],
    )

    # Live prices: bid=3060, ask=3062 for spot; bid=3058, ask=3061 for perp
    con.executemany(
        "INSERT INTO prices_v3(venue, inst_id, ts, bid, ask, mid, last) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("hyperliquid", "XAUT0/USDC", now_ms, 3060.0, 3062.0, 3061.0, 3061.0),
            ("hyperliquid", "xyz:GOLD", now_ms, 3058.0, 3061.0, 3059.5, 3060.0),
        ],
    )
    con.commit()


def test_long_leg_uses_bid():
    """LONG leg uPnL = (bid - avg_entry) * size."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    results = compute_unrealized_pnl(con)
    gold_spot = next((r for r in results if r["leg_id"] == "gold_spot"), None)
    assert gold_spot is not None

    # bid=3060, entry=3050, size=0.6608
    # uPnL = (3060 - 3050) * 0.6608 = 6.608
    expected = (3060.0 - 3050.0) * 0.6608
    assert abs(gold_spot["unrealized_pnl"] - expected) < 0.01
    assert gold_spot["price_used"] == 3060.0
    assert gold_spot["price_type"] == "bid"

    # Verify pm_legs updated
    row = con.execute("SELECT unrealized_pnl, current_price FROM pm_legs WHERE leg_id = 'gold_spot'").fetchone()
    assert abs(row[0] - expected) < 0.01
    assert abs(row[1] - 3060.0) < 0.01

    con.close()


def test_short_leg_uses_ask():
    """SHORT leg uPnL = -(ask - avg_entry) * size."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    results = compute_unrealized_pnl(con)
    gold_perp = next((r for r in results if r["leg_id"] == "gold_perp"), None)
    assert gold_perp is not None

    # ask=3061, entry=3055, size=0.6608
    # uPnL = -(3061 - 3055) * 0.6608 = -3.9648
    expected = -(3061.0 - 3055.0) * 0.6608
    assert abs(gold_perp["unrealized_pnl"] - expected) < 0.01
    assert gold_perp["price_used"] == 3061.0
    assert gold_perp["price_type"] == "ask"

    con.close()


def test_position_level_upnl():
    """Position-level uPnL = SUM(leg uPnLs)."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    results = compute_unrealized_pnl(con)

    spot_upnl = (3060.0 - 3050.0) * 0.6608
    perp_upnl = -(3061.0 - 3055.0) * 0.6608
    expected_total = spot_upnl + perp_upnl

    pos = next((r for r in results if r.get("position_id") == "pos_xyz_GOLD" and "position_upnl" in r), None)
    if pos is not None:
        assert abs(pos["position_upnl"] - expected_total) < 0.01

    con.close()


def test_fallback_to_mid_when_bid_ask_missing():
    """When bid/ask is NULL, fallback to mid with quality flag."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    # Overwrite prices to have NULL bid/ask but valid mid
    con.execute("DELETE FROM prices_v3")
    con.execute(
        "INSERT INTO prices_v3(venue, inst_id, ts, bid, ask, mid, last) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "XAUT0/USDC", 1711900000000, None, None, 3061.0, 3061.0),
    )
    con.execute(
        "INSERT INTO prices_v3(venue, inst_id, ts, bid, ask, mid, last) VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("hyperliquid", "xyz:GOLD", 1711900000000, None, None, 3059.5, 3060.0),
    )
    con.commit()

    results = compute_unrealized_pnl(con)
    gold_spot = next((r for r in results if r["leg_id"] == "gold_spot"), None)
    assert gold_spot is not None
    assert gold_spot["price_type"] == "mid"  # fallback

    con.close()


def test_no_price_skipped():
    """Legs with no price data in prices_v3 are skipped."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    # Remove all prices
    con.execute("DELETE FROM prices_v3")
    con.commit()

    results = compute_unrealized_pnl(con)
    # Should still return results but with skipped legs flagged
    for r in results:
        if "leg_id" in r and r.get("skipped"):
            assert r["skip_reason"] == "no_price"

    con.close()


def test_no_entry_price_skipped():
    """Legs with no entry price (no fills) are skipped."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    con = _create_test_db()
    _seed_data(con)

    # Remove entry prices
    con.execute("DELETE FROM pm_entry_prices")
    con.commit()

    results = compute_unrealized_pnl(con)
    assert len(results) == 0  # No legs have entry prices

    con.close()


def main() -> int:
    test_long_leg_uses_bid()
    print("PASS: test_long_leg_uses_bid")
    test_short_leg_uses_ask()
    print("PASS: test_short_leg_uses_ask")
    test_position_level_upnl()
    print("PASS: test_position_level_upnl")
    test_fallback_to_mid_when_bid_ask_missing()
    print("PASS: test_fallback_to_mid_when_bid_ask_missing")
    test_no_price_skipped()
    print("PASS: test_no_price_skipped")
    test_no_entry_price_skipped()
    print("PASS: test_no_entry_price_skipped")
    print("\nAll upnl tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: Run tests to verify they fail

- [ ] **Run:**

```bash
.venv/bin/python tests/test_upnl.py
```

Expected: `ModuleNotFoundError: No module named 'tracking.pipeline.upnl'`

### Step 3: Implement upnl module

- [ ] **Create `tracking/pipeline/upnl.py`**

```python
"""Unrealized PnL computation using bid/ask prices (ADR-001).

Per-leg uPnL:
  LONG:  (current_bid - avg_entry) * size
  SHORT: -(current_ask - avg_entry) * size

Prices come from prices_v3 table (latest row for each venue + inst_id).
Fallback: if bid/ask NULL, use mid or last with quality flag.

Updates pm_legs.unrealized_pnl and pm_legs.current_price.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fetch_latest_price(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
) -> Optional[Dict[str, Any]]:
    """Fetch the most recent price row from prices_v3 for a given instrument.

    Returns dict with bid, ask, mid, last, ts, or None if not found.
    """
    row = con.execute(
        """
        SELECT bid, ask, mid, last, ts
        FROM prices_v3
        WHERE venue = ? AND inst_id = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (venue, inst_id),
    ).fetchone()

    if row is None:
        return None

    return {
        "bid": row[0],
        "ask": row[1],
        "mid": row[2],
        "last": row[3],
        "ts": row[4],
    }


def _resolve_exit_price(
    price_row: Dict[str, Any],
    side: str,
) -> Tuple[Optional[float], str]:
    """Resolve the exit price for a leg based on its side.

    LONG exits at bid (selling). SHORT exits at ask (buying to close).

    Returns (price, price_type) where price_type is 'bid', 'ask', 'mid', or 'last'.
    Falls back through bid/ask -> mid -> last.
    """
    if side == "LONG":
        preferred = price_row.get("bid")
        preferred_type = "bid"
    else:
        preferred = price_row.get("ask")
        preferred_type = "ask"

    if preferred is not None:
        return float(preferred), preferred_type

    # Fallback to mid
    mid = price_row.get("mid")
    if mid is not None:
        return float(mid), "mid"

    # Fallback to last
    last = price_row.get("last")
    if last is not None:
        return float(last), "last"

    return None, "none"


def compute_leg_upnl(side: str, avg_entry: float, exit_price: float, size: float) -> float:
    """Compute unrealized PnL for a single leg.

    Args:
        side: 'LONG' or 'SHORT'
        avg_entry: VWAP entry price
        exit_price: bid for LONG exit, ask for SHORT exit
        size: position size (always positive)
    """
    if side == "LONG":
        return (exit_price - avg_entry) * size
    else:
        return -(exit_price - avg_entry) * size


def compute_unrealized_pnl(
    con: sqlite3.Connection,
    *,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Compute unrealized PnL for all OPEN legs with entry prices.

    Reads from pm_entry_prices + prices_v3, updates pm_legs.unrealized_pnl
    and pm_legs.current_price.

    Only processes legs in OPEN or PAUSED positions (not CLOSED -- those have
    realized PnL, not unrealized).

    Args:
        con: SQLite connection
        position_ids: Optional filter

    Returns:
        List of per-leg result dicts + position-level summaries.
    """
    # Load legs with entry prices for non-closed positions
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        sql = f"""
            SELECT l.leg_id, l.position_id, l.venue, l.inst_id, l.side, l.size,
                   e.avg_entry_price
            FROM pm_legs l
            JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE l.position_id IN ({placeholders})
              AND p.status != 'CLOSED'
        """
        legs = con.execute(sql, position_ids).fetchall()
    else:
        sql = """
            SELECT l.leg_id, l.position_id, l.venue, l.inst_id, l.side, l.size,
                   e.avg_entry_price
            FROM pm_legs l
            JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE p.status != 'CLOSED'
        """
        legs = con.execute(sql).fetchall()

    if not legs:
        return []

    results: List[Dict[str, Any]] = []
    # Track position-level aggregation
    pos_upnl: Dict[str, float] = {}

    for leg_id, position_id, venue, inst_id, side, size, avg_entry in legs:
        price_row = _fetch_latest_price(con, venue, inst_id)

        if price_row is None:
            results.append({
                "leg_id": leg_id,
                "position_id": position_id,
                "skipped": True,
                "skip_reason": "no_price",
            })
            continue

        exit_price, price_type = _resolve_exit_price(price_row, side)

        if exit_price is None:
            results.append({
                "leg_id": leg_id,
                "position_id": position_id,
                "skipped": True,
                "skip_reason": "no_usable_price",
            })
            continue

        # Compute uPnL per ADR-001
        upnl = compute_leg_upnl(side, avg_entry, exit_price, size)

        # Update pm_legs
        meta = {}
        if price_type not in ("bid", "ask"):
            meta["price_fallback"] = price_type
        meta_json = json.dumps(meta) if meta else None

        con.execute(
            "UPDATE pm_legs SET unrealized_pnl = ?, current_price = ? WHERE leg_id = ?",
            (upnl, exit_price, leg_id),
        )

        results.append({
            "leg_id": leg_id,
            "position_id": position_id,
            "unrealized_pnl": upnl,
            "price_used": exit_price,
            "price_type": price_type,
            "avg_entry": avg_entry,
            "size": size,
            "side": side,
        })

        # Accumulate position-level uPnL
        pos_upnl[position_id] = pos_upnl.get(position_id, 0.0) + upnl

    con.commit()

    # Append position-level summaries
    for pid, total in pos_upnl.items():
        results.append({
            "position_id": pid,
            "position_upnl": total,
        })

    return results
```

### Step 4: Run tests to verify they pass

- [ ] **Run:**

```bash
.venv/bin/python tests/test_upnl.py
```

Expected:
```
PASS: test_long_leg_uses_bid
PASS: test_short_leg_uses_ask
PASS: test_position_level_upnl
PASS: test_fallback_to_mid_when_bid_ask_missing
PASS: test_no_price_skipped
PASS: test_no_entry_price_skipped

All upnl tests passed!
```

### Step 5: Commit

- [ ] **Commit:**

```bash
git add tracking/pipeline/upnl.py tests/test_upnl.py
git commit -m "feat: add unrealized PnL computation using bid/ask (ADR-001, Phase 1b)"
```

---

## Task 3: Entry/Exit Spread Calculator

**Files:**
- Create: `tracking/pipeline/spreads.py`
- Create: `tests/test_spreads.py`

### Step 1: Write failing tests

- [ ] **Create `tests/test_spreads.py`**

```python
#!/usr/bin/env python3
"""Tests for entry/exit spread computation (ADR-008)."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db() -> sqlite3.Connection:
    """Create an in-memory test DB with required tables."""
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")

    con.executescript("""
        CREATE TABLE pm_positions (
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
          raw_json TEXT,
          meta_json TEXT,
          account_id TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
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
          meta_json TEXT,
          FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
        );
        CREATE TABLE instruments_v3 (
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          symbol_key TEXT,
          symbol_base TEXT,
          PRIMARY KEY (venue, inst_id)
        );
        CREATE TABLE prices_v3 (
          venue TEXT NOT NULL,
          inst_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          bid REAL,
          ask REAL,
          last REAL,
          mid REAL,
          mark REAL,
          index_price REAL,
          source TEXT,
          quality_flags TEXT,
          PRIMARY KEY (venue, inst_id, ts),
          FOREIGN KEY (venue, inst_id) REFERENCES instruments_v3(venue, inst_id)
        );
        CREATE TABLE pm_spreads (
          spread_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
          position_id TEXT NOT NULL,
          long_leg_id TEXT NOT NULL,
          short_leg_id TEXT NOT NULL,
          entry_spread REAL,
          long_avg_entry REAL,
          short_avg_entry REAL,
          exit_spread REAL,
          long_exit_price REAL,
          short_exit_price REAL,
          spread_pnl_bps REAL,
          computed_at_ms INTEGER NOT NULL,
          meta_json TEXT,
          FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
          FOREIGN KEY (long_leg_id) REFERENCES pm_legs(leg_id),
          FOREIGN KEY (short_leg_id) REFERENCES pm_legs(leg_id),
          UNIQUE (position_id, long_leg_id, short_leg_id)
        );
    """)
    return con


def _seed_simple(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed a simple SPOT_PERP position: 1 spot + 1 perp."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        [("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms)],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 0.6608, "OPEN", now_ms, "0xalt"),
            ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 0.6608, "OPEN", now_ms, "0xalt"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_entry_prices(leg_id, position_id, avg_entry_price, total_filled_qty, total_cost, fill_count, computed_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("gold_spot", "pos_xyz_GOLD", 3050.0, 0.6608, 3050.0 * 0.6608, 1, now_ms),
            ("gold_perp", "pos_xyz_GOLD", 3055.0, 0.6608, 3055.0 * 0.6608, 1, now_ms),
        ],
    )
    con.executemany(
        "INSERT INTO instruments_v3(venue, inst_id) VALUES (?, ?)",
        [("hyperliquid", "XAUT0/USDC"), ("hyperliquid", "xyz:GOLD")],
    )
    con.executemany(
        "INSERT INTO prices_v3(venue, inst_id, ts, bid, ask, mid, last) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("hyperliquid", "XAUT0/USDC", now_ms, 3060.0, 3062.0, 3061.0, 3061.0),
            ("hyperliquid", "xyz:GOLD", now_ms, 3058.0, 3061.0, 3059.5, 3060.0),
        ],
    )
    con.commit()


def _seed_split_leg(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed a split-leg position: 1 spot + 2 perps (like HYPE)."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms) VALUES (?, ?, ?, ?, ?, ?)",
        [("pos_hyna_HYPE", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms)],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE/USDC", "LONG", 126.98, "OPEN", now_ms, "0xalt"),
            ("hype_perp_hyna", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 89.48, "OPEN", now_ms, "0xalt"),
            ("hype_perp_native", "pos_hyna_HYPE", "hyperliquid", "HYPE", "SHORT", 37.50, "OPEN", now_ms, "0xalt"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_entry_prices(leg_id, position_id, avg_entry_price, total_filled_qty, total_cost, fill_count, computed_at_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("hype_spot", "pos_hyna_HYPE", 20.00, 126.98, 20.00 * 126.98, 3, now_ms),
            ("hype_perp_hyna", "pos_hyna_HYPE", 20.05, 89.48, 20.05 * 89.48, 2, now_ms),
            ("hype_perp_native", "pos_hyna_HYPE", 20.03, 37.50, 20.03 * 37.50, 1, now_ms),
        ],
    )
    con.executemany(
        "INSERT INTO instruments_v3(venue, inst_id) VALUES (?, ?)",
        [("hyperliquid", "HYPE/USDC"), ("hyperliquid", "hyna:HYPE"), ("hyperliquid", "HYPE")],
    )
    con.executemany(
        "INSERT INTO prices_v3(venue, inst_id, ts, bid, ask, mid, last) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("hyperliquid", "HYPE/USDC", now_ms, 19.90, 19.92, 19.91, 19.91),
            ("hyperliquid", "hyna:HYPE", now_ms, 19.88, 19.93, 19.905, 19.90),
            ("hyperliquid", "HYPE", now_ms, 19.89, 19.92, 19.905, 19.91),
        ],
    )
    con.commit()


def test_simple_spread():
    """Single spot + single perp: entry/exit spread computed correctly."""
    from tracking.pipeline.spreads import compute_spreads

    con = _create_test_db()
    _seed_simple(con)

    results = compute_spreads(con)
    assert len(results) == 1

    r = results[0]
    assert r["position_id"] == "pos_xyz_GOLD"
    assert r["long_leg_id"] == "gold_spot"
    assert r["short_leg_id"] == "gold_perp"

    # entry_spread = 3050 / 3055 - 1 = -0.001636...
    expected_entry = 3050.0 / 3055.0 - 1.0
    assert abs(r["entry_spread"] - expected_entry) < 1e-6

    # exit_spread = long_bid / short_ask - 1 = 3060 / 3061 - 1 = -0.000327...
    expected_exit = 3060.0 / 3061.0 - 1.0
    assert abs(r["exit_spread"] - expected_exit) < 1e-6

    # spread_pnl_bps = (exit - entry) * 10000
    expected_bps = (expected_exit - expected_entry) * 10000
    assert abs(r["spread_pnl_bps"] - expected_bps) < 0.01

    # Verify written to DB
    row = con.execute(
        "SELECT entry_spread, exit_spread, spread_pnl_bps FROM pm_spreads WHERE position_id = 'pos_xyz_GOLD'"
    ).fetchone()
    assert row is not None
    assert abs(row[0] - expected_entry) < 1e-6
    assert abs(row[1] - expected_exit) < 1e-6

    con.close()


def test_split_leg_generates_two_sub_pairs():
    """Split-leg position (1 spot + 2 perps) generates 2 sub-pair spreads."""
    from tracking.pipeline.spreads import compute_spreads

    con = _create_test_db()
    _seed_split_leg(con)

    results = compute_spreads(con)
    assert len(results) == 2

    # Both sub-pairs share the same long leg
    assert all(r["long_leg_id"] == "hype_spot" for r in results)

    # Short legs are different
    short_ids = {r["short_leg_id"] for r in results}
    assert short_ids == {"hype_perp_hyna", "hype_perp_native"}

    # Verify sub-pair 1: hype_spot vs hype_perp_hyna
    hyna = next(r for r in results if r["short_leg_id"] == "hype_perp_hyna")
    expected_entry_hyna = 20.00 / 20.05 - 1.0
    assert abs(hyna["entry_spread"] - expected_entry_hyna) < 1e-6
    expected_exit_hyna = 19.90 / 19.93 - 1.0  # spot bid / perp ask
    assert abs(hyna["exit_spread"] - expected_exit_hyna) < 1e-6

    # Verify sub-pair 2: hype_spot vs hype_perp_native
    native = next(r for r in results if r["short_leg_id"] == "hype_perp_native")
    expected_entry_native = 20.00 / 20.03 - 1.0
    assert abs(native["entry_spread"] - expected_entry_native) < 1e-6
    expected_exit_native = 19.90 / 19.92 - 1.0  # spot bid / perp ask
    assert abs(native["exit_spread"] - expected_exit_native) < 1e-6

    con.close()


def test_missing_entry_price_skips():
    """Sub-pair with missing entry price is skipped."""
    from tracking.pipeline.spreads import compute_spreads

    con = _create_test_db()
    _seed_simple(con)

    # Remove perp entry price
    con.execute("DELETE FROM pm_entry_prices WHERE leg_id = 'gold_perp'")
    con.commit()

    results = compute_spreads(con)
    assert len(results) == 0  # Can't compute spread without both entry prices

    con.close()


def test_missing_exit_price_partial():
    """Sub-pair with missing exit price: entry_spread computed, exit_spread NULL."""
    from tracking.pipeline.spreads import compute_spreads

    con = _create_test_db()
    _seed_simple(con)

    # Remove live prices for perp
    con.execute("DELETE FROM prices_v3 WHERE inst_id = 'xyz:GOLD'")
    con.commit()

    results = compute_spreads(con)
    assert len(results) == 1

    r = results[0]
    expected_entry = 3050.0 / 3055.0 - 1.0
    assert abs(r["entry_spread"] - expected_entry) < 1e-6
    assert r["exit_spread"] is None
    assert r["spread_pnl_bps"] is None

    con.close()


def test_recompute_overwrites():
    """Running compute_spreads twice overwrites (INSERT OR REPLACE via UNIQUE constraint)."""
    from tracking.pipeline.spreads import compute_spreads

    con = _create_test_db()
    _seed_simple(con)

    compute_spreads(con)
    compute_spreads(con)

    count = con.execute("SELECT COUNT(*) FROM pm_spreads WHERE position_id = 'pos_xyz_GOLD'").fetchone()[0]
    assert count == 1  # Not duplicated

    con.close()


def main() -> int:
    test_simple_spread()
    print("PASS: test_simple_spread")
    test_split_leg_generates_two_sub_pairs()
    print("PASS: test_split_leg_generates_two_sub_pairs")
    test_missing_entry_price_skips()
    print("PASS: test_missing_entry_price_skips")
    test_missing_exit_price_partial()
    print("PASS: test_missing_exit_price_partial")
    test_recompute_overwrites()
    print("PASS: test_recompute_overwrites")
    print("\nAll spreads tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: Run tests to verify they fail

- [ ] **Run:**

```bash
.venv/bin/python tests/test_spreads.py
```

Expected: `ModuleNotFoundError: No module named 'tracking.pipeline.spreads'`

### Step 3: Implement spreads module

- [ ] **Create `tracking/pipeline/spreads.py`**

```python
"""Entry/exit spread computation per sub-pair (ADR-008).

For SPOT_PERP positions:
  entry_spread = long_avg_entry / short_avg_entry - 1
  exit_spread  = long_exit_bid / short_exit_ask - 1
  spread_pnl_bps = (exit_spread - entry_spread) * 10000

For split-leg positions (1 LONG + N SHORTs), each SHORT leg pairs with
the LONG leg to form an independent sub-pair.

Writes to pm_spreads table (INSERT OR REPLACE on UNIQUE constraint).
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fetch_latest_price(
    con: sqlite3.Connection,
    venue: str,
    inst_id: str,
) -> Optional[Dict[str, Any]]:
    """Fetch the most recent price row from prices_v3."""
    row = con.execute(
        """
        SELECT bid, ask, mid, last, ts
        FROM prices_v3
        WHERE venue = ? AND inst_id = ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (venue, inst_id),
    ).fetchone()

    if row is None:
        return None

    return {
        "bid": row[0],
        "ask": row[1],
        "mid": row[2],
        "last": row[3],
        "ts": row[4],
    }


def _get_exit_bid(price_row: Dict[str, Any]) -> Optional[float]:
    """Get best bid from price row. Fallback: mid -> last."""
    if price_row.get("bid") is not None:
        return float(price_row["bid"])
    if price_row.get("mid") is not None:
        return float(price_row["mid"])
    if price_row.get("last") is not None:
        return float(price_row["last"])
    return None


def _get_exit_ask(price_row: Dict[str, Any]) -> Optional[float]:
    """Get best ask from price row. Fallback: mid -> last."""
    if price_row.get("ask") is not None:
        return float(price_row["ask"])
    if price_row.get("mid") is not None:
        return float(price_row["mid"])
    if price_row.get("last") is not None:
        return float(price_row["last"])
    return None


def entry_spread(long_avg_entry: float, short_avg_entry: float) -> float:
    """Entry basis spread. Positive = long leg at premium."""
    if short_avg_entry == 0:
        return 0.0
    return long_avg_entry / short_avg_entry - 1.0


def exit_spread(long_exit_bid: float, short_exit_ask: float) -> float:
    """Exit basis spread using executable prices."""
    if short_exit_ask == 0:
        return 0.0
    return long_exit_bid / short_exit_ask - 1.0


def spread_pnl_bps(entry: float, exit_val: float) -> float:
    """Spread P&L in basis points."""
    return (exit_val - entry) * 10000


def compute_spreads(
    con: sqlite3.Connection,
    *,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Compute entry/exit spreads for all active positions (non-CLOSED).

    For each position, identifies LONG leg(s) and SHORT leg(s),
    then creates sub-pairs (each SHORT paired with each LONG).

    Args:
        con: SQLite connection
        position_ids: Optional filter

    Returns:
        List of sub-pair spread dicts.
    """
    # Load all active positions (not CLOSED)
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        pos_sql = f"""
            SELECT position_id FROM pm_positions
            WHERE position_id IN ({placeholders})
              AND status != 'CLOSED'
        """
        pos_rows = con.execute(pos_sql, position_ids).fetchall()
    else:
        pos_sql = """
            SELECT position_id FROM pm_positions
            WHERE status != 'CLOSED'
        """
        pos_rows = con.execute(pos_sql).fetchall()

    if not pos_rows:
        return []

    now = _now_ms()
    results: List[Dict[str, Any]] = []

    for (position_id,) in pos_rows:
        # Load legs with entry prices
        legs = con.execute(
            """
            SELECT l.leg_id, l.venue, l.inst_id, l.side,
                   e.avg_entry_price
            FROM pm_legs l
            JOIN pm_entry_prices e ON e.leg_id = l.leg_id
            WHERE l.position_id = ?
            """,
            (position_id,),
        ).fetchall()

        long_legs = [(lid, v, iid, ep) for lid, v, iid, s, ep in legs if s == "LONG"]
        short_legs = [(lid, v, iid, ep) for lid, v, iid, s, ep in legs if s == "SHORT"]

        if not long_legs or not short_legs:
            continue

        # Generate sub-pairs: each SHORT paired with each LONG
        for long_lid, long_venue, long_iid, long_entry in long_legs:
            for short_lid, short_venue, short_iid, short_entry in short_legs:
                if long_entry <= 0 or short_entry <= 0:
                    continue

                # Entry spread
                entry_spread_val = entry_spread(long_entry, short_entry)

                # Exit spread (from live prices)
                long_price_row = _fetch_latest_price(con, long_venue, long_iid)
                short_price_row = _fetch_latest_price(con, short_venue, short_iid)

                exit_spread_val = None
                long_exit_px = None
                short_exit_px = None
                spread_pnl_bps_val = None

                if long_price_row is not None and short_price_row is not None:
                    long_exit_px = _get_exit_bid(long_price_row)
                    short_exit_px = _get_exit_ask(short_price_row)

                    if long_exit_px is not None and short_exit_px is not None and short_exit_px > 0:
                        exit_spread_val = exit_spread(long_exit_px, short_exit_px)
                        spread_pnl_bps_val = spread_pnl_bps(entry_spread_val, exit_spread_val)

                # Write to pm_spreads (upsert via delete + insert for UNIQUE constraint)
                # SQLite INSERT OR REPLACE works on UNIQUE constraints
                con.execute(
                    """
                    DELETE FROM pm_spreads
                    WHERE position_id = ? AND long_leg_id = ? AND short_leg_id = ?
                    """,
                    (position_id, long_lid, short_lid),
                )
                con.execute(
                    """
                    INSERT INTO pm_spreads
                      (position_id, long_leg_id, short_leg_id,
                       entry_spread, long_avg_entry, short_avg_entry,
                       exit_spread, long_exit_price, short_exit_price,
                       spread_pnl_bps, computed_at_ms)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (position_id, long_lid, short_lid,
                     entry_spread_val, long_entry, short_entry,
                     exit_spread_val, long_exit_px, short_exit_px,
                     spread_pnl_bps_val, now),
                )

                results.append({
                    "position_id": position_id,
                    "long_leg_id": long_lid,
                    "short_leg_id": short_lid,
                    "entry_spread": entry_spread_val,
                    "exit_spread": exit_spread_val,
                    "long_avg_entry": long_entry,
                    "short_avg_entry": short_entry,
                    "long_exit_price": long_exit_px,
                    "short_exit_price": short_exit_px,
                    "spread_pnl_bps": spread_pnl_bps_val,
                })

    con.commit()
    return results
```

### Step 4: Run tests to verify they pass

- [ ] **Run:**

```bash
.venv/bin/python tests/test_spreads.py
```

Expected:
```
PASS: test_simple_spread
PASS: test_split_leg_generates_two_sub_pairs
PASS: test_missing_entry_price_skips
PASS: test_missing_exit_price_partial
PASS: test_recompute_overwrites

All spreads tests passed!
```

### Step 5: Commit

- [ ] **Commit:**

```bash
git add tracking/pipeline/spreads.py tests/test_spreads.py
git commit -m "feat: add entry/exit spread computation per sub-pair (ADR-008, Phase 1b)"
```

---

## Task 4: Portfolio Aggregator

**Files:**
- Create: `tracking/pipeline/portfolio.py`

### Step 1: Implement portfolio module

- [ ] **Create `tracking/pipeline/portfolio.py`**

```python
"""Portfolio-level aggregation and snapshot writer.

Computes:
- Total equity from latest pm_account_snapshots (across all wallets)
- Funding today: SUM(FUNDING cashflows WHERE ts >= today_start_utc)
- Funding all-time: SUM(FUNDING cashflows WHERE ts >= tracking_start_date)
- Fees all-time: SUM(FEE cashflows WHERE ts >= tracking_start_date)
- Total unrealized PnL from pm_legs
- Cashflow-adjusted APR: (equity_change - net_deposits) / prior_equity / days * 365

Writes hourly snapshot to pm_portfolio_snapshots.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


# Default tracking start date (when the system started monitoring)
DEFAULT_TRACKING_START = "2026-01-15"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_start_ms() -> int:
    """Return epoch ms for start of current UTC day."""
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.timestamp() * 1000)


def _date_to_ms(date_str: str) -> int:
    """Convert ISO date string (YYYY-MM-DD) to epoch ms."""
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _get_total_equity(con: sqlite3.Connection) -> Dict[str, Any]:
    """Get total equity from latest pm_account_snapshots per account_id.

    Returns:
        {
            "total_equity_usd": float,
            "equity_by_account": {"main": float, "alt": float, ...},
        }
    """
    # Get latest snapshot per account_id
    rows = con.execute(
        """
        SELECT a.account_id, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) as max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    equity_by_account: Dict[str, float] = {}
    total = 0.0

    for account_id, balance in rows:
        if balance is not None:
            equity_by_account[account_id] = float(balance)
            total += float(balance)

    return {
        "total_equity_usd": total,
        "equity_by_account": equity_by_account,
    }


def _get_funding_sum(
    con: sqlite3.Connection,
    *,
    since_ms: int,
) -> float:
    """Sum all FUNDING cashflows since a given timestamp."""
    row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0.0)
        FROM pm_cashflows
        WHERE cf_type = 'FUNDING' AND ts >= ?
        """,
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_fees_sum(
    con: sqlite3.Connection,
    *,
    since_ms: int,
) -> float:
    """Sum all FEE cashflows since a given timestamp."""
    row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0.0)
        FROM pm_cashflows
        WHERE cf_type = 'FEE' AND ts >= ?
        """,
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_total_unrealized_pnl(con: sqlite3.Connection) -> float:
    """Sum unrealized_pnl from all OPEN legs in non-CLOSED positions."""
    row = con.execute(
        """
        SELECT COALESCE(SUM(l.unrealized_pnl), 0.0)
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.status != 'CLOSED' AND l.unrealized_pnl IS NOT NULL
        """
    ).fetchone()
    return float(row[0])


def _get_net_deposits(
    con: sqlite3.Connection,
    *,
    since_ms: int,
) -> float:
    """Net deposits = SUM(DEPOSIT amounts) + SUM(WITHDRAW amounts).

    Deposits are positive, Withdrawals are negative (by convention in pm_cashflows).
    """
    row = con.execute(
        """
        SELECT COALESCE(SUM(amount), 0.0)
        FROM pm_cashflows
        WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ?
        """,
        (since_ms,),
    ).fetchone()
    return float(row[0])


def _get_prior_equity(
    con: sqlite3.Connection,
    *,
    hours_ago: int = 24,
) -> Optional[float]:
    """Get total equity from the snapshot closest to N hours ago."""
    target_ms = _now_ms() - hours_ago * 3600 * 1000

    row = con.execute(
        """
        SELECT total_equity_usd
        FROM pm_portfolio_snapshots
        WHERE ts <= ?
        ORDER BY ts DESC
        LIMIT 1
        """,
        (target_ms,),
    ).fetchone()

    if row is None or row[0] is None:
        return None
    return float(row[0])


def compute_position_net_funding(con: sqlite3.Connection, position_id: str) -> float:
    """Compute net funding earned for a specific position (all legs combined).

    For SPOT_PERP: only short leg has funding (positive).
    For PERP_PERP: both legs have funding. Long funding is typically negative,
    short funding positive. Returns the net sum.
    """
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
        (position_id,),
    ).fetchone()
    return float(row[0])


def compute_portfolio_snapshot(
    con: sqlite3.Connection,
    *,
    tracking_start_date: str = DEFAULT_TRACKING_START,
) -> Dict[str, Any]:
    """Compute and write a portfolio snapshot.

    This is designed to run hourly. The UNIQUE index on
    CAST(ts / 3600000 AS INTEGER) prevents duplicate hourly entries --
    we use INSERT OR REPLACE to overwrite within the same hour.

    Args:
        con: SQLite connection
        tracking_start_date: ISO date (YYYY-MM-DD) for all-time calculations

    Returns:
        Dict with all computed metrics.
    """
    now = _now_ms()
    today_start = _today_start_ms()
    tracking_start_ms = _date_to_ms(tracking_start_date)

    # 1. Total equity
    equity_data = _get_total_equity(con)
    total_equity = equity_data["total_equity_usd"]
    equity_by_account = equity_data["equity_by_account"]

    # 2. Total unrealized PnL
    total_upnl = _get_total_unrealized_pnl(con)

    # 3. Funding today
    funding_today = _get_funding_sum(con, since_ms=today_start)

    # 4. Funding all-time
    funding_alltime = _get_funding_sum(con, since_ms=tracking_start_ms)

    # 5. Fees all-time
    fees_alltime = _get_fees_sum(con, since_ms=tracking_start_ms)

    # 6. Daily change and APR
    prior_equity = _get_prior_equity(con, hours_ago=24)
    daily_change = None
    cashflow_adjusted_change = None
    apr_daily = None

    if prior_equity is not None and prior_equity > 0:
        daily_change = total_equity - prior_equity

        # Net deposits in last 24h
        net_deposits_24h = _get_net_deposits(
            con, since_ms=now - 24 * 3600 * 1000
        )
        cashflow_adjusted_change = daily_change - net_deposits_24h

        # APR = (organic_change / prior_equity) * 365
        apr_daily = (cashflow_adjusted_change / prior_equity) * 365.0

    snapshot = {
        "ts": now,
        "total_equity_usd": total_equity,
        "equity_by_account_json": json.dumps(equity_by_account),
        "total_unrealized_pnl": total_upnl,
        "total_funding_today": funding_today,
        "total_funding_alltime": funding_alltime,
        "total_fees_alltime": fees_alltime,
        "daily_change_usd": daily_change,
        "cashflow_adjusted_change": cashflow_adjusted_change,
        "apr_daily": apr_daily,
        "tracking_start_date": tracking_start_date,
    }

    # Write to pm_portfolio_snapshots
    # The UNIQUE index on CAST(ts / 3600000 AS INTEGER) means only one row per hour.
    # We delete + insert to handle the hourly upsert cleanly.
    hour_bucket = now // 3600000
    con.execute(
        """
        DELETE FROM pm_portfolio_snapshots
        WHERE CAST(ts / 3600000 AS INTEGER) = ?
        """,
        (hour_bucket,),
    )
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots
          (ts, total_equity_usd, equity_by_account_json,
           total_unrealized_pnl, total_funding_today, total_funding_alltime,
           total_fees_alltime, daily_change_usd, cashflow_adjusted_change,
           apr_daily, tracking_start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (now, total_equity, json.dumps(equity_by_account),
         total_upnl, funding_today, funding_alltime,
         fees_alltime, daily_change, cashflow_adjusted_change,
         apr_daily, tracking_start_date),
    )
    con.commit()

    return snapshot
```

### Step 2: Verify manually (no unit tests needed -- integration test with live DB)

- [ ] **Smoke test against live DB:**

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
from pathlib import Path
from tracking.pipeline.portfolio import compute_portfolio_snapshot

ROOT = Path('.')
DB = ROOT / 'tracking' / 'db' / 'arbit_v3.db'

con = sqlite3.connect(str(DB))
con.execute('PRAGMA foreign_keys = ON')

try:
    result = compute_portfolio_snapshot(con)
    print(f'Total equity: \${result[\"total_equity_usd\"]:,.2f}')
    print(f'Unrealized PnL: \${result[\"total_unrealized_pnl\"]:,.2f}')
    print(f'Funding today: \${result[\"total_funding_today\"]:,.2f}')
    print(f'Funding all-time: \${result[\"total_funding_alltime\"]:,.2f}')
    print(f'Fees all-time: \${result[\"total_fees_alltime\"]:,.2f}')
    print(f'Daily change: {result[\"daily_change_usd\"]}')
    print(f'APR (daily): {result[\"apr_daily\"]}')
    print('OK: portfolio snapshot computed')
finally:
    con.close()
"
```

Expected: Prints portfolio metrics (values depend on current DB state). Key check: no errors and total_equity > 0.

### Step 3: Commit

- [ ] **Commit:**

```bash
git add tracking/pipeline/portfolio.py
git commit -m "feat: add portfolio aggregator with equity, funding, and APR computation (Phase 1b)"
```

---

## Task 5: Hourly Pipeline Orchestrator

**Files:**
- Create: `scripts/pipeline_hourly.py`

### Step 1: Implement orchestrator

- [ ] **Create `scripts/pipeline_hourly.py`**

```python
#!/usr/bin/env python3
"""Hourly pipeline orchestrator.

Runs all computation steps in order:
1. Fetch spot_meta (symbol resolution cache)
2. Ingest fills from Hyperliquid
3. Compute entry prices (VWAP)
4. Compute unrealized PnL (bid/ask)
5. Compute entry/exit spreads
6. Compute portfolio snapshot

Each step logs its result. Errors in one step do not block subsequent steps.

Usage:
  source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py
  source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py --skip-ingest  # recompute only
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DB_DEFAULT = ROOT / "tracking" / "db" / "arbit_v3.db"


def _log(step: str, msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    print(f"[{ts}] [{step}] {msg}")


def _run_step(step_name: str, fn, *args, **kwargs):
    """Run a pipeline step, catching and logging errors."""
    try:
        _log(step_name, "starting...")
        result = fn(*args, **kwargs)
        _log(step_name, f"OK: {result}")
        return result
    except Exception as e:
        _log(step_name, f"ERROR: {e}")
        traceback.print_exc()
        return None


def step_spot_meta() -> dict:
    """Fetch spotMeta and return the index map."""
    from tracking.pipeline.spot_meta import fetch_spot_index_map

    cache = fetch_spot_index_map()
    return {"pairs_loaded": len(cache), "cache": cache}


def step_ingest_fills(con: sqlite3.Connection, spot_cache: dict, since_hours: int = 504) -> str:
    """Ingest fills from Hyperliquid for all active legs.

    Uses the fill_ingester module from Phase 1a.
    """
    from tracking.pipeline.fill_ingester import (
        load_fill_targets,
        ingest_hl_fills,
    )

    targets = load_fill_targets(con)
    if not targets:
        return "no active fill targets"

    n = ingest_hl_fills(con, targets=targets, spot_index_map=spot_cache, since_hours=since_hours)
    return f"{n} new fills ingested"


def step_entry_prices(con: sqlite3.Connection) -> str:
    """Compute VWAP entry prices for all legs with fills."""
    from tracking.pipeline.entry_price import compute_entry_prices

    results = compute_entry_prices(con)
    return f"{len(results)} entry prices computed"


def step_upnl(con: sqlite3.Connection) -> str:
    """Compute unrealized PnL for all OPEN legs."""
    from tracking.pipeline.upnl import compute_unrealized_pnl

    results = compute_unrealized_pnl(con)
    leg_results = [r for r in results if "leg_id" in r and not r.get("skipped")]
    skipped = [r for r in results if r.get("skipped")]
    pos_results = [r for r in results if "position_upnl" in r]

    parts = [f"{len(leg_results)} legs computed"]
    if skipped:
        parts.append(f"{len(skipped)} skipped")
    if pos_results:
        total_upnl = sum(r["position_upnl"] for r in pos_results)
        parts.append(f"total uPnL=${total_upnl:+.2f}")
    return ", ".join(parts)


def step_spreads(con: sqlite3.Connection) -> str:
    """Compute entry/exit spreads for all OPEN positions."""
    from tracking.pipeline.spreads import compute_spreads

    results = compute_spreads(con)
    return f"{len(results)} sub-pair spreads computed"


def step_portfolio(con: sqlite3.Connection) -> str:
    """Compute and write portfolio snapshot."""
    from tracking.pipeline.portfolio import compute_portfolio_snapshot

    snap = compute_portfolio_snapshot(con)
    equity = snap.get("total_equity_usd", 0)
    apr = snap.get("apr_daily")
    apr_str = f"{apr:.1f}%" if apr is not None else "N/A"
    return f"equity=${equity:,.2f}, APR={apr_str}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Hourly pipeline orchestrator")
    ap.add_argument("--db", type=Path, default=DB_DEFAULT)
    ap.add_argument("--skip-ingest", action="store_true", help="Skip fill ingestion (recompute only)")
    ap.add_argument("--since-hours", type=int, default=504, help="Fill lookback window in hours (default 21 days)")
    args = ap.parse_args()

    if not args.db.exists():
        _log("init", f"DB not found: {args.db}")
        return 1

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA foreign_keys = ON")

    try:
        # Step 1: Spot meta (needed for fill ingestion)
        spot_result = None
        if not args.skip_ingest:
            spot_result = _run_step("spot_meta", step_spot_meta)

        # Step 2: Ingest fills
        if not args.skip_ingest and spot_result is not None:
            spot_cache = spot_result.get("cache", {})
            _run_step("ingest_fills", step_ingest_fills, con, spot_cache, args.since_hours)

        # Step 3: Compute entry prices
        _run_step("entry_prices", step_entry_prices, con)

        # Step 4: Compute uPnL
        _run_step("upnl", step_upnl, con)

        # Step 5: Compute spreads
        _run_step("spreads", step_spreads, con)

        # Step 6: Portfolio snapshot
        _run_step("portfolio", step_portfolio, con)

        _log("done", "pipeline complete")
        return 0

    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

### Step 2: Verify dry-run (recompute only, no API calls)

- [ ] **Run with --skip-ingest:**

```bash
source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py --skip-ingest
```

Expected output (approximate):
```
[2026-03-29 XX:XX:XX] [entry_prices] starting...
[2026-03-29 XX:XX:XX] [entry_prices] OK: N entry prices computed
[2026-03-29 XX:XX:XX] [upnl] starting...
[2026-03-29 XX:XX:XX] [upnl] OK: N legs computed, ...
[2026-03-29 XX:XX:XX] [spreads] starting...
[2026-03-29 XX:XX:XX] [spreads] OK: N sub-pair spreads computed
[2026-03-29 XX:XX:XX] [portfolio] starting...
[2026-03-29 XX:XX:XX] [portfolio] OK: equity=$XX,XXX.XX, APR=...
[2026-03-29 XX:XX:XX] [done] pipeline complete
```

Key checks:
- No Python exceptions
- Each step logs "OK" or handles missing data gracefully
- Entry prices show 0 (no fills yet until Phase 1a fills are ingested)

### Step 3: Commit

- [ ] **Commit:**

```bash
git add scripts/pipeline_hourly.py
git commit -m "feat: add hourly pipeline orchestrator for computation layer (Phase 1b)"
```

---

## Task 6: Integration Verification

### Step 1: Run all tests together

- [ ] **Run all Phase 1b tests:**

```bash
.venv/bin/python tests/test_entry_price.py && \
.venv/bin/python tests/test_upnl.py && \
.venv/bin/python tests/test_spreads.py
```

Expected: All tests pass.

### Step 2: End-to-end verification with synthetic data

- [ ] **Run end-to-end check with the live DB:**

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
from pathlib import Path

DB = Path('tracking/db/arbit_v3.db')
con = sqlite3.connect(str(DB))
con.execute('PRAGMA foreign_keys = ON')

# Check pm_fills exist (requires Phase 1a)
fill_count = con.execute('SELECT COUNT(*) FROM pm_fills').fetchone()[0]
print(f'Fills in DB: {fill_count}')

if fill_count == 0:
    print('NOTE: No fills yet -- Phase 1a fill ingestion has not run.')
    print('Computation layer is ready but needs fills to produce results.')
    con.close()
    exit(0)

# If fills exist, verify entry prices computed
from tracking.pipeline.entry_price import compute_entry_prices
results = compute_entry_prices(con)
print(f'Entry prices computed: {len(results)}')
for r in results:
    print(f\"  {r['leg_id']}: avg_entry={r['avg_entry_price']:.4f}, fills={r['fill_count']}\")

# Verify uPnL
from tracking.pipeline.upnl import compute_unrealized_pnl
upnl_results = compute_unrealized_pnl(con)
leg_upnls = [r for r in upnl_results if 'unrealized_pnl' in r]
print(f'uPnL computed for {len(leg_upnls)} legs')
for r in leg_upnls:
    print(f\"  {r['leg_id']}: uPnL=\${r['unrealized_pnl']:+.2f} ({r['price_type']} @ {r['price_used']:.2f})\")

# Verify spreads
from tracking.pipeline.spreads import compute_spreads
spread_results = compute_spreads(con)
print(f'Spreads computed: {len(spread_results)} sub-pairs')
for r in spread_results:
    entry_bps = r['entry_spread'] * 10000 if r['entry_spread'] is not None else None
    exit_bps = r['exit_spread'] * 10000 if r['exit_spread'] is not None else None
    pnl = r['spread_pnl_bps']
    print(f\"  {r['long_leg_id']} vs {r['short_leg_id']}: entry={entry_bps:.1f}bps, exit={exit_bps:.1f}bps, pnl={pnl:+.1f}bps\" if pnl is not None else f\"  {r['long_leg_id']} vs {r['short_leg_id']}: entry={entry_bps:.1f}bps, exit=N/A\")

# Verify portfolio snapshot
from tracking.pipeline.portfolio import compute_portfolio_snapshot
snap = compute_portfolio_snapshot(con)
print(f\"Portfolio: equity=\${snap['total_equity_usd']:,.2f}, funding_today=\${snap['total_funding_today']:.2f}\")

con.close()
print('\\nEnd-to-end verification complete!')
"
```

### Step 3: Verify DB writes

- [ ] **Check DB tables populated:**

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
con = sqlite3.connect('tracking/db/arbit_v3.db')
for table in ['pm_entry_prices', 'pm_spreads', 'pm_portfolio_snapshots']:
    count = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    print(f'{table}: {count} rows')
con.close()
"
```

Expected: Each table has >= 0 rows (0 if no fills from Phase 1a yet, > 0 after ingestion).

### Step 4: Final commit

- [ ] **Commit any verification fixes:**

If any tests failed during integration, fix and commit. Then:

```bash
git log --oneline -5
```

Expected: 4-5 commits from Phase 1b tasks.

---

## Summary Checklist

| Module | File | Test File | Status |
|--------|------|-----------|--------|
| Entry Price | `tracking/pipeline/entry_price.py` | `tests/test_entry_price.py` | - [ ] |
| Unrealized PnL | `tracking/pipeline/upnl.py` | `tests/test_upnl.py` | - [ ] |
| Spreads | `tracking/pipeline/spreads.py` | `tests/test_spreads.py` | - [ ] |
| Portfolio | `tracking/pipeline/portfolio.py` | (integration test) | - [ ] |
| Orchestrator | `scripts/pipeline_hourly.py` | (manual verify) | - [ ] |
| Integration | -- | (end-to-end) | - [ ] |
