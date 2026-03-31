# Vault Multi-Strategy Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Track equity, APR, and cashflows across multiple strategies (Lending, Delta Neutral, Depeg) at both strategy and vault level, with daily snapshots and retroactive recalculation.

**Architecture:** Strategy Registry Pattern — a `vault_*` table layer on top of the existing `pm_*` tables. Each strategy type has an equity provider plugin. A daily cron job snapshots all strategies and computes vault-level rollups. Cashflows (deposits, withdrawals, inter-strategy transfers) are tracked separately with auto-recalc for late entries.

**Tech Stack:** Python 3.11, SQLite (existing), PostgreSQL (read-only for lending via `psycopg2`), FastAPI, Next.js 14, Tailwind CSS.

**Spec:** `docs/superpowers/specs/2026-03-31-vault-multi-strategy-tracking-design.md`

---

## File Structure

```
# New files to create
config/strategies.json                      # Strategy registry (source of truth)
tracking/sql/schema_vault.sql               # vault_* table definitions
tracking/vault/__init__.py                  # Package init
tracking/vault/registry.py                  # Load & validate strategies.json
tracking/vault/db_sync.py                   # Sync registry → vault_strategies table
tracking/vault/apr.py                       # Unified cashflow-adjusted APR calculator
tracking/vault/snapshot.py                  # Daily snapshot orchestrator
tracking/vault/recalc.py                    # Retroactive recalculation
tracking/vault/providers/__init__.py        # Provider registry
tracking/vault/providers/base.py            # EquityProvider ABC + StrategyEquity
tracking/vault/providers/delta_neutral.py   # Reads pm_account_snapshots
tracking/vault/providers/lending.py         # Reads harmonix-nav-platform Postgres
tracking/vault/providers/depeg.py           # Reads HL API for depeg wallet
scripts/vault.py                            # CLI: sync-registry, list, cashflow, recalc, snapshot
scripts/vault_daily_snapshot.py             # Cron job entry point
api/routers/vault.py                        # /api/vault/* endpoints
api/models/vault_schemas.py                 # Pydantic models for vault API
docs/runbook-vault-operations.md            # Runbook for vault CLI (recalc, etc.)
tests/test_vault_apr.py                     # APR calculation tests
tests/test_vault_registry.py                # Registry + sync tests
tests/test_vault_snapshot.py                # Snapshot pipeline tests
tests/test_vault_recalc.py                  # Retroactive recalc tests
tests/test_vault_api.py                     # API endpoint tests

# Files to modify
api/main.py                                 # Register vault router
```

---

### Task 1: Database Schema

**Files:**
- Create: `tracking/sql/schema_vault.sql`

- [ ] **Step 1: Create the vault schema file**

```sql
-- tracking/sql/schema_vault.sql
-- Vault multi-strategy tracking tables.
-- Run once to create; safe to re-run (IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS vault_strategies (
  strategy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'PAUSED', 'CLOSED')),
  wallets_json TEXT,
  target_weight_pct REAL,
  config_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vault_strategy_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_id TEXT NOT NULL,
  ts INTEGER NOT NULL,
  equity_usd REAL NOT NULL,
  equity_breakdown_json TEXT,
  apr_since_inception REAL,
  apr_30d REAL,
  apr_7d REAL,
  meta_json TEXT,
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_strat_snap_daily
  ON vault_strategy_snapshots(strategy_id, CAST(ts / 86400000 AS INTEGER));
CREATE INDEX IF NOT EXISTS idx_vault_strat_snap_strategy
  ON vault_strategy_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_vault_strat_snap_ts
  ON vault_strategy_snapshots(ts);

CREATE TABLE IF NOT EXISTS vault_cashflows (
  cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  cf_type TEXT NOT NULL
    CHECK (cf_type IN ('DEPOSIT', 'WITHDRAW', 'TRANSFER')),
  amount REAL NOT NULL,
  currency TEXT NOT NULL DEFAULT 'USDC',
  strategy_id TEXT,
  from_strategy_id TEXT,
  to_strategy_id TEXT,
  description TEXT,
  meta_json TEXT,
  created_at_ms INTEGER NOT NULL,
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (from_strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (to_strategy_id) REFERENCES vault_strategies(strategy_id)
);

CREATE INDEX IF NOT EXISTS idx_vault_cf_ts ON vault_cashflows(ts);
CREATE INDEX IF NOT EXISTS idx_vault_cf_strategy ON vault_cashflows(strategy_id);
CREATE INDEX IF NOT EXISTS idx_vault_cf_type ON vault_cashflows(cf_type);

CREATE TABLE IF NOT EXISTS vault_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,
  total_equity_usd REAL NOT NULL,
  strategy_weights_json TEXT,
  total_apr REAL,
  apr_30d REAL,
  apr_7d REAL,
  net_deposits_alltime REAL,
  meta_json TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_vault_snap_daily
  ON vault_snapshots(CAST(ts / 86400000 AS INTEGER));
CREATE INDEX IF NOT EXISTS idx_vault_snap_ts
  ON vault_snapshots(ts);
```

- [ ] **Step 2: Apply schema to existing database**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/.claude/worktrees/competent-chaum
source .arbit_env && sqlite3 tracking/db/arbit_v3.db < tracking/sql/schema_vault.sql
```

Expected: tables created without errors. Verify:

```bash
source .arbit_env && sqlite3 tracking/db/arbit_v3.db ".tables" | grep vault
```

Expected output includes: `vault_cashflows vault_snapshots vault_strategies vault_strategy_snapshots`

- [ ] **Step 3: Commit**

```bash
git add tracking/sql/schema_vault.sql
git commit -m "feat(vault): add vault_* database schema for multi-strategy tracking"
```

---

### Task 2: Strategy Config File

**Files:**
- Create: `config/strategies.json`

- [ ] **Step 1: Create strategies.json**

```json
{
  "vault_name": "OpenClaw Vault",
  "strategies": [
    {
      "strategy_id": "lending",
      "name": "Lending",
      "type": "LENDING",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "lending", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 50.0,
      "config": {}
    },
    {
      "strategy_id": "delta_neutral",
      "name": "Delta Neutral",
      "type": "DELTA_NEUTRAL",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "alt", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 45.0,
      "config": {}
    },
    {
      "strategy_id": "depeg",
      "name": "Stablecoin Depeg",
      "type": "DEPEG",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "depeg", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 5.0,
      "config": {}
    }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add config/strategies.json
git commit -m "feat(vault): add strategies.json config for 3 initial strategies"
```

---

### Task 3: Registry Loader & Validator

**Files:**
- Create: `tracking/vault/__init__.py`
- Create: `tracking/vault/registry.py`
- Create: `tests/test_vault_registry.py`

- [ ] **Step 1: Create package init**

```python
# tracking/vault/__init__.py
```

- [ ] **Step 2: Write failing tests for registry loader**

```python
# tests/test_vault_registry.py
"""Tests for vault strategy registry loader and validator."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from tempfile import NamedTemporaryFile

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.vault.registry import load_registry, StrategyConfig


VALID_STRATEGIES = {
    "vault_name": "Test Vault",
    "strategies": [
        {
            "strategy_id": "lending",
            "name": "Lending",
            "type": "LENDING",
            "status": "ACTIVE",
            "wallets": [{"wallet_label": "lending", "venue": "hyperliquid"}],
            "target_weight_pct": 50.0,
            "config": {},
        },
        {
            "strategy_id": "delta_neutral",
            "name": "Delta Neutral",
            "type": "DELTA_NEUTRAL",
            "status": "ACTIVE",
            "wallets": [{"wallet_label": "alt", "venue": "hyperliquid"}],
            "target_weight_pct": 45.0,
            "config": {},
        },
    ],
}


def _write_json(data) -> Path:
    f = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(data, f)
    f.close()
    return Path(f.name)


def test_load_valid_registry():
    path = _write_json(VALID_STRATEGIES)
    vault_name, strategies = load_registry(path)
    assert vault_name == "Test Vault"
    assert len(strategies) == 2
    assert strategies[0].strategy_id == "lending"
    assert strategies[0].type == "LENDING"
    assert strategies[1].strategy_id == "delta_neutral"
    assert strategies[1].wallets[0]["wallet_label"] == "alt"


def test_load_missing_file():
    with pytest.raises(FileNotFoundError):
        load_registry(Path("/nonexistent/file.json"))


def test_load_invalid_json():
    f = NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    f.write("{bad json")
    f.close()
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_registry(Path(f.name))


def test_validate_missing_strategy_id():
    data = {
        "vault_name": "Test",
        "strategies": [
            {"name": "X", "type": "LENDING", "status": "ACTIVE", "wallets": [], "target_weight_pct": 50.0, "config": {}},
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="strategy_id is required"):
        load_registry(path)


def test_validate_invalid_status():
    data = {
        "vault_name": "Test",
        "strategies": [
            {"strategy_id": "x", "name": "X", "type": "LENDING", "status": "INVALID", "wallets": [], "target_weight_pct": 50.0, "config": {}},
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="status must be one of"):
        load_registry(path)


def test_validate_duplicate_strategy_ids():
    data = {
        "vault_name": "Test",
        "strategies": [
            {"strategy_id": "dup", "name": "A", "type": "LENDING", "status": "ACTIVE", "wallets": [], "target_weight_pct": 50.0, "config": {}},
            {"strategy_id": "dup", "name": "B", "type": "DEPEG", "status": "ACTIVE", "wallets": [], "target_weight_pct": 50.0, "config": {}},
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="duplicate strategy_id"):
        load_registry(path)


def test_validate_weights_exceed_100():
    data = {
        "vault_name": "Test",
        "strategies": [
            {"strategy_id": "a", "name": "A", "type": "LENDING", "status": "ACTIVE", "wallets": [], "target_weight_pct": 60.0, "config": {}},
            {"strategy_id": "b", "name": "B", "type": "DEPEG", "status": "ACTIVE", "wallets": [], "target_weight_pct": 50.0, "config": {}},
        ],
    }
    path = _write_json(data)
    with pytest.raises(ValueError, match="target weights sum to"):
        load_registry(path)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/.claude/worktrees/competent-chaum
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_registry.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 4: Implement registry loader**

```python
# tracking/vault/registry.py
"""Vault Strategy Registry Loader and Validator.

Loads and validates strategy configurations from strategies.json.
Pattern follows tracking/position_manager/registry.py.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


VALID_STATUSES = {"ACTIVE", "PAUSED", "CLOSED"}


@dataclass
class StrategyConfig:
    """Configuration for a single strategy."""
    strategy_id: str
    name: str
    type: str
    status: str
    wallets: List[Dict[str, str]]
    target_weight_pct: float
    config: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        """Validate strategy configuration. Returns list of error messages."""
        errors = []
        if not self.strategy_id:
            errors.append("strategy_id is required")
        if not self.name:
            errors.append("name is required")
        if not self.type:
            errors.append("type is required")
        if not self.status:
            errors.append("status is required")
        elif self.status not in VALID_STATUSES:
            errors.append(f"status must be one of {VALID_STATUSES}, got '{self.status}'")
        if self.target_weight_pct is not None and self.target_weight_pct < 0:
            errors.append(f"target_weight_pct must be non-negative, got {self.target_weight_pct}")
        return errors


def load_registry(path: Path) -> Tuple[str, List[StrategyConfig]]:
    """Load strategy registry from JSON file.

    Args:
        path: Path to strategies.json

    Returns:
        Tuple of (vault_name, list of StrategyConfig)

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If JSON is invalid or validation fails
    """
    if not path.exists():
        raise FileNotFoundError(f"Registry file not found: {path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {path}: {e}")

    if not isinstance(data, dict):
        raise ValueError(f"Registry must be a JSON object with 'vault_name' and 'strategies'")

    vault_name = data.get("vault_name", "Vault")
    raw_strategies = data.get("strategies", [])

    if not isinstance(raw_strategies, list):
        raise ValueError("'strategies' must be a list")

    strategies = []
    all_errors = []

    for i, s in enumerate(raw_strategies):
        try:
            cfg = StrategyConfig(
                strategy_id=s.get("strategy_id", ""),
                name=s.get("name", ""),
                type=s.get("type", ""),
                status=s.get("status", ""),
                wallets=s.get("wallets", []),
                target_weight_pct=s.get("target_weight_pct", 0.0),
                config=s.get("config", {}),
            )
            errors = cfg.validate()
            if errors:
                all_errors.extend([f"strategy {i} ({cfg.strategy_id}): {e}" for e in errors])
            strategies.append(cfg)
        except Exception as e:
            all_errors.append(f"strategy {i}: {e}")

    # Check duplicate strategy_ids
    ids = [s.strategy_id for s in strategies if s.strategy_id]
    if len(ids) != len(set(ids)):
        dupes = [sid for sid in ids if ids.count(sid) > 1]
        all_errors.append(f"duplicate strategy_id(s): {set(dupes)}")

    # Check target weights sum for ACTIVE strategies
    active_weights = sum(s.target_weight_pct for s in strategies if s.status == "ACTIVE")
    if active_weights > 100.01:  # small epsilon for float
        all_errors.append(f"target weights sum to {active_weights:.1f}% (exceeds 100%)")

    if all_errors:
        raise ValueError("Validation failed:\n" + "\n".join(all_errors))

    return vault_name, strategies
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_registry.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tracking/vault/__init__.py tracking/vault/registry.py tests/test_vault_registry.py
git commit -m "feat(vault): add strategy registry loader with validation"
```

---

### Task 4: DB Sync

**Files:**
- Create: `tracking/vault/db_sync.py`

- [ ] **Step 1: Implement DB sync**

```python
# tracking/vault/db_sync.py
"""Database synchronization for vault strategy registry.

Syncs StrategyConfig objects to vault_strategies table.
Pattern follows tracking/position_manager/db_sync.py.
"""

from __future__ import annotations

import json
import sqlite3
import time
from typing import List

from .registry import StrategyConfig


def sync_registry(con: sqlite3.Connection, vault_name: str, strategies: List[StrategyConfig]) -> int:
    """Sync strategy configs to vault_strategies table.

    Args:
        con: Database connection
        vault_name: Vault name (stored in meta for reference)
        strategies: List of strategy configurations

    Returns:
        Number of strategies synced
    """
    now_ms = int(time.time() * 1000)

    for s in strategies:
        # Preserve original created_at if exists
        row = con.execute(
            "SELECT created_at_ms FROM vault_strategies WHERE strategy_id = ?",
            (s.strategy_id,),
        ).fetchone()
        created_at_ms = row[0] if row else now_ms

        con.execute(
            """
            INSERT INTO vault_strategies(
                strategy_id, name, type, status,
                wallets_json, target_weight_pct, config_json,
                created_at_ms, updated_at_ms
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(strategy_id) DO UPDATE SET
                name = excluded.name,
                type = excluded.type,
                status = excluded.status,
                wallets_json = excluded.wallets_json,
                target_weight_pct = excluded.target_weight_pct,
                config_json = excluded.config_json,
                updated_at_ms = excluded.updated_at_ms
            """,
            (
                s.strategy_id,
                s.name,
                s.type,
                s.status,
                json.dumps(s.wallets, separators=(",", ":")),
                s.target_weight_pct,
                json.dumps(s.config, separators=(",", ":")) if s.config else None,
                created_at_ms,
                now_ms,
            ),
        )

    con.commit()
    return len(strategies)


def list_strategies(con: sqlite3.Connection) -> List[dict]:
    """List all strategies with latest snapshot data."""
    cursor = con.execute(
        """
        SELECT s.strategy_id, s.name, s.type, s.status,
               s.target_weight_pct, s.wallets_json, s.updated_at_ms,
               snap.equity_usd, snap.apr_since_inception, snap.apr_7d, snap.apr_30d, snap.ts
        FROM vault_strategies s
        LEFT JOIN vault_strategy_snapshots snap ON snap.strategy_id = s.strategy_id
            AND snap.ts = (
                SELECT MAX(ts) FROM vault_strategy_snapshots WHERE strategy_id = s.strategy_id
            )
        ORDER BY s.target_weight_pct DESC
        """
    )
    results = []
    for row in cursor.fetchall():
        results.append({
            "strategy_id": row[0],
            "name": row[1],
            "type": row[2],
            "status": row[3],
            "target_weight_pct": row[4],
            "wallets": json.loads(row[5]) if row[5] else [],
            "updated_at_ms": row[6],
            "equity_usd": row[7],
            "apr_since_inception": row[8],
            "apr_7d": row[9],
            "apr_30d": row[10],
            "last_snapshot_ts": row[11],
        })
    return results
```

- [ ] **Step 2: Commit**

```bash
git add tracking/vault/db_sync.py
git commit -m "feat(vault): add DB sync for strategy registry"
```

---

### Task 5: APR Calculator

**Files:**
- Create: `tracking/vault/apr.py`
- Create: `tests/test_vault_apr.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_vault_apr.py
"""Tests for unified cashflow-adjusted APR calculator."""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.vault.apr import cashflow_adjusted_apr


def test_positive_return_no_cashflows():
    # 10000 -> 10100 over 10 days, no deposits
    apr = cashflow_adjusted_apr(
        current_equity=10100.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    # (100 / 10000) / 10 * 365 = 36.5%
    assert abs(apr - 3.65) < 0.01


def test_deposit_excluded_from_return():
    # 10000 -> 15100 over 10 days, but 5000 was deposited
    apr = cashflow_adjusted_apr(
        current_equity=15100.0,
        prior_equity=10000.0,
        net_external_cashflows=5000.0,
        period_days=10.0,
    )
    # organic = 15100 - 10000 - 5000 = 100
    # (100 / 10000) / 10 * 365 = 36.5%
    assert abs(apr - 3.65) < 0.01


def test_withdrawal_excluded_from_return():
    # 10000 -> 5100 over 10 days, but 5000 was withdrawn
    apr = cashflow_adjusted_apr(
        current_equity=5100.0,
        prior_equity=10000.0,
        net_external_cashflows=-5000.0,
        period_days=10.0,
    )
    # organic = 5100 - 10000 - (-5000) = 100
    # (100 / 10000) / 10 * 365 = 36.5%
    assert abs(apr - 3.65) < 0.01


def test_negative_return():
    # 10000 -> 9900 over 10 days, no cashflows
    apr = cashflow_adjusted_apr(
        current_equity=9900.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    # organic = -100
    # (-100 / 10000) / 10 * 365 = -3.65%
    assert abs(apr - (-3.65)) < 0.01


def test_zero_prior_equity():
    apr = cashflow_adjusted_apr(
        current_equity=100.0,
        prior_equity=0.0,
        net_external_cashflows=0.0,
        period_days=10.0,
    )
    assert apr == 0.0


def test_zero_period():
    apr = cashflow_adjusted_apr(
        current_equity=10100.0,
        prior_equity=10000.0,
        net_external_cashflows=0.0,
        period_days=0.0,
    )
    assert apr == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_apr.py -v
```

Expected: FAIL (module not found)

- [ ] **Step 3: Implement APR calculator**

```python
# tracking/vault/apr.py
"""Unified cashflow-adjusted APR calculator.

Used at both strategy and vault level. Same formula everywhere:
organic_change = (current - prior) - net_cashflows
apr = (organic_change / prior) / days * 365
"""

from __future__ import annotations


def cashflow_adjusted_apr(
    current_equity: float,
    prior_equity: float,
    net_external_cashflows: float,
    period_days: float,
) -> float:
    """Compute annualized return adjusted for external cashflows.

    Args:
        current_equity: Current equity value
        prior_equity: Equity at start of period
        net_external_cashflows: Sum of deposits (positive) + withdrawals (negative)
            in the period. Transfers between strategies are excluded.
        period_days: Length of period in days

    Returns:
        Annualized return as a percentage (e.g., 3.65 means 3.65%).
        Returns 0.0 if prior_equity or period_days is zero/negative.
    """
    if prior_equity <= 0 or period_days <= 0:
        return 0.0
    organic_change = (current_equity - prior_equity) - net_external_cashflows
    daily_return = organic_change / prior_equity / period_days
    return daily_return * 365 * 100  # percentage
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_apr.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracking/vault/apr.py tests/test_vault_apr.py
git commit -m "feat(vault): add unified cashflow-adjusted APR calculator"
```

---

### Task 6: Equity Providers

**Files:**
- Create: `tracking/vault/providers/__init__.py`
- Create: `tracking/vault/providers/base.py`
- Create: `tracking/vault/providers/delta_neutral.py`
- Create: `tracking/vault/providers/lending.py`
- Create: `tracking/vault/providers/depeg.py`

- [ ] **Step 1: Create provider base and registry**

```python
# tracking/vault/providers/__init__.py
"""Equity provider registry.

Maps strategy type strings to provider classes.
"""

from .base import EquityProvider, StrategyEquity
from .delta_neutral import DeltaNeutralProvider
from .lending import LendingProvider
from .depeg import DepegProvider

PROVIDER_REGISTRY: dict[str, type[EquityProvider]] = {
    "DELTA_NEUTRAL": DeltaNeutralProvider,
    "LENDING": LendingProvider,
    "DEPEG": DepegProvider,
}

__all__ = [
    "EquityProvider",
    "StrategyEquity",
    "PROVIDER_REGISTRY",
    "DeltaNeutralProvider",
    "LendingProvider",
    "DepegProvider",
]
```

```python
# tracking/vault/providers/base.py
"""Base class for strategy equity providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class StrategyEquity:
    """Result of an equity query for a strategy."""
    equity_usd: float
    breakdown: dict            # per-wallet, per-protocol, or per-asset
    timestamp_ms: int
    meta: dict = field(default_factory=dict)


class EquityProvider(ABC):
    """Abstract base for fetching equity of a strategy."""

    @abstractmethod
    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        """Fetch current equity for this strategy.

        Args:
            strategy: Row from vault_strategies (dict with strategy_id, wallets_json, etc.)
            db: SQLite connection (for reading pm_* tables or vault_* tables)

        Returns:
            StrategyEquity with current equity data
        """
        pass
```

- [ ] **Step 2: Implement DeltaNeutralProvider**

```python
# tracking/vault/providers/delta_neutral.py
"""Delta Neutral equity provider.

Reads equity from pm_account_snapshots for the wallets assigned to this strategy.
The existing hourly pipeline (pipeline_hourly.py) already computes and writes
pm_account_snapshots every 5 minutes.
"""

from __future__ import annotations

import json
import time
import sqlite3

from .base import EquityProvider, StrategyEquity


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        from tracking.position_manager.accounts import resolve_venue_accounts

        total_equity = 0.0
        breakdown = {}

        for wallet in wallets:
            label = wallet.get("wallet_label", "main")
            venue = wallet.get("venue", "hyperliquid")
            accounts = resolve_venue_accounts(venue)
            address = accounts.get(label)
            if not address:
                continue

            # Get latest account snapshot for this wallet
            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (address, venue),
            ).fetchone()

            if row:
                equity = float(row[0]) if row[0] else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
```

- [ ] **Step 3: Implement LendingProvider**

```python
# tracking/vault/providers/lending.py
"""Lending equity provider.

Reads total lending equity from harmonix-nav-platform PostgreSQL database.
The external system (Prefect flows) pulls on-chain data for multiple protocols
(HyperLend, Felix, HypurrFi) and stores it in Postgres.
"""

from __future__ import annotations

import os
import time
import logging

from .base import EquityProvider, StrategyEquity

log = logging.getLogger(__name__)


class LendingProvider(EquityProvider):
    """Reads lending equity from harmonix-nav-platform Postgres."""

    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        db_url = os.environ.get("HARMONIX_NAV_DB_URL", "")
        if not db_url:
            log.warning("HARMONIX_NAV_DB_URL not set, returning zero equity for lending")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "HARMONIX_NAV_DB_URL not configured"},
            )

        try:
            import psycopg2
            con = psycopg2.connect(db_url)
            try:
                return self._query_lending_equity(con)
            finally:
                con.close()
        except ImportError:
            log.error("psycopg2 not installed. Run: pip install psycopg2-binary")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": "psycopg2 not installed"},
            )
        except Exception as e:
            log.error(f"Failed to query harmonix-nav-platform: {e}")
            return StrategyEquity(
                equity_usd=0.0,
                breakdown={},
                timestamp_ms=int(time.time() * 1000),
                meta={"error": str(e)},
            )

    def _query_lending_equity(self, pg_con) -> StrategyEquity:
        """Query lending equity from harmonix-nav-platform.

        TODO: Update this query once we have the exact harmonix-nav-platform
        schema. For now, this is a placeholder that queries a generic
        wallet_balances or positions table. The actual table/column names
        will be confirmed when we get access to the harmonix-nav-platform schema.
        """
        cursor = pg_con.cursor()

        # Placeholder query — update with actual harmonix-nav-platform schema
        # Expected: sum equity across all lending protocols for our wallets
        cursor.execute(
            """
            SELECT
                COALESCE(SUM(balance_usd), 0) as total_equity,
                json_agg(json_build_object(
                    'protocol', protocol_name,
                    'equity_usd', balance_usd
                )) as breakdown
            FROM wallet_balances
            WHERE wallet_type = 'lending'
            """
        )
        row = cursor.fetchone()
        total_equity = float(row[0]) if row and row[0] else 0.0
        breakdown_raw = row[1] if row and row[1] else []

        breakdown = {}
        if isinstance(breakdown_raw, list):
            for item in breakdown_raw:
                if isinstance(item, dict) and item.get("protocol"):
                    breakdown[item["protocol"]] = {
                        "equity_usd": float(item.get("equity_usd", 0)),
                    }

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
```

- [ ] **Step 4: Implement DepegProvider**

```python
# tracking/vault/providers/depeg.py
"""Depeg equity provider.

Reads total account equity from Hyperliquid for the dedicated depeg wallet.
Same API calls as DN (clearinghouseState + spotClearinghouseState)
but for a different wallet address.
"""

from __future__ import annotations

import json
import time
import sqlite3

from .base import EquityProvider, StrategyEquity


class DepegProvider(EquityProvider):
    """Reads depeg wallet equity from pm_account_snapshots (same source as DN)."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        from tracking.position_manager.accounts import resolve_venue_accounts

        total_equity = 0.0
        breakdown = {}

        for wallet in wallets:
            label = wallet.get("wallet_label", "depeg")
            venue = wallet.get("venue", "hyperliquid")
            accounts = resolve_venue_accounts(venue)
            address = accounts.get(label)
            if not address:
                continue

            # Get latest account snapshot — same table as DN, different account_id
            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (address, venue),
            ).fetchone()

            if row:
                equity = float(row[0]) if row[0] else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
```

- [ ] **Step 5: Commit**

```bash
git add tracking/vault/providers/
git commit -m "feat(vault): add equity providers (DN, Lending, Depeg)"
```

---

### Task 7: Snapshot Pipeline + Recalc

**Files:**
- Create: `tracking/vault/snapshot.py`
- Create: `tracking/vault/recalc.py`
- Create: `tests/test_vault_snapshot.py`
- Create: `tests/test_vault_recalc.py`

- [ ] **Step 1: Write failing tests for snapshot**

```python
# tests/test_vault_snapshot.py
"""Tests for vault daily snapshot pipeline."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMA_PM = Path(__file__).parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = Path(__file__).parent.parent / "tracking" / "sql" / "schema_vault.sql"


def _setup_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())
    return con


def _insert_strategy(con, strategy_id="test_strat", stype="DELTA_NEUTRAL", status="ACTIVE"):
    now_ms = int(time.time() * 1000)
    con.execute(
        "INSERT INTO vault_strategies(strategy_id, name, type, status, wallets_json, target_weight_pct, created_at_ms, updated_at_ms) VALUES (?,?,?,?,?,?,?,?)",
        (strategy_id, "Test", stype, status, "[]", 100.0, now_ms, now_ms),
    )
    con.commit()


def test_run_snapshot_empty_strategies():
    from tracking.vault.snapshot import run_daily_snapshot
    con = _setup_db()
    result = run_daily_snapshot(con)
    assert result["strategies_processed"] == 0
    assert result["vault_equity"] == 0.0


def test_run_snapshot_writes_strategy_snapshot():
    from tracking.vault.snapshot import run_daily_snapshot
    from unittest.mock import patch, MagicMock
    from tracking.vault.providers.base import StrategyEquity

    con = _setup_db()
    _insert_strategy(con, "dn", "DELTA_NEUTRAL")

    mock_equity = StrategyEquity(equity_usd=10000.0, breakdown={"alt": {"equity_usd": 10000.0}}, timestamp_ms=int(time.time() * 1000))

    with patch("tracking.vault.providers.DeltaNeutralProvider.get_equity", return_value=mock_equity):
        result = run_daily_snapshot(con)

    assert result["strategies_processed"] == 1
    assert result["vault_equity"] == 10000.0

    # Verify strategy snapshot was written
    row = con.execute("SELECT equity_usd FROM vault_strategy_snapshots WHERE strategy_id = 'dn'").fetchone()
    assert row is not None
    assert row[0] == 10000.0

    # Verify vault snapshot was written
    row = con.execute("SELECT total_equity_usd FROM vault_snapshots ORDER BY ts DESC LIMIT 1").fetchone()
    assert row is not None
    assert row[0] == 10000.0
```

- [ ] **Step 2: Implement snapshot pipeline**

```python
# tracking/vault/snapshot.py
"""Daily vault snapshot pipeline.

Orchestrates: load strategies → fetch equity per provider → compute APR → write snapshots.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from typing import Any, Dict

from .apr import cashflow_adjusted_apr
from .providers import PROVIDER_REGISTRY

log = logging.getLogger(__name__)


def run_daily_snapshot(con: sqlite3.Connection) -> Dict[str, Any]:
    """Run the daily vault snapshot pipeline.

    Args:
        con: SQLite connection (writable)

    Returns:
        Summary dict with strategies_processed, vault_equity, etc.
    """
    now_ms = int(time.time() * 1000)

    # Load active strategies
    rows = con.execute(
        "SELECT strategy_id, name, type, status, wallets_json, target_weight_pct, config_json "
        "FROM vault_strategies WHERE status = 'ACTIVE'"
    ).fetchall()

    strategy_equities = {}
    strategies_processed = 0

    for row in rows:
        strategy = {
            "strategy_id": row[0],
            "name": row[1],
            "type": row[2],
            "status": row[3],
            "wallets_json": row[4],
            "target_weight_pct": row[5],
            "config_json": row[6],
        }
        sid = strategy["strategy_id"]
        stype = strategy["type"]

        provider_cls = PROVIDER_REGISTRY.get(stype)
        if not provider_cls:
            log.warning(f"No provider for strategy type '{stype}', skipping {sid}")
            continue

        try:
            provider = provider_cls()
            equity = provider.get_equity(strategy, con)
            strategy_equities[sid] = equity

            # Compute APR windows
            apr_inception = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, window_days=None)
            apr_30d = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, window_days=30)
            apr_7d = _compute_apr_for_strategy(con, sid, equity.equity_usd, now_ms, window_days=7)

            # Write strategy snapshot (upsert by day)
            _upsert_strategy_snapshot(con, sid, now_ms, equity, apr_inception, apr_30d, apr_7d)
            strategies_processed += 1
            log.info(f"  {sid}: equity=${equity.equity_usd:,.2f}, APR(inception)={apr_inception:.2f}%")

        except Exception as e:
            log.error(f"Failed to snapshot strategy {sid}: {e}")

    # Vault rollup
    vault_equity = sum(e.equity_usd for e in strategy_equities.values())
    weights = {}
    if vault_equity > 0:
        weights = {sid: e.equity_usd / vault_equity * 100 for sid, e in strategy_equities.items()}

    # Vault-level APR
    vault_apr = _compute_vault_apr(con, vault_equity, now_ms, window_days=None)
    vault_apr_30d = _compute_vault_apr(con, vault_equity, now_ms, window_days=30)
    vault_apr_7d = _compute_vault_apr(con, vault_equity, now_ms, window_days=7)

    # Net deposits all-time
    net_deposits = _get_net_deposits(con)

    _upsert_vault_snapshot(con, now_ms, vault_equity, weights, vault_apr, vault_apr_30d, vault_apr_7d, net_deposits)
    con.commit()

    log.info(f"Vault snapshot: equity=${vault_equity:,.2f}, APR={vault_apr:.2f}%, strategies={strategies_processed}")

    return {
        "strategies_processed": strategies_processed,
        "vault_equity": vault_equity,
        "vault_apr": vault_apr,
        "weights": weights,
    }


def _compute_apr_for_strategy(
    con: sqlite3.Connection,
    strategy_id: str,
    current_equity: float,
    now_ms: int,
    window_days: int | None,
) -> float:
    """Compute APR for a strategy over a given window."""
    if window_days is None:
        # Since inception: use earliest snapshot
        row = con.execute(
            "SELECT equity_usd, ts FROM vault_strategy_snapshots WHERE strategy_id = ? ORDER BY ts ASC LIMIT 1",
            (strategy_id,),
        ).fetchone()
    else:
        cutoff_ms = now_ms - (window_days * 86400 * 1000)
        row = con.execute(
            "SELECT equity_usd, ts FROM vault_strategy_snapshots WHERE strategy_id = ? AND ts <= ? ORDER BY ts DESC LIMIT 1",
            (strategy_id, cutoff_ms),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (now_ms - prior_ts) / 86400000.0

    # Get net external cashflows for this strategy in the period
    # Exclude TRANSFER type — only DEPOSIT and WITHDRAW
    cf_row = con.execute(
        """
        SELECT COALESCE(SUM(
            CASE
                WHEN cf_type = 'DEPOSIT' AND strategy_id = ? THEN amount
                WHEN cf_type = 'WITHDRAW' AND strategy_id = ? THEN amount
                WHEN cf_type = 'TRANSFER' AND to_strategy_id = ? THEN amount
                WHEN cf_type = 'TRANSFER' AND from_strategy_id = ? THEN -amount
                ELSE 0
            END
        ), 0)
        FROM vault_cashflows
        WHERE ts >= ? AND ts <= ?
          AND cf_type IN ('DEPOSIT', 'WITHDRAW')
        """,
        (strategy_id, strategy_id, strategy_id, strategy_id, prior_ts, now_ms),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _compute_vault_apr(
    con: sqlite3.Connection,
    current_equity: float,
    now_ms: int,
    window_days: int | None,
) -> float:
    """Compute vault-level APR."""
    if window_days is None:
        row = con.execute(
            "SELECT total_equity_usd, ts FROM vault_snapshots ORDER BY ts ASC LIMIT 1"
        ).fetchone()
    else:
        cutoff_ms = now_ms - (window_days * 86400 * 1000)
        row = con.execute(
            "SELECT total_equity_usd, ts FROM vault_snapshots WHERE ts <= ? ORDER BY ts DESC LIMIT 1",
            (cutoff_ms,),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (now_ms - prior_ts) / 86400000.0

    # Vault level: only DEPOSIT and WITHDRAW (transfers cancel out)
    cf_row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ? AND ts <= ?",
        (prior_ts, now_ms),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _get_net_deposits(con: sqlite3.Connection) -> float:
    """Get all-time net deposits (deposits - withdrawals)."""
    row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW')"
    ).fetchone()
    return float(row[0]) if row else 0.0


def _upsert_strategy_snapshot(
    con: sqlite3.Connection,
    strategy_id: str,
    ts: int,
    equity: Any,
    apr_inception: float,
    apr_30d: float,
    apr_7d: float,
) -> None:
    """Insert or update strategy snapshot (one per day per strategy)."""
    day_bucket = ts // 86400000

    # Delete existing snapshot for this day (if re-running)
    con.execute(
        "DELETE FROM vault_strategy_snapshots WHERE strategy_id = ? AND CAST(ts / 86400000 AS INTEGER) = ?",
        (strategy_id, day_bucket),
    )

    con.execute(
        """
        INSERT INTO vault_strategy_snapshots(
            strategy_id, ts, equity_usd, equity_breakdown_json,
            apr_since_inception, apr_30d, apr_7d, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            strategy_id,
            ts,
            equity.equity_usd,
            json.dumps(equity.breakdown, separators=(",", ":")),
            apr_inception,
            apr_30d,
            apr_7d,
            json.dumps(equity.meta, separators=(",", ":")) if equity.meta else None,
        ),
    )


def _upsert_vault_snapshot(
    con: sqlite3.Connection,
    ts: int,
    total_equity: float,
    weights: dict,
    total_apr: float,
    apr_30d: float,
    apr_7d: float,
    net_deposits: float,
) -> None:
    """Insert or update vault snapshot (one per day)."""
    day_bucket = ts // 86400000

    con.execute(
        "DELETE FROM vault_snapshots WHERE CAST(ts / 86400000 AS INTEGER) = ?",
        (day_bucket,),
    )

    con.execute(
        """
        INSERT INTO vault_snapshots(
            ts, total_equity_usd, strategy_weights_json,
            total_apr, apr_30d, apr_7d, net_deposits_alltime, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            ts,
            total_equity,
            json.dumps(weights, separators=(",", ":")),
            total_apr,
            apr_30d,
            apr_7d,
            net_deposits,
            None,
        ),
    )
```

- [ ] **Step 3: Implement recalc**

```python
# tracking/vault/recalc.py
"""Retroactive snapshot recalculation.

When a cashflow is inserted with a timestamp before the latest snapshot,
APR fields in affected snapshots must be recalculated.
Equity values stay unchanged — only APR is recomputed.
"""

from __future__ import annotations

import logging
import sqlite3

from .apr import cashflow_adjusted_apr

log = logging.getLogger(__name__)


def recalc_snapshots(con: sqlite3.Connection, since_ms: int) -> int:
    """Recalculate APR for all snapshots from since_ms forward.

    Args:
        con: Writable SQLite connection
        since_ms: Epoch ms — recalculate snapshots at or after this time

    Returns:
        Number of snapshots recalculated
    """
    # Get all strategy snapshots that need recalc
    rows = con.execute(
        """
        SELECT snapshot_id, strategy_id, ts, equity_usd
        FROM vault_strategy_snapshots
        WHERE ts >= ?
        ORDER BY ts ASC
        """,
        (since_ms,),
    ).fetchall()

    count = 0
    for snapshot_id, strategy_id, ts, equity_usd in rows:
        # Recompute APR windows
        apr_inception = _recompute_strategy_apr(con, strategy_id, equity_usd, ts, window_days=None)
        apr_30d = _recompute_strategy_apr(con, strategy_id, equity_usd, ts, window_days=30)
        apr_7d = _recompute_strategy_apr(con, strategy_id, equity_usd, ts, window_days=7)

        con.execute(
            """
            UPDATE vault_strategy_snapshots
            SET apr_since_inception = ?, apr_30d = ?, apr_7d = ?
            WHERE snapshot_id = ?
            """,
            (apr_inception, apr_30d, apr_7d, snapshot_id),
        )
        count += 1

    # Also recalc vault snapshots
    vault_rows = con.execute(
        "SELECT snapshot_id, ts, total_equity_usd FROM vault_snapshots WHERE ts >= ? ORDER BY ts ASC",
        (since_ms,),
    ).fetchall()

    for snapshot_id, ts, total_equity in vault_rows:
        vault_apr = _recompute_vault_apr(con, total_equity, ts, window_days=None)
        vault_apr_30d = _recompute_vault_apr(con, total_equity, ts, window_days=30)
        vault_apr_7d = _recompute_vault_apr(con, total_equity, ts, window_days=7)

        con.execute(
            "UPDATE vault_snapshots SET total_apr = ?, apr_30d = ?, apr_7d = ? WHERE snapshot_id = ?",
            (vault_apr, vault_apr_30d, vault_apr_7d, snapshot_id),
        )

    con.commit()
    log.info(f"Recalculated {count} strategy snapshots and {len(vault_rows)} vault snapshots from ts={since_ms}")
    return count


def _recompute_strategy_apr(
    con: sqlite3.Connection,
    strategy_id: str,
    current_equity: float,
    snapshot_ts: int,
    window_days: int | None,
) -> float:
    """Recompute APR for a strategy snapshot at a given timestamp."""
    if window_days is None:
        row = con.execute(
            "SELECT equity_usd, ts FROM vault_strategy_snapshots WHERE strategy_id = ? ORDER BY ts ASC LIMIT 1",
            (strategy_id,),
        ).fetchone()
    else:
        cutoff_ms = snapshot_ts - (window_days * 86400 * 1000)
        row = con.execute(
            "SELECT equity_usd, ts FROM vault_strategy_snapshots WHERE strategy_id = ? AND ts <= ? ORDER BY ts DESC LIMIT 1",
            (strategy_id, cutoff_ms),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (snapshot_ts - prior_ts) / 86400000.0

    cf_row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND strategy_id = ? AND ts >= ? AND ts <= ?",
        (strategy_id, prior_ts, snapshot_ts),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)


def _recompute_vault_apr(
    con: sqlite3.Connection,
    current_equity: float,
    snapshot_ts: int,
    window_days: int | None,
) -> float:
    """Recompute vault-level APR for a snapshot."""
    if window_days is None:
        row = con.execute("SELECT total_equity_usd, ts FROM vault_snapshots ORDER BY ts ASC LIMIT 1").fetchone()
    else:
        cutoff_ms = snapshot_ts - (window_days * 86400 * 1000)
        row = con.execute(
            "SELECT total_equity_usd, ts FROM vault_snapshots WHERE ts <= ? ORDER BY ts DESC LIMIT 1",
            (cutoff_ms,),
        ).fetchone()

    if not row:
        return 0.0

    prior_equity = float(row[0])
    prior_ts = int(row[1])
    period_days = (snapshot_ts - prior_ts) / 86400000.0

    cf_row = con.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM vault_cashflows WHERE cf_type IN ('DEPOSIT', 'WITHDRAW') AND ts >= ? AND ts <= ?",
        (prior_ts, snapshot_ts),
    ).fetchone()
    net_cashflows = float(cf_row[0]) if cf_row else 0.0

    return cashflow_adjusted_apr(current_equity, prior_equity, net_cashflows, period_days)
```

- [ ] **Step 4: Write recalc tests**

```python
# tests/test_vault_recalc.py
"""Tests for retroactive snapshot recalculation."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMA_PM = Path(__file__).parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = Path(__file__).parent.parent / "tracking" / "sql" / "schema_vault.sql"


def _setup_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())
    return con


def test_recalc_updates_apr_not_equity():
    """Recalc should change APR but leave equity unchanged."""
    from tracking.vault.recalc import recalc_snapshots

    con = _setup_db()
    now_ms = int(time.time() * 1000)
    day_ms = 86400000

    # Insert strategy
    con.execute(
        "INSERT INTO vault_strategies(strategy_id, name, type, status, wallets_json, target_weight_pct, created_at_ms, updated_at_ms) VALUES (?,?,?,?,?,?,?,?)",
        ("test", "Test", "DELTA_NEUTRAL", "ACTIVE", "[]", 100.0, now_ms, now_ms),
    )

    # Insert 2 daily snapshots
    ts_day1 = now_ms - 2 * day_ms
    ts_day2 = now_ms - day_ms
    con.execute(
        "INSERT INTO vault_strategy_snapshots(strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d) VALUES (?,?,?,?,?,?)",
        ("test", ts_day1, 10000.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        "INSERT INTO vault_strategy_snapshots(strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d) VALUES (?,?,?,?,?,?)",
        ("test", ts_day2, 10100.0, 5.0, 5.0, 5.0),
    )

    # Insert vault snapshots
    con.execute(
        "INSERT INTO vault_snapshots(ts, total_equity_usd, total_apr, apr_30d, apr_7d) VALUES (?,?,?,?,?)",
        (ts_day1, 10000.0, 0.0, 0.0, 0.0),
    )
    con.execute(
        "INSERT INTO vault_snapshots(ts, total_equity_usd, total_apr, apr_30d, apr_7d) VALUES (?,?,?,?,?)",
        (ts_day2, 10100.0, 5.0, 5.0, 5.0),
    )
    con.commit()

    # Now insert a backdated deposit that should change APR
    con.execute(
        "INSERT INTO vault_cashflows(ts, cf_type, amount, strategy_id, created_at_ms) VALUES (?,?,?,?,?)",
        (ts_day1 + 1000, "DEPOSIT", 50.0, "test", now_ms),
    )
    con.commit()

    # Recalc from day1
    count = recalc_snapshots(con, ts_day1)
    assert count == 2  # both snapshots recalculated

    # Equity should be unchanged
    row = con.execute("SELECT equity_usd FROM vault_strategy_snapshots WHERE ts = ?", (ts_day2,)).fetchone()
    assert row[0] == 10100.0

    # APR should have changed (deposit reduces organic change)
    row = con.execute("SELECT apr_since_inception FROM vault_strategy_snapshots WHERE ts = ?", (ts_day2,)).fetchone()
    assert row[0] != 5.0  # should be different after accounting for deposit
```

- [ ] **Step 5: Run all tests**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_snapshot.py tests/test_vault_recalc.py -v
```

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add tracking/vault/snapshot.py tracking/vault/recalc.py tests/test_vault_snapshot.py tests/test_vault_recalc.py
git commit -m "feat(vault): add snapshot pipeline and retroactive recalculation"
```

---

### Task 8: CLI Tool

**Files:**
- Create: `scripts/vault.py`
- Create: `scripts/vault_daily_snapshot.py`

- [ ] **Step 1: Implement vault.py CLI**

```python
#!/usr/bin/env python3
"""Vault Strategy Manager CLI.

Commands:
- sync-registry: load config/strategies.json and upsert into vault_strategies
- list: show managed strategies with latest equity
- cashflow: record deposit/withdrawal/transfer
- recalc: retroactive APR recalculation
- snapshot: run daily snapshot manually

Pattern follows scripts/pm.py.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"


def connect(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def cmd_sync_registry(con: sqlite3.Connection, registry_path: Path) -> int:
    from tracking.vault.registry import load_registry
    from tracking.vault.db_sync import sync_registry

    vault_name, strategies = load_registry(registry_path)
    count = sync_registry(con, vault_name, strategies)
    print(f"OK: synced {count} strategies from {registry_path}")
    return 0


def cmd_list(con: sqlite3.Connection, as_json: bool) -> int:
    from tracking.vault.db_sync import list_strategies

    rows = list_strategies(con)
    if as_json:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("(no strategies)")
        return 0
    for r in rows:
        equity = f"${r['equity_usd']:,.2f}" if r.get("equity_usd") else "no data"
        apr = f"{r['apr_since_inception']:.2f}%" if r.get("apr_since_inception") is not None else "n/a"
        print(f"{r['strategy_id']}: {r['name']} | {r['type']} | {r['status']} | {equity} | APR={apr} | target={r['target_weight_pct']}%")
    return 0


def cmd_cashflow(con: sqlite3.Connection, args) -> int:
    from tracking.vault.recalc import recalc_snapshots

    ts = int(args.ts) if args.ts else int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    if args.type == "TRANSFER":
        if not args.from_strategy or not args.to_strategy:
            print("ERROR: TRANSFER requires --from and --to")
            return 1
        con.execute(
            "INSERT INTO vault_cashflows(ts, cf_type, amount, from_strategy_id, to_strategy_id, description, created_at_ms) VALUES (?,?,?,?,?,?,?)",
            (ts, "TRANSFER", args.amount, args.from_strategy, args.to_strategy, args.description, now_ms),
        )
    else:
        if not args.strategy:
            print("ERROR: DEPOSIT/WITHDRAW requires --strategy")
            return 1
        signed = args.amount if args.type == "DEPOSIT" else -args.amount
        con.execute(
            "INSERT INTO vault_cashflows(ts, cf_type, amount, strategy_id, description, created_at_ms) VALUES (?,?,?,?,?,?)",
            (ts, args.type, signed, args.strategy, args.description, now_ms),
        )

    con.commit()
    print(f"OK: {args.type} of {args.amount} USDC recorded")

    # Check if backdated — auto-recalc
    latest_snap_ts = con.execute("SELECT MAX(ts) FROM vault_strategy_snapshots").fetchone()[0]
    if latest_snap_ts and ts < latest_snap_ts:
        count = recalc_snapshots(con, ts)
        print(f"  -> Recalculated {count} snapshots (backdated cashflow)")

    return 0


def cmd_recalc(con: sqlite3.Connection, args) -> int:
    from tracking.vault.recalc import recalc_snapshots

    if args.all:
        since_ms = 0
    elif args.since:
        dt = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        since_ms = int(dt.timestamp() * 1000)
    else:
        print("ERROR: provide --since DATE or --all")
        return 1

    count = recalc_snapshots(con, since_ms)
    print(f"OK: recalculated {count} snapshots")
    return 0


def cmd_snapshot(con: sqlite3.Connection) -> int:
    from tracking.vault.snapshot import run_daily_snapshot

    result = run_daily_snapshot(con)
    print(f"OK: snapshot complete")
    print(f"  Strategies: {result['strategies_processed']}")
    print(f"  Vault equity: ${result['vault_equity']:,.2f}")
    print(f"  Vault APR: {result['vault_apr']:.2f}%")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(prog="vault")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)

    sub = ap.add_subparsers(dest="cmd", required=True)

    sp_sync = sub.add_parser("sync-registry", help="Sync strategies.json to DB")
    sp_sync.add_argument("--registry", type=Path, default=ROOT / "config" / "strategies.json")

    sp_list = sub.add_parser("list", help="List strategies with latest data")
    sp_list.add_argument("--json", action="store_true")

    sp_cf = sub.add_parser("cashflow", help="Record a cashflow event")
    sp_cf.add_argument("--type", required=True, choices=["DEPOSIT", "WITHDRAW", "TRANSFER"])
    sp_cf.add_argument("--amount", required=True, type=float)
    sp_cf.add_argument("--strategy", help="Target strategy (for DEPOSIT/WITHDRAW)")
    sp_cf.add_argument("--from", dest="from_strategy", help="Source strategy (for TRANSFER)")
    sp_cf.add_argument("--to", dest="to_strategy", help="Destination strategy (for TRANSFER)")
    sp_cf.add_argument("--ts", help="Epoch ms (defaults to now)")
    sp_cf.add_argument("--description", default="")

    sp_recalc = sub.add_parser("recalc", help="Recalculate APR for snapshots")
    sp_recalc.add_argument("--since", help="YYYY-MM-DD date to recalc from")
    sp_recalc.add_argument("--all", action="store_true", help="Recalculate all snapshots")

    sub.add_parser("snapshot", help="Run daily snapshot now")

    args = ap.parse_args()
    con = connect(args.db)

    try:
        if args.cmd == "sync-registry":
            return cmd_sync_registry(con, args.registry)
        elif args.cmd == "list":
            return cmd_list(con, getattr(args, "json", False))
        elif args.cmd == "cashflow":
            return cmd_cashflow(con, args)
        elif args.cmd == "recalc":
            return cmd_recalc(con, args)
        elif args.cmd == "snapshot":
            return cmd_snapshot(con)
        else:
            print(f"Unknown command: {args.cmd}")
            return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement vault_daily_snapshot.py cron entry point**

```python
#!/usr/bin/env python3
"""Vault daily snapshot cron job.

Runs once daily (02:05 UTC / 09:05 ICT) via cron:
  5 2 * * * cd $WORKSPACE && source .arbit_env && .venv/bin/python scripts/vault_daily_snapshot.py

Pattern follows scripts/pipeline_hourly.py.
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

DEFAULT_DB = ROOT / "tracking" / "db" / "arbit_v3.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [vault_snapshot] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = ap.parse_args()

    log.info("Starting vault daily snapshot")
    t0 = time.time()

    con = sqlite3.connect(str(args.db))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys = ON")

    try:
        from tracking.vault.snapshot import run_daily_snapshot
        result = run_daily_snapshot(con)
        elapsed = time.time() - t0
        log.info(
            f"Done in {elapsed:.1f}s: "
            f"strategies={result['strategies_processed']}, "
            f"equity=${result['vault_equity']:,.2f}, "
            f"apr={result['vault_apr']:.2f}%"
        )
        return 0
    except Exception:
        log.exception("Vault snapshot failed")
        return 1
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Commit**

```bash
git add scripts/vault.py scripts/vault_daily_snapshot.py
git commit -m "feat(vault): add vault CLI and daily snapshot cron job"
```

---

### Task 9: API Endpoints

**Files:**
- Create: `api/models/vault_schemas.py`
- Create: `api/routers/vault.py`
- Modify: `api/main.py` (register vault router)

- [ ] **Step 1: Create Pydantic models**

```python
# api/models/vault_schemas.py
"""Pydantic models for vault API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StrategySummary(BaseModel):
    strategy_id: str
    name: str
    type: str
    status: str
    equity_usd: Optional[float] = None
    weight_pct: Optional[float] = Field(None, description="Actual weight = equity / total * 100")
    target_weight_pct: Optional[float] = None
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None


class VaultOverview(BaseModel):
    vault_name: str
    total_equity_usd: float
    total_apr: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    net_deposits_alltime: Optional[float] = None
    strategies: List[StrategySummary]
    as_of: Optional[str] = None


class StrategyDetail(BaseModel):
    strategy_id: str
    name: str
    type: str
    status: str
    target_weight_pct: Optional[float] = None
    equity_usd: Optional[float] = None
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    equity_breakdown: Optional[Dict[str, Any]] = None
    wallets: Optional[List[Dict[str, str]]] = None


class StrategySnapshot(BaseModel):
    ts: int
    equity_usd: float
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None


class VaultSnapshot(BaseModel):
    ts: int
    total_equity_usd: float
    total_apr: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    strategy_weights: Optional[Dict[str, float]] = None


class VaultCashflowRequest(BaseModel):
    cf_type: str = Field(..., description="DEPOSIT, WITHDRAW, or TRANSFER")
    amount: float = Field(..., gt=0, description="Always positive; sign derived from cf_type")
    strategy_id: Optional[str] = Field(None, description="Target for DEPOSIT/WITHDRAW")
    from_strategy_id: Optional[str] = Field(None, description="Source for TRANSFER")
    to_strategy_id: Optional[str] = Field(None, description="Destination for TRANSFER")
    ts: Optional[int] = Field(None, description="Epoch ms; defaults to now")
    currency: str = "USDC"
    description: str = ""


class VaultCashflowResponse(BaseModel):
    cashflow_id: int
    recalculated: bool = False
    recalc_snapshots_affected: int = 0
    message: str


class VaultCashflowItem(BaseModel):
    cashflow_id: int
    ts: int
    cf_type: str
    amount: float
    currency: str
    strategy_id: Optional[str] = None
    from_strategy_id: Optional[str] = None
    to_strategy_id: Optional[str] = None
    description: Optional[str] = None
```

- [ ] **Step 2: Create vault router**

```python
# api/routers/vault.py
"""Vault API endpoints.

GET  /api/vault/overview            — vault summary with all strategies
GET  /api/vault/strategies          — list strategies
GET  /api/vault/strategies/{id}     — strategy detail
GET  /api/vault/snapshots           — historical vault snapshots
GET  /api/vault/strategies/{id}/snapshots — historical strategy snapshots
GET  /api/vault/cashflows           — list cashflows
POST /api/vault/cashflows           — create cashflow (auto-recalc if backdated)
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_db, get_db_writable
from api.models.vault_schemas import (
    VaultOverview,
    StrategySummary,
    StrategyDetail,
    StrategySnapshot,
    VaultSnapshot,
    VaultCashflowRequest,
    VaultCashflowResponse,
    VaultCashflowItem,
)

router = APIRouter(prefix="/api/vault", tags=["vault"])


@router.get("/overview", response_model=VaultOverview)
def vault_overview(db: sqlite3.Connection = Depends(get_db)):
    """Vault-level overview: total equity, APR, strategy weights."""
    # Get latest vault snapshot
    snap = db.execute("SELECT * FROM vault_snapshots ORDER BY ts DESC LIMIT 1").fetchone()

    # Get strategies with latest snapshots
    rows = db.execute(
        """
        SELECT s.strategy_id, s.name, s.type, s.status, s.target_weight_pct,
               ss.equity_usd, ss.apr_since_inception, ss.apr_30d, ss.apr_7d
        FROM vault_strategies s
        LEFT JOIN vault_strategy_snapshots ss ON ss.strategy_id = s.strategy_id
            AND ss.ts = (SELECT MAX(ts) FROM vault_strategy_snapshots WHERE strategy_id = s.strategy_id)
        ORDER BY s.target_weight_pct DESC
        """
    ).fetchall()

    total_equity = float(snap["total_equity_usd"]) if snap else 0.0

    strategies = []
    for r in rows:
        equity = float(r["equity_usd"]) if r["equity_usd"] else None
        weight = (equity / total_equity * 100) if equity and total_equity > 0 else None
        strategies.append(StrategySummary(
            strategy_id=r["strategy_id"],
            name=r["name"],
            type=r["type"],
            status=r["status"],
            equity_usd=equity,
            weight_pct=round(weight, 2) if weight else None,
            target_weight_pct=r["target_weight_pct"],
            apr_since_inception=r["apr_since_inception"],
            apr_30d=r["apr_30d"],
            apr_7d=r["apr_7d"],
        ))

    as_of = datetime.fromtimestamp(snap["ts"] / 1000, tz=timezone.utc).isoformat() if snap else None

    # Get vault name from first strategy's config or default
    vault_name_row = db.execute("SELECT config_json FROM vault_strategies LIMIT 1").fetchone()
    vault_name = "OpenClaw Vault"

    return VaultOverview(
        vault_name=vault_name,
        total_equity_usd=total_equity,
        total_apr=snap["total_apr"] if snap else None,
        apr_30d=snap["apr_30d"] if snap else None,
        apr_7d=snap["apr_7d"] if snap else None,
        net_deposits_alltime=snap["net_deposits_alltime"] if snap else None,
        strategies=strategies,
        as_of=as_of,
    )


@router.get("/strategies/{strategy_id}", response_model=StrategyDetail)
def strategy_detail(strategy_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Strategy detail with equity breakdown."""
    row = db.execute(
        "SELECT * FROM vault_strategies WHERE strategy_id = ?", (strategy_id,)
    ).fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Strategy '{strategy_id}' not found")

    snap = db.execute(
        "SELECT * FROM vault_strategy_snapshots WHERE strategy_id = ? ORDER BY ts DESC LIMIT 1",
        (strategy_id,),
    ).fetchone()

    return StrategyDetail(
        strategy_id=row["strategy_id"],
        name=row["name"],
        type=row["type"],
        status=row["status"],
        target_weight_pct=row["target_weight_pct"],
        equity_usd=snap["equity_usd"] if snap else None,
        apr_since_inception=snap["apr_since_inception"] if snap else None,
        apr_30d=snap["apr_30d"] if snap else None,
        apr_7d=snap["apr_7d"] if snap else None,
        equity_breakdown=json.loads(snap["equity_breakdown_json"]) if snap and snap["equity_breakdown_json"] else None,
        wallets=json.loads(row["wallets_json"]) if row["wallets_json"] else None,
    )


@router.get("/snapshots", response_model=List[VaultSnapshot])
def vault_snapshots(
    limit: int = Query(30, ge=1, le=365),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Historical vault snapshots."""
    sql = "SELECT * FROM vault_snapshots WHERE 1=1"
    params = []
    if from_ts:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        VaultSnapshot(
            ts=r["ts"],
            total_equity_usd=r["total_equity_usd"],
            total_apr=r["total_apr"],
            apr_30d=r["apr_30d"],
            apr_7d=r["apr_7d"],
            strategy_weights=json.loads(r["strategy_weights_json"]) if r["strategy_weights_json"] else None,
        )
        for r in rows
    ]


@router.get("/strategies/{strategy_id}/snapshots", response_model=List[StrategySnapshot])
def strategy_snapshots(
    strategy_id: str,
    limit: int = Query(30, ge=1, le=365),
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Historical strategy snapshots."""
    sql = "SELECT * FROM vault_strategy_snapshots WHERE strategy_id = ?"
    params: list = [strategy_id]
    if from_ts:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        StrategySnapshot(
            ts=r["ts"],
            equity_usd=r["equity_usd"],
            apr_since_inception=r["apr_since_inception"],
            apr_30d=r["apr_30d"],
            apr_7d=r["apr_7d"],
        )
        for r in rows
    ]


@router.get("/cashflows", response_model=List[VaultCashflowItem])
def list_cashflows(
    strategy_id: Optional[str] = None,
    cf_type: Optional[str] = None,
    from_ts: Optional[int] = Query(None, alias="from"),
    to_ts: Optional[int] = Query(None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    db: sqlite3.Connection = Depends(get_db),
):
    """List vault cashflows with filters."""
    sql = "SELECT * FROM vault_cashflows WHERE 1=1"
    params: list = []
    if strategy_id:
        sql += " AND (strategy_id = ? OR from_strategy_id = ? OR to_strategy_id = ?)"
        params.extend([strategy_id, strategy_id, strategy_id])
    if cf_type:
        sql += " AND cf_type = ?"
        params.append(cf_type)
    if from_ts:
        sql += " AND ts >= ?"
        params.append(from_ts)
    if to_ts:
        sql += " AND ts <= ?"
        params.append(to_ts)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)

    rows = db.execute(sql, params).fetchall()
    return [
        VaultCashflowItem(
            cashflow_id=r["cashflow_id"],
            ts=r["ts"],
            cf_type=r["cf_type"],
            amount=r["amount"],
            currency=r["currency"],
            strategy_id=r["strategy_id"],
            from_strategy_id=r["from_strategy_id"],
            to_strategy_id=r["to_strategy_id"],
            description=r["description"],
        )
        for r in rows
    ]


@router.post("/cashflows", response_model=VaultCashflowResponse, status_code=201)
def create_cashflow(
    body: VaultCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Create a vault cashflow. Auto-recalculates if backdated."""
    ts = body.ts or int(time.time() * 1000)
    now_ms = int(time.time() * 1000)

    if body.cf_type == "TRANSFER":
        cursor = db.execute(
            "INSERT INTO vault_cashflows(ts, cf_type, amount, from_strategy_id, to_strategy_id, currency, description, created_at_ms) VALUES (?,?,?,?,?,?,?,?)",
            (ts, "TRANSFER", body.amount, body.from_strategy_id, body.to_strategy_id, body.currency, body.description, now_ms),
        )
    else:
        signed = body.amount if body.cf_type == "DEPOSIT" else -body.amount
        cursor = db.execute(
            "INSERT INTO vault_cashflows(ts, cf_type, amount, strategy_id, currency, description, created_at_ms) VALUES (?,?,?,?,?,?,?)",
            (ts, body.cf_type, signed, body.strategy_id, body.currency, body.description, now_ms),
        )

    db.commit()
    cf_id = cursor.lastrowid

    # Auto-recalc if backdated
    recalculated = False
    recalc_count = 0
    latest_snap_ts = db.execute("SELECT MAX(ts) FROM vault_strategy_snapshots").fetchone()[0]
    if latest_snap_ts and ts < latest_snap_ts:
        from tracking.vault.recalc import recalc_snapshots
        recalc_count = recalc_snapshots(db, ts)
        recalculated = True

    return VaultCashflowResponse(
        cashflow_id=cf_id,
        recalculated=recalculated,
        recalc_snapshots_affected=recalc_count,
        message=f"{body.cf_type} of {body.amount} {body.currency} recorded" + (f" ({recalc_count} snapshots recalculated)" if recalculated else ""),
    )
```

- [ ] **Step 3: Register vault router in api/main.py**

Find the router registration section in `api/main.py` and add:

```python
from api.routers.vault import router as vault_router

# In the router registration section, add:
app.include_router(vault_router)
```

- [ ] **Step 4: Commit**

```bash
git add api/models/vault_schemas.py api/routers/vault.py api/main.py
git commit -m "feat(vault): add vault API endpoints (overview, strategies, cashflows, snapshots)"
```

---

### Task 10: Runbook

**Files:**
- Create: `docs/runbook-vault-operations.md`

- [ ] **Step 1: Write runbook**

```markdown
# Vault Operations Runbook

## Overview

The vault system tracks equity and APR across multiple strategies (Lending, Delta Neutral, Depeg).
Data flows: `config/strategies.json` → `vault_strategies` (DB) → daily snapshots → API → dashboard.

## Common Operations

### Add a New Strategy

1. Edit `config/strategies.json` — add new strategy object
2. Sync to DB:
   ```bash
   source .arbit_env && .venv/bin/python scripts/vault.py sync-registry
   ```
3. Verify:
   ```bash
   .venv/bin/python scripts/vault.py list
   ```
4. If a new wallet label is needed, add it to `HYPERLIQUID_ACCOUNTS_JSON` in `.arbit_env`

### Record a Deposit

```bash
source .arbit_env && .venv/bin/python scripts/vault.py cashflow \
  --type DEPOSIT --amount 5000 --strategy lending \
  --description "Bridge from Arbitrum"
```

### Record a Withdrawal

```bash
source .arbit_env && .venv/bin/python scripts/vault.py cashflow \
  --type WITHDRAW --amount 1000 --strategy delta_neutral \
  --description "Profit withdrawal"
```

### Transfer Between Strategies

```bash
source .arbit_env && .venv/bin/python scripts/vault.py cashflow \
  --type TRANSFER --amount 2000 \
  --from lending --to delta_neutral \
  --description "Rebalance: lending -> DN"
```

### Backdated Cashflow (Late Entry)

If you forgot to log a cashflow before the daily snapshot ran, add it with `--ts`:

```bash
# Convert your time to epoch ms first
# Example: 2026-03-31 01:30 UTC = 1743383400000

source .arbit_env && .venv/bin/python scripts/vault.py cashflow \
  --type DEPOSIT --amount 5000 --strategy lending \
  --ts 1743383400000 \
  --description "Bridge from Arbitrum (logged late)"
```

The system auto-detects this is backdated and recalculates APR for all affected snapshots.

### Manual Recalculation

If you need to force-recalculate APR (e.g., after fixing a cashflow entry):

```bash
# Recalc from a specific date
source .arbit_env && .venv/bin/python scripts/vault.py recalc --since 2026-03-30

# Nuclear option: recalculate everything
source .arbit_env && .venv/bin/python scripts/vault.py recalc --all
```

**What recalc does:**
- Reads all vault_strategy_snapshots and vault_snapshots from the given date forward
- Re-queries vault_cashflows to get corrected net cashflows for each period
- Recomputes APR fields (since_inception, 30d, 7d)
- Equity values are NOT changed — only APR is recalculated

### Run Daily Snapshot Manually

```bash
source .arbit_env && .venv/bin/python scripts/vault.py snapshot
```

Or via the cron entry point:
```bash
source .arbit_env && .venv/bin/python scripts/vault_daily_snapshot.py
```

### View Current State

```bash
# List all strategies with latest equity and APR
source .arbit_env && .venv/bin/python scripts/vault.py list

# JSON output for scripting
source .arbit_env && .venv/bin/python scripts/vault.py list --json
```

## Cron Setup

Add to crontab on the VPS:

```cron
# Daily vault snapshot (02:05 UTC = 09:05 ICT)
5 2 * * * cd /path/to/workspace && source .arbit_env && .venv/bin/python scripts/vault_daily_snapshot.py >> logs/vault_daily.log 2>&1
```

## Troubleshooting

### "No provider for strategy type X"
A new strategy type was added to strategies.json but no EquityProvider is registered. Implement the provider in `tracking/vault/providers/` and register it in `tracking/vault/providers/__init__.py`.

### "HARMONIX_NAV_DB_URL not set"
The lending provider can't connect to the harmonix-nav-platform database. Set the env var in `.arbit_env`.

### APR looks wrong after a deposit/withdrawal
Run recalc: `vault.py recalc --since YYYY-MM-DD`

### Snapshot shows 0 equity for a strategy
Check the provider is working: `vault.py snapshot` with verbose logging. Common causes:
- Wallet address not in HYPERLIQUID_ACCOUNTS_JSON
- No pm_account_snapshots data (for DN/Depeg — ensure pull_positions_v3.py has run)
- Postgres connection failed (for Lending)
```

- [ ] **Step 2: Commit**

```bash
git add docs/runbook-vault-operations.md
git commit -m "docs: add vault operations runbook with recalc instructions"
```

---

### Task 11: Frontend — Vault Dashboard Components

**Note:** This task covers the backend-connected frontend pages. The exact component styling follows existing patterns in `frontend/components/`. Implement after verifying the API endpoints work with real data.

**Files:**
- Create: `frontend/app/vault/page.tsx`
- Create: `frontend/app/vault/cashflows/page.tsx`
- Create: `frontend/app/vault/strategies/[id]/page.tsx`
- Create: `frontend/components/VaultSummary.tsx`
- Create: `frontend/components/StrategyTable.tsx`
- Create: `frontend/components/CashflowForm.tsx`
- Create: `frontend/components/AllocationBar.tsx`
- Modify: `frontend/lib/api.ts` (add vault API functions)
- Modify: `frontend/lib/types.ts` (add vault types)
- Modify: `frontend/app/page.tsx` (add vault summary at top)

This task should be implemented with the `frontend-design` skill for proper component design and styling. The key data contracts are:

- `GET /api/vault/overview` → VaultSummary + StrategyTable + AllocationBar
- `GET /api/vault/cashflows` → Cashflow history table
- `POST /api/vault/cashflows` → CashflowForm submission
- `GET /api/vault/snapshots` → Equity/APR charts
- `GET /api/vault/strategies/{id}` → Strategy detail page

- [ ] **Step 1: Add vault types to frontend**

Add to `frontend/lib/types.ts`:

```typescript
// Vault types
export interface StrategySummary {
  strategy_id: string;
  name: string;
  type: string;
  status: string;
  equity_usd: number | null;
  weight_pct: number | null;
  target_weight_pct: number | null;
  apr_since_inception: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
}

export interface VaultOverview {
  vault_name: string;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  net_deposits_alltime: number | null;
  strategies: StrategySummary[];
  as_of: string | null;
}

export interface VaultCashflow {
  cashflow_id: number;
  ts: number;
  cf_type: string;
  amount: number;
  currency: string;
  strategy_id: string | null;
  from_strategy_id: string | null;
  to_strategy_id: string | null;
  description: string | null;
}

export interface VaultSnapshot {
  ts: number;
  total_equity_usd: number;
  total_apr: number | null;
  apr_30d: number | null;
  apr_7d: number | null;
  strategy_weights: Record<string, number> | null;
}
```

- [ ] **Step 2: Add vault API functions to frontend**

Add to `frontend/lib/api.ts`:

```typescript
export async function fetchVaultOverview(): Promise<VaultOverview> {
  return apiFetch('/api/vault/overview');
}

export async function fetchVaultSnapshots(limit = 30): Promise<VaultSnapshot[]> {
  return apiFetch(`/api/vault/snapshots?limit=${limit}`);
}

export async function fetchVaultCashflows(limit = 50): Promise<VaultCashflow[]> {
  return apiFetch(`/api/vault/cashflows?limit=${limit}`);
}

export async function createVaultCashflow(data: {
  cf_type: string;
  amount: number;
  strategy_id?: string;
  from_strategy_id?: string;
  to_strategy_id?: string;
  ts?: number;
  description?: string;
}): Promise<{ cashflow_id: number; recalculated: boolean; message: string }> {
  return apiFetch('/api/vault/cashflows', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}
```

- [ ] **Step 3: Implement frontend pages and components**

Use the `frontend-design` skill for this step. The pages should follow the existing dashboard patterns (`frontend/app/page.tsx`, `frontend/components/EquityCard.tsx`, etc.).

Key pages:
1. **`/vault`** — Vault overview with equity chart, strategy table, allocation bar
2. **`/vault/cashflows`** — Cashflow form + history table
3. **`/vault/strategies/[id]`** — Strategy detail page
4. **Updated `/`** — Add VaultSummary card at top of existing dashboard

- [ ] **Step 4: Commit**

```bash
git add frontend/
git commit -m "feat(vault): add vault dashboard pages (overview, cashflows, strategy detail)"
```

---

### Task 12: Integration Test & Manual Verification

**Files:**
- Create: `tests/test_vault_api.py`

- [ ] **Step 1: Write API integration tests**

```python
# tests/test_vault_api.py
"""Integration tests for vault API endpoints."""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

SCHEMA_PM = Path(__file__).parent.parent / "tracking" / "sql" / "schema_pm_v3.sql"
SCHEMA_VAULT = Path(__file__).parent.parent / "tracking" / "sql" / "schema_vault.sql"

TEST_API_KEY = "test-key-123"


def _setup_test_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "test.db"
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA_PM.read_text())
    con.executescript(SCHEMA_VAULT.read_text())

    now_ms = int(time.time() * 1000)

    # Insert test strategies
    con.execute(
        "INSERT INTO vault_strategies VALUES (?,?,?,?,?,?,?,?,?)",
        ("lending", "Lending", "LENDING", "ACTIVE", '[{"wallet_label":"lending"}]', 50.0, None, now_ms, now_ms),
    )
    con.execute(
        "INSERT INTO vault_strategies VALUES (?,?,?,?,?,?,?,?,?)",
        ("delta_neutral", "DN", "DELTA_NEUTRAL", "ACTIVE", '[{"wallet_label":"alt"}]', 45.0, None, now_ms, now_ms),
    )

    # Insert test snapshots
    con.execute(
        "INSERT INTO vault_strategy_snapshots(strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d) VALUES (?,?,?,?,?,?)",
        ("lending", now_ms, 50000.0, 4.0, 3.8, 4.2),
    )
    con.execute(
        "INSERT INTO vault_strategy_snapshots(strategy_id, ts, equity_usd, apr_since_inception, apr_30d, apr_7d) VALUES (?,?,?,?,?,?)",
        ("delta_neutral", now_ms, 45000.0, 18.0, 15.0, 20.0),
    )

    # Insert vault snapshot
    con.execute(
        "INSERT INTO vault_snapshots(ts, total_equity_usd, strategy_weights_json, total_apr, apr_30d, apr_7d, net_deposits_alltime) VALUES (?,?,?,?,?,?,?)",
        (now_ms, 95000.0, '{"lending":52.6,"delta_neutral":47.4}', 10.5, 9.0, 11.5, 80000.0),
    )

    con.commit()
    con.close()
    return db_path


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = _setup_test_db(tmp_path)
    monkeypatch.setenv("ARBIT_DB_PATH", str(db_path))
    monkeypatch.setenv("API_KEY", TEST_API_KEY)

    from api.main import app
    return TestClient(app)


def _headers():
    return {"X-API-Key": TEST_API_KEY}


def test_vault_overview(client):
    resp = client.get("/api/vault/overview", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_equity_usd"] == 95000.0
    assert len(data["strategies"]) == 2
    assert data["strategies"][0]["equity_usd"] is not None


def test_strategy_detail(client):
    resp = client.get("/api/vault/strategies/lending", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert data["strategy_id"] == "lending"
    assert data["equity_usd"] == 50000.0


def test_strategy_not_found(client):
    resp = client.get("/api/vault/strategies/nonexistent", headers=_headers())
    assert resp.status_code == 404


def test_create_cashflow(client):
    resp = client.post(
        "/api/vault/cashflows",
        headers=_headers(),
        json={"cf_type": "DEPOSIT", "amount": 5000.0, "strategy_id": "lending", "description": "test deposit"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["cashflow_id"] > 0
    assert "DEPOSIT" in data["message"]


def test_list_cashflows(client):
    # Create one first
    client.post(
        "/api/vault/cashflows",
        headers=_headers(),
        json={"cf_type": "DEPOSIT", "amount": 1000.0, "strategy_id": "lending"},
    )
    resp = client.get("/api/vault/cashflows", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1


def test_vault_snapshots(client):
    resp = client.get("/api/vault/snapshots?limit=10", headers=_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert data[0]["total_equity_usd"] == 95000.0
```

- [ ] **Step 2: Run all tests**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_vault_apr.py tests/test_vault_registry.py tests/test_vault_snapshot.py tests/test_vault_recalc.py tests/test_vault_api.py -v
```

Expected: all tests PASS

- [ ] **Step 3: Manual verification against spreadsheet**

```bash
# 1. Sync registry
source .arbit_env && .venv/bin/python scripts/vault.py sync-registry

# 2. List strategies
.venv/bin/python scripts/vault.py list

# 3. Run first snapshot
.venv/bin/python scripts/vault.py snapshot

# 4. Check API
curl -H "X-API-Key: $API_KEY" http://localhost:8000/api/vault/overview | python -m json.tool
```

Compare equity values with spreadsheet data for the same date.

- [ ] **Step 4: Commit**

```bash
git add tests/test_vault_api.py
git commit -m "test(vault): add API integration tests and manual verification"
```

---

## Summary

| Task | Description | New Files | Tests |
|------|-------------|-----------|-------|
| 1 | Database schema | schema_vault.sql | — |
| 2 | Config file | strategies.json | — |
| 3 | Registry loader | registry.py | test_vault_registry.py |
| 4 | DB sync | db_sync.py | — |
| 5 | APR calculator | apr.py | test_vault_apr.py |
| 6 | Equity providers | providers/*.py | — |
| 7 | Snapshot + recalc | snapshot.py, recalc.py | test_vault_snapshot.py, test_vault_recalc.py |
| 8 | CLI tool | vault.py, vault_daily_snapshot.py | — |
| 9 | API endpoints | vault.py (router), vault_schemas.py | — |
| 10 | Runbook | runbook-vault-operations.md | — |
| 11 | Frontend | vault pages + components | — |
| 12 | Integration tests | — | test_vault_api.py |
