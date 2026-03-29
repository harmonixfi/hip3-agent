# Phase 1a: Backend Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the DB schema for fill tracking, build a fill ingestion pipeline for Hyperliquid (spot + perp), set up an encrypted secret vault, and backfill all 11 existing positions.

**Architecture:** New SQLite tables (`pm_fills`, `pm_entry_prices`, `pm_spreads`, `pm_portfolio_snapshots`) added via migration script. A fill ingester module under `tracking/pipeline/` pulls fills from HL `userFillsByTime`, resolves spot `@index` coins via `spotMeta`, maps fills to position legs, and inserts with dedup. Vault uses `age` + `sops` for encrypted secret storage.

**Tech Stack:** Python 3.11+, SQLite3 (stdlib), `urllib.request` (no `requests` — consistent with existing code), `age`/`sops` for vault, `hashlib` for synthetic TIDs.

**References:**
- Architecture spec: `docs/PLAN.md` sections 3.1–3.6
- Decisions: `docs/DECISIONS.md` (ADR-004, ADR-007, ADR-011)
- Existing schema: `tracking/sql/schema_pm_v3.sql`
- Existing HL connector: `tracking/connectors/hyperliquid_private.py`
- Existing cashflow ingest pattern: `scripts/pm_cashflows.py` lines 314–459
- Position config: `config/positions.json`

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `tracking/sql/schema_monitoring_v1.sql` | New tables DDL |
| Create | `scripts/db_monitoring_migrate.py` | Apply migration + legacy inst_id fix |
| Create | `tracking/pipeline/__init__.py` | Package init |
| Create | `tracking/pipeline/spot_meta.py` | spotMeta fetch + `@index` → symbol resolution |
| Create | `tracking/pipeline/fill_ingester.py` | Pull HL fills, resolve symbols, map to legs, insert |
| Create | `scripts/backfill_fills.py` | CLI wrapper for full/selective backfill |
| Create | `vault/.gitignore` | Ignore age identity file |
| Create | `vault/vault.py` | Python helper: decrypt secrets via sops |
| Create | `.sops.yaml` | sops configuration |
| Create | `tests/test_spot_meta.py` | Unit tests for spot symbol resolution |
| Create | `tests/test_fill_ingester.py` | Unit tests for fill ingestion pipeline |
| Create | `tests/test_vault.py` | Unit tests for vault decrypt |

---

## Task 1: SQL Migration Script

**Files:**
- Create: `tracking/sql/schema_monitoring_v1.sql`
- Create: `scripts/db_monitoring_migrate.py`

- [ ] **Step 1: Create the schema SQL file**

Create `tracking/sql/schema_monitoring_v1.sql`:

```sql
-- schema_monitoring_v1.sql
-- New tables for fill tracking, entry prices, spreads, and portfolio snapshots.
-- Applied as an additive migration on top of schema_pm_v3.sql.

-- Enable WAL mode for concurrent read/write (cron writes, API reads)
PRAGMA journal_mode=WAL;

-- ============================================================
-- pm_fills: Raw trade fills from all venues
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_fills (
  fill_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  -- Identifiers
  venue TEXT NOT NULL,
  account_id TEXT NOT NULL,
  -- Fill data
  tid TEXT,
  oid TEXT,
  inst_id TEXT NOT NULL,
  side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
  px REAL NOT NULL,
  sz REAL NOT NULL,
  fee REAL,
  fee_currency TEXT,
  ts INTEGER NOT NULL,
  -- HL-specific fields (nullable for other venues)
  closed_pnl REAL,
  dir TEXT,
  builder_fee REAL,
  -- Position mapping
  position_id TEXT,
  leg_id TEXT,
  -- Raw data
  raw_json TEXT,
  meta_json TEXT,
  -- Constraints
  UNIQUE (venue, account_id, tid),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_fills_venue_account ON pm_fills(venue, account_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_inst_id ON pm_fills(inst_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_ts ON pm_fills(ts);
CREATE INDEX IF NOT EXISTS idx_pm_fills_position_id ON pm_fills(position_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_leg_id ON pm_fills(leg_id);
CREATE INDEX IF NOT EXISTS idx_pm_fills_oid ON pm_fills(oid);

-- ============================================================
-- pm_entry_prices: Materialized VWAP per leg (derived from fills)
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_entry_prices (
  leg_id TEXT NOT NULL,
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
  PRIMARY KEY (leg_id),
  FOREIGN KEY (leg_id) REFERENCES pm_legs(leg_id),
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);

CREATE INDEX IF NOT EXISTS idx_pm_entry_prices_position ON pm_entry_prices(position_id);

-- ============================================================
-- pm_spreads: Entry/exit basis spread per sub-pair
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_spreads (
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

CREATE INDEX IF NOT EXISTS idx_pm_spreads_position ON pm_spreads(position_id);

-- ============================================================
-- pm_portfolio_snapshots: Hourly aggregate portfolio metrics
-- ============================================================
CREATE TABLE IF NOT EXISTS pm_portfolio_snapshots (
  snapshot_id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  total_equity_usd REAL NOT NULL,
  equity_by_account_json TEXT,
  total_unrealized_pnl REAL,
  total_funding_today REAL,
  total_funding_alltime REAL,
  total_fees_alltime REAL,
  daily_change_usd REAL,
  cashflow_adjusted_change REAL,
  apr_daily REAL,
  tracking_start_date TEXT,
  meta_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_ts ON pm_portfolio_snapshots(ts);
CREATE UNIQUE INDEX IF NOT EXISTS idx_pm_portfolio_snapshots_hourly
  ON pm_portfolio_snapshots(CAST(ts / 3600000 AS INTEGER));
```

- [ ] **Step 2: Create the migration runner script**

Create `scripts/db_monitoring_migrate.py`:

```python
#!/usr/bin/env python3
"""Apply monitoring v1 schema migration to arbit_v3.db.

Creates new tables: pm_fills, pm_entry_prices, pm_spreads, pm_portfolio_snapshots.
Also fixes legacy spot inst_ids in pm_legs (e.g., GOOGL -> GOOGL/USDC).
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCHEMA_MONITORING = ROOT / "tracking" / "sql" / "schema_monitoring_v1.sql"
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def apply_schema(con: sqlite3.Connection) -> None:
    """Apply the monitoring v1 schema."""
    sql = SCHEMA_MONITORING.read_text(encoding="utf-8")
    con.executescript(sql)
    print("OK: monitoring v1 schema applied")


def fix_legacy_spot_inst_ids(con: sqlite3.Connection) -> int:
    """Append /USDC to legacy spot inst_ids that lack a slash.

    Targets: LONG legs in SPOT_PERP positions where inst_id has no '/'.
    Example: GOOGL -> GOOGL/USDC
    """
    cur = con.execute(
        """
        SELECT l.leg_id, l.inst_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.strategy = 'SPOT_PERP'
          AND l.side = 'LONG'
          AND l.inst_id NOT LIKE '%/%'
        """
    )
    rows = cur.fetchall()
    if not rows:
        print("OK: no legacy spot inst_ids to fix")
        return 0

    for leg_id, old_inst_id in rows:
        new_inst_id = f"{old_inst_id}/USDC"
        con.execute(
            "UPDATE pm_legs SET inst_id = ? WHERE leg_id = ?",
            (new_inst_id, leg_id),
        )
        print(f"  fixed: {leg_id}: {old_inst_id} -> {new_inst_id}")

    con.commit()
    print(f"OK: fixed {len(rows)} legacy spot inst_ids")
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply monitoring v1 migration")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without applying")
    args = ap.parse_args()

    if not SCHEMA_MONITORING.exists():
        raise SystemExit(f"missing schema: {SCHEMA_MONITORING}")
    if not args.db.exists():
        raise SystemExit(f"DB not found: {args.db}. Run db_v3_init.py first.")

    con = sqlite3.connect(str(args.db))
    try:
        con.execute("PRAGMA foreign_keys = ON")

        if args.dry_run:
            # Show legacy inst_ids that would be fixed
            cur = con.execute(
                """
                SELECT l.leg_id, l.inst_id
                FROM pm_legs l
                JOIN pm_positions p ON p.position_id = l.position_id
                WHERE p.strategy = 'SPOT_PERP'
                  AND l.side = 'LONG'
                  AND l.inst_id NOT LIKE '%/%'
                """
            )
            rows = cur.fetchall()
            print(f"DRY RUN: would fix {len(rows)} inst_ids:")
            for leg_id, inst_id in rows:
                print(f"  {leg_id}: {inst_id} -> {inst_id}/USDC")
            return 0

        apply_schema(con)
        fix_legacy_spot_inst_ids(con)

    finally:
        con.close()

    print(f"\nMigration complete: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run migration dry-run to verify**

Run:
```bash
source .arbit_env && .venv/bin/python scripts/db_monitoring_migrate.py --dry-run
```

Expected: Lists legacy spot inst_ids that would be fixed (GOOGL, MSFT, NVDA, ORCL, MU, CRCL, MSTR).

- [ ] **Step 4: Run migration for real**

Run:
```bash
source .arbit_env && .venv/bin/python scripts/db_monitoring_migrate.py
```

Expected:
```
OK: monitoring v1 schema applied
  fixed: <leg_id>: GOOGL -> GOOGL/USDC
  fixed: <leg_id>: MSFT -> MSFT/USDC
  ...
OK: fixed 7 legacy spot inst_ids
Migration complete: tracking/db/arbit_v3.db
```

- [ ] **Step 5: Verify tables exist**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
con = sqlite3.connect('tracking/db/arbit_v3.db')
tables = [r[0] for r in con.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'pm_%'\").fetchall()]
print('Tables:', sorted(tables))
assert 'pm_fills' in tables
assert 'pm_entry_prices' in tables
assert 'pm_spreads' in tables
assert 'pm_portfolio_snapshots' in tables
print('OK: all new tables exist')
# Verify WAL mode
mode = con.execute('PRAGMA journal_mode').fetchone()[0]
print(f'Journal mode: {mode}')
con.close()
"
```

Expected: All 4 new tables listed + journal_mode = wal.

- [ ] **Step 6: Verify legacy inst_id fix**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
con = sqlite3.connect('tracking/db/arbit_v3.db')
cur = con.execute(\"\"\"
    SELECT l.leg_id, l.inst_id
    FROM pm_legs l
    JOIN pm_positions p ON p.position_id = l.position_id
    WHERE p.strategy = 'SPOT_PERP' AND l.side = 'LONG'
\"\"\")
for leg_id, inst_id in cur.fetchall():
    assert '/' in inst_id, f'{leg_id} still has old format: {inst_id}'
    print(f'  {leg_id}: {inst_id}')
print('OK: all spot legs have SYMBOL/USDC format')
con.close()
"
```

Expected: All LONG legs show SYMBOL/USDC format.

- [ ] **Step 7: Commit**

```bash
git add tracking/sql/schema_monitoring_v1.sql scripts/db_monitoring_migrate.py
git commit -m "feat: add monitoring v1 schema (pm_fills, pm_entry_prices, pm_spreads, pm_portfolio_snapshots)"
```

---

## Task 2: Spot Symbol Resolution Module

**Files:**
- Create: `tracking/pipeline/__init__.py`
- Create: `tracking/pipeline/spot_meta.py`
- Create: `tests/test_spot_meta.py`

- [ ] **Step 1: Create the pipeline package**

Create `tracking/pipeline/__init__.py`:

```python
"""Data pipeline modules for fill ingestion and metric computation."""
```

- [ ] **Step 2: Write failing tests for spot_meta**

Create `tests/test_spot_meta.py`:

```python
#!/usr/bin/env python3
"""Tests for spot symbol resolution via spotMeta."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.pipeline.spot_meta import (
    build_spot_index_map,
    resolve_coin,
)


def test_build_spot_index_map():
    """spotMeta response is parsed into {index: 'SYMBOL/QUOTE'} map."""
    raw_response = {
        "tokens": [
            {"name": "USDC", "index": 0},
            {"name": "PURR", "index": 1},
            {"name": "HFUN", "index": 2},
            {"name": "HYPE", "index": 150},
        ],
        "universe": [
            {"name": "PURR/USDC", "tokens": [1, 0], "index": 0},
            {"name": "@1", "tokens": [2, 0], "index": 1},
            {"name": "HYPE/USDC", "tokens": [150, 0], "index": 107},
        ],
    }
    result = build_spot_index_map(raw_response)

    # Canonical pairs keep their name
    assert result[0] == "PURR/USDC"
    # Non-canonical pairs (@N) are resolved from tokens
    assert result[1] == "HFUN/USDC"
    # HYPE/USDC at universe index 107
    assert result[107] == "HYPE/USDC"


def test_resolve_coin_spot_index():
    """@107 resolves to HYPE/USDC."""
    cache = {107: "HYPE/USDC", 0: "PURR/USDC"}
    assert resolve_coin("@107", cache) == "HYPE/USDC"
    assert resolve_coin("@0", cache) == "PURR/USDC"


def test_resolve_coin_builder_dex_passthrough():
    """Builder dex coins pass through unchanged."""
    cache = {}
    assert resolve_coin("xyz:GOLD", cache) == "xyz:GOLD"
    assert resolve_coin("hyna:HYPE", cache) == "hyna:HYPE"


def test_resolve_coin_native_perp_passthrough():
    """Native perp coins pass through unchanged."""
    cache = {}
    assert resolve_coin("HYPE", cache) == "HYPE"
    assert resolve_coin("BTC", cache) == "BTC"


def test_resolve_coin_unknown_index_raises():
    """Unknown @index raises ValueError."""
    cache = {107: "HYPE/USDC"}
    try:
        resolve_coin("@999", cache)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "999" in str(e)


def main() -> int:
    test_build_spot_index_map()
    print("PASS: test_build_spot_index_map")
    test_resolve_coin_spot_index()
    print("PASS: test_resolve_coin_spot_index")
    test_resolve_coin_builder_dex_passthrough()
    print("PASS: test_resolve_coin_builder_dex_passthrough")
    test_resolve_coin_native_perp_passthrough()
    print("PASS: test_resolve_coin_native_perp_passthrough")
    test_resolve_coin_unknown_index_raises()
    print("PASS: test_resolve_coin_unknown_index_raises")
    print("\nAll spot_meta tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_spot_meta.py
```

Expected: `ModuleNotFoundError: No module named 'tracking.pipeline.spot_meta'` or `ImportError`.

- [ ] **Step 4: Implement spot_meta module**

Create `tracking/pipeline/spot_meta.py`:

```python
"""Spot symbol resolution via Hyperliquid spotMeta API.

Hyperliquid spot fills use @{index} format (e.g., @107) instead of human-readable
symbols. This module fetches the spotMeta endpoint to build an index-to-symbol map
and provides a resolver for fill coin fields.

Usage:
    cache = fetch_spot_index_map()
    inst_id = resolve_coin("@107", cache)  # -> "HYPE/USDC"
    inst_id = resolve_coin("xyz:GOLD", cache)  # -> "xyz:GOLD" (passthrough)
"""

from __future__ import annotations

from typing import Any, Dict


def build_spot_index_map(spot_meta: Dict[str, Any]) -> Dict[int, str]:
    """Build {universe_index: 'SYMBOL/QUOTE'} map from spotMeta response.

    The spotMeta response has two arrays:
    - tokens: [{name, index, ...}] — all tokens (USDC, PURR, HYPE, ...)
    - universe: [{name, tokens: [base_idx, quote_idx], index}] — spot pairs

    For canonical pairs, universe[].name is "PURR/USDC".
    For non-canonical pairs, universe[].name is "@N" — we resolve from tokens.
    """
    tokens = spot_meta.get("tokens", [])
    universe = spot_meta.get("universe", [])

    # Build token index -> name lookup
    token_names: Dict[int, str] = {}
    for tok in tokens:
        idx = tok.get("index")
        name = tok.get("name", "")
        if idx is not None:
            token_names[int(idx)] = name

    # Build universe index -> pair name
    result: Dict[int, str] = {}
    for pair in universe:
        uni_index = pair.get("index")
        if uni_index is None:
            continue
        uni_index = int(uni_index)

        pair_name = str(pair.get("name", ""))
        if "/" in pair_name and not pair_name.startswith("@"):
            # Canonical: "PURR/USDC" — use as-is
            result[uni_index] = pair_name
        else:
            # Non-canonical: "@1" — resolve from tokens array
            pair_tokens = pair.get("tokens", [])
            if len(pair_tokens) >= 2:
                base_name = token_names.get(int(pair_tokens[0]), "???")
                quote_name = token_names.get(int(pair_tokens[1]), "USDC")
                result[uni_index] = f"{base_name}/{quote_name}"

    return result


def resolve_coin(coin: str, spot_index_map: Dict[int, str]) -> str:
    """Resolve a fill's coin field to a canonical inst_id.

    Rules:
    - '@107' -> lookup in spot_index_map -> 'HYPE/USDC'
    - 'xyz:GOLD' -> passthrough (builder dex perp)
    - 'HYPE' -> passthrough (native perp)

    Raises ValueError for unknown @index.
    """
    coin = str(coin or "").strip()
    if not coin:
        raise ValueError("Empty coin field")

    if coin.startswith("@"):
        index = int(coin[1:])
        resolved = spot_index_map.get(index)
        if resolved is None:
            raise ValueError(f"Unknown spot index: {coin} (index={index})")
        return resolved

    # Builder dex (xyz:GOLD) or native perp (HYPE) — passthrough
    return coin


def fetch_spot_index_map() -> Dict[int, str]:
    """Fetch spotMeta from Hyperliquid API and build the index map.

    Makes one POST to https://api.hyperliquid.xyz/info with {"type": "spotMeta"}.
    """
    from tracking.connectors.hyperliquid_private import post_info

    raw = post_info({"type": "spotMeta"}, dex="")
    if not isinstance(raw, dict):
        raise ValueError(f"Unexpected spotMeta response type: {type(raw)}")
    return build_spot_index_map(raw)
```

- [ ] **Step 5: Run tests to verify they pass**

Run:
```bash
.venv/bin/python tests/test_spot_meta.py
```

Expected: `All spot_meta tests passed!`

- [ ] **Step 6: Verify against live API (smoke test)**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from tracking.pipeline.spot_meta import fetch_spot_index_map, resolve_coin

cache = fetch_spot_index_map()
print(f'Loaded {len(cache)} spot pairs')

# Verify known pairs exist
for idx, name in sorted(cache.items())[:10]:
    print(f'  @{idx} -> {name}')

# Test resolution
print(f'resolve @107 -> {resolve_coin(\"@107\", cache)}')
print(f'resolve xyz:GOLD -> {resolve_coin(\"xyz:GOLD\", cache)}')
print(f'resolve HYPE -> {resolve_coin(\"HYPE\", cache)}')
print('OK: live smoke test passed')
"
```

Expected: Shows loaded pairs including `@107 -> HYPE/USDC` (or similar), all resolutions work.

- [ ] **Step 7: Commit**

```bash
git add tracking/pipeline/__init__.py tracking/pipeline/spot_meta.py tests/test_spot_meta.py
git commit -m "feat: add spot symbol resolution module (spotMeta @index -> SYMBOL/USDC)"
```

---

## Task 3: Fill Ingester Module

**Files:**
- Create: `tracking/pipeline/fill_ingester.py`
- Create: `tests/test_fill_ingester.py`

- [ ] **Step 1: Write failing tests for fill ingester**

Create `tests/test_fill_ingester.py`:

```python
#!/usr/bin/env python3
"""Tests for Hyperliquid fill ingester."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


def _create_test_db(db_path: Path) -> sqlite3.Connection:
    """Create a test DB with pm_positions, pm_legs, and pm_fills tables."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    # Minimal position/leg tables (matching schema_pm_v3.sql)
    con.executescript("""
        CREATE TABLE pm_positions(
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
        CREATE TABLE pm_legs(
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
    """)

    # pm_fills (matching schema_monitoring_v1.sql)
    con.executescript("""
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
    """)
    return con


def _seed_positions(con: sqlite3.Connection, now_ms: int = 1711900000000) -> None:
    """Seed test positions matching the actual config structure."""
    con.executemany(
        "INSERT INTO pm_positions(position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("pos_xyz_GOLD", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_hyna_HYPE", "hyperliquid", "SPOT_PERP", "OPEN", now_ms, now_ms, "{}"),
            ("pos_xyz_GOOGL", "hyperliquid", "SPOT_PERP", "CLOSED", now_ms, now_ms, "{}"),
            ("pos_paused", "hyperliquid", "SPOT_PERP", "PAUSED", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        "INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, opened_at_ms, account_id, raw_json, meta_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            # GOLD: spot + perp
            ("gold_spot", "pos_xyz_GOLD", "hyperliquid", "XAUT0/USDC", "LONG", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("gold_perp", "pos_xyz_GOLD", "hyperliquid", "xyz:GOLD", "SHORT", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            # HYPE: spot + 2 perps
            ("hype_spot", "pos_hyna_HYPE", "hyperliquid", "HYPE/USDC", "LONG", 200.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            ("hype_perp_hyna", "pos_hyna_HYPE", "hyperliquid", "hyna:HYPE", "SHORT", 100.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            ("hype_perp_native", "pos_hyna_HYPE", "hyperliquid", "HYPE", "SHORT", 100.0, "OPEN", now_ms, "0xdef", "{}", "{}"),
            # GOOGL: CLOSED
            ("googl_spot", "pos_xyz_GOOGL", "hyperliquid", "GOOGL/USDC", "LONG", 5.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            ("googl_perp", "pos_xyz_GOOGL", "hyperliquid", "xyz:GOOGL", "SHORT", 5.0, "CLOSED", now_ms, "0xabc", "{}", "{}"),
            # PAUSED position
            ("paused_spot", "pos_paused", "hyperliquid", "TEST/USDC", "LONG", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
            ("paused_perp", "pos_paused", "hyperliquid", "TEST", "SHORT", 1.0, "OPEN", now_ms, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


def test_load_fill_targets_excludes_closed():
    """CLOSED positions are excluded from fill targets."""
    from tracking.pipeline.fill_ingester import load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con)

        # OPEN positions are included
        assert any(t["leg_id"] == "gold_spot" for t in targets)
        assert any(t["leg_id"] == "gold_perp" for t in targets)
        # PAUSED positions are included
        assert any(t["leg_id"] == "paused_spot" for t in targets)
        # CLOSED positions are excluded
        assert not any(t["leg_id"] == "googl_spot" for t in targets)
        assert not any(t["leg_id"] == "googl_perp" for t in targets)

        con.close()


def test_load_fill_targets_for_backfill_includes_closed():
    """Backfill mode includes CLOSED positions."""
    from tracking.pipeline.fill_ingester import load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con, include_closed=True)

        assert any(t["leg_id"] == "googl_spot" for t in targets)
        assert any(t["leg_id"] == "googl_perp" for t in targets)

        con.close()


def test_map_fill_to_leg():
    """Fill is mapped to correct leg by inst_id + account_id."""
    from tracking.pipeline.fill_ingester import map_fill_to_leg, load_fill_targets

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        targets = load_fill_targets(con)

        # Perp fill maps to perp leg
        result = map_fill_to_leg("xyz:GOLD", "0xabc", targets)
        assert result is not None
        assert result["leg_id"] == "gold_perp"

        # Spot fill maps to spot leg
        result = map_fill_to_leg("XAUT0/USDC", "0xabc", targets)
        assert result is not None
        assert result["leg_id"] == "gold_spot"

        # Split perp: hyna:HYPE maps to hype_perp_hyna
        result = map_fill_to_leg("hyna:HYPE", "0xdef", targets)
        assert result is not None
        assert result["leg_id"] == "hype_perp_hyna"

        # Native perp: HYPE maps to hype_perp_native
        result = map_fill_to_leg("HYPE", "0xdef", targets)
        assert result is not None
        assert result["leg_id"] == "hype_perp_native"

        # Unknown inst_id returns None
        result = map_fill_to_leg("UNKNOWN", "0xabc", targets)
        assert result is None

        con.close()


def test_insert_fills_dedup():
    """Duplicate fills (same venue+account+tid) are skipped."""
    from tracking.pipeline.fill_ingester import insert_fills

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_positions(con)

        fills = [
            {
                "venue": "hyperliquid",
                "account_id": "0xabc",
                "tid": "t001",
                "oid": "o001",
                "inst_id": "xyz:GOLD",
                "side": "SELL",
                "px": 3000.0,
                "sz": 1.0,
                "fee": 0.5,
                "fee_currency": "USDC",
                "ts": 1711900000000,
                "position_id": "pos_xyz_GOLD",
                "leg_id": "gold_perp",
                "raw_json": "{}",
            }
        ]

        # First insert: 1 new
        inserted = insert_fills(con, fills)
        assert inserted == 1

        # Second insert: 0 (dedup)
        inserted = insert_fills(con, fills)
        assert inserted == 0

        # Verify only 1 row in DB
        count = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
        assert count == 1

        con.close()


def test_synthetic_tid():
    """Venues without native tid get a synthetic hash-based tid."""
    from tracking.pipeline.fill_ingester import generate_synthetic_tid

    tid = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=150.0,
        sz=10.0,
        ts=1711900000000,
    )
    assert tid.startswith("syn_")
    assert len(tid) > 10

    # Same inputs produce same tid (deterministic)
    tid2 = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=150.0,
        sz=10.0,
        ts=1711900000000,
    )
    assert tid == tid2

    # Different inputs produce different tid
    tid3 = generate_synthetic_tid(
        venue="felix",
        account_id="0x123",
        inst_id="AAPL/USDC",
        side="BUY",
        px=151.0,  # different price
        sz=10.0,
        ts=1711900000000,
    )
    assert tid != tid3


def test_parse_hl_fill_valid():
    """A well-formed HL fill response is parsed correctly."""
    from tracking.pipeline.fill_ingester import parse_hl_fill

    raw = {
        "time": 1711900000000,
        "coin": "HYPE",
        "side": "A",
        "px": "25.50",
        "sz": "100.0",
        "fee": "0.45",
        "oid": 12345,
        "tid": 67890,
        "dir": "Open Short",
        "closedPnl": "0.0",
    }
    spot_cache = {}
    targets = [
        {"leg_id": "hype_perp", "position_id": "pos_hype", "inst_id": "HYPE", "side": "SHORT", "account_id": "0xabc", "venue": "hyperliquid"},
    ]

    result = parse_hl_fill(raw, "0xabc", spot_cache, targets, dex="")
    assert result is not None
    assert result["inst_id"] == "HYPE"
    assert result["side"] == "SELL"
    assert result["px"] == 25.50
    assert result["sz"] == 100.0
    assert result["fee"] == 0.45
    assert result["leg_id"] == "hype_perp"
    assert result["position_id"] == "pos_hype"


def test_parse_hl_fill_malformed():
    """Malformed fill responses return None."""
    from tracking.pipeline.fill_ingester import parse_hl_fill

    # Missing time
    assert parse_hl_fill({}, "0xabc", {}, []) is None
    # Missing coin
    assert parse_hl_fill({"time": 123}, "0xabc", {}, []) is None
    # Zero price
    assert parse_hl_fill({"time": 123, "coin": "X", "side": "B", "px": "0", "sz": "1"}, "0xabc", {}, []) is None
    # Invalid side
    assert parse_hl_fill({"time": 123, "coin": "X", "side": "Z", "px": "1", "sz": "1"}, "0xabc", {}, []) is None


def main() -> int:
    test_load_fill_targets_excludes_closed()
    print("PASS: test_load_fill_targets_excludes_closed")
    test_load_fill_targets_for_backfill_includes_closed()
    print("PASS: test_load_fill_targets_for_backfill_includes_closed")
    test_map_fill_to_leg()
    print("PASS: test_map_fill_to_leg")
    test_insert_fills_dedup()
    print("PASS: test_insert_fills_dedup")
    test_synthetic_tid()
    print("PASS: test_synthetic_tid")
    test_parse_hl_fill_valid()
    print("PASS: test_parse_hl_fill_valid")
    test_parse_hl_fill_malformed()
    print("PASS: test_parse_hl_fill_malformed")
    print("\nAll fill_ingester tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_fill_ingester.py
```

Expected: ImportError — `tracking.pipeline.fill_ingester` doesn't exist yet.

- [ ] **Step 3: Implement fill ingester**

Create `tracking/pipeline/fill_ingester.py`:

```python
"""Hyperliquid fill ingester.

Pulls trade fills from userFillsByTime for all managed wallets,
resolves spot @index coins, maps to position legs, and inserts into pm_fills.

Usage:
    from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills

    con = sqlite3.connect("tracking/db/arbit_v3.db")
    spot_cache = fetch_spot_index_map()
    count = ingest_hyperliquid_fills(con, spot_cache)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

from tracking.pipeline.spot_meta import resolve_coin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def now_ms() -> int:
    return int(time.time() * 1000)


def generate_synthetic_tid(
    venue: str,
    account_id: str,
    inst_id: str,
    side: str,
    px: float,
    sz: float,
    ts: int,
) -> str:
    """Generate a deterministic synthetic trade ID for venues without native TIDs."""
    payload = f"{venue}|{account_id}|{inst_id}|{side}|{px}|{sz}|{ts}"
    h = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"syn_{h}"


# ---------------------------------------------------------------------------
# Target loading
# ---------------------------------------------------------------------------

def load_fill_targets(
    con: sqlite3.Connection,
    *,
    include_closed: bool = False,
    position_ids: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    """Load all legs that should receive fill mappings.

    By default, excludes CLOSED positions (fills for closed positions have no
    active leg to map to). Set include_closed=True for backfill operations.

    Returns list of dicts: {leg_id, position_id, inst_id, side, account_id, venue}
    """
    if position_ids:
        placeholders = ",".join("?" for _ in position_ids)
        sql = f"""
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE l.position_id IN ({placeholders})
        """
        rows = con.execute(sql, position_ids).fetchall()
    elif include_closed:
        sql = """
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
        """
        rows = con.execute(sql).fetchall()
    else:
        sql = """
            SELECT l.leg_id, l.position_id, l.inst_id, l.side, l.account_id, l.venue
            FROM pm_legs l
            JOIN pm_positions p ON p.position_id = l.position_id
            WHERE p.status != 'CLOSED'
        """
        rows = con.execute(sql).fetchall()

    return [
        {
            "leg_id": r[0],
            "position_id": r[1],
            "inst_id": r[2],
            "side": r[3],
            "account_id": r[4],
            "venue": r[5],
        }
        for r in rows
    ]


def map_fill_to_leg(
    inst_id: str,
    account_id: str,
    targets: List[Dict[str, str]],
) -> Optional[Dict[str, str]]:
    """Find the matching leg for a fill based on inst_id + account_id.

    Returns the target dict or None if no match found.
    """
    for t in targets:
        if t["inst_id"] == inst_id and t["account_id"] == account_id:
            return t
    return None


# ---------------------------------------------------------------------------
# Fill insertion
# ---------------------------------------------------------------------------

_INSERT_FILL_SQL = """
    INSERT OR IGNORE INTO pm_fills (
        venue, account_id, tid, oid, inst_id, side, px, sz,
        fee, fee_currency, ts, closed_pnl, dir, builder_fee,
        position_id, leg_id, raw_json, meta_json
    ) VALUES (
        :venue, :account_id, :tid, :oid, :inst_id, :side, :px, :sz,
        :fee, :fee_currency, :ts, :closed_pnl, :dir, :builder_fee,
        :position_id, :leg_id, :raw_json, :meta_json
    )
"""


def insert_fills(con: sqlite3.Connection, fills: List[Dict[str, Any]]) -> int:
    """Insert fills into pm_fills, skipping duplicates via UNIQUE constraint.

    Returns number of newly inserted rows.
    """
    if not fills:
        return 0

    before = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]

    for fill in fills:
        params = {
            "venue": fill.get("venue", ""),
            "account_id": fill.get("account_id", ""),
            "tid": fill.get("tid"),
            "oid": fill.get("oid"),
            "inst_id": fill.get("inst_id", ""),
            "side": fill.get("side", ""),
            "px": fill.get("px", 0),
            "sz": fill.get("sz", 0),
            "fee": fill.get("fee"),
            "fee_currency": fill.get("fee_currency"),
            "ts": fill.get("ts", 0),
            "closed_pnl": fill.get("closed_pnl"),
            "dir": fill.get("dir"),
            "builder_fee": fill.get("builder_fee"),
            "position_id": fill.get("position_id"),
            "leg_id": fill.get("leg_id"),
            "raw_json": fill.get("raw_json"),
            "meta_json": fill.get("meta_json"),
        }
        con.execute(_INSERT_FILL_SQL, params)

    con.commit()

    after = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
    return after - before


# ---------------------------------------------------------------------------
# HL fill parsing
# ---------------------------------------------------------------------------

def parse_hl_fill(
    raw: Dict[str, Any],
    account_id: str,
    spot_index_map: Dict[int, str],
    targets: List[Dict[str, str]],
    *,
    dex: str = "",
) -> Optional[Dict[str, Any]]:
    """Parse a single HL userFillsByTime response item into a pm_fills dict.

    Returns None if the fill cannot be parsed or mapped.
    """
    ts = raw.get("time") or raw.get("ts") or raw.get("timestamp")
    if ts is None:
        return None
    ts_ms = int(ts)

    raw_coin = str(raw.get("coin") or raw.get("asset") or "")
    if not raw_coin:
        return None

    # Resolve coin to inst_id
    try:
        inst_id = resolve_coin(raw_coin, spot_index_map)
    except ValueError:
        return None

    # Map to leg
    target = map_fill_to_leg(inst_id, account_id, targets)

    # Parse fill fields
    px = float(raw.get("px", 0))
    sz = float(raw.get("sz", 0))
    if px <= 0 or sz <= 0:
        return None

    hl_side = str(raw.get("side", ""))
    side = "BUY" if hl_side == "B" else "SELL" if hl_side == "A" else ""
    if not side:
        return None

    fee = None
    raw_fee = raw.get("fee")
    if raw_fee is not None:
        try:
            fee = float(raw_fee)
        except (TypeError, ValueError):
            pass

    builder_fee = None
    raw_bfee = raw.get("builderFee")
    if raw_bfee is not None:
        try:
            builder_fee = float(raw_bfee)
        except (TypeError, ValueError):
            pass

    closed_pnl = None
    raw_cpnl = raw.get("closedPnl")
    if raw_cpnl is not None:
        try:
            closed_pnl = float(raw_cpnl)
        except (TypeError, ValueError):
            pass

    tid = str(raw.get("tid", "")) or None
    oid = str(raw.get("oid", "")) or None

    meta = {"raw_coin": raw_coin, "dex": dex}
    if raw_coin.startswith("@"):
        meta["resolved_from_spot_index"] = True

    return {
        "venue": "hyperliquid",
        "account_id": account_id,
        "tid": tid,
        "oid": oid,
        "inst_id": inst_id,
        "side": side,
        "px": px,
        "sz": sz,
        "fee": fee,
        "fee_currency": "USDC" if fee is not None else None,
        "ts": ts_ms,
        "closed_pnl": closed_pnl,
        "dir": str(raw.get("dir", "")) or None,
        "builder_fee": builder_fee,
        "position_id": target["position_id"] if target else None,
        "leg_id": target["leg_id"] if target else None,
        "raw_json": json.dumps(raw),
        "meta_json": json.dumps(meta),
    }


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def get_watermark(con: sqlite3.Connection, venue: str, account_id: str) -> int:
    """Get the latest fill timestamp for a venue+account, or 0 if none."""
    row = con.execute(
        "SELECT MAX(ts) FROM pm_fills WHERE venue = ? AND account_id = ?",
        (venue, account_id),
    ).fetchone()
    return int(row[0]) if row and row[0] else 0


_WINDOW_MS = 24 * 3600 * 1000  # 24 hours in milliseconds


def _iter_time_windows(start_ms: int, end_ms: int, window_ms: int = _WINDOW_MS):
    """Yield (win_start, win_end) chunks from start to end.

    Matches the windowing pattern in pm_cashflows.py to avoid
    response truncation on large time ranges.
    """
    cursor = start_ms
    while cursor < end_ms:
        win_end = min(cursor + window_ms, end_ms)
        yield cursor, win_end
        cursor = win_end


def ingest_hyperliquid_fills(
    con: sqlite3.Connection,
    spot_index_map: Dict[int, str],
    *,
    include_closed: bool = False,
    since_ms: Optional[int] = None,
    position_ids: Optional[List[str]] = None,
) -> int:
    """Pull and ingest fills from Hyperliquid for all managed wallets.

    Args:
        con: DB connection
        spot_index_map: from fetch_spot_index_map()
        include_closed: if True, also ingest for CLOSED positions (backfill)
        since_ms: override start time (epoch ms). Default: watermark from DB.
        position_ids: if set, only ingest for these specific positions.

    Returns: number of new fills inserted.
    """
    from tracking.connectors.hyperliquid_private import (
        post_info as hyperliquid_post_info,
        split_inst_id,
    )

    targets = load_fill_targets(
        con,
        include_closed=include_closed,
        position_ids=position_ids,
    )
    if not targets:
        return 0

    # Group targets by account_id
    accounts: Dict[str, List[Dict[str, str]]] = {}
    for t in targets:
        accounts.setdefault(t["account_id"], []).append(t)

    end_ms = now_ms()
    all_fills: List[Dict[str, Any]] = []

    for account_id, account_targets in accounts.items():
        # Determine which dexes this account needs
        dexes_needed: set = set()
        for t in account_targets:
            dex, _coin = split_inst_id(t["inst_id"])
            dexes_needed.add(dex)
        # Spot fills come through default (no dex) endpoint
        dexes_needed.add("")

        start_ms = since_ms if since_ms is not None else get_watermark(con, "hyperliquid", account_id)
        # Add 1ms to avoid re-fetching the last fill
        if start_ms > 0:
            start_ms += 1

        for dex in dexes_needed:
            # Use 24h windows to avoid response truncation (matches pm_cashflows pattern)
            for win_start, win_end in _iter_time_windows(start_ms, end_ms):
                try:
                    fills_raw = hyperliquid_post_info(
                        {
                            "type": "userFillsByTime",
                            "user": account_id,
                            "startTime": int(win_start),
                            "endTime": int(win_end),
                            "aggregateByTime": False,
                        },
                        dex=dex or "",
                    )
                except Exception as e:
                    print(f"  WARN: failed to fetch fills for {account_id} dex={dex!r} window={win_start}-{win_end}: {e}")
                    continue

                if not isinstance(fills_raw, list):
                    continue

                for raw_fill in fills_raw:
                    if not isinstance(raw_fill, dict):
                        continue
                    parsed = parse_hl_fill(
                        raw_fill, account_id, spot_index_map, targets, dex=dex,
                    )
                    if parsed:
                        all_fills.append(parsed)

    inserted = insert_fills(con, all_fills)
    print(f"  fills: {len(all_fills)} parsed, {inserted} new inserted")
    return inserted
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
.venv/bin/python tests/test_fill_ingester.py
```

Expected: `All fill_ingester tests passed!`

- [ ] **Step 5: Commit**

```bash
git add tracking/pipeline/fill_ingester.py tests/test_fill_ingester.py
git commit -m "feat: add Hyperliquid fill ingester with dedup, spot resolution, leg mapping"
```

---

## Task 3.5: Validate Spot Fill API Endpoint

**Files:** None (verification only)

This is a critical validation step. The fill ingester assumes `userFillsByTime` with `dex=""` returns spot fills (with `@N` coin format). This assumption has not been verified in this codebase before — existing code only queries perp fills.

- [ ] **Step 1: Test spot fill retrieval from HL API**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from tracking.connectors.hyperliquid_private import post_info
from tracking.position_manager.accounts import resolve_venue_accounts
import json

accounts = resolve_venue_accounts('hyperliquid')
for label, address in accounts.items():
    print(f'Account: {label} ({address[:10]}...)')
    fills = post_info(
        {'type': 'userFillsByTime', 'user': address, 'startTime': 0, 'endTime': 9999999999999, 'aggregateByTime': False},
        dex='',
    )
    if isinstance(fills, list):
        # Find spot fills (contain @ in coin field)
        spot_fills = [f for f in fills if str(f.get('coin', '')).startswith('@')]
        perp_fills = [f for f in fills if not str(f.get('coin', '')).startswith('@')]
        print(f'  Total fills: {len(fills)}, Spot fills (@N): {len(spot_fills)}, Perp fills: {len(perp_fills)}')
        if spot_fills:
            print(f'  Sample spot fill: {json.dumps(spot_fills[0], indent=2)}')
        if perp_fills[:1]:
            print(f'  Sample perp fill: {json.dumps(perp_fills[0], indent=2)}')
    else:
        print(f'  Unexpected response type: {type(fills)}')
"
```

Expected: Both spot fills (with `@N` coin format) and perp fills are returned. If spot fills are NOT returned, investigate the correct HL API for spot trade history before proceeding to Task 4.

- [ ] **Step 2: If spot fills missing — check alternative endpoints**

If Step 1 shows zero spot fills but you know spot trades were executed, try:
```bash
source .arbit_env && .venv/bin/python -c "
from tracking.connectors.hyperliquid_private import post_info
from tracking.position_manager.accounts import resolve_venue_accounts

accounts = resolve_venue_accounts('hyperliquid')
for label, address in accounts.items():
    # Try userFills (non-time-based) which may include spot
    fills = post_info({'type': 'userFills', 'user': address, 'aggregateByTime': False}, dex='')
    if isinstance(fills, list):
        spot = [f for f in fills if str(f.get('coin', '')).startswith('@')]
        print(f'{label}: userFills returned {len(fills)} total, {len(spot)} spot')
"
```

If this also fails, the fill ingester will need a separate spot fill endpoint. Document findings and adjust `ingest_hyperliquid_fills` accordingly before proceeding.

---

## Task 4: Backfill Script

**Files:**
- Create: `scripts/backfill_fills.py`

- [ ] **Step 1: Create the backfill CLI script**

Create `scripts/backfill_fills.py`:

```python
#!/usr/bin/env python3
"""Backfill trade fills for existing positions.

Pulls fill history from Hyperliquid and stores in pm_fills.
Supports backfilling all positions, specific positions, or since a date.

Usage:
    python scripts/backfill_fills.py --all
    python scripts/backfill_fills.py --position pos_xyz_GOLD
    python scripts/backfill_fills.py --since 2026-01-01
    python scripts/backfill_fills.py --all --dry-run
"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill trade fills from Hyperliquid")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--all", action="store_true", help="Backfill all positions (OPEN + CLOSED)")
    ap.add_argument("--position", type=str, help="Backfill a specific position ID")
    ap.add_argument("--since", type=str, help="Start date (YYYY-MM-DD). Default: beginning of time")
    ap.add_argument("--dry-run", action="store_true", help="Show targets without ingesting")
    args = ap.parse_args()

    if not args.all and not args.position:
        ap.error("Specify --all or --position <id>")

    from tracking.pipeline.spot_meta import fetch_spot_index_map
    from tracking.pipeline.fill_ingester import (
        load_fill_targets,
        ingest_hyperliquid_fills,
    )

    con = connect(args.db)

    # Determine since_ms
    since_ms = 0
    if args.since:
        dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        since_ms = int(dt.timestamp() * 1000)

    # Determine position filter
    position_ids = None
    if args.position:
        position_ids = [args.position]

    # Show targets
    targets = load_fill_targets(
        con,
        include_closed=True,
        position_ids=position_ids,
    )

    print(f"Backfill targets: {len(targets)} legs")
    positions_seen = set()
    for t in targets:
        pid = t["position_id"]
        if pid not in positions_seen:
            positions_seen.add(pid)
            # Get position status
            row = con.execute(
                "SELECT status, strategy FROM pm_positions WHERE position_id = ?",
                (pid,),
            ).fetchone()
            status = row[0] if row else "?"
            strategy = row[1] if row else "?"
            print(f"  {pid} [{status}] ({strategy})")
        print(f"    - {t['leg_id']}: {t['inst_id']} ({t['side']}) account={t['account_id'][:8]}...")

    if args.dry_run:
        print("\nDRY RUN: no fills ingested")
        return 0

    # Fetch spot metadata
    print("\nFetching spotMeta...")
    spot_cache = fetch_spot_index_map()
    print(f"  loaded {len(spot_cache)} spot pairs")

    # Run ingestion
    print(f"\nIngesting fills (since_ms={since_ms})...")
    count = ingest_hyperliquid_fills(
        con,
        spot_cache,
        include_closed=True,
        since_ms=since_ms,
        position_ids=position_ids,
    )

    # Summary
    total = con.execute("SELECT COUNT(*) FROM pm_fills").fetchone()[0]
    print(f"\nBackfill complete: {count} new fills inserted, {total} total in DB")

    # Per-position fill counts
    cur = con.execute("""
        SELECT position_id, COUNT(*) as cnt
        FROM pm_fills
        WHERE position_id IS NOT NULL
        GROUP BY position_id
        ORDER BY cnt DESC
    """)
    print("\nFills per position:")
    for pid, cnt in cur.fetchall():
        print(f"  {pid}: {cnt} fills")

    # Unmapped fills
    unmapped = con.execute(
        "SELECT COUNT(*) FROM pm_fills WHERE position_id IS NULL"
    ).fetchone()[0]
    if unmapped > 0:
        print(f"\n  WARNING: {unmapped} fills could not be mapped to a position")

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run dry-run to verify target listing**

Run:
```bash
source .arbit_env && .venv/bin/python scripts/backfill_fills.py --all --dry-run
```

Expected: Lists all 11 positions (4 OPEN + 7 CLOSED) with their legs, account IDs. No actual ingestion.

- [ ] **Step 3: Run full backfill**

Run:
```bash
source .arbit_env && .venv/bin/python scripts/backfill_fills.py --all
```

Expected: Fetches spotMeta, ingests fills for all accounts, shows per-position fill counts. Verify all 11 positions have fills.

- [ ] **Step 4: Verify dedup — run backfill again**

Run:
```bash
source .arbit_env && .venv/bin/python scripts/backfill_fills.py --all
```

Expected: `0 new fills inserted` — dedup prevents duplicates.

- [ ] **Step 5: Spot-check fill data quality**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
con = sqlite3.connect('tracking/db/arbit_v3.db')

# Check spot fills have SYMBOL/USDC format
spot_fills = con.execute(\"\"\"
    SELECT inst_id, COUNT(*)
    FROM pm_fills
    WHERE inst_id LIKE '%/%'
    GROUP BY inst_id
\"\"\").fetchall()
print('Spot fills by inst_id:')
for inst_id, cnt in spot_fills:
    print(f'  {inst_id}: {cnt}')

# Check perp fills
perp_fills = con.execute(\"\"\"
    SELECT inst_id, COUNT(*)
    FROM pm_fills
    WHERE inst_id NOT LIKE '%/%'
    GROUP BY inst_id
\"\"\").fetchall()
print('Perp fills by inst_id:')
for inst_id, cnt in perp_fills:
    print(f'  {inst_id}: {cnt}')

# Sample a fill
fill = con.execute('SELECT * FROM pm_fills LIMIT 1').fetchone()
cols = [d[0] for d in con.execute('SELECT * FROM pm_fills LIMIT 0').description]
print('\\nSample fill:')
for col, val in zip(cols, fill):
    print(f'  {col}: {val}')

con.close()
"
```

Expected: Spot fills show `XAUT0/USDC`, `HYPE/USDC`, etc. Perp fills show `xyz:GOLD`, `hyna:HYPE`, `HYPE`, etc. All fields populated.

- [ ] **Step 6: Commit**

```bash
git add scripts/backfill_fills.py
git commit -m "feat: add backfill script for trade fills (all positions)"
```

---

## Task 5: Vault Setup

**Files:**
- Create: `vault/.gitignore`
- Create: `vault/vault.py`
- Create: `.sops.yaml`
- Create: `tests/test_vault.py`

- [ ] **Step 1: Create vault directory and .gitignore**

Create `vault/.gitignore`:

```gitignore
# age identity file (private key — NEVER commit)
age-identity.txt

# Decrypted secrets (temporary)
*.dec.json
```

- [ ] **Step 2: Write failing tests for vault module**

Create `tests/test_vault.py`:

```python
#!/usr/bin/env python3
"""Tests for vault secret management."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from vault.vault import get_secret, get_secret_with_env_fallback


def test_env_fallback():
    """When vault is not available, falls back to env var."""
    with patch.dict(os.environ, {"TEST_SECRET": "from_env"}):
        result = get_secret_with_env_fallback("test_key", env_var="TEST_SECRET")
        assert result == "from_env"


def test_env_fallback_missing():
    """When both vault and env var are missing, returns None."""
    env = os.environ.copy()
    env.pop("NONEXISTENT_VAR", None)
    with patch.dict(os.environ, env, clear=True):
        result = get_secret_with_env_fallback("test_key", env_var="NONEXISTENT_VAR")
        assert result is None


def main() -> int:
    test_env_fallback()
    print("PASS: test_env_fallback")
    test_env_fallback_missing()
    print("PASS: test_env_fallback_missing")
    print("\nAll vault tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run tests to verify they fail**

Run:
```bash
.venv/bin/python tests/test_vault.py
```

Expected: ImportError — `vault.vault` doesn't exist yet.

- [ ] **Step 4: Implement vault module**

Create `vault/vault.py`:

```python
"""Secret vault — encrypted secret management via age/sops.

Provides get_secret() to retrieve decrypted secrets from the sops-encrypted
vault file. Falls back to environment variables during the migration period.

Setup:
    1. Install: brew install age sops  (or apt-get install age sops)
    2. Generate key: age-keygen -o vault/age-identity.txt
    3. Configure .sops.yaml with the age public key
    4. Create vault/secrets.enc.json and encrypt with sops

Usage:
    from vault.vault import get_secret, get_secret_with_env_fallback

    # Direct vault access
    key = get_secret("hl_main_private_key")

    # With env var fallback (migration period)
    key = get_secret_with_env_fallback("hl_main_private_key", env_var="HL_PRIVATE_KEY")
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).parent.parent
DEFAULT_VAULT_PATH = ROOT / "vault" / "secrets.enc.json"

# Cache decrypted secrets in memory for the process lifetime
_secrets_cache: Optional[Dict[str, Any]] = None


def decrypt_secrets(vault_path: Optional[Path] = None) -> Dict[str, Any]:
    """Decrypt the sops-encrypted secrets file using age.

    Returns a dict of secret key -> value.
    Raises RuntimeError if decryption fails.
    """
    global _secrets_cache
    if _secrets_cache is not None:
        return _secrets_cache

    path = vault_path or DEFAULT_VAULT_PATH
    if not path.exists():
        return {}

    try:
        result = subprocess.run(
            ["sops", "--decrypt", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        _secrets_cache = json.loads(result.stdout)
        return _secrets_cache
    except FileNotFoundError:
        # sops not installed
        return {}
    except subprocess.CalledProcessError:
        # Decryption failed (no key, wrong key, etc.)
        return {}
    except json.JSONDecodeError:
        return {}


def get_secret(key: str, vault_path: Optional[Path] = None) -> Optional[str]:
    """Get a single secret by key from the vault.

    Returns None if the key is not found or vault is unavailable.
    """
    secrets = decrypt_secrets(vault_path)
    value = secrets.get(key)
    return str(value) if value is not None else None


def get_secret_with_env_fallback(
    key: str,
    env_var: str,
    vault_path: Optional[Path] = None,
) -> Optional[str]:
    """Get a secret from vault, falling back to an environment variable.

    Priority: vault > env var > None
    This allows gradual migration from .arbit_env to the vault.
    """
    # Try vault first
    value = get_secret(key, vault_path)
    if value is not None:
        return value

    # Fallback to env var
    return os.environ.get(env_var)


def clear_cache() -> None:
    """Clear the in-memory secrets cache (useful for testing)."""
    global _secrets_cache
    _secrets_cache = None
```

- [ ] **Step 5: Create vault __init__.py**

Create `vault/__init__.py`:

```python
"""Encrypted secret vault using age + sops."""
```

- [ ] **Step 6: Run tests to verify they pass**

Run:
```bash
.venv/bin/python tests/test_vault.py
```

Expected: `All vault tests passed!`

- [ ] **Step 7: Create .sops.yaml config template**

Create `.sops.yaml`:

```yaml
# sops configuration for age encryption
# To set up:
#   1. age-keygen -o vault/age-identity.txt
#   2. Copy the public key from the output
#   3. Replace AGE_PUBLIC_KEY_HERE below
#   4. Create vault/secrets.enc.json with your secrets
#   5. sops --encrypt --in-place vault/secrets.enc.json
#
# To decrypt: sops --decrypt vault/secrets.enc.json
# Requires: SOPS_AGE_KEY_FILE=vault/age-identity.txt (or set in env)

creation_rules:
  - path_regex: vault/.*\.enc\.json$
    age: >-
      AGE_PUBLIC_KEY_HERE
```

- [ ] **Step 8: Commit**

```bash
git add vault/.gitignore vault/__init__.py vault/vault.py .sops.yaml tests/test_vault.py
git commit -m "feat: add encrypted secret vault (age + sops) with env fallback"
```

---

## Task 6: Integration Smoke Test

**Files:** None (verification only)

- [ ] **Step 1: Verify full pipeline works end-to-end**

Run the complete flow: migration → backfill → verify:

```bash
source .arbit_env

# 1. Verify migration was applied
.venv/bin/python -c "
import sqlite3
con = sqlite3.connect('tracking/db/arbit_v3.db')
fills = con.execute('SELECT COUNT(*) FROM pm_fills').fetchone()[0]
print(f'Total fills in DB: {fills}')
assert fills > 0, 'No fills found — backfill may not have run'

# 2. Verify all OPEN positions have fills
open_positions = con.execute(\"\"\"
    SELECT p.position_id, p.status
    FROM pm_positions p
    WHERE p.status != 'CLOSED'
\"\"\").fetchall()
print(f'\nOpen/Paused positions: {len(open_positions)}')
for pid, status in open_positions:
    fill_count = con.execute(
        'SELECT COUNT(*) FROM pm_fills WHERE position_id = ?', (pid,)
    ).fetchone()[0]
    print(f'  {pid} ({status}): {fill_count} fills')
    assert fill_count > 0, f'No fills for active position {pid}'

# 3. Verify closed positions have fills
closed_positions = con.execute(\"\"\"
    SELECT p.position_id
    FROM pm_positions p
    WHERE p.status = 'CLOSED'
\"\"\").fetchall()
print(f'\nClosed positions: {len(closed_positions)}')
for (pid,) in closed_positions:
    fill_count = con.execute(
        'SELECT COUNT(*) FROM pm_fills WHERE position_id = ?', (pid,)
    ).fetchone()[0]
    print(f'  {pid}: {fill_count} fills')

# 4. Verify no inst_id without slash for spot legs
bad_legs = con.execute(\"\"\"
    SELECT l.leg_id, l.inst_id
    FROM pm_legs l
    JOIN pm_positions p ON p.position_id = l.position_id
    WHERE p.strategy = 'SPOT_PERP' AND l.side = 'LONG' AND l.inst_id NOT LIKE '%/%'
\"\"\").fetchall()
assert len(bad_legs) == 0, f'Legacy inst_ids still exist: {bad_legs}'
print('\nAll inst_ids canonicalized ✓')

# 5. Verify vault module loads
from vault.vault import get_secret_with_env_fallback
print('Vault module imports ✓')

print('\n=== ALL CHECKS PASSED ===')
con.close()
"
```

Expected: All positions have fills, no legacy inst_ids, vault imports work.

- [ ] **Step 2: Run dedup verification**

```bash
source .arbit_env && .venv/bin/python scripts/backfill_fills.py --all
```

Expected: `0 new fills inserted` — confirms dedup works.

- [ ] **Step 3: Final commit with any fixes**

If any issues were found and fixed:
```bash
git add -A
git commit -m "fix: address integration test findings in phase 1a"
```

---

## Summary

| Task | Files | What it does |
|------|-------|-------------|
| 1 | schema SQL + migration script | New DB tables + legacy inst_id fix |
| 2 | spot_meta.py + tests | @index → SYMBOL/USDC resolution |
| 3 | fill_ingester.py + tests | Pull HL fills, resolve, map, insert |
| 4 | backfill_fills.py | CLI to backfill all 11 positions |
| 5 | vault.py + config | Encrypted secrets with env fallback |
| 6 | (verification) | End-to-end smoke test |

**Execution order:** Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 (sequential — each depends on the previous).
