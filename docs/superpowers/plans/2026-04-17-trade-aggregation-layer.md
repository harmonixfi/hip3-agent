# Trade Aggregation Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a Trade aggregation layer between Position and Fill so each delta-neutral deploy/unwind batch computes its own entry/exit spread and realized P&L accurately. Deprecate `config/positions.json` in favor of UI-driven Position + Trade management with DRAFT/FINALIZED lifecycle.

**Architecture:** New `pm_trades` + `pm_trade_fills` + `pm_trade_reconcile_warnings` tables cache user-defined cohorts of fills. A Position is the rollup of its FINALIZED trades (qty/status derived). DRAFT trades auto-reconcile late fills; FINALIZED trades are locked snapshots that raise warnings on late arrivals. Feature-flagged rollout (`TRADES_LAYER_ENABLED`), positions.json backed up to `.bak` after validated migration.

**Tech Stack:** Python 3.11 + FastAPI + sqlite (backend); Next.js 14 App Router + TypeScript + Tailwind (frontend); pytest (tests). Follows existing patterns in `tracking/pipeline/`, `api/routers/`, `frontend/components/`.

**Spec:** `docs/superpowers/specs/2026-04-17-trade-aggregation-layer-design.md`

**Phases:**
- **Phase A** — Schema + core pipeline module (pure math, state transitions, reconcile)
- **Phase B** — REST API (9 new endpoints + 2 extended positions endpoints)
- **Phase C** — Frontend (/trades global page, /positions/:id detail tabs, modals)
- **Phase D** — Migration script + E2E harness + positions.json deprecation + docs

---

## File Structure

### Created
- `tracking/sql/schema_monitoring_v2.sql` — new tables DDL
- `tracking/pipeline/trades.py` — aggregation, compute, state transitions
- `tracking/pipeline/trade_reconcile.py` — cron-hook reconcile logic
- `api/routers/trades.py` — REST endpoints
- `api/models/trade_schemas.py` — pydantic request/response models
- `scripts/migrate_positions_to_db.py` — positions.json → DB one-shot
- `scripts/e2e_real_fills.py` — real-data E2E acceptance harness
- `tests/test_trades_aggregate.py` — aggregation + spread + P&L math
- `tests/test_trades_state.py` — DRAFT/FINALIZED transitions, validation
- `tests/test_trades_reconcile.py` — late-fill reconcile behavior
- `tests/test_trades_api.py` — API endpoint smoke tests
- `tests/test_migrate_positions_to_db.py` — migration idempotency + diff
- `frontend/app/trades/page.tsx` — global /trades page
- `frontend/app/trades/[id]/page.tsx` — trade detail
- `frontend/components/TradesTable.tsx` — reusable table (global + embedded)
- `frontend/components/NewTradeModal.tsx`
- `frontend/components/NewPositionModal.tsx`
- `frontend/components/TradeDetailDrawer.tsx`
- `frontend/lib/trades.ts` — API client functions + types

### Modified
- `tracking/pipeline/entry_price.py` — switch to consuming FINALIZED OPEN trades; legacy fallback preserved
- `tracking/pipeline/spreads.py` — same refactor as entry_price
- `api/routers/positions.py` — add `POST /api/positions`, extend `GET /api/positions/:id` with derived fields
- `api/main.py` — register new `trades` router
- `api/models/schemas.py` — add derived fields to `PositionDetail`
- `scripts/pipeline_hourly.py` — call `trade_reconcile.run_reconcile()` after fill ingestion
- `scripts/pm.py` — `sync-registry` prints deprecation warning and no-ops when `TRADES_LAYER_ENABLED=true`
- `frontend/app/positions/[id]/page.tsx` — add Trades/Legs/Cashflows tabs
- `frontend/components/PositionsTable.tsx` — add "+ New Position" button + new derived columns
- `docs/playbook-position-management.md` — replace JSON-edit flow with UI flow
- `CLAUDE.md` — update "Position Management Workflow" section

### Renamed (after validation)
- `config/positions.json` → `config/positions.json.bak`

---

## Phase A — Schema + Core Pipeline

### Task A1: Schema DDL for new tables

**Files:**
- Create: `tracking/sql/schema_monitoring_v2.sql`

- [ ] **Step 1: Write DDL file**

```sql
-- schema_monitoring_v2.sql
-- Trade aggregation layer. Layered on top of schema_monitoring_v1.sql and
-- schema_pm_v3.sql. Idempotent (IF NOT EXISTS).

PRAGMA foreign_keys = ON;

-- Extend pm_positions with declarative intent columns (nullable for migration).
-- SQLite has no native ADD COLUMN IF NOT EXISTS; loader tolerates duplicate error.
ALTER TABLE pm_positions ADD COLUMN base TEXT;
ALTER TABLE pm_positions ADD COLUMN strategy_type TEXT
  CHECK (strategy_type IN ('SPOT_PERP','PERP_PERP'));

CREATE TABLE IF NOT EXISTS pm_trades (
  trade_id        TEXT PRIMARY KEY,
  position_id     TEXT NOT NULL REFERENCES pm_positions(position_id),
  trade_type      TEXT NOT NULL CHECK (trade_type IN ('OPEN','CLOSE')),
  state           TEXT NOT NULL CHECK (state IN ('DRAFT','FINALIZED')),
  start_ts        INTEGER NOT NULL,
  end_ts          INTEGER NOT NULL,
  note            TEXT,

  long_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  long_size       REAL,
  long_notional   REAL,
  long_avg_px     REAL,
  long_fees       REAL,
  long_fill_count INTEGER,

  short_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  short_size       REAL,
  short_notional   REAL,
  short_avg_px     REAL,
  short_fees       REAL,
  short_fill_count INTEGER,

  spread_bps        REAL,
  realized_pnl_bps  REAL,

  created_at_ms     INTEGER NOT NULL,
  finalized_at_ms   INTEGER,
  computed_at_ms    INTEGER NOT NULL,

  UNIQUE (position_id, trade_type, start_ts, end_ts)
);

CREATE INDEX IF NOT EXISTS idx_pm_trades_position ON pm_trades(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_trades_window ON pm_trades(start_ts, end_ts);
CREATE INDEX IF NOT EXISTS idx_pm_trades_state ON pm_trades(state);

CREATE TABLE IF NOT EXISTS pm_trade_fills (
  trade_id  TEXT NOT NULL REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  fill_id   INTEGER NOT NULL REFERENCES pm_fills(fill_id),
  leg_side  TEXT NOT NULL CHECK (leg_side IN ('LONG','SHORT')),
  PRIMARY KEY (trade_id, fill_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_trade_fills_fill ON pm_trade_fills(fill_id);

CREATE TABLE IF NOT EXISTS pm_trade_reconcile_warnings (
  trade_id          TEXT PRIMARY KEY REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  unassigned_count  INTEGER NOT NULL,
  first_seen_ms     INTEGER NOT NULL,
  last_checked_ms   INTEGER NOT NULL
);
```

- [ ] **Step 2: Add a migration helper script invocation**

Modify `scripts/db_monitoring_migrate.py` to also apply `schema_monitoring_v2.sql`. Locate the section that applies `schema_monitoring_v1.sql` (grep for the string) and add immediately after:

```python
_apply_sql_file(con, ROOT / "tracking/sql/schema_monitoring_v2.sql", tolerate_duplicate_column=True)
```

Where `_apply_sql_file` is the existing helper; if the helper does not accept that kwarg, wrap ALTER TABLE errors:

```python
def _apply_sql_file(con, path, tolerate_duplicate_column=False):
    sql = path.read_text()
    for stmt in sql.split(";"):
        stmt = stmt.strip()
        if not stmt:
            continue
        try:
            con.execute(stmt)
        except sqlite3.OperationalError as e:
            if tolerate_duplicate_column and "duplicate column name" in str(e):
                continue
            raise
    con.commit()
```

- [ ] **Step 3: Run the migration against a fresh DB**

```bash
source .arbit_env && .venv/bin/python scripts/db_monitoring_migrate.py --db tracking/db/arbit_v3.db
```

Expected: exits 0; running twice is a no-op.

- [ ] **Step 4: Verify tables exist**

```bash
.venv/bin/python -c "import sqlite3; c = sqlite3.connect('tracking/db/arbit_v3.db'); print([r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'pm_trade%'\").fetchall()])"
```

Expected output: `['pm_trades', 'pm_trade_fills', 'pm_trade_reconcile_warnings']`

- [ ] **Step 5: Commit**

```bash
git add tracking/sql/schema_monitoring_v2.sql scripts/db_monitoring_migrate.py
git commit -m "feat(schema): add pm_trades + pm_trade_fills + reconcile warnings tables"
```

---

### Task A2: Pure aggregation + math helpers (no DB)

**Files:**
- Create: `tracking/pipeline/trades.py`
- Test: `tests/test_trades_aggregate.py`

- [ ] **Step 1: Write failing unit tests**

```python
# tests/test_trades_aggregate.py
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
    # VWAP = (100*2 + 102*3) / (2+3) = 506/5 = 101.2
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
    assert agg.fees == 0.0  # None fees counted as 0


def test_compute_spread_bps_positive():
    # long=101, short=100 → (101/100 - 1) * 10_000 = +100 bps
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
    # OPEN spread = +50 bps, CLOSE spread = +30 bps
    # realized = (open - close) * 10000 but already in bps → open - close = 20 bps
    # Weighted avg entry = 50 (single open), close = 30 → realized = 50 - 30 = 20 bps
    opens = [(50.0, 10.0)]  # (spread_bps, long_size)
    assert compute_realized_pnl_bps(opens, close_spread_bps=30.0) == pytest.approx(20.0)


def test_compute_realized_pnl_bps_multi_open_weighted_avg():
    # opens: 60 bps × size 10, 40 bps × size 30 → weighted = (60*10 + 40*30)/40 = 45 bps
    # close = 20 bps → realized = 45 - 20 = 25 bps
    opens = [(60.0, 10.0), (40.0, 30.0)]
    assert compute_realized_pnl_bps(opens, close_spread_bps=20.0) == pytest.approx(25.0)


def test_compute_realized_pnl_bps_no_opens_raises():
    with pytest.raises(ValueError, match="no FINALIZED OPEN"):
        compute_realized_pnl_bps([], close_spread_bps=30.0)


def test_compute_realized_pnl_bps_zero_size_open_skipped():
    # A zero-size open is an aborted batch; must not participate in weights.
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_aggregate.py -v
```

Expected: ImportError (module not yet created).

- [ ] **Step 3: Write minimal implementation**

```python
# tracking/pipeline/trades.py
"""Trade aggregation layer.

Pure math first (this file); DB I/O layered on top in later tasks.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


VALID_TYPES = {"OPEN", "CLOSE"}
VALID_SIDES = {"LONG", "SHORT"}


@dataclass
class FillRow:
    """Minimal fill projection used by aggregate_fills. Maps to pm_fills columns."""
    fill_id: int
    px: float
    sz: float
    fee: Optional[float] = None


@dataclass
class LegAggregate:
    size: float
    notional: float
    avg_px: Optional[float]  # None when size == 0
    fees: float
    fill_count: int


def aggregate_fills(fills: Iterable[FillRow]) -> LegAggregate:
    """Compute VWAP aggregate for a set of fills (all same leg + side).

    Returns zeroed aggregate when no fills. avg_px is None iff size == 0.
    """
    fills = list(fills)
    if not fills:
        return LegAggregate(size=0.0, notional=0.0, avg_px=None, fees=0.0, fill_count=0)

    notional = 0.0
    size = 0.0
    fees = 0.0
    for f in fills:
        notional += f.px * f.sz
        size += f.sz
        if f.fee is not None:
            fees += f.fee

    avg_px: Optional[float] = notional / size if size > 0 else None
    return LegAggregate(
        size=size,
        notional=notional,
        avg_px=avg_px,
        fees=fees,
        fill_count=len(fills),
    )


def compute_spread_bps(long_avg_px: Optional[float], short_avg_px: Optional[float]) -> Optional[float]:
    """spread_bps = (long_avg_px / short_avg_px - 1) * 10_000.

    Returns None if either side has no fills (avg_px is None).
    Raises ValueError on zero short price.
    """
    if long_avg_px is None or short_avg_px is None:
        return None
    if short_avg_px == 0:
        raise ValueError("zero short price")
    return (long_avg_px / short_avg_px - 1.0) * 10_000.0


def compute_realized_pnl_bps(
    open_spreads_and_sizes: List[Tuple[float, float]],
    close_spread_bps: float,
) -> float:
    """Size-weighted avg of FINALIZED OPEN spreads minus close spread.

    Args:
        open_spreads_and_sizes: list of (spread_bps, long_size) for FINALIZED OPEN
                                trades of the same Position. Zero-size entries skipped.
        close_spread_bps: spread_bps of the current CLOSE trade.

    Returns:
        realized_pnl_bps = weighted_avg_open_spread - close_spread_bps.
    """
    weighted = [(s, w) for s, w in open_spreads_and_sizes if w > 0]
    if not weighted:
        raise ValueError("no FINALIZED OPEN trades with positive size")

    total_weight = sum(w for _, w in weighted)
    weighted_avg = sum(s * w for s, w in weighted) / total_weight
    return weighted_avg - close_spread_bps


def side_for(trade_type: str, leg_side: str) -> str:
    """Map trade_type + leg_side → expected pm_fills.side value.

    OPEN+LONG→BUY; OPEN+SHORT→SELL; CLOSE+LONG→SELL; CLOSE+SHORT→BUY.
    """
    if trade_type not in VALID_TYPES:
        raise ValueError(f"invalid trade_type: {trade_type}")
    if leg_side not in VALID_SIDES:
        raise ValueError(f"invalid leg_side: {leg_side}")

    if trade_type == "OPEN":
        return "BUY" if leg_side == "LONG" else "SELL"
    # CLOSE
    return "SELL" if leg_side == "LONG" else "BUY"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_aggregate.py -v
```

Expected: 16 passed.

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/trades.py tests/test_trades_aggregate.py
git commit -m "feat(trades): add pure aggregation + spread + realized P&L math"
```

---

### Task A3: Trade ID generation + overlap validator

**Files:**
- Modify: `tracking/pipeline/trades.py`
- Modify: `tests/test_trades_aggregate.py`

- [ ] **Step 1: Write failing tests (append to existing file)**

```python
# Append to tests/test_trades_aggregate.py:

from tracking.pipeline.trades import (
    resolve_trade_id,
    overlaps,
    TradeWindow,
)
from datetime import datetime


def test_resolve_trade_id_basic():
    ts_ms = int(datetime(2026, 4, 17, 10, 0).timestamp() * 1000)
    existing = set()
    assert resolve_trade_id("GOOGL", "OPEN", ts_ms, existing) == "trd_GOOGL_202604171000_open"


def test_resolve_trade_id_collision_suffixed():
    ts_ms = int(datetime(2026, 4, 17, 10, 0).timestamp() * 1000)
    existing = {"trd_GOOGL_202604171000_open"}
    assert resolve_trade_id("GOOGL", "OPEN", ts_ms, existing) == "trd_GOOGL_202604171000_open_2"


def test_resolve_trade_id_close_type():
    ts_ms = int(datetime(2026, 4, 17, 11, 30).timestamp() * 1000)
    assert resolve_trade_id("MSFT", "CLOSE", ts_ms, set()) == "trd_MSFT_202604171130_close"


def test_overlaps_disjoint_false():
    a = TradeWindow(start_ts=100, end_ts=200)
    b = TradeWindow(start_ts=300, end_ts=400)
    assert overlaps(a, b) is False


def test_overlaps_touching_edge_false():
    # end of a == start of b is NOT overlap (half-open intervals)
    a = TradeWindow(start_ts=100, end_ts=200)
    b = TradeWindow(start_ts=200, end_ts=300)
    assert overlaps(a, b) is False


def test_overlaps_contained_true():
    a = TradeWindow(start_ts=100, end_ts=400)
    b = TradeWindow(start_ts=200, end_ts=300)
    assert overlaps(a, b) is True


def test_overlaps_partial_true():
    a = TradeWindow(start_ts=100, end_ts=250)
    b = TradeWindow(start_ts=200, end_ts=300)
    assert overlaps(a, b) is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_aggregate.py -v -k "resolve_trade_id or overlaps"
```

Expected: ImportError.

- [ ] **Step 3: Implement helpers in `tracking/pipeline/trades.py`**

Append after `side_for`:

```python
from datetime import datetime, timezone


@dataclass
class TradeWindow:
    """Half-open interval [start_ts, end_ts) in epoch ms."""
    start_ts: int
    end_ts: int


def overlaps(a: TradeWindow, b: TradeWindow) -> bool:
    """True iff half-open intervals overlap. Touching edges do not overlap."""
    return a.start_ts < b.end_ts and b.start_ts < a.end_ts


def resolve_trade_id(
    base: str,
    trade_type: str,
    anchor_ts_ms: int,
    existing_ids: set[str],
) -> str:
    """Generate deterministic trade_id.

    Format: trd_<base>_<YYYYMMDDHHmm>_<open|close>[_<n>]
    Suffix _2, _3, ... on collision.
    """
    dt = datetime.fromtimestamp(anchor_ts_ms / 1000, tz=timezone.utc)
    stamp = dt.strftime("%Y%m%d%H%M")
    base_id = f"trd_{base}_{stamp}_{trade_type.lower()}"
    if base_id not in existing_ids:
        return base_id
    n = 2
    while f"{base_id}_{n}" in existing_ids:
        n += 1
    return f"{base_id}_{n}"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_aggregate.py -v
```

Expected: 19 passed.

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/trades.py tests/test_trades_aggregate.py
git commit -m "feat(trades): add trade_id resolver + window overlap check"
```

---

### Task A4: DB-backed trade creation (DRAFT)

**Files:**
- Modify: `tracking/pipeline/trades.py`
- Create: `tests/test_trades_state.py`

- [ ] **Step 1: Write failing integration tests**

```python
# tests/test_trades_state.py
"""Integration tests for DRAFT creation, FINALIZE/REOPEN/DELETE, and validation.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
"""
from __future__ import annotations
import sqlite3
import time

import pytest

from tracking.pipeline.trades import (
    create_draft_trade,
    TradeCreateError,
)


_SCHEMA_SQL = """
CREATE TABLE pm_positions (
  position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT,
  status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
  closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT
);
CREATE TABLE pm_legs (
  leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL,
  inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL,
  entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
  status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER,
  raw_json TEXT, meta_json TEXT, account_id TEXT
);
CREATE TABLE pm_fills (
  fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT,
  inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
  px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT,
  ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL,
  position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT
);
CREATE TABLE pm_trades (
  trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL,
  state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT,
  long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL,
  long_fees REAL, long_fill_count INTEGER,
  short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL,
  short_fees REAL, short_fill_count INTEGER,
  spread_bps REAL, realized_pnl_bps REAL,
  created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL,
  UNIQUE (position_id, trade_type, start_ts, end_ts)
);
CREATE TABLE pm_trade_fills (
  trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL,
  PRIMARY KEY (trade_id, fill_id)
);
CREATE TABLE pm_trade_reconcile_warnings (
  trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL,
  first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL
);
"""


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(_SCHEMA_SQL)
    now = int(time.time() * 1000)
    # Seed a position with two legs (spot LONG + perp SHORT)
    c.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES ('pos_X', 'hyperliquid', 'OPEN', ?, ?, 'GOOGL', 'SPOT_PERP')",
        (now, now),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_SPOT', 'pos_X', 'hyperliquid', 'GOOGL', 'LONG', 0, 'OPEN', ?, '0xMAIN')",
        (now,),
    )
    c.execute(
        "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) "
        "VALUES ('pos_X_PERP', 'pos_X', 'hyperliquid', 'xyz:GOOGL', 'SHORT', 0, 'OPEN', ?, '0xMAIN')",
        (now,),
    )
    # Seed fills at t=1000..2000 (OPEN batch): 2 BUY spot, 2 SELL perp
    c.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",  100.0, 2.0, 0.05, 1100, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",  102.0, 3.0, 0.08, 1500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL","SELL", 101.0, 2.0, 0.04, 1200, "pos_X_PERP", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL","SELL", 103.0, 3.0, 0.06, 1700, "pos_X_PERP", "pos_X"),
            # Out-of-window fill:
            ("hyperliquid", "0xMAIN", "GOOGL",    "BUY",   99.0, 1.0, 0.03, 5000, "pos_X_SPOT", "pos_X"),
        ],
    )
    c.commit()
    yield c
    c.close()


def test_create_draft_open_aggregates_in_window_fills(con):
    result = create_draft_trade(
        con,
        position_id="pos_X",
        trade_type="OPEN",
        start_ts=1000,
        end_ts=2000,
        note="initial",
    )
    # Spot long: 2+3 = 5 size; notional = 100*2 + 102*3 = 506; avg = 101.2
    assert result["long_size"] == pytest.approx(5.0)
    assert result["long_avg_px"] == pytest.approx(101.2)
    # Perp short: 2+3 = 5 size; notional = 101*2 + 103*3 = 511; avg = 102.2
    assert result["short_size"] == pytest.approx(5.0)
    assert result["short_avg_px"] == pytest.approx(102.2)
    # spread = (101.2 / 102.2 - 1) * 10000 ≈ -97.85 bps
    assert result["spread_bps"] == pytest.approx(-97.84735, abs=0.01)
    assert result["state"] == "DRAFT"
    assert result["realized_pnl_bps"] is None

    # Linkage materialized
    links = con.execute(
        "SELECT fill_id, leg_side FROM pm_trade_fills WHERE trade_id = ?",
        (result["trade_id"],),
    ).fetchall()
    assert len(links) == 4


def test_create_draft_excludes_out_of_window_fills(con):
    result = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    assert result["long_fill_count"] == 2  # out-of-window fill at ts=5000 excluded


def test_create_draft_rejects_if_fill_already_linked(con):
    create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    # Second trade in same window → fills already bound → should reject with 0 fills
    with pytest.raises(TradeCreateError, match="already linked|no fills"):
        create_draft_trade(con, "pos_X", "OPEN", 1000, 2000, note="dup")


def test_create_draft_rejects_unknown_position(con):
    with pytest.raises(TradeCreateError, match="position"):
        create_draft_trade(con, "pos_MISSING", "OPEN", 1000, 2000)


def test_create_draft_rejects_invalid_window(con):
    with pytest.raises(TradeCreateError, match="window"):
        create_draft_trade(con, "pos_X", "OPEN", 2000, 1000)  # start > end


def test_create_draft_rejects_invalid_trade_type(con):
    with pytest.raises(TradeCreateError, match="trade_type"):
        create_draft_trade(con, "pos_X", "ADD", 1000, 2000)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
```

Expected: ImportError for `create_draft_trade`, `TradeCreateError`.

- [ ] **Step 3: Implement in `tracking/pipeline/trades.py`**

Append:

```python
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional


class TradeCreateError(Exception):
    pass


def _now_ms() -> int:
    return int(time.time() * 1000)


def _fetch_position_legs(
    con: sqlite3.Connection, position_id: str
) -> Dict[str, Dict[str, Any]]:
    """Return {'LONG': {leg_id, account_id, inst_id, venue}, 'SHORT': {...}}."""
    rows = con.execute(
        "SELECT leg_id, side, account_id, inst_id, venue FROM pm_legs WHERE position_id = ?",
        (position_id,),
    ).fetchall()
    legs: Dict[str, Dict[str, Any]] = {}
    for leg_id, side, account_id, inst_id, venue in rows:
        legs[side] = {
            "leg_id": leg_id,
            "account_id": account_id,
            "inst_id": inst_id,
            "venue": venue,
        }
    return legs


def _fetch_window_fills(
    con: sqlite3.Connection,
    leg_id: str,
    fill_side: str,
    start_ts: int,
    end_ts: int,
) -> List[FillRow]:
    """Fetch fills for a leg in [start_ts, end_ts) with matching side, excluding
    fills already bound to another trade via pm_trade_fills."""
    rows = con.execute(
        """
        SELECT f.fill_id, f.px, f.sz, f.fee
        FROM pm_fills f
        WHERE f.leg_id = ?
          AND f.side = ?
          AND f.ts >= ?
          AND f.ts < ?
          AND NOT EXISTS (SELECT 1 FROM pm_trade_fills tf WHERE tf.fill_id = f.fill_id)
        ORDER BY f.ts
        """,
        (leg_id, fill_side, start_ts, end_ts),
    ).fetchall()
    return [FillRow(fill_id=r[0], px=r[1], sz=r[2], fee=r[3]) for r in rows]


def _fetch_finalized_open_spreads(
    con: sqlite3.Connection, position_id: str
) -> List[tuple[float, float]]:
    """For realized P&L calc: (spread_bps, long_size) of FINALIZED OPEN trades."""
    rows = con.execute(
        "SELECT spread_bps, long_size FROM pm_trades "
        "WHERE position_id = ? AND trade_type = 'OPEN' AND state = 'FINALIZED' "
        "AND spread_bps IS NOT NULL AND long_size IS NOT NULL AND long_size > 0",
        (position_id,),
    ).fetchall()
    return [(float(r[0]), float(r[1])) for r in rows]


def create_draft_trade(
    con: sqlite3.Connection,
    position_id: str,
    trade_type: str,
    start_ts: int,
    end_ts: int,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Create DRAFT trade, materialize pm_trade_fills, compute aggregates.

    Raises TradeCreateError on validation failure.
    """
    if trade_type not in VALID_TYPES:
        raise TradeCreateError(f"invalid trade_type: {trade_type}")
    if start_ts >= end_ts:
        raise TradeCreateError("invalid window: start_ts must be < end_ts")

    pos_row = con.execute(
        "SELECT base, status FROM pm_positions WHERE position_id = ?",
        (position_id,),
    ).fetchone()
    if not pos_row:
        raise TradeCreateError(f"position not found: {position_id}")
    base, pos_status = pos_row
    if pos_status == "CLOSED":
        raise TradeCreateError(f"position {position_id} is CLOSED")
    if not base:
        raise TradeCreateError(f"position {position_id} missing base — run migration")

    legs = _fetch_position_legs(con, position_id)
    if "LONG" not in legs or "SHORT" not in legs:
        raise TradeCreateError(f"position {position_id} missing LONG or SHORT leg")

    long_leg = legs["LONG"]
    short_leg = legs["SHORT"]

    long_side_filter = side_for(trade_type, "LONG")
    short_side_filter = side_for(trade_type, "SHORT")

    long_fills = _fetch_window_fills(con, long_leg["leg_id"], long_side_filter, start_ts, end_ts)
    short_fills = _fetch_window_fills(con, short_leg["leg_id"], short_side_filter, start_ts, end_ts)

    if not long_fills and not short_fills:
        raise TradeCreateError(
            "no fills in window (empty window, already linked to another trade, or wrong wallet)"
        )

    long_agg = aggregate_fills(long_fills)
    short_agg = aggregate_fills(short_fills)
    spread_bps = compute_spread_bps(long_agg.avg_px, short_agg.avg_px)

    realized_pnl_bps: Optional[float] = None
    if trade_type == "CLOSE" and spread_bps is not None:
        opens = _fetch_finalized_open_spreads(con, position_id)
        if opens:
            realized_pnl_bps = compute_realized_pnl_bps(opens, spread_bps)

    existing_ids = {
        r[0] for r in con.execute("SELECT trade_id FROM pm_trades").fetchall()
    }
    trade_id = resolve_trade_id(base, trade_type, start_ts, existing_ids)

    now = _now_ms()
    con.execute(
        """
        INSERT INTO pm_trades (
            trade_id, position_id, trade_type, state, start_ts, end_ts, note,
            long_leg_id, long_size, long_notional, long_avg_px, long_fees, long_fill_count,
            short_leg_id, short_size, short_notional, short_avg_px, short_fees, short_fill_count,
            spread_bps, realized_pnl_bps,
            created_at_ms, computed_at_ms
        ) VALUES (?,?,?,?,?,?,?, ?,?,?,?,?,?, ?,?,?,?,?,?, ?,?, ?,?)
        """,
        (
            trade_id, position_id, trade_type, "DRAFT", start_ts, end_ts, note,
            long_leg["leg_id"], long_agg.size, long_agg.notional, long_agg.avg_px, long_agg.fees, long_agg.fill_count,
            short_leg["leg_id"], short_agg.size, short_agg.notional, short_agg.avg_px, short_agg.fees, short_agg.fill_count,
            spread_bps, realized_pnl_bps,
            now, now,
        ),
    )

    for f in long_fills:
        con.execute(
            "INSERT INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?, ?, 'LONG')",
            (trade_id, f.fill_id),
        )
    for f in short_fills:
        con.execute(
            "INSERT INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?, ?, 'SHORT')",
            (trade_id, f.fill_id),
        )

    con.commit()

    return {
        "trade_id": trade_id,
        "position_id": position_id,
        "trade_type": trade_type,
        "state": "DRAFT",
        "start_ts": start_ts,
        "end_ts": end_ts,
        "note": note,
        "long_leg_id": long_leg["leg_id"],
        "long_size": long_agg.size,
        "long_notional": long_agg.notional,
        "long_avg_px": long_agg.avg_px,
        "long_fees": long_agg.fees,
        "long_fill_count": long_agg.fill_count,
        "short_leg_id": short_leg["leg_id"],
        "short_size": short_agg.size,
        "short_notional": short_agg.notional,
        "short_avg_px": short_agg.avg_px,
        "short_fees": short_agg.fees,
        "short_fill_count": short_agg.fill_count,
        "spread_bps": spread_bps,
        "realized_pnl_bps": realized_pnl_bps,
        "created_at_ms": now,
        "computed_at_ms": now,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/trades.py tests/test_trades_state.py
git commit -m "feat(trades): DRAFT creation with fill aggregation + validation"
```

---

### Task A5: Recompute, finalize, reopen, delete

**Files:**
- Modify: `tracking/pipeline/trades.py`
- Modify: `tests/test_trades_state.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_trades_state.py`:

```python
from tracking.pipeline.trades import (
    recompute_trade,
    finalize_trade,
    reopen_trade,
    delete_trade,
)


def test_recompute_draft_picks_up_new_fill(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]

    # Insert a late fill at t=1800 (within window)
    con.execute(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,1.0,0.02,1800,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    result = recompute_trade(con, tid)
    # new long size = 5 + 1 = 6
    assert result["long_size"] == pytest.approx(6.0)


def test_finalize_sets_state_and_timestamp(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalized = finalize_trade(con, t["trade_id"])
    assert finalized["state"] == "FINALIZED"
    assert finalized["finalized_at_ms"] is not None


def test_finalize_updates_leg_qty_and_position_status(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t["trade_id"])
    # pm_legs.size updated
    long_size = con.execute("SELECT size FROM pm_legs WHERE leg_id = 'pos_X_SPOT'").fetchone()[0]
    short_size = con.execute("SELECT size FROM pm_legs WHERE leg_id = 'pos_X_PERP'").fetchone()[0]
    assert long_size == pytest.approx(5.0)
    assert short_size == pytest.approx(5.0)
    status = con.execute("SELECT status FROM pm_positions WHERE position_id = 'pos_X'").fetchone()[0]
    assert status == "OPEN"


def test_finalize_rejects_overlap_with_existing_finalized(con):
    t1 = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t1["trade_id"])

    # Need to seed more fills to create t2 (fills in 1000-2000 are consumed)
    con.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",     "BUY",  100.0, 1.0, 0.01, 1500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL", "SELL", 101.0, 1.0, 0.01, 1500, "pos_X_PERP", "pos_X"),
        ],
    )
    con.commit()
    t2 = create_draft_trade(con, "pos_X", "OPEN", 1000, 1800)  # overlaps with 1000-2000
    with pytest.raises(TradeCreateError, match="overlap"):
        finalize_trade(con, t2["trade_id"])


def test_reopen_finalized_goes_back_to_draft(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t["trade_id"])
    reopened = reopen_trade(con, t["trade_id"])
    assert reopened["state"] == "DRAFT"
    assert reopened["finalized_at_ms"] is None


def test_delete_draft_releases_fills(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]

    delete_trade(con, tid)

    assert con.execute("SELECT COUNT(*) FROM pm_trades WHERE trade_id = ?", (tid,)).fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM pm_trade_fills WHERE trade_id = ?", (tid,)).fetchone()[0] == 0
    # And fills remain in pm_fills
    assert con.execute("SELECT COUNT(*) FROM pm_fills WHERE leg_id = 'pos_X_SPOT'").fetchone()[0] >= 2


def test_close_realized_pnl_after_open_finalized(con):
    # Open trade finalized with spread -97.85 bps (computed above).
    t_open = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    finalize_trade(con, t_open["trade_id"])

    # Seed CLOSE fills (spot SELL + perp BUY) at 3000..4000
    con.executemany(
        "INSERT INTO pm_fills (venue, account_id, inst_id, side, px, sz, fee, ts, leg_id, position_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid", "0xMAIN", "GOOGL",     "SELL", 110.0, 5.0, 0.10, 3500, "pos_X_SPOT", "pos_X"),
            ("hyperliquid", "0xMAIN", "xyz:GOOGL", "BUY",  108.0, 5.0, 0.10, 3500, "pos_X_PERP", "pos_X"),
        ],
    )
    con.commit()

    t_close = create_draft_trade(con, "pos_X", "CLOSE", 3000, 4000)
    # close spread = (110 / 108 - 1) * 10000 ≈ 185.19 bps
    # realized = -97.85 - 185.19 ≈ -283.04 bps
    assert t_close["realized_pnl_bps"] == pytest.approx(-283.0, abs=0.5)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
```

Expected: ImportError for new functions.

- [ ] **Step 3: Implement in `tracking/pipeline/trades.py`**

Append:

```python
def _update_leg_sizes_and_position_status(con: sqlite3.Connection, position_id: str) -> None:
    """Recompute pm_legs.size and pm_positions.status from FINALIZED trades."""
    legs = _fetch_position_legs(con, position_id)

    for side, leg in legs.items():
        row = con.execute(
            """
            SELECT
              COALESCE(SUM(CASE WHEN trade_type='OPEN'  THEN
                  CASE WHEN ?='LONG' THEN long_size ELSE short_size END
                ELSE 0 END), 0)
              - COALESCE(SUM(CASE WHEN trade_type='CLOSE' THEN
                  CASE WHEN ?='LONG' THEN long_size ELSE short_size END
                ELSE 0 END), 0) AS net_size
            FROM pm_trades
            WHERE position_id = ? AND state = 'FINALIZED'
            """,
            (side, side, position_id),
        ).fetchone()
        net = row[0] or 0.0
        con.execute(
            "UPDATE pm_legs SET size = ? WHERE leg_id = ?",
            (net, leg["leg_id"]),
        )

    # Status: manual overrides (PAUSED, EXITING) preserved
    current_status = con.execute(
        "SELECT status FROM pm_positions WHERE position_id = ?",
        (position_id,),
    ).fetchone()[0]
    if current_status in ("PAUSED", "EXITING"):
        return

    agg = con.execute(
        """
        SELECT
          SUM(CASE WHEN trade_type='OPEN'  AND state='FINALIZED' THEN 1 ELSE 0 END),
          SUM(CASE WHEN trade_type='CLOSE' AND state='FINALIZED' THEN 1 ELSE 0 END)
        FROM pm_trades WHERE position_id = ?
        """,
        (position_id,),
    ).fetchone()
    n_open, n_close = (agg[0] or 0), (agg[1] or 0)

    leg_sizes = con.execute(
        "SELECT size FROM pm_legs WHERE position_id = ?",
        (position_id,),
    ).fetchall()
    all_zero = all((s[0] or 0) == 0 for s in leg_sizes)

    now = _now_ms()
    if n_open > 0 and not all_zero:
        con.execute(
            "UPDATE pm_positions SET status='OPEN', updated_at_ms=? WHERE position_id=?",
            (now, position_id),
        )
    elif all_zero and n_close > 0:
        con.execute(
            "UPDATE pm_positions SET status='CLOSED', updated_at_ms=?, closed_at_ms=? WHERE position_id=?",
            (now, now, position_id),
        )


def _serialize_trade_row(row: sqlite3.Row) -> Dict[str, Any]:
    cols = [d[0] for d in row.description] if hasattr(row, "description") else None
    # sqlite3.Row indexable; use keys()
    d = {k: row[k] for k in row.keys()}
    return d


def recompute_trade(con: sqlite3.Connection, trade_id: str) -> Dict[str, Any]:
    """Recompute aggregates for a DRAFT trade by re-scanning fills in its window.

    Idempotent: appends newly-available fills via INSERT OR IGNORE.
    """
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM pm_trades WHERE trade_id = ?", (trade_id,)).fetchone()
    if not row:
        raise TradeCreateError(f"trade not found: {trade_id}")
    if row["state"] != "DRAFT":
        raise TradeCreateError(f"trade {trade_id} not DRAFT (state={row['state']})")

    trade_type = row["trade_type"]
    position_id = row["position_id"]
    start_ts = row["start_ts"]
    end_ts = row["end_ts"]
    long_leg_id = row["long_leg_id"]
    short_leg_id = row["short_leg_id"]

    long_side = side_for(trade_type, "LONG")
    short_side = side_for(trade_type, "SHORT")

    long_fills = _fetch_window_fills(con, long_leg_id, long_side, start_ts, end_ts)
    short_fills = _fetch_window_fills(con, short_leg_id, short_side, start_ts, end_ts)

    # Re-link (idempotent): only append fills not yet in pm_trade_fills for ANY trade
    for f in long_fills:
        con.execute(
            "INSERT OR IGNORE INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?,?, 'LONG')",
            (trade_id, f.fill_id),
        )
    for f in short_fills:
        con.execute(
            "INSERT OR IGNORE INTO pm_trade_fills (trade_id, fill_id, leg_side) VALUES (?,?, 'SHORT')",
            (trade_id, f.fill_id),
        )

    # Now re-aggregate from pm_trade_fills (authoritative link)
    def agg_for_side(side_label: str) -> LegAggregate:
        rows = con.execute(
            """
            SELECT f.fill_id, f.px, f.sz, f.fee
            FROM pm_trade_fills tf JOIN pm_fills f ON f.fill_id = tf.fill_id
            WHERE tf.trade_id = ? AND tf.leg_side = ?
            """,
            (trade_id, side_label),
        ).fetchall()
        return aggregate_fills([FillRow(fill_id=r[0], px=r[1], sz=r[2], fee=r[3]) for r in rows])

    long_agg = agg_for_side("LONG")
    short_agg = agg_for_side("SHORT")
    spread_bps = compute_spread_bps(long_agg.avg_px, short_agg.avg_px)

    realized_pnl_bps: Optional[float] = None
    if trade_type == "CLOSE" and spread_bps is not None:
        opens = _fetch_finalized_open_spreads(con, position_id)
        if opens:
            realized_pnl_bps = compute_realized_pnl_bps(opens, spread_bps)

    now = _now_ms()
    con.execute(
        """
        UPDATE pm_trades SET
          long_size=?, long_notional=?, long_avg_px=?, long_fees=?, long_fill_count=?,
          short_size=?, short_notional=?, short_avg_px=?, short_fees=?, short_fill_count=?,
          spread_bps=?, realized_pnl_bps=?, computed_at_ms=?
        WHERE trade_id=?
        """,
        (
            long_agg.size, long_agg.notional, long_agg.avg_px, long_agg.fees, long_agg.fill_count,
            short_agg.size, short_agg.notional, short_agg.avg_px, short_agg.fees, short_agg.fill_count,
            spread_bps, realized_pnl_bps, now, trade_id,
        ),
    )
    con.commit()

    return _serialize_trade_row(
        con.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    )


def finalize_trade(con: sqlite3.Connection, trade_id: str) -> Dict[str, Any]:
    """DRAFT → FINALIZED. Checks overlap with existing FINALIZED; updates leg qty + position status.

    For CLOSE trades: rejects if no FINALIZED OPEN trades exist for the position.
    """
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM pm_trades WHERE trade_id = ?", (trade_id,)).fetchone()
    if not row:
        raise TradeCreateError(f"trade not found: {trade_id}")
    if row["state"] != "DRAFT":
        raise TradeCreateError(f"trade {trade_id} not DRAFT")

    position_id = row["position_id"]
    trade_type = row["trade_type"]
    this_window = TradeWindow(start_ts=row["start_ts"], end_ts=row["end_ts"])

    # Check FINALIZED overlap on same legs
    other_finalized = con.execute(
        """
        SELECT trade_id, start_ts, end_ts, trade_type FROM pm_trades
        WHERE position_id = ? AND state = 'FINALIZED' AND trade_id != ?
          AND trade_type = ?
          AND (long_leg_id = ? OR short_leg_id = ?)
        """,
        (position_id, trade_id, trade_type, row["long_leg_id"], row["short_leg_id"]),
    ).fetchall()
    for o in other_finalized:
        other_win = TradeWindow(start_ts=o["start_ts"], end_ts=o["end_ts"])
        if overlaps(this_window, other_win):
            raise TradeCreateError(
                f"overlap with FINALIZED trade {o['trade_id']} "
                f"({o['start_ts']}..{o['end_ts']})"
            )

    # CLOSE must have at least one FINALIZED OPEN
    if trade_type == "CLOSE":
        if not _fetch_finalized_open_spreads(con, position_id):
            raise TradeCreateError(
                "cannot finalize CLOSE: no FINALIZED OPEN trades on position"
            )

    now = _now_ms()
    con.execute(
        "UPDATE pm_trades SET state='FINALIZED', finalized_at_ms=?, computed_at_ms=? WHERE trade_id=?",
        (now, now, trade_id),
    )
    _update_leg_sizes_and_position_status(con, position_id)
    con.commit()

    return _serialize_trade_row(
        con.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    )


def reopen_trade(con: sqlite3.Connection, trade_id: str) -> Dict[str, Any]:
    """FINALIZED → DRAFT."""
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise TradeCreateError(f"trade not found: {trade_id}")
    if row["state"] != "FINALIZED":
        raise TradeCreateError(f"trade {trade_id} not FINALIZED")
    position_id = row["position_id"]

    con.execute(
        "UPDATE pm_trades SET state='DRAFT', finalized_at_ms=NULL, computed_at_ms=? WHERE trade_id=?",
        (_now_ms(), trade_id),
    )
    _update_leg_sizes_and_position_status(con, position_id)
    # Clear any reconcile warning
    con.execute("DELETE FROM pm_trade_reconcile_warnings WHERE trade_id=?", (trade_id,))
    con.commit()

    return _serialize_trade_row(
        con.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    )


def delete_trade(con: sqlite3.Connection, trade_id: str) -> None:
    """Hard delete. pm_trade_fills cascade via PK; pm_fills untouched."""
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT position_id FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise TradeCreateError(f"trade not found: {trade_id}")
    position_id = row["position_id"]

    con.execute("DELETE FROM pm_trade_fills WHERE trade_id=?", (trade_id,))
    con.execute("DELETE FROM pm_trade_reconcile_warnings WHERE trade_id=?", (trade_id,))
    con.execute("DELETE FROM pm_trades WHERE trade_id=?", (trade_id,))
    _update_leg_sizes_and_position_status(con, position_id)
    con.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_state.py -v
```

Expected: 13 passed (6 from Task A4 + 7 new).

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/trades.py tests/test_trades_state.py
git commit -m "feat(trades): recompute, finalize, reopen, delete + position status derivation"
```

---

### Task A6: Reconcile hook (late-fill auto-pickup + FINALIZED warnings)

**Files:**
- Create: `tracking/pipeline/trade_reconcile.py`
- Create: `tests/test_trades_reconcile.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_trades_reconcile.py
"""Reconcile hook: DRAFT auto-picks late fills; FINALIZED raises warning.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_reconcile.py -v
"""
from __future__ import annotations
import sqlite3
import time

import pytest

from tracking.pipeline.trades import create_draft_trade, finalize_trade
from tracking.pipeline.trade_reconcile import run_reconcile


# Re-use _SCHEMA_SQL fixture from test_trades_state.py by copy (keep test files independent).
_SCHEMA_SQL = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


@pytest.fixture
def con():
    c = sqlite3.connect(":memory:")
    c.executescript(_SCHEMA_SQL)
    now = int(time.time() * 1000)
    c.execute("INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) VALUES ('pos_X','hyperliquid','OPEN',?,?,'GOOGL','SPOT_PERP')", (now, now))
    c.execute("INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES ('pos_X_SPOT','pos_X','hyperliquid','GOOGL','LONG',0,'OPEN',?, '0xMAIN')", (now,))
    c.execute("INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id) VALUES ('pos_X_PERP','pos_X','hyperliquid','xyz:GOOGL','SHORT',0,'OPEN',?, '0xMAIN')", (now,))
    c.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL","BUY",100.0,2.0,0.05,1100,"pos_X_SPOT","pos_X"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0,2.0,0.04,1200,"pos_X_PERP","pos_X"),
        ],
    )
    c.commit()
    yield c
    c.close()


def test_reconcile_draft_picks_up_late_fill(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    assert t["long_size"] == pytest.approx(2.0)

    # Late fill arrives (within window, inserted after DRAFT creation)
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)

    long_size = con.execute("SELECT long_size FROM pm_trades WHERE trade_id=?", (tid,)).fetchone()[0]
    assert long_size == pytest.approx(5.0)


def test_reconcile_finalized_raises_warning_not_auto_merge(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    finalize_trade(con, tid)

    # Late fill arrives in the FINALIZED window
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)

    # Aggregates unchanged
    long_size = con.execute("SELECT long_size FROM pm_trades WHERE trade_id=?", (tid,)).fetchone()[0]
    assert long_size == pytest.approx(2.0)
    # Warning row written
    warn = con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone()
    assert warn is not None
    assert warn[0] == 1


def test_reconcile_finalized_old_trade_skipped_or_still_warned(con):
    t = create_draft_trade(con, "pos_X", "OPEN", 1000, 2000)
    tid = t["trade_id"]
    finalize_trade(con, tid)

    # Age the trade by patching finalized_at_ms far in the past
    con.execute(
        "UPDATE pm_trades SET finalized_at_ms = 0 WHERE trade_id=?", (tid,)
    )
    # Inject a late fill
    con.execute(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) "
        "VALUES ('hyperliquid','0xMAIN','GOOGL','BUY',105.0,3.0,0.06,1500,'pos_X_SPOT','pos_X')"
    )
    con.commit()

    run_reconcile(con)  # should still produce warning regardless of age
    warn = con.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?", (tid,)
    ).fetchone()
    assert warn is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_reconcile.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `tracking/pipeline/trade_reconcile.py`**

```python
"""Trade reconcile hook — called after fill_ingester cron run.

DRAFT trades auto-pick up newly-ingested fills in their window.
FINALIZED trades count unassigned fills and raise warnings (no auto-merge).
"""
from __future__ import annotations

import sqlite3
import time
from typing import Dict, List

from tracking.pipeline.trades import recompute_trade, side_for


def _now_ms() -> int:
    return int(time.time() * 1000)


def _count_unassigned_fills_in_window(
    con: sqlite3.Connection,
    long_leg_id: str,
    short_leg_id: str,
    long_side: str,
    short_side: str,
    start_ts: int,
    end_ts: int,
) -> int:
    row = con.execute(
        """
        SELECT COUNT(*) FROM pm_fills f
        WHERE f.ts >= ? AND f.ts < ?
          AND (
            (f.leg_id = ? AND f.side = ?) OR
            (f.leg_id = ? AND f.side = ?)
          )
          AND NOT EXISTS (SELECT 1 FROM pm_trade_fills tf WHERE tf.fill_id = f.fill_id)
        """,
        (start_ts, end_ts, long_leg_id, long_side, short_leg_id, short_side),
    ).fetchone()
    return int(row[0] or 0)


def run_reconcile(con: sqlite3.Connection) -> Dict[str, int]:
    """Refresh DRAFT trades and raise warnings for FINALIZED with late fills.

    Returns summary dict: {'drafts_recomputed': int, 'warnings_raised': int, 'warnings_cleared': int}.
    """
    con.row_factory = sqlite3.Row
    drafts_recomputed = 0
    warnings_raised = 0
    warnings_cleared = 0

    # DRAFT: blindly recompute each
    draft_ids = [
        r["trade_id"]
        for r in con.execute("SELECT trade_id FROM pm_trades WHERE state = 'DRAFT'").fetchall()
    ]
    for tid in draft_ids:
        recompute_trade(con, tid)
        drafts_recomputed += 1

    # FINALIZED: count unassigned fills in window + legs + sides → upsert warning
    finalized = con.execute(
        "SELECT trade_id, trade_type, start_ts, end_ts, long_leg_id, short_leg_id "
        "FROM pm_trades WHERE state = 'FINALIZED'"
    ).fetchall()

    now = _now_ms()
    for t in finalized:
        long_side = side_for(t["trade_type"], "LONG")
        short_side = side_for(t["trade_type"], "SHORT")
        n = _count_unassigned_fills_in_window(
            con,
            t["long_leg_id"], t["short_leg_id"],
            long_side, short_side,
            t["start_ts"], t["end_ts"],
        )

        existing = con.execute(
            "SELECT unassigned_count, first_seen_ms FROM pm_trade_reconcile_warnings WHERE trade_id=?",
            (t["trade_id"],),
        ).fetchone()

        if n > 0:
            if existing is None:
                con.execute(
                    "INSERT INTO pm_trade_reconcile_warnings (trade_id, unassigned_count, first_seen_ms, last_checked_ms) "
                    "VALUES (?,?,?,?)",
                    (t["trade_id"], n, now, now),
                )
                warnings_raised += 1
            else:
                con.execute(
                    "UPDATE pm_trade_reconcile_warnings SET unassigned_count=?, last_checked_ms=? WHERE trade_id=?",
                    (n, now, t["trade_id"]),
                )
        else:
            if existing is not None:
                con.execute(
                    "DELETE FROM pm_trade_reconcile_warnings WHERE trade_id=?",
                    (t["trade_id"],),
                )
                warnings_cleared += 1

    con.commit()
    return {
        "drafts_recomputed": drafts_recomputed,
        "warnings_raised": warnings_raised,
        "warnings_cleared": warnings_cleared,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_reconcile.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/trade_reconcile.py tests/test_trades_reconcile.py
git commit -m "feat(trades): reconcile hook — DRAFT auto-merge + FINALIZED warnings"
```

---

### Task A7: Wire reconcile into hourly pipeline

**Files:**
- Modify: `scripts/pipeline_hourly.py`

- [ ] **Step 1: Inspect existing pipeline to find the post-ingest hook point**

```bash
grep -n "ingest_hyperliquid_fills\|compute_entry_prices\|compute_spreads" scripts/pipeline_hourly.py
```

- [ ] **Step 2: Add reconcile call after fill ingestion**

After the last call to `ingest_hyperliquid_fills` (and any Felix equivalent), before `compute_entry_prices`, add:

```python
# Reconcile DRAFT trades + update FINALIZED warnings
if os.getenv("TRADES_LAYER_ENABLED", "false").lower() == "true":
    from tracking.pipeline.trade_reconcile import run_reconcile
    recon_summary = run_reconcile(con)
    print(f"  trade reconcile: {recon_summary}")
```

- [ ] **Step 3: Verify the script still imports cleanly**

```bash
source .arbit_env && .venv/bin/python -c "import scripts.pipeline_hourly"
```

Expected: no traceback.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline_hourly.py
git commit -m "feat(pipeline): invoke trade reconcile after fill ingestion (flag-gated)"
```

---

## Phase B — REST API

### Task B1: Pydantic models for trade API

**Files:**
- Create: `api/models/trade_schemas.py`

- [ ] **Step 1: Create the schema module**

```python
# api/models/trade_schemas.py
"""Pydantic request/response models for /api/trades and position create."""
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class TradeCreateRequest(BaseModel):
    position_id: str
    trade_type: Literal["OPEN", "CLOSE"]
    start_ts: int = Field(..., description="epoch ms UTC")
    end_ts: int = Field(..., description="epoch ms UTC, exclusive")
    note: Optional[str] = None


class TradePreviewRequest(TradeCreateRequest):
    pass


class TradeEditRequest(BaseModel):
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    trade_type: Optional[Literal["OPEN", "CLOSE"]] = None
    note: Optional[str] = None


class TradeItem(BaseModel):
    trade_id: str
    position_id: str
    trade_type: Literal["OPEN", "CLOSE"]
    state: Literal["DRAFT", "FINALIZED"]
    start_ts: int
    end_ts: int
    note: Optional[str] = None

    long_leg_id: str
    long_size: Optional[float] = None
    long_notional: Optional[float] = None
    long_avg_px: Optional[float] = None
    long_fees: Optional[float] = None
    long_fill_count: Optional[int] = None

    short_leg_id: str
    short_size: Optional[float] = None
    short_notional: Optional[float] = None
    short_avg_px: Optional[float] = None
    short_fees: Optional[float] = None
    short_fill_count: Optional[int] = None

    spread_bps: Optional[float] = None
    realized_pnl_bps: Optional[float] = None

    created_at_ms: int
    finalized_at_ms: Optional[int] = None
    computed_at_ms: int

    unassigned_fills_count: Optional[int] = None  # populated when warning row exists


class TradeListResponse(BaseModel):
    items: list[TradeItem]
    total: int


class LinkedFillItem(BaseModel):
    fill_id: int
    leg_side: Literal["LONG", "SHORT"]
    inst_id: str
    side: Literal["BUY", "SELL"]
    px: float
    sz: float
    fee: Optional[float] = None
    ts: int


class TradeDetailResponse(TradeItem):
    fills: list[LinkedFillItem]


class PositionLegInput(BaseModel):
    leg_id: str
    venue: str
    inst_id: str
    side: Literal["LONG", "SHORT"]
    wallet_label: Optional[str] = None
    account_id: Optional[str] = None


class PositionCreateRequest(BaseModel):
    position_id: str
    base: str
    strategy_type: Literal["SPOT_PERP", "PERP_PERP"]
    venue: str
    long_leg: PositionLegInput
    short_leg: PositionLegInput
```

- [ ] **Step 2: Verify import**

```bash
source .arbit_env && .venv/bin/python -c "from api.models.trade_schemas import TradeCreateRequest"
```

Expected: no traceback.

- [ ] **Step 3: Commit**

```bash
git add api/models/trade_schemas.py
git commit -m "feat(api): add pydantic models for trades + position create"
```

---

### Task B2: Trades router skeleton + list/get endpoints

**Files:**
- Create: `api/routers/trades.py`
- Modify: `api/main.py`

- [ ] **Step 1: Create router with list + detail endpoints**

```python
# api/routers/trades.py
"""Trade aggregation endpoints.

POST   /api/trades               create DRAFT
POST   /api/trades/preview       dry-run aggregation
GET    /api/trades               list with filters
GET    /api/trades/:id           detail + linked fills
PATCH  /api/trades/:id           edit DRAFT
POST   /api/trades/:id/finalize
POST   /api/trades/:id/reopen
POST   /api/trades/:id/recompute
DELETE /api/trades/:id
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.models.trade_schemas import (
    TradeCreateRequest,
    TradePreviewRequest,
    TradeEditRequest,
    TradeItem,
    TradeListResponse,
    TradeDetailResponse,
    LinkedFillItem,
)
from tracking.pipeline.trades import (
    create_draft_trade,
    recompute_trade,
    finalize_trade,
    reopen_trade,
    delete_trade,
    TradeCreateError,
)


router = APIRouter(prefix="/api/trades", tags=["trades"])


def _row_to_item(row: sqlite3.Row, unassigned: Optional[int] = None) -> TradeItem:
    d = {k: row[k] for k in row.keys()}
    d["unassigned_fills_count"] = unassigned
    return TradeItem(**d)


def _row_to_dict_item(row: dict, unassigned: Optional[int] = None) -> TradeItem:
    row = dict(row)
    row["unassigned_fills_count"] = unassigned
    return TradeItem(**row)


@router.get("", response_model=TradeListResponse)
def list_trades(
    position_id: Optional[str] = None,
    trade_type: Optional[str] = Query(None, regex="^(OPEN|CLOSE)$"),
    state: Optional[str] = Query(None, regex="^(DRAFT|FINALIZED)$"),
    start_ts_gte: Optional[int] = None,
    end_ts_lte: Optional[int] = None,
    db: sqlite3.Connection = Depends(get_db),
):
    db.row_factory = sqlite3.Row
    clauses = []
    args: list = []
    if position_id:
        clauses.append("position_id = ?"); args.append(position_id)
    if trade_type:
        clauses.append("trade_type = ?"); args.append(trade_type)
    if state:
        clauses.append("state = ?"); args.append(state)
    if start_ts_gte is not None:
        clauses.append("start_ts >= ?"); args.append(start_ts_gte)
    if end_ts_lte is not None:
        clauses.append("end_ts <= ?"); args.append(end_ts_lte)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    rows = db.execute(
        f"SELECT * FROM pm_trades {where} ORDER BY start_ts DESC LIMIT 500", args
    ).fetchall()

    warn_map = {
        r[0]: r[1]
        for r in db.execute(
            "SELECT trade_id, unassigned_count FROM pm_trade_reconcile_warnings"
        ).fetchall()
    }

    items = [_row_to_item(r, warn_map.get(r["trade_id"])) for r in rows]
    return TradeListResponse(items=items, total=len(items))


@router.get("/{trade_id}", response_model=TradeDetailResponse)
def get_trade(trade_id: str, db: sqlite3.Connection = Depends(get_db)):
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"trade not found: {trade_id}")
    warn_row = db.execute(
        "SELECT unassigned_count FROM pm_trade_reconcile_warnings WHERE trade_id=?",
        (trade_id,),
    ).fetchone()
    warn = warn_row[0] if warn_row else None

    fill_rows = db.execute(
        """
        SELECT tf.fill_id, tf.leg_side, f.inst_id, f.side, f.px, f.sz, f.fee, f.ts
        FROM pm_trade_fills tf JOIN pm_fills f ON f.fill_id = tf.fill_id
        WHERE tf.trade_id = ?
        ORDER BY f.ts
        """,
        (trade_id,),
    ).fetchall()
    fills = [
        LinkedFillItem(
            fill_id=r["fill_id"], leg_side=r["leg_side"],
            inst_id=r["inst_id"], side=r["side"], px=r["px"], sz=r["sz"],
            fee=r["fee"], ts=r["ts"],
        )
        for r in fill_rows
    ]

    d = {k: row[k] for k in row.keys()}
    d["unassigned_fills_count"] = warn
    d["fills"] = fills
    return TradeDetailResponse(**d)
```

- [ ] **Step 2: Register router in `api/main.py`**

Find the section where other routers are imported/registered (grep for `include_router`), and add:

```python
from api.routers import trades as trades_router
# ...
app.include_router(trades_router.router)
```

- [ ] **Step 3: Smoke test the endpoints**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py -v 2>&1 | tail -20
```

Expected: existing tests still pass; no import errors for trades router.

Also verify with curl (manual spot-check):

```bash
.venv/bin/uvicorn api.main:app --host 127.0.0.1 --port 8765 &
sleep 2
curl -s http://127.0.0.1:8765/api/trades | head
kill %1
```

Expected: `{"items":[],"total":0}` (empty DB).

- [ ] **Step 4: Commit**

```bash
git add api/routers/trades.py api/main.py
git commit -m "feat(api): add /api/trades list + detail endpoints"
```

---

### Task B3: Create DRAFT + preview + edit + state-transition endpoints

**Files:**
- Modify: `api/routers/trades.py`

- [ ] **Step 1: Append POST create + preview**

```python
@router.post("", response_model=TradeItem, status_code=201)
def create_trade(
    req: TradeCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    try:
        result = create_draft_trade(
            db,
            position_id=req.position_id,
            trade_type=req.trade_type,
            start_ts=req.start_ts,
            end_ts=req.end_ts,
            note=req.note,
        )
    except TradeCreateError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _row_to_dict_item(result)


@router.post("/preview", response_model=TradeItem)
def preview_trade(
    req: TradePreviewRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    """Dry-run: create DRAFT in a savepoint then roll back. Returns computed aggregates."""
    db.execute("SAVEPOINT preview")
    try:
        result = create_draft_trade(
            db, req.position_id, req.trade_type, req.start_ts, req.end_ts, req.note
        )
    except TradeCreateError as e:
        db.execute("ROLLBACK TO preview")
        db.execute("RELEASE preview")
        raise HTTPException(status_code=422, detail=str(e))
    db.execute("ROLLBACK TO preview")
    db.execute("RELEASE preview")
    return _row_to_dict_item(result)
```

- [ ] **Step 2: Append PATCH (edit DRAFT), finalize, reopen, recompute, delete**

```python
@router.patch("/{trade_id}", response_model=TradeItem)
def edit_trade(
    trade_id: str,
    req: TradeEditRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    db.row_factory = sqlite3.Row
    row = db.execute("SELECT * FROM pm_trades WHERE trade_id=?", (trade_id,)).fetchone()
    if not row:
        raise HTTPException(404, f"trade not found: {trade_id}")
    if row["state"] != "DRAFT":
        raise HTTPException(409, f"cannot edit trade in state {row['state']}; reopen first")

    updates = []
    args: list = []
    if req.start_ts is not None:
        updates.append("start_ts = ?"); args.append(req.start_ts)
    if req.end_ts is not None:
        updates.append("end_ts = ?"); args.append(req.end_ts)
    if req.trade_type is not None:
        updates.append("trade_type = ?"); args.append(req.trade_type)
    if req.note is not None:
        updates.append("note = ?"); args.append(req.note)
    if not updates:
        raise HTTPException(400, "no fields to update")

    # Clear link table: window/type change invalidates previous binding
    db.execute("DELETE FROM pm_trade_fills WHERE trade_id = ?", (trade_id,))
    args.append(trade_id)
    db.execute(f"UPDATE pm_trades SET {', '.join(updates)} WHERE trade_id = ?", args)
    db.commit()

    try:
        result = recompute_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(422, str(e))
    return _row_to_dict_item(result)


@router.post("/{trade_id}/finalize", response_model=TradeItem)
def finalize(trade_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        result = finalize_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(409, str(e))
    return _row_to_dict_item(result)


@router.post("/{trade_id}/reopen", response_model=TradeItem)
def reopen(trade_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        result = reopen_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(409, str(e))
    return _row_to_dict_item(result)


@router.post("/{trade_id}/recompute", response_model=TradeItem)
def recompute(trade_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        result = recompute_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(409, str(e))
    return _row_to_dict_item(result)


@router.delete("/{trade_id}", status_code=204)
def delete(trade_id: str, db: sqlite3.Connection = Depends(get_db)):
    try:
        delete_trade(db, trade_id)
    except TradeCreateError as e:
        raise HTTPException(404, str(e))
```

- [ ] **Step 3: Smoke test**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py -v 2>&1 | tail -10
```

Expected: existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add api/routers/trades.py
git commit -m "feat(api): create/preview/edit/finalize/reopen/recompute/delete for trades"
```

---

### Task B4: API integration tests (e2e over TestClient)

**Files:**
- Create: `tests/test_trades_api.py`

- [ ] **Step 1: Write tests exercising the full lifecycle over TestClient**

```python
# tests/test_trades_api.py
"""E2E test for /api/trades router using fastapi TestClient + in-memory DB.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_trades_api.py -v
"""
from __future__ import annotations
import sqlite3

import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.deps import get_db


_SCHEMA_SQL = open("tests/_schema_trades.sql").read() if False else None  # placeholder, inlined below


_INLINE_SCHEMA = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


@pytest.fixture
def client():
    con = sqlite3.connect(":memory:", check_same_thread=False)
    con.executescript(_INLINE_SCHEMA)
    con.execute("INSERT INTO pm_positions (position_id,venue,status,created_at_ms,updated_at_ms,base,strategy_type) VALUES ('pos_X','hyperliquid','OPEN',0,0,'GOOGL','SPOT_PERP')")
    con.execute("INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_X_SPOT','pos_X','hyperliquid','GOOGL','LONG',0,'OPEN',0,'0xMAIN')")
    con.execute("INSERT INTO pm_legs (leg_id,position_id,venue,inst_id,side,size,status,opened_at_ms,account_id) VALUES ('pos_X_PERP','pos_X','hyperliquid','xyz:GOOGL','SHORT',0,'OPEN',0,'0xMAIN')")
    con.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL","BUY",100.0,2.0,0.05,1100,"pos_X_SPOT","pos_X"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0,2.0,0.04,1200,"pos_X_PERP","pos_X"),
        ],
    )
    con.commit()

    def _override_db():
        yield con

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    con.close()


def test_preview_then_create_then_finalize(client):
    # Preview
    r = client.post("/api/trades/preview", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    assert r.status_code == 200, r.text
    assert r.json()["long_size"] == pytest.approx(2.0)

    # Preview must NOT persist
    r2 = client.get("/api/trades")
    assert r2.json()["total"] == 0

    # Create
    r3 = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    assert r3.status_code == 201, r3.text
    tid = r3.json()["trade_id"]

    # Finalize
    r4 = client.post(f"/api/trades/{tid}/finalize")
    assert r4.status_code == 200, r4.text
    assert r4.json()["state"] == "FINALIZED"


def test_edit_draft_updates_window(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]

    r2 = client.patch(f"/api/trades/{tid}", json={"end_ts": 1150})
    assert r2.status_code == 200, r2.text
    # Only the spot fill at ts=1100 falls in [1000, 1150)
    assert r2.json()["long_fill_count"] == 1


def test_delete_draft_releases_fills(client):
    r = client.post("/api/trades", json={
        "position_id": "pos_X", "trade_type": "OPEN",
        "start_ts": 1000, "end_ts": 2000,
    })
    tid = r.json()["trade_id"]
    r2 = client.delete(f"/api/trades/{tid}")
    assert r2.status_code == 204
    r3 = client.get(f"/api/trades/{tid}")
    assert r3.status_code == 404


def test_list_filters(client):
    client.post("/api/trades", json={"position_id":"pos_X","trade_type":"OPEN","start_ts":1000,"end_ts":2000})
    r = client.get("/api/trades?trade_type=OPEN&state=DRAFT")
    assert r.status_code == 200
    assert r.json()["total"] == 1


def test_get_detail_includes_linked_fills(client):
    r = client.post("/api/trades", json={"position_id":"pos_X","trade_type":"OPEN","start_ts":1000,"end_ts":2000})
    tid = r.json()["trade_id"]
    r2 = client.get(f"/api/trades/{tid}")
    assert r2.status_code == 200
    assert len(r2.json()["fills"]) == 2
```

- [ ] **Step 2: Run the tests**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_trades_api.py -v
```

Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/test_trades_api.py
git commit -m "test(api): e2e lifecycle over TestClient for /api/trades"
```

---

### Task B5: Position create endpoint + extended detail

**Files:**
- Modify: `api/routers/positions.py`
- Modify: `api/models/schemas.py` (add derived fields to PositionDetail)

- [ ] **Step 1: Read existing positions router structure**

```bash
wc -l api/routers/positions.py && grep -n "^def \|@router" api/routers/positions.py | head -20
```

- [ ] **Step 2: Add POST /api/positions handler**

At the end of `api/routers/positions.py`:

```python
from api.models.trade_schemas import PositionCreateRequest


@router.post("", status_code=201)
def create_position(
    req: PositionCreateRequest,
    db: sqlite3.Connection = Depends(get_db),
):
    # Validate legs have opposite sides
    if req.long_leg.side != "LONG" or req.short_leg.side != "SHORT":
        raise HTTPException(422, "long_leg must be LONG, short_leg must be SHORT")

    now = int(datetime.now(tz=timezone.utc).timestamp() * 1000)

    existing = db.execute(
        "SELECT 1 FROM pm_positions WHERE position_id = ?", (req.position_id,)
    ).fetchone()
    if existing:
        raise HTTPException(409, f"position already exists: {req.position_id}")

    db.execute(
        "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
        "VALUES (?,?,?,?,?,?,?)",
        (req.position_id, req.venue, "OPEN", now, now, req.base, req.strategy_type),
    )
    for leg in (req.long_leg, req.short_leg):
        db.execute(
            "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, meta_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                leg.leg_id, req.position_id, leg.venue, leg.inst_id, leg.side,
                0.0, "OPEN", now, leg.account_id,
                f'{{"wallet_label":"{leg.wallet_label}"}}' if leg.wallet_label else None,
            ),
        )
    db.commit()
    return {"position_id": req.position_id, "status": "OPEN"}
```

- [ ] **Step 3: Extend GET /api/positions/:id to include derived fields**

Find the existing `@router.get("/{position_id}")` handler and add, after the base query:

```python
# Derived from trades
trades_agg = db.execute(
    """
    SELECT
      COUNT(*) FILTER (WHERE state='FINALIZED' AND trade_type='OPEN') AS open_count,
      COUNT(*) FILTER (WHERE state='FINALIZED' AND trade_type='CLOSE') AS close_count,
      SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN spread_bps*long_size ELSE 0 END)
        / NULLIF(SUM(CASE WHEN state='FINALIZED' AND trade_type='OPEN' THEN long_size ELSE 0 END), 0)
        AS weighted_avg_entry_spread_bps
    FROM pm_trades WHERE position_id = ?
    """,
    (position_id,),
).fetchone()
```

Add the derived values to the response dict.

(The exact fields returned depend on the existing `PositionDetail` schema; add `weighted_avg_entry_spread_bps: Optional[float]`, `open_trades_count: Optional[int]`, `close_trades_count: Optional[int]` to `api/models/schemas.py:PositionDetail` and populate them.)

- [ ] **Step 4: Verify existing tests + manual smoke**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py tests/test_trades_api.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add api/routers/positions.py api/models/schemas.py
git commit -m "feat(api): POST /api/positions + derived trade metrics on detail"
```

---

## Phase C — Frontend

### Task C1: API client + types

**Files:**
- Create: `frontend/lib/trades.ts`

- [ ] **Step 1: Create typed client**

```typescript
// frontend/lib/trades.ts
import { apiGet, apiPost, apiPatch, apiDelete } from "./api";

export type TradeType = "OPEN" | "CLOSE";
export type TradeState = "DRAFT" | "FINALIZED";

export interface Trade {
  trade_id: string;
  position_id: string;
  trade_type: TradeType;
  state: TradeState;
  start_ts: number;
  end_ts: number;
  note: string | null;

  long_leg_id: string;
  long_size: number | null;
  long_notional: number | null;
  long_avg_px: number | null;
  long_fees: number | null;
  long_fill_count: number | null;

  short_leg_id: string;
  short_size: number | null;
  short_notional: number | null;
  short_avg_px: number | null;
  short_fees: number | null;
  short_fill_count: number | null;

  spread_bps: number | null;
  realized_pnl_bps: number | null;

  created_at_ms: number;
  finalized_at_ms: number | null;
  computed_at_ms: number;

  unassigned_fills_count: number | null;
}

export interface LinkedFill {
  fill_id: number;
  leg_side: "LONG" | "SHORT";
  inst_id: string;
  side: "BUY" | "SELL";
  px: number;
  sz: number;
  fee: number | null;
  ts: number;
}

export interface TradeDetail extends Trade {
  fills: LinkedFill[];
}

export interface TradeListFilters {
  position_id?: string;
  trade_type?: TradeType;
  state?: TradeState;
  start_ts_gte?: number;
  end_ts_lte?: number;
}

export interface TradeCreateInput {
  position_id: string;
  trade_type: TradeType;
  start_ts: number;
  end_ts: number;
  note?: string;
}

export async function listTrades(filters: TradeListFilters = {}): Promise<{ items: Trade[]; total: number }> {
  const qs = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => { if (v != null) qs.set(k, String(v)); });
  return apiGet(`/api/trades?${qs.toString()}`);
}

export async function getTrade(id: string): Promise<TradeDetail> {
  return apiGet(`/api/trades/${id}`);
}

export async function previewTrade(input: TradeCreateInput): Promise<Trade> {
  return apiPost("/api/trades/preview", input);
}

export async function createTrade(input: TradeCreateInput): Promise<Trade> {
  return apiPost("/api/trades", input);
}

export async function editTrade(id: string, patch: Partial<TradeCreateInput>): Promise<Trade> {
  return apiPatch(`/api/trades/${id}`, patch);
}

export async function finalizeTrade(id: string): Promise<Trade> {
  return apiPost(`/api/trades/${id}/finalize`, {});
}

export async function reopenTrade(id: string): Promise<Trade> {
  return apiPost(`/api/trades/${id}/reopen`, {});
}

export async function recomputeTrade(id: string): Promise<Trade> {
  return apiPost(`/api/trades/${id}/recompute`, {});
}

export async function deleteTrade(id: string): Promise<void> {
  return apiDelete(`/api/trades/${id}`);
}
```

- [ ] **Step 2: Ensure `frontend/lib/api.ts` exports the generic helpers**

```bash
grep -n "export async function apiGet\|export async function apiPost\|export async function apiPatch\|export async function apiDelete" frontend/lib/api.ts
```

If any helper missing, add it following existing `apiGet` pattern in the file.

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/trades.ts frontend/lib/api.ts
git commit -m "feat(frontend): add trades API client + types"
```

---

### Task C2: TradesTable component (reusable)

**Files:**
- Create: `frontend/components/TradesTable.tsx`

- [ ] **Step 1: Build the table**

```tsx
// frontend/components/TradesTable.tsx
"use client";

import Link from "next/link";
import { useMemo } from "react";
import type { Trade } from "@/lib/trades";
import { formatUSD, formatBps } from "@/lib/format";

interface Props {
  trades: Trade[];
  showPosition?: boolean; // false when embedded in position detail
}

function formatWindow(start: number, end: number): string {
  const s = new Date(start).toISOString().slice(0, 16).replace("T", " ");
  const e = new Date(end).toISOString().slice(0, 16).replace("T", " ");
  return `${s} → ${e}`;
}

export default function TradesTable({ trades, showPosition = true }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left">
          <tr>
            <th className="p-2">Trade</th>
            {showPosition && <th className="p-2">Position</th>}
            <th className="p-2">Type</th>
            <th className="p-2">State</th>
            <th className="p-2">Window</th>
            <th className="p-2">Long Size</th>
            <th className="p-2">Long Notional</th>
            <th className="p-2">Long Avg Px</th>
            <th className="p-2">Short Size</th>
            <th className="p-2">Short Notional</th>
            <th className="p-2">Short Avg Px</th>
            <th className="p-2">Spread (bps)</th>
            <th className="p-2">Realized P&L (bps)</th>
            <th className="p-2">Fees</th>
            <th className="p-2">Fills</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.trade_id} className="border-t hover:bg-gray-50">
              <td className="p-2">
                <Link href={`/trades/${t.trade_id}`} className="text-blue-600 hover:underline">
                  {t.trade_id}
                </Link>
                {t.unassigned_fills_count ? (
                  <span className="ml-2 rounded bg-yellow-100 px-1 text-xs text-yellow-800">
                    ⚠ {t.unassigned_fills_count} late
                  </span>
                ) : null}
              </td>
              {showPosition && (
                <td className="p-2">
                  <Link href={`/positions/${t.position_id}`} className="text-blue-600 hover:underline">
                    {t.position_id}
                  </Link>
                </td>
              )}
              <td className="p-2">{t.trade_type}</td>
              <td className="p-2">
                <span
                  className={
                    t.state === "DRAFT"
                      ? "rounded bg-gray-200 px-1 text-xs"
                      : "rounded bg-green-100 px-1 text-xs text-green-800"
                  }
                >
                  {t.state}
                </span>
              </td>
              <td className="p-2 whitespace-nowrap">{formatWindow(t.start_ts, t.end_ts)}</td>
              <td className="p-2">{t.long_size?.toFixed(4) ?? "—"}</td>
              <td className="p-2">{t.long_notional != null ? formatUSD(t.long_notional) : "—"}</td>
              <td className="p-2">{t.long_avg_px?.toFixed(4) ?? "—"}</td>
              <td className="p-2">{t.short_size?.toFixed(4) ?? "—"}</td>
              <td className="p-2">{t.short_notional != null ? formatUSD(t.short_notional) : "—"}</td>
              <td className="p-2">{t.short_avg_px?.toFixed(4) ?? "—"}</td>
              <td className="p-2">{t.spread_bps != null ? formatBps(t.spread_bps) : "—"}</td>
              <td className="p-2">{t.realized_pnl_bps != null ? formatBps(t.realized_pnl_bps) : "—"}</td>
              <td className="p-2">
                {((t.long_fees ?? 0) + (t.short_fees ?? 0)).toFixed(2)}
              </td>
              <td className="p-2">
                {(t.long_fill_count ?? 0) + (t.short_fill_count ?? 0)}
              </td>
            </tr>
          ))}
          {trades.length === 0 && (
            <tr>
              <td colSpan={showPosition ? 15 : 14} className="p-4 text-center text-gray-500">
                No trades.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && yarn tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/TradesTable.tsx
git commit -m "feat(frontend): add reusable TradesTable component"
```

---

### Task C3: /trades global page

**Files:**
- Create: `frontend/app/trades/page.tsx`

- [ ] **Step 1: Create page**

```tsx
// frontend/app/trades/page.tsx
"use client";

import { useEffect, useState } from "react";
import TradesTable from "@/components/TradesTable";
import NewTradeModal from "@/components/NewTradeModal";
import { listTrades, type Trade, type TradeType, type TradeState } from "@/lib/trades";

export default function TradesPage() {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [positionFilter, setPositionFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<TradeType | "">("");
  const [stateFilter, setStateFilter] = useState<TradeState | "">("");
  const [showModal, setShowModal] = useState(false);

  async function load() {
    setLoading(true);
    try {
      const res = await listTrades({
        position_id: positionFilter || undefined,
        trade_type: typeFilter || undefined,
        state: stateFilter || undefined,
      });
      setTrades(res.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [positionFilter, typeFilter, stateFilter]);

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trades</h1>
        <button
          onClick={() => setShowModal(true)}
          className="rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
        >
          + New Trade
        </button>
      </div>
      <div className="mb-4 flex gap-3">
        <input
          className="rounded border px-2 py-1"
          placeholder="Filter by position_id"
          value={positionFilter}
          onChange={(e) => setPositionFilter(e.target.value)}
        />
        <select
          className="rounded border px-2 py-1"
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value as TradeType | "")}
        >
          <option value="">All Types</option>
          <option value="OPEN">OPEN</option>
          <option value="CLOSE">CLOSE</option>
        </select>
        <select
          className="rounded border px-2 py-1"
          value={stateFilter}
          onChange={(e) => setStateFilter(e.target.value as TradeState | "")}
        >
          <option value="">All States</option>
          <option value="DRAFT">DRAFT</option>
          <option value="FINALIZED">FINALIZED</option>
        </select>
      </div>
      {loading ? <p>Loading…</p> : <TradesTable trades={trades} />}
      {showModal && (
        <NewTradeModal
          onClose={() => setShowModal(false)}
          onSaved={() => { setShowModal(false); load(); }}
        />
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add nav link**

Edit `frontend/components/NavSidebar.tsx` — add "Trades" link after "Positions" pointing at `/trades`.

- [ ] **Step 3: Build + visual smoke**

```bash
cd frontend && yarn build 2>&1 | tail -20
```

Expected: build succeeds (page may show "NewTradeModal not found" — that's the next task; if so, stub a minimal file to unblock the build).

- [ ] **Step 4: Commit**

```bash
git add frontend/app/trades/page.tsx frontend/components/NavSidebar.tsx
git commit -m "feat(frontend): add /trades global page with filters"
```

---

### Task C4: NewTradeModal with preview + save + finalize

**Files:**
- Create: `frontend/components/NewTradeModal.tsx`

- [ ] **Step 1: Build the modal**

```tsx
// frontend/components/NewTradeModal.tsx
"use client";

import { useEffect, useState } from "react";
import { previewTrade, createTrade, finalizeTrade, type Trade, type TradeType } from "@/lib/trades";
import { apiGet } from "@/lib/api";

interface Position { position_id: string; base: string | null; status: string; }

interface Props {
  onClose: () => void;
  onSaved: () => void;
  defaultPositionId?: string;
}

function toEpochMs(localStr: string): number {
  return new Date(localStr).getTime();
}

function fromEpochMs(ms: number): string {
  const d = new Date(ms);
  return d.toISOString().slice(0, 16);
}

export default function NewTradeModal({ onClose, onSaved, defaultPositionId }: Props) {
  const [positions, setPositions] = useState<Position[]>([]);
  const [positionId, setPositionId] = useState(defaultPositionId || "");
  const [tradeType, setTradeType] = useState<TradeType>("OPEN");
  const [startStr, setStartStr] = useState(fromEpochMs(Date.now() - 3600 * 1000));
  const [endStr, setEndStr] = useState(fromEpochMs(Date.now()));
  const [note, setNote] = useState("");

  const [preview, setPreview] = useState<Trade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    apiGet<{ items: Position[] }>("/api/positions").then((r) => setPositions(r.items));
  }, []);

  async function runPreview() {
    setError(null);
    setBusy(true);
    try {
      const p = await previewTrade({
        position_id: positionId,
        trade_type: tradeType,
        start_ts: toEpochMs(startStr),
        end_ts: toEpochMs(endStr),
        note: note || undefined,
      });
      setPreview(p);
    } catch (e: any) {
      setError(e.message || String(e));
      setPreview(null);
    } finally { setBusy(false); }
  }

  async function save(doFinalize: boolean) {
    setError(null);
    setBusy(true);
    try {
      const t = await createTrade({
        position_id: positionId,
        trade_type: tradeType,
        start_ts: toEpochMs(startStr),
        end_ts: toEpochMs(endStr),
        note: note || undefined,
      });
      if (doFinalize) {
        await finalizeTrade(t.trade_id);
      }
      onSaved();
    } catch (e: any) {
      setError(e.message || String(e));
    } finally { setBusy(false); }
  }

  const sizeDelta =
    preview && preview.long_size != null && preview.short_size != null
      ? Math.abs(preview.long_size - preview.short_size)
      : 0;
  const avgSize =
    preview && preview.long_size != null && preview.short_size != null
      ? (preview.long_size + preview.short_size) / 2
      : 0;
  const sizeMismatchPct = avgSize > 0 ? (sizeDelta / avgSize) * 100 : 0;
  const showSizeWarning = sizeMismatchPct > 0.5;

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black bg-opacity-40 z-50">
      <div className="w-[600px] max-h-[90vh] overflow-auto rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-xl font-bold">New Trade</h2>

        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium">Position</label>
            <select className="mt-1 w-full rounded border px-2 py-1"
                    value={positionId} onChange={(e) => setPositionId(e.target.value)}>
              <option value="">— select —</option>
              {positions.filter(p => p.status !== "CLOSED").map(p => (
                <option key={p.position_id} value={p.position_id}>
                  {p.position_id} ({p.base || "?"})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium">Type</label>
            <div className="mt-1 flex gap-3">
              <label><input type="radio" checked={tradeType==="OPEN"}  onChange={()=>setTradeType("OPEN")}/> OPEN</label>
              <label><input type="radio" checked={tradeType==="CLOSE"} onChange={()=>setTradeType("CLOSE")}/> CLOSE</label>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="block text-sm font-medium">Start (local)</label>
              <input type="datetime-local" className="mt-1 w-full rounded border px-2 py-1"
                     value={startStr} onChange={(e) => setStartStr(e.target.value)} />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium">End (local)</label>
              <input type="datetime-local" className="mt-1 w-full rounded border px-2 py-1"
                     value={endStr} onChange={(e) => setEndStr(e.target.value)} />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium">Note (optional)</label>
            <textarea className="mt-1 w-full rounded border px-2 py-1" rows={2}
                      value={note} onChange={(e) => setNote(e.target.value)} />
          </div>

          <button onClick={runPreview} disabled={busy || !positionId}
                  className="rounded bg-gray-600 px-3 py-1 text-white disabled:opacity-50">
            Preview
          </button>

          {error && <p className="text-red-600">{error}</p>}

          {preview && (
            <div className="mt-3 rounded bg-gray-50 p-3 text-sm">
              <p><b>Long leg ({preview.long_leg_id}):</b> {preview.long_fill_count} fills,
                 size={preview.long_size?.toFixed(4)}, notional=${preview.long_notional?.toFixed(2)},
                 avg_px={preview.long_avg_px?.toFixed(4)}, fees=${preview.long_fees?.toFixed(4)}</p>
              <p><b>Short leg ({preview.short_leg_id}):</b> {preview.short_fill_count} fills,
                 size={preview.short_size?.toFixed(4)}, notional=${preview.short_notional?.toFixed(2)},
                 avg_px={preview.short_avg_px?.toFixed(4)}, fees=${preview.short_fees?.toFixed(4)}</p>
              {showSizeWarning && (
                <p className="text-yellow-700">⚠ Size delta {sizeMismatchPct.toFixed(2)}% (not delta-neutral)</p>
              )}
              <p className="font-medium">
                {tradeType === "OPEN"
                  ? `Entry spread: ${preview.spread_bps?.toFixed(2)} bps`
                  : `Exit spread: ${preview.spread_bps?.toFixed(2)} bps; realized P&L: ${preview.realized_pnl_bps?.toFixed(2) ?? "—"} bps`}
              </p>
            </div>
          )}
        </div>

        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1">Cancel</button>
          <button onClick={() => save(false)} disabled={busy || !preview}
                  className="rounded bg-gray-700 px-3 py-1 text-white disabled:opacity-50">
            Save as DRAFT
          </button>
          <button onClick={() => save(true)} disabled={busy || !preview}
                  className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50">
            Finalize now
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

```bash
cd frontend && yarn tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/components/NewTradeModal.tsx
git commit -m "feat(frontend): NewTradeModal with preview + save + finalize"
```

---

### Task C5: Trade detail page + drawer actions

**Files:**
- Create: `frontend/app/trades/[id]/page.tsx`

- [ ] **Step 1: Create detail page**

```tsx
// frontend/app/trades/[id]/page.tsx
"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  getTrade, finalizeTrade, reopenTrade, recomputeTrade, deleteTrade,
  type TradeDetail,
} from "@/lib/trades";
import { formatBps, formatUSD } from "@/lib/format";

export default function TradeDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const [trade, setTrade] = useState<TradeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setError(null);
    try { setTrade(await getTrade(params.id)); }
    catch (e: any) { setError(e.message); }
  }
  useEffect(() => { load(); }, [params.id]);

  async function onFinalize() { await finalizeTrade(params.id); load(); }
  async function onReopen() { await reopenTrade(params.id); load(); }
  async function onRecompute() { await recomputeTrade(params.id); load(); }
  async function onDelete() {
    if (!confirm("Delete this trade? Linked fills return to unassigned pool.")) return;
    await deleteTrade(params.id);
    router.push("/trades");
  }

  function downloadCsv() {
    if (!trade) return;
    const header = "fill_id,leg_side,inst_id,side,px,sz,fee,ts\n";
    const rows = trade.fills.map(f =>
      `${f.fill_id},${f.leg_side},${f.inst_id},${f.side},${f.px},${f.sz},${f.fee ?? ""},${f.ts}`
    );
    const blob = new Blob([header + rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${trade.trade_id}_fills.csv`; a.click();
    URL.revokeObjectURL(url);
  }

  if (error) return <div className="p-6 text-red-600">Error: {error}</div>;
  if (!trade) return <div className="p-6">Loading…</div>;

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">{trade.trade_id}</h1>
        <div className="flex gap-2">
          {trade.state === "DRAFT" && (
            <>
              <button onClick={onRecompute} className="rounded border px-3 py-1">Recompute</button>
              <button onClick={onFinalize} className="rounded bg-blue-600 px-3 py-1 text-white">Finalize</button>
              <button onClick={onDelete} className="rounded bg-red-600 px-3 py-1 text-white">Delete</button>
            </>
          )}
          {trade.state === "FINALIZED" && (
            <>
              <button onClick={onReopen} className="rounded border px-3 py-1">Reopen to edit</button>
              <button onClick={onDelete} className="rounded bg-red-600 px-3 py-1 text-white">Delete</button>
            </>
          )}
          <button onClick={downloadCsv} className="rounded border px-3 py-1">Download CSV</button>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-2 gap-6 rounded border p-4 text-sm">
        <div>
          <p><b>Position:</b> {trade.position_id}</p>
          <p><b>Type:</b> {trade.trade_type}</p>
          <p><b>State:</b> {trade.state}{trade.unassigned_fills_count ? ` ⚠ ${trade.unassigned_fills_count} late fills` : ""}</p>
          <p><b>Window:</b> {new Date(trade.start_ts).toISOString()} → {new Date(trade.end_ts).toISOString()}</p>
          {trade.note && <p><b>Note:</b> {trade.note}</p>}
        </div>
        <div>
          <p><b>Spread:</b> {trade.spread_bps != null ? formatBps(trade.spread_bps) : "—"}</p>
          <p><b>Realized P&L:</b> {trade.realized_pnl_bps != null ? formatBps(trade.realized_pnl_bps) : "—"}</p>
          <p><b>Fees:</b> ${((trade.long_fees ?? 0) + (trade.short_fees ?? 0)).toFixed(2)}</p>
        </div>
      </div>

      <h2 className="mb-2 text-lg font-semibold">Linked Fills ({trade.fills.length})</h2>
      <table className="w-full text-sm">
        <thead><tr className="bg-gray-50 text-left">
          <th className="p-2">Fill</th><th className="p-2">Leg</th><th className="p-2">Instrument</th>
          <th className="p-2">Side</th><th className="p-2">Px</th><th className="p-2">Sz</th>
          <th className="p-2">Fee</th><th className="p-2">Timestamp</th>
        </tr></thead>
        <tbody>
          {trade.fills.map(f => (
            <tr key={f.fill_id} className="border-t">
              <td className="p-2">{f.fill_id}</td>
              <td className="p-2">{f.leg_side}</td>
              <td className="p-2">{f.inst_id}</td>
              <td className="p-2">{f.side}</td>
              <td className="p-2">{f.px}</td>
              <td className="p-2">{f.sz}</td>
              <td className="p-2">{f.fee ?? "—"}</td>
              <td className="p-2">{new Date(f.ts).toISOString()}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 2: Build check**

```bash
cd frontend && yarn tsc --noEmit
```

Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add frontend/app/trades/'[id]'/page.tsx
git commit -m "feat(frontend): /trades/:id detail page with actions + CSV export"
```

---

### Task C6: Embed Trades tab in /positions/:id + "+ New Position" modal

**Files:**
- Modify: `frontend/app/positions/[id]/page.tsx`
- Create: `frontend/components/NewPositionModal.tsx`
- Modify: `frontend/components/PositionsTable.tsx`

- [ ] **Step 1: Read existing detail page to understand its layout**

```bash
cat frontend/app/positions/'[id]'/page.tsx
```

- [ ] **Step 2: Add Trades tab to existing position detail page**

Insert a tab state (if not present) and a new tab rendering `<TradesTable trades={...} showPosition={false} />` populated by `listTrades({ position_id: id })`. Add a "+ New Trade" button that opens `NewTradeModal` with `defaultPositionId` prefilled.

Exact code:

```tsx
// In frontend/app/positions/[id]/page.tsx:
import TradesTable from "@/components/TradesTable";
import NewTradeModal from "@/components/NewTradeModal";
import { listTrades, type Trade } from "@/lib/trades";
// ... (existing imports)

// Inside the component body:
const [trades, setTrades] = useState<Trade[]>([]);
const [showTradeModal, setShowTradeModal] = useState(false);

useEffect(() => {
  listTrades({ position_id: params.id }).then(r => setTrades(r.items));
}, [params.id]);

// In the tab section, add:
<section className="mt-6">
  <div className="mb-2 flex items-center justify-between">
    <h2 className="text-lg font-semibold">Trades</h2>
    <button onClick={() => setShowTradeModal(true)}
            className="rounded bg-blue-600 px-3 py-1 text-white">+ New Trade</button>
  </div>
  <TradesTable trades={trades} showPosition={false} />
</section>

{showTradeModal && (
  <NewTradeModal
    defaultPositionId={params.id}
    onClose={() => setShowTradeModal(false)}
    onSaved={() => {
      setShowTradeModal(false);
      listTrades({ position_id: params.id }).then(r => setTrades(r.items));
    }}
  />
)}
```

- [ ] **Step 3: Create NewPositionModal**

```tsx
// frontend/components/NewPositionModal.tsx
"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

type StrategyType = "SPOT_PERP" | "PERP_PERP";

export default function NewPositionModal({ onClose, onSaved }: Props) {
  const [positionId, setPositionId] = useState("");
  const [base, setBase] = useState("");
  const [strategyType, setStrategyType] = useState<StrategyType>("SPOT_PERP");
  const [venue, setVenue] = useState("hyperliquid");
  const [longInst, setLongInst] = useState("");
  const [longWallet, setLongWallet] = useState("main");
  const [shortInst, setShortInst] = useState("");
  const [shortWallet, setShortWallet] = useState("main");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setError(null); setBusy(true);
    try {
      await apiPost("/api/positions", {
        position_id: positionId,
        base,
        strategy_type: strategyType,
        venue,
        long_leg: {
          leg_id: `${positionId}_SPOT`,
          venue,
          inst_id: longInst,
          side: "LONG",
          wallet_label: longWallet,
        },
        short_leg: {
          leg_id: `${positionId}_PERP`,
          venue,
          inst_id: shortInst,
          side: "SHORT",
          wallet_label: shortWallet,
        },
      });
      onSaved();
    } catch (e: any) {
      setError(e.message || String(e));
    } finally { setBusy(false); }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-40">
      <div className="w-[500px] rounded bg-white p-6 shadow-lg">
        <h2 className="mb-4 text-xl font-bold">New Position</h2>
        <div className="space-y-3 text-sm">
          <label className="block"><span className="font-medium">Position ID</span>
            <input className="mt-1 w-full rounded border px-2 py-1" value={positionId} onChange={e=>setPositionId(e.target.value)} placeholder="pos_xyz_GOOGL"/></label>
          <label className="block"><span className="font-medium">Base</span>
            <input className="mt-1 w-full rounded border px-2 py-1" value={base} onChange={e=>setBase(e.target.value)} placeholder="GOOGL"/></label>
          <label className="block"><span className="font-medium">Strategy</span>
            <select className="mt-1 w-full rounded border px-2 py-1" value={strategyType} onChange={e=>setStrategyType(e.target.value as StrategyType)}>
              <option value="SPOT_PERP">SPOT_PERP</option><option value="PERP_PERP">PERP_PERP</option>
            </select></label>
          <label className="block"><span className="font-medium">Venue</span>
            <input className="mt-1 w-full rounded border px-2 py-1" value={venue} onChange={e=>setVenue(e.target.value)}/></label>
          <div className="rounded border p-2">
            <p className="font-medium">Long leg</p>
            <label className="block"><span>inst_id</span>
              <input className="mt-1 w-full rounded border px-2 py-1" value={longInst} onChange={e=>setLongInst(e.target.value)}/></label>
            <label className="block"><span>wallet</span>
              <input className="mt-1 w-full rounded border px-2 py-1" value={longWallet} onChange={e=>setLongWallet(e.target.value)}/></label>
          </div>
          <div className="rounded border p-2">
            <p className="font-medium">Short leg</p>
            <label className="block"><span>inst_id</span>
              <input className="mt-1 w-full rounded border px-2 py-1" value={shortInst} onChange={e=>setShortInst(e.target.value)}/></label>
            <label className="block"><span>wallet</span>
              <input className="mt-1 w-full rounded border px-2 py-1" value={shortWallet} onChange={e=>setShortWallet(e.target.value)}/></label>
          </div>
          {error && <p className="text-red-600">{error}</p>}
        </div>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onClose} className="rounded border px-3 py-1">Cancel</button>
          <button onClick={save} disabled={busy}
                  className="rounded bg-blue-600 px-3 py-1 text-white disabled:opacity-50">Create</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add "+ New Position" button in PositionsTable**

In `frontend/components/PositionsTable.tsx`, add state + button above the table:

```tsx
import NewPositionModal from "./NewPositionModal";
import { useState } from "react";
// ...
const [showNewPos, setShowNewPos] = useState(false);
// Above the table:
<div className="mb-2 flex justify-end">
  <button onClick={() => setShowNewPos(true)} className="rounded bg-blue-600 px-3 py-1 text-white">+ New Position</button>
</div>
{showNewPos && <NewPositionModal onClose={()=>setShowNewPos(false)} onSaved={()=>{setShowNewPos(false); window.location.reload();}}/>}
```

- [ ] **Step 5: Build**

```bash
cd frontend && yarn tsc --noEmit && yarn build 2>&1 | tail -20
```

Expected: exit 0.

- [ ] **Step 6: Commit**

```bash
git add frontend/app/positions frontend/components/NewPositionModal.tsx frontend/components/PositionsTable.tsx
git commit -m "feat(frontend): embed Trades tab in position detail + NewPositionModal"
```

---

## Phase D — Migration + E2E + Deprecation

### Task D1: Migration script positions.json → DB

**Files:**
- Create: `scripts/migrate_positions_to_db.py`
- Create: `tests/test_migrate_positions_to_db.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_migrate_positions_to_db.py
"""Tests for migrate_positions_to_db.py — idempotency + diff report.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_positions_to_db.py -v
"""
from __future__ import annotations
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from scripts.migrate_positions_to_db import migrate


_SCHEMA = """
CREATE TABLE pm_positions (position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT, status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, base TEXT, strategy_type TEXT);
CREATE TABLE pm_legs (leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL, inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL, entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL, status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT, account_id TEXT);
CREATE TABLE pm_fills (fill_id INTEGER PRIMARY KEY AUTOINCREMENT, venue TEXT NOT NULL, account_id TEXT NOT NULL, tid TEXT, oid TEXT, inst_id TEXT NOT NULL, side TEXT NOT NULL CHECK (side IN ('BUY','SELL')), px REAL NOT NULL, sz REAL NOT NULL, fee REAL, fee_currency TEXT, ts INTEGER NOT NULL, closed_pnl REAL, dir TEXT, builder_fee REAL, position_id TEXT, leg_id TEXT, raw_json TEXT, meta_json TEXT);
CREATE TABLE pm_trades (trade_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, trade_type TEXT NOT NULL, state TEXT NOT NULL, start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, note TEXT, long_leg_id TEXT NOT NULL, long_size REAL, long_notional REAL, long_avg_px REAL, long_fees REAL, long_fill_count INTEGER, short_leg_id TEXT NOT NULL, short_size REAL, short_notional REAL, short_avg_px REAL, short_fees REAL, short_fill_count INTEGER, spread_bps REAL, realized_pnl_bps REAL, created_at_ms INTEGER NOT NULL, finalized_at_ms INTEGER, computed_at_ms INTEGER NOT NULL, UNIQUE (position_id, trade_type, start_ts, end_ts));
CREATE TABLE pm_trade_fills (trade_id TEXT NOT NULL, fill_id INTEGER NOT NULL, leg_side TEXT NOT NULL, PRIMARY KEY (trade_id, fill_id));
CREATE TABLE pm_trade_reconcile_warnings (trade_id TEXT PRIMARY KEY, unassigned_count INTEGER NOT NULL, first_seen_ms INTEGER NOT NULL, last_checked_ms INTEGER NOT NULL);
"""


def _fixture_positions():
    return [{
        "position_id": "pos_xyz_GOOGL",
        "strategy_type": "SPOT_PERP",
        "base": "GOOGL",
        "status": "CLOSED",
        "legs": [
            {"leg_id":"pos_xyz_GOOGL_SPOT","venue":"hyperliquid","inst_id":"GOOGL","side":"LONG","qty":5.0,"wallet_label":"main"},
            {"leg_id":"pos_xyz_GOOGL_PERP","venue":"hyperliquid","inst_id":"xyz:GOOGL","side":"SHORT","qty":5.0,"wallet_label":"main"},
        ],
    }]


def _seed_fills(con):
    con.executemany(
        "INSERT INTO pm_fills (venue,account_id,inst_id,side,px,sz,fee,ts,leg_id,position_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            ("hyperliquid","0xMAIN","GOOGL",    "BUY", 100.0, 5.0, 0.1, 1000, "pos_xyz_GOOGL_SPOT","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","SELL",101.0, 5.0, 0.1, 1100, "pos_xyz_GOOGL_PERP","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","GOOGL",    "SELL",110.0, 5.0, 0.1, 5000, "pos_xyz_GOOGL_SPOT","pos_xyz_GOOGL"),
            ("hyperliquid","0xMAIN","xyz:GOOGL","BUY", 108.0, 5.0, 0.1, 5100, "pos_xyz_GOOGL_PERP","pos_xyz_GOOGL"),
        ],
    )


def test_migrate_creates_position_and_trades_then_idempotent(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    _seed_fills(con); con.commit()

    pos_path = tmp_path / "positions.json"
    pos_path.write_text(json.dumps(_fixture_positions()))

    report = migrate(con, positions_path=pos_path, commit=True)

    # Position + legs created
    assert con.execute("SELECT COUNT(*) FROM pm_positions").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM pm_legs").fetchone()[0] == 2
    # 2 FINALIZED trades (OPEN + CLOSE, since status=CLOSED)
    tcount = con.execute("SELECT COUNT(*) FROM pm_trades WHERE state='FINALIZED'").fetchone()[0]
    assert tcount == 2
    # Status derived → CLOSED
    status = con.execute("SELECT status FROM pm_positions").fetchone()[0]
    assert status == "CLOSED"

    # Second run is a no-op
    report2 = migrate(con, positions_path=pos_path, commit=True)
    assert report2["positions_created"] == 0
    assert report2["trades_created"] == 0


def test_migrate_qty_diff_within_tolerance(tmp_path):
    db = tmp_path / "t.db"
    con = sqlite3.connect(str(db))
    con.executescript(_SCHEMA)
    _seed_fills(con); con.commit()

    pos_path = tmp_path / "positions.json"
    pos_path.write_text(json.dumps(_fixture_positions()))

    report = migrate(con, positions_path=pos_path, commit=True)
    for d in report["qty_diffs"]:
        assert abs(d["delta_pct"]) < 0.01  # 0.01%
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_positions_to_db.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement script**

```python
# scripts/migrate_positions_to_db.py
"""Migrate config/positions.json → pm_positions / pm_legs / pm_trades.

Usage:
  .venv/bin/python scripts/migrate_positions_to_db.py --dry-run      # print plan
  .venv/bin/python scripts/migrate_positions_to_db.py --commit       # apply

Idempotent: re-runs are no-ops for positions/legs/trades that already exist.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List

from tracking.pipeline.trades import (
    create_draft_trade, finalize_trade, resolve_trade_id, TradeCreateError,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POSITIONS = ROOT / "config" / "positions.json"
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _wallet_to_account(wallet_label: str | None) -> str | None:
    """Resolve wallet_label → account_id via HYPERLIQUID_ACCOUNTS_JSON env var."""
    import os
    raw = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "{}")
    try:
        accts = json.loads(raw)
    except Exception:
        return None
    if wallet_label in accts:
        return accts[wallet_label].get("address") or accts[wallet_label].get("account_id")
    return None


def migrate(
    con: sqlite3.Connection,
    positions_path: Path = DEFAULT_POSITIONS,
    commit: bool = False,
) -> Dict[str, Any]:
    positions = json.loads(Path(positions_path).read_text())
    now = _now_ms()

    report: Dict[str, Any] = {
        "positions_created": 0,
        "legs_created": 0,
        "trades_created": 0,
        "qty_diffs": [],
        "errors": [],
    }

    for pos in positions:
        pid = pos["position_id"]
        existing = con.execute("SELECT 1 FROM pm_positions WHERE position_id=?", (pid,)).fetchone()
        if not existing:
            con.execute(
                "INSERT INTO pm_positions (position_id, venue, status, created_at_ms, updated_at_ms, base, strategy_type) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    pid,
                    pos["legs"][0]["venue"],
                    pos.get("status", "OPEN"),
                    now, now,
                    pos.get("base"),
                    pos.get("strategy_type"),
                ),
            )
            report["positions_created"] += 1

            for leg in pos["legs"]:
                account_id = _wallet_to_account(leg.get("wallet_label")) or ""
                con.execute(
                    "INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, meta_json) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        leg["leg_id"], pid, leg["venue"], leg["inst_id"], leg["side"],
                        0.0, "OPEN", now, account_id,
                        json.dumps({"wallet_label": leg.get("wallet_label")}),
                    ),
                )
                report["legs_created"] += 1

        # Synthesize OPEN trade from earliest open-side fills
        legs = {l["side"]: l for l in pos["legs"]}
        long_leg_id = legs["LONG"]["leg_id"]
        short_leg_id = legs["SHORT"]["leg_id"]

        open_bounds = con.execute(
            """
            SELECT MIN(ts), MAX(ts) FROM pm_fills
            WHERE (leg_id = ? AND side = 'BUY') OR (leg_id = ? AND side = 'SELL')
            """,
            (long_leg_id, short_leg_id),
        ).fetchone()
        if open_bounds and open_bounds[0] is not None:
            start_ts, end_ts = open_bounds[0], open_bounds[1] + 1
            existing_trade = con.execute(
                "SELECT 1 FROM pm_trades WHERE position_id=? AND trade_type='OPEN'", (pid,)
            ).fetchone()
            if not existing_trade:
                try:
                    t = create_draft_trade(con, pid, "OPEN", start_ts, end_ts, note="migrated")
                    finalize_trade(con, t["trade_id"])
                    report["trades_created"] += 1
                except TradeCreateError as e:
                    report["errors"].append(f"{pid} OPEN: {e}")

        # Synthesize CLOSE trade if status == CLOSED
        if pos.get("status") == "CLOSED":
            close_bounds = con.execute(
                """
                SELECT MIN(ts), MAX(ts) FROM pm_fills
                WHERE (leg_id = ? AND side = 'SELL') OR (leg_id = ? AND side = 'BUY')
                """,
                (long_leg_id, short_leg_id),
            ).fetchone()
            # Heuristic: close fills come AFTER open bounds
            if close_bounds and close_bounds[1] is not None and open_bounds and close_bounds[1] > open_bounds[1]:
                c_start, c_end = (open_bounds[1] + 1), close_bounds[1] + 1
                existing_close = con.execute(
                    "SELECT 1 FROM pm_trades WHERE position_id=? AND trade_type='CLOSE'", (pid,)
                ).fetchone()
                if not existing_close:
                    try:
                        t = create_draft_trade(con, pid, "CLOSE", c_start, c_end, note="migrated")
                        finalize_trade(con, t["trade_id"])
                        report["trades_created"] += 1
                    except TradeCreateError as e:
                        report["errors"].append(f"{pid} CLOSE: {e}")

        # Qty diff check
        for leg in pos["legs"]:
            expected = float(leg.get("qty", 0))
            actual = con.execute("SELECT size FROM pm_legs WHERE leg_id=?", (leg["leg_id"],)).fetchone()[0] or 0.0
            abs_exp = abs(expected) if expected else 1e-9
            delta_pct = abs(abs(actual) - abs(expected)) / abs_exp * 100
            report["qty_diffs"].append({
                "leg_id": leg["leg_id"],
                "expected": expected, "actual": actual, "delta_pct": delta_pct,
            })

    if commit:
        con.commit()
    else:
        con.rollback()
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--positions", type=Path, default=DEFAULT_POSITIONS)
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(str(args.db))
    report = migrate(con, positions_path=args.positions, commit=args.commit)
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_positions_to_db.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_positions_to_db.py tests/test_migrate_positions_to_db.py
git commit -m "feat(migrate): positions.json → DB with synthesized trades + idempotency"
```

---

### Task D2: Real-data E2E harness

**Files:**
- Create: `scripts/e2e_real_fills.py`

- [ ] **Step 1: Implement the harness**

```python
# scripts/e2e_real_fills.py
"""Real-data E2E acceptance harness (spec §9 Real-data E2E).

Usage:
  source .arbit_env
  .venv/bin/python scripts/e2e_real_fills.py --lookback-days 60

Produces: docs/tasks/e2e_real_fills_report_YYYYMMDD.md
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.migrate_positions_to_db import migrate as run_migrate


def _apply_schemas(con: sqlite3.Connection):
    for path in [
        ROOT / "tracking/sql/schema_pm_v3.sql",
        ROOT / "tracking/sql/schema_monitoring_v1.sql",
        ROOT / "tracking/sql/schema_monitoring_v2.sql",
    ]:
        sql = path.read_text()
        for stmt in sql.split(";"):
            s = stmt.strip()
            if not s:
                continue
            try: con.execute(s)
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e): continue
                raise
    con.commit()


def _ingest_real_fills(con: sqlite3.Connection, lookback_days: int):
    from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills
    from tracking.pipeline.spot_meta import fetch_spot_index_map
    since_ms = int((time.time() - lookback_days * 86400) * 1000)
    spot_map = fetch_spot_index_map()
    n = ingest_hyperliquid_fills(con, spot_map, include_closed=True, since_ms=since_ms)
    print(f"  HL fills ingested: {n}")
    # Felix (optional, skip if connector missing)
    try:
        from tracking.pipeline.felix_fill_ingester import ingest_felix_fills
        n2 = ingest_felix_fills(con, since_ms=since_ms)
        print(f"  Felix fills ingested: {n2}")
    except Exception as e:
        print(f"  Felix ingest skipped: {e}")


def _validate(con: sqlite3.Connection) -> dict:
    """Run all 5 validation checks; return report dict."""
    con.row_factory = sqlite3.Row
    report = {"positions": [], "global_violations": 0}

    positions = con.execute("SELECT position_id, base, status FROM pm_positions").fetchall()
    for pos in positions:
        pid = pos["position_id"]
        prow = {"position_id": pid, "base": pos["base"], "status": pos["status"]}

        # (1) Volume reconciliation
        legs = con.execute("SELECT leg_id, side FROM pm_legs WHERE position_id=?", (pid,)).fetchall()
        for leg in legs:
            net = con.execute(
                """
                SELECT
                  COALESCE(SUM(CASE WHEN trade_type='OPEN' THEN
                    CASE WHEN ?='LONG' THEN long_size ELSE short_size END ELSE 0 END),0)
                  - COALESCE(SUM(CASE WHEN trade_type='CLOSE' THEN
                    CASE WHEN ?='LONG' THEN long_size ELSE short_size END ELSE 0 END),0)
                FROM pm_trades WHERE position_id=? AND state='FINALIZED'
                """,
                (leg["side"], leg["side"], pid),
            ).fetchone()[0] or 0.0
            actual = con.execute("SELECT size FROM pm_legs WHERE leg_id=?", (leg["leg_id"],)).fetchone()[0] or 0.0
            prow[f"{leg['side'].lower()}_leg_net_trades"] = net
            prow[f"{leg['side'].lower()}_leg_qty_db"] = actual

        # (2) Fill coverage
        total_fills = con.execute(
            "SELECT COUNT(*) FROM pm_fills f JOIN pm_legs l ON f.leg_id=l.leg_id WHERE l.position_id=?",
            (pid,),
        ).fetchone()[0]
        linked = con.execute(
            """SELECT COUNT(*) FROM pm_trade_fills tf
               JOIN pm_fills f ON f.fill_id=tf.fill_id
               JOIN pm_legs l ON f.leg_id=l.leg_id
               WHERE l.position_id=?""",
            (pid,),
        ).fetchone()[0]
        coverage = (linked / total_fills * 100) if total_fills else 100
        prow["fill_coverage_pct"] = round(coverage, 2)
        prow["unassigned_fills"] = total_fills - linked

        # (3) Spread sanity
        spread_stats = con.execute(
            "SELECT MIN(spread_bps), MAX(spread_bps) FROM pm_trades WHERE position_id=? AND trade_type='OPEN'",
            (pid,),
        ).fetchone()
        prow["open_spread_min_bps"] = spread_stats[0]
        prow["open_spread_max_bps"] = spread_stats[1]
        if spread_stats[0] is not None and (abs(spread_stats[0]) > 100 or abs(spread_stats[1] or 0) > 100):
            prow["spread_flag"] = "|spread| > 100 bps — manual review"
            report["global_violations"] += 1

        # (4) Realized P&L consistency
        cashflow_sum = con.execute(
            "SELECT COALESCE(SUM(amount),0) FROM pm_cashflows WHERE position_id=? AND cf_type IN ('REALIZED_PNL','FUNDING')",
            (pid,),
        ).fetchone()[0]
        pnl_from_trades = con.execute(
            """SELECT COALESCE(SUM(realized_pnl_bps * long_notional / 10000.0), 0)
               FROM pm_trades WHERE position_id=? AND trade_type='CLOSE' AND state='FINALIZED' AND realized_pnl_bps IS NOT NULL""",
            (pid,),
        ).fetchone()[0]
        prow["cashflow_realized_usd"] = cashflow_sum
        prow["trades_realized_usd"] = pnl_from_trades
        if cashflow_sum and abs(pnl_from_trades - cashflow_sum) / abs(cashflow_sum) > 0.05:
            prow["pnl_flag"] = "delta > 5%"
            report["global_violations"] += 1

        # (5) Side mapping — sample 5 fills
        sample = con.execute(
            """SELECT tf.leg_side, t.trade_type, f.side FROM pm_trade_fills tf
               JOIN pm_trades t ON t.trade_id=tf.trade_id
               JOIN pm_fills f ON f.fill_id=tf.fill_id
               WHERE t.position_id=? LIMIT 5""",
            (pid,),
        ).fetchall()
        expected_map = {("OPEN","LONG"):"BUY",("OPEN","SHORT"):"SELL",("CLOSE","LONG"):"SELL",("CLOSE","SHORT"):"BUY"}
        for s in sample:
            exp = expected_map.get((s["trade_type"], s["leg_side"]))
            if exp != s["side"]:
                prow["side_violation"] = f"{s['trade_type']}+{s['leg_side']} expected {exp}, got {s['side']}"
                report["global_violations"] += 1
                break

        report["positions"].append(prow)

    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookback-days", type=int, default=60)
    args = ap.parse_args()

    ts = time.strftime("%Y%m%d_%H%M%S")
    tmp_db = ROOT / f"tracking/db/e2e_{ts}.db"
    tmp_db.parent.mkdir(exist_ok=True, parents=True)
    con = sqlite3.connect(str(tmp_db))
    print(f"Harness DB: {tmp_db}")

    _apply_schemas(con)
    _ingest_real_fills(con, args.lookback_days)
    run_migrate(con, positions_path=ROOT / "config/positions.json", commit=True)
    report = _validate(con)

    out_path = ROOT / f"docs/tasks/e2e_real_fills_report_{time.strftime('%Y%m%d')}.md"
    out_path.parent.mkdir(exist_ok=True, parents=True)
    lines = [f"# E2E Real Fills Report — {ts}", "", f"Global violations: {report['global_violations']}", "", "## Per-position"]
    for p in report["positions"]:
        lines.append("```json"); lines.append(json.dumps(p, indent=2)); lines.append("```")
    out_path.write_text("\n".join(lines))
    print(f"Report written to {out_path}")
    print(f"Violations: {report['global_violations']}")

    sys.exit(0 if report["global_violations"] == 0 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-run the harness**

```bash
source .arbit_env && .venv/bin/python scripts/e2e_real_fills.py --lookback-days 7
```

Expected: produces a report file under `docs/tasks/` and exits 0 or 1 depending on violations. A non-zero exit here is acceptable at plan-time; the report will be reviewed before flipping the flag.

- [ ] **Step 3: Commit the harness (not the report)**

```bash
git add scripts/e2e_real_fills.py
git commit -m "feat(e2e): real-fills acceptance harness with 5 validation checks"
```

---

### Task D3: Flip feature flag + deprecate positions.json

**Files:**
- Modify: `scripts/pm.py`
- Modify: `.arbit_env.example` (document `TRADES_LAYER_ENABLED`)
- Rename: `config/positions.json` → `config/positions.json.bak` (manual step, see below)
- Modify: `docs/playbook-position-management.md`
- Modify: `CLAUDE.md`

**IMPORTANT:** this task modifies workflow-critical files. Before the rename, confirm Task D2's E2E report shows zero violations and user has approved the flip.

- [ ] **Step 1: Add deprecation warning to `scripts/pm.py sync-registry`**

Find the `sync-registry` subcommand handler (grep for `sync-registry`) and at its top:

```python
import os
if os.environ.get("TRADES_LAYER_ENABLED", "false").lower() == "true":
    print("WARNING: sync-registry is deprecated under TRADES_LAYER_ENABLED=true. "
          "Positions are managed via /api/positions (UI). This command is a no-op.")
    return
```

- [ ] **Step 2: Document the env var in `.arbit_env.example`**

Append:

```bash
# Trade aggregation layer (spec: 2026-04-17-trade-aggregation-layer-design.md)
# Set to "true" after running scripts/migrate_positions_to_db.py --commit
# and verifying scripts/e2e_real_fills.py report shows zero violations.
TRADES_LAYER_ENABLED=false
```

- [ ] **Step 3: Grep for remaining positions.json consumers and list them**

```bash
grep -rn "positions\.json\|load_positions_from_json" --include="*.py" scripts/ tracking/ api/ 2>/dev/null
```

For each hit that is not the migrate script or already guarded: either gate behind the flag or migrate to DB read. Common hits so far:
- `scripts/pm.py` — `sync-registry` (guarded in Step 1)
- `tracking/position_manager/registry.py` — module used by scripts only; verify nothing in `api/` or `tracking/pipeline/trades.py` imports it

- [ ] **Step 4: Rename config file (confirm with user first)**

```bash
mv config/positions.json config/positions.json.bak
```

- [ ] **Step 5: Update `docs/playbook-position-management.md`**

Replace the "Quick reference" block with:

```markdown
Quick reference:
1. **Create Position** via UI (/positions → "+ New Position") or `POST /api/positions`
2. **Create Trade** per deploy/unwind batch via UI (/trades → "+ New Trade" or /positions/:id Trades tab)
3. **Preview** first to verify aggregates (size delta, spread); **Finalize** locks the snapshot
4. **Reconcile warnings** (⚠ N late fills) → Reopen to DRAFT, then Finalize again

Common operations:
- **Open new position**: UI → New Position → fill base/strategy/legs → Save. Then create OPEN trade.
- **Add to existing position**: UI → New Trade (OPEN) on the existing position, window covering the add batch.
- **Partial/full close**: UI → New Trade (CLOSE), window covering the unwind batch. Status flips to CLOSED when leg sizes net to zero.
- **Pause / Exit**: status (PAUSED, EXITING) is manual override — set via Position detail page (not derived from trades).

Notes:
- `config/positions.json.bak` kept for reference; no longer read by any pipeline.
- `scripts/pm.py sync-registry` is deprecated; no-ops under `TRADES_LAYER_ENABLED=true`.
```

- [ ] **Step 6: Update `CLAUDE.md` "Position Management Workflow" section**

Replace the existing block (lines referencing `positions.json` as source-of-truth + `pm.py sync-registry`) with a pointer:

```markdown
## Position Management Workflow

Playbook: `docs/playbook-position-management.md`

Positions and trades are managed via the dashboard UI (`/positions`, `/trades`).
`config/positions.json` was deprecated on 2026-04-17; kept as `.bak` for reference.
See `docs/superpowers/specs/2026-04-17-trade-aggregation-layer-design.md` for the
Trade layer design.
```

Also update the "Trading Decision Workflow" section: replace "edit positions.json → pm.py sync-registry → verify" with "create/edit Trade via UI → Finalize → verify /positions/:id derived size + status".

- [ ] **Step 7: Commit**

```bash
git add scripts/pm.py .arbit_env.example docs/playbook-position-management.md CLAUDE.md config/positions.json.bak
git rm config/positions.json 2>/dev/null || true
git commit -m "chore: deprecate positions.json; switch to Trade-layer-driven workflow"
```

---

### Task D4: Final smoke + verification

- [ ] **Step 1: Run the full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 2: Boot the stack locally and spot-check UI**

```bash
source .arbit_env
.venv/bin/uvicorn api.main:app --host 0.0.0.0 --port 8000 &
cd frontend && yarn dev &
```

Open http://localhost:3000 — verify:
- `/positions` loads, "+ New Position" button visible
- `/trades` loads, filter dropdowns work
- Create a fake position + draft trade + finalize → verify row appears and spread is sensible

- [ ] **Step 3: Final commit if any fixups**

```bash
git status
# if any stragglers from smoke, commit them
```

- [ ] **Step 4: Push branch and open PR**

```bash
git push -u origin feat/monitoring-system
gh pr create --title "feat: trade aggregation layer" --body "$(cat <<'EOF'
## Summary
- Introduces `pm_trades` + `pm_trade_fills` layer for per-batch spread + realized P&L
- DRAFT/FINALIZED lifecycle with reconcile hook for late fills
- Full UI: `/trades` global, `/positions/:id` trades tab, New Trade + New Position modals
- Migrates `config/positions.json` → DB; file kept as `.bak`

## Spec
`docs/superpowers/specs/2026-04-17-trade-aggregation-layer-design.md`

## Test plan
- [ ] All pytest suites pass locally
- [ ] `scripts/e2e_real_fills.py` report shows zero violations
- [ ] UI smoke: create position → create OPEN trade → finalize → spread matches hand-calc
- [ ] Reconcile hook fires in hourly pipeline (verify logs after 1 cycle)
- [ ] `TRADES_LAYER_ENABLED=true` flipped after E2E report review

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Self-Review Checklist (complete before starting execution)

**Spec coverage** — each spec section has a task:
- §5 Data model → A1
- §6 Ingestion & reconcile → A2, A3, A4, A5, A6, A7
- §7 UI surface → B1, B2, B3, C1–C6
- §8 Migration plan → D1, D3
- §9 Testing (unit, integration, E2E, manual smoke) → A2–A6 unit, B4 integration, D2 real-data E2E, D4 manual
- §4 key decisions — all 8 decisions reflected in tasks above

**Type consistency** — verified that every function called in a later task (e.g., `create_draft_trade`, `finalize_trade`, `run_reconcile`, `migrate`) is defined in an earlier task with matching signature.

**Placeholder scan** — no TBD, TODO, "add appropriate error handling", "implement later" found.

**Scope check** — plan covers the full spec (Phases 1–3 of spec §8, deferring spec Phase 4 cleanup as post-ship follow-up). Large but unified; user requested a single plan.
