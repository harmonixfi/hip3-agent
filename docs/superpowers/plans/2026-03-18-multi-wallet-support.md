# Multi-Wallet Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable tracking positions across multiple wallets per venue in a single database, with backward-compatible fallback to single-wallet mode.

**Architecture:** Add `wallet_label` to registry/config layer, `account_id` to DB leg tables, credential override to all connectors, and a partition-by-wallet-then-match loop in both the puller and cashflows ingest. A shared `resolve_venue_accounts()` helper reads `{VENUE}_ACCOUNTS_JSON` env vars with legacy fallback.

**Tech Stack:** Python 3.9, SQLite3, dataclasses, unittest

**Spec:** `docs/superpowers/specs/2026-03-18-multi-wallet-support-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `tracking/position_manager/accounts.py` | **Create** | Shared `resolve_venue_accounts()` helper |
| `tracking/position_manager/registry.py` | Modify | Add `wallet_label` to `LegConfig`, update `parse_position()` |
| `tracking/position_manager/db_sync.py` | Modify | Migration helper, `upsert_leg()` writes `account_id`+`wallet_label`, `list_positions()` reads `account_id` |
| `tracking/position_manager/puller.py` | Modify | Multi-wallet loop in `run_pull()`, update `load_positions_from_db/registry()`, `write_leg_snapshots()`, `pull_venue_positions()` |
| `tracking/position_manager/cashflows.py` | Modify | `load_managed_leg_index()` key includes `account_id` |
| `tracking/connectors/private_base.py` | No change | Base class unchanged — children handle overrides directly |
| `tracking/connectors/hyperliquid_private.py` | Modify | Accept `address` override |
| `tracking/connectors/paradex_private.py` | Modify | Accept credential overrides |
| `tracking/connectors/ethereal_private.py` | Modify | Accept `address` override |
| `tracking/connectors/hyena_private.py` | Modify | Accept `address` override |
| `tracking/connectors/lighter_private.py` | Modify | Accept `address` override |
| `tracking/connectors/okx_private.py` | Modify | Accept credential overrides |
| `tracking/sql/schema_pm_v3.sql` | Modify | Add `account_id` columns (reference) |
| `scripts/pm_cashflows.py` | Modify | Multi-wallet ingest loop |
| `scripts/pm_healthcheck.py` | Modify | Multi-wallet mismatch checks |
| `scripts/test_multi_wallet.py` | **Create** | Integration tests |

---

### Task 1: Shared Account Resolution Helper

**Files:**
- Create: `tracking/position_manager/accounts.py`
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for `resolve_venue_accounts()`**

Create test file `scripts/test_multi_wallet.py`:

```python
"""Tests for multi-wallet support."""

import json
import os
import unittest


class TestResolveVenueAccounts(unittest.TestCase):
    """Test tracking.position_manager.accounts.resolve_venue_accounts()."""

    def setUp(self):
        # Clear relevant env vars before each test
        for key in list(os.environ):
            if key.endswith("_ACCOUNTS_JSON"):
                del os.environ[key]
        for key in [
            "HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS",
            "PARADEX_ACCOUNT_ADDRESS", "HYENA_ADDRESS",
            "LIGHTER_L1_ADDRESS",
            "OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE",
        ]:
            os.environ.pop(key, None)

    def test_accounts_json_present(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ACCOUNTS_JSON"] = json.dumps({"main": "0xabc", "alt": "0xdef"})
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xabc", "alt": "0xdef"})

    def test_legacy_fallback_hyperliquid(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ADDRESS"] = "0xlegacy"
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xlegacy"})

    def test_legacy_fallback_hyperliquid_ethereal(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["ETHEREAL_ACCOUNT_ADDRESS"] = "0xeth_fallback"
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xeth_fallback"})

    def test_legacy_fallback_paradex(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["PARADEX_ACCOUNT_ADDRESS"] = "0xpdx"
        result = resolve_venue_accounts("paradex")
        self.assertEqual(result, {"main": "0xpdx"})

    def test_no_config_returns_empty(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {})

    def test_accounts_json_overrides_legacy(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYPERLIQUID_ADDRESS"] = "0xold"
        os.environ["HYPERLIQUID_ACCOUNTS_JSON"] = json.dumps({"main": "0xnew"})
        result = resolve_venue_accounts("hyperliquid")
        self.assertEqual(result, {"main": "0xnew"})

    def test_legacy_fallback_hyena(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["HYENA_ADDRESS"] = "0xhyena"
        result = resolve_venue_accounts("hyena")
        self.assertEqual(result, {"main": "0xhyena"})

    def test_legacy_fallback_lighter(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["LIGHTER_L1_ADDRESS"] = "0xlighter"
        result = resolve_venue_accounts("lighter")
        self.assertEqual(result, {"main": "0xlighter"})

    def test_legacy_fallback_okx(self):
        from tracking.position_manager.accounts import resolve_venue_accounts
        os.environ["OKX_API_KEY"] = "key123"
        result = resolve_venue_accounts("okx")
        self.assertEqual(result, {"main": "key123"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tracking.position_manager.accounts'`

- [ ] **Step 3: Implement `resolve_venue_accounts()`**

Create `tracking/position_manager/accounts.py`:

```python
"""Multi-wallet account resolution.

Resolves venue accounts from environment variables.
Supports {VENUE}_ACCOUNTS_JSON (multi-wallet) with legacy single-var fallback.
"""

from __future__ import annotations

import json
import os
from typing import Dict


# Legacy env var mappings: venue -> list of (env_var_name,) to try in order
_LEGACY_ENV = {
    "hyperliquid": ["HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "paradex": ["PARADEX_ACCOUNT_ADDRESS"],
    "ethereal": ["ETHEREAL_ACCOUNT_ADDRESS", "ETHEREAL_SENDER"],
    "hyena": ["HYENA_ADDRESS"],
    "lighter": ["LIGHTER_L1_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "okx": ["OKX_API_KEY"],
}


def resolve_venue_accounts(venue: str) -> Dict[str, str]:
    """Resolve wallet accounts for a venue.

    Priority:
    1. {VENUE}_ACCOUNTS_JSON env var (JSON object: label -> address)
    2. Legacy single env var with label "main"

    Returns:
        Dict mapping wallet_label -> address/credential.
        Empty dict if no config found.
    """
    venue_upper = venue.upper()
    json_var = f"{venue_upper}_ACCOUNTS_JSON"
    raw = os.environ.get(json_var, "").strip()
    if raw:
        try:
            accounts = json.loads(raw)
            if isinstance(accounts, dict) and accounts:
                return {str(k): str(v) for k, v in accounts.items()}
        except (json.JSONDecodeError, TypeError):
            pass

    # Legacy fallback
    for env_key in _LEGACY_ENV.get(venue, []):
        val = os.environ.get(env_key, "").strip()
        if val:
            return {"main": val}

    return {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestResolveVenueAccounts -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracking/position_manager/accounts.py scripts/test_multi_wallet.py
git commit -m "feat: add shared account resolution helper for multi-wallet support"
```

---

### Task 2: Registry — Add `wallet_label` to `LegConfig`

**Files:**
- Modify: `tracking/position_manager/registry.py:22-58` (LegConfig), `tracking/position_manager/registry.py:170-183` (parse_position)
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for registry wallet_label**

Append to `scripts/test_multi_wallet.py`:

```python
class TestRegistryWalletLabel(unittest.TestCase):
    """Test wallet_label field on LegConfig."""

    def test_leg_config_default_wallet_label(self):
        from tracking.position_manager.registry import LegConfig
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0)
        self.assertIsNone(leg.wallet_label)

    def test_leg_config_with_wallet_label(self):
        from tracking.position_manager.registry import LegConfig
        leg = LegConfig(leg_id="l1", venue="hyperliquid", inst_id="BTC", side="LONG", qty=1.0, wallet_label="alt")
        self.assertEqual(leg.wallet_label, "alt")

    def test_parse_position_reads_wallet_label(self):
        from tracking.position_manager.registry import parse_position
        data = {
            "position_id": "p1", "strategy_type": "SPOT_PERP",
            "base": "BTC", "status": "OPEN",
            "legs": [{
                "leg_id": "l1", "venue": "hyperliquid",
                "inst_id": "BTC", "side": "LONG", "qty": 1.0,
                "wallet_label": "alt",
            }],
        }
        pos = parse_position(data)
        self.assertEqual(pos.legs[0].wallet_label, "alt")

    def test_parse_position_no_wallet_label(self):
        from tracking.position_manager.registry import parse_position
        data = {
            "position_id": "p1", "strategy_type": "SPOT_PERP",
            "base": "BTC", "status": "OPEN",
            "legs": [{
                "leg_id": "l1", "venue": "hyperliquid",
                "inst_id": "BTC", "side": "LONG", "qty": 1.0,
            }],
        }
        pos = parse_position(data)
        self.assertIsNone(pos.legs[0].wallet_label)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestRegistryWalletLabel -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'wallet_label'`

- [ ] **Step 3: Add `wallet_label` to `LegConfig` and `parse_position()`**

In `tracking/position_manager/registry.py`:

Add field to `LegConfig` dataclass (after `collateral` field, line 32):
```python
    wallet_label: Optional[str] = None
```

In `parse_position()` (line 181, after `collateral=leg_data.get("collateral")`):
```python
            wallet_label=leg_data.get("wallet_label"),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestRegistryWalletLabel -v`
Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracking/position_manager/registry.py scripts/test_multi_wallet.py
git commit -m "feat: add wallet_label field to LegConfig and parse_position"
```

---

### Task 3: DB Schema Migration Helper

**Files:**
- Modify: `tracking/position_manager/db_sync.py:1-22`
- Modify: `tracking/sql/schema_pm_v3.sql`
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for migration helper**

Append to `scripts/test_multi_wallet.py`:

```python
import sqlite3
import tempfile
from pathlib import Path


class TestMigrationHelper(unittest.TestCase):
    """Test ensure_multi_wallet_columns() migration."""

    def _create_db(self):
        """Create an in-memory DB with original schema (no account_id on pm_legs)."""
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        con.execute("""
            CREATE TABLE pm_positions (
                position_id TEXT PRIMARY KEY,
                venue TEXT NOT NULL, strategy TEXT, status TEXT,
                created_at_ms INTEGER, updated_at_ms INTEGER,
                closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT
            )
        """)
        con.execute("""
            CREATE TABLE pm_legs (
                leg_id TEXT PRIMARY KEY,
                position_id TEXT REFERENCES pm_positions(position_id),
                venue TEXT, inst_id TEXT, side TEXT, size REAL,
                entry_price REAL, current_price REAL,
                unrealized_pnl REAL, realized_pnl REAL,
                status TEXT, opened_at_ms INTEGER, closed_at_ms INTEGER,
                raw_json TEXT, meta_json TEXT
            )
        """)
        con.execute("""
            CREATE TABLE pm_leg_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                leg_id TEXT REFERENCES pm_legs(leg_id),
                position_id TEXT REFERENCES pm_positions(position_id),
                venue TEXT, inst_id TEXT, ts INTEGER, side TEXT,
                size REAL, entry_price REAL, current_price REAL,
                unrealized_pnl REAL, realized_pnl REAL,
                raw_json TEXT, meta_json TEXT
            )
        """)
        return con

    def test_migration_adds_columns(self):
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        con = self._create_db()
        ensure_multi_wallet_columns(con)
        # Verify columns exist by inserting with account_id
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, '0xabc')
        """)
        con.execute("""
            INSERT INTO pm_leg_snapshots(leg_id, position_id, venue, inst_id, ts, side, size, account_id)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 1000, 'LONG', 1.0, '0xabc')
        """)
        con.commit()

    def test_migration_idempotent(self):
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        con = self._create_db()
        ensure_multi_wallet_columns(con)
        ensure_multi_wallet_columns(con)  # Should not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestMigrationHelper -v`
Expected: FAIL — `ImportError: cannot import name 'ensure_multi_wallet_columns'`

- [ ] **Step 3: Implement `ensure_multi_wallet_columns()` in `db_sync.py`**

Add to `tracking/position_manager/db_sync.py` after the `connect()` function (after line 21):

```python
def ensure_multi_wallet_columns(con: sqlite3.Connection) -> None:
    """Add account_id columns to pm_legs and pm_leg_snapshots if missing."""
    for table in ("pm_legs", "pm_leg_snapshots"):
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN account_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
    try:
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_account "
            "ON pm_leg_snapshots(account_id, leg_id)"
        )
    except sqlite3.OperationalError:
        pass
    con.commit()
```

Also update `tracking/sql/schema_pm_v3.sql` — add `account_id TEXT` column to `pm_legs` and `pm_leg_snapshots` table definitions (for new installs). In `pm_legs`, add after the `meta_json TEXT` line:
```sql
  account_id TEXT,
```

In `pm_leg_snapshots`, add after the `meta_json TEXT` line:
```sql
  account_id TEXT,
```

Add index after `pm_leg_snapshots` table:
```sql
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_account ON pm_leg_snapshots(account_id, leg_id);
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestMigrationHelper -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tracking/position_manager/db_sync.py tracking/sql/schema_pm_v3.sql scripts/test_multi_wallet.py
git commit -m "feat: add DB migration helper for account_id columns"
```

---

### Task 4: DB Sync — `upsert_leg()` and `list_positions()` Updates

**Files:**
- Modify: `tracking/position_manager/db_sync.py:111-149` (upsert_leg), `tracking/position_manager/db_sync.py:152-219` (list_positions), `tracking/position_manager/db_sync.py:24-66` (sync_registry)
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for upsert_leg with wallet_label and list_positions with account_id**

Append to `scripts/test_multi_wallet.py`:

```python
class TestDbSyncWalletLabel(unittest.TestCase):
    """Test upsert_leg stores wallet_label in meta_json and list_positions returns account_id."""

    def _create_db(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        # Use schema with account_id column
        con.execute("""
            CREATE TABLE pm_positions (
                position_id TEXT PRIMARY KEY,
                venue TEXT NOT NULL, strategy TEXT, status TEXT,
                created_at_ms INTEGER, updated_at_ms INTEGER,
                closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT
            )
        """)
        con.execute("""
            CREATE TABLE pm_legs (
                leg_id TEXT PRIMARY KEY,
                position_id TEXT REFERENCES pm_positions(position_id),
                venue TEXT, inst_id TEXT, side TEXT, size REAL,
                entry_price REAL, current_price REAL,
                unrealized_pnl REAL, realized_pnl REAL,
                status TEXT, opened_at_ms INTEGER, closed_at_ms INTEGER,
                raw_json TEXT, meta_json TEXT, account_id TEXT
            )
        """)
        return con

    def test_upsert_leg_stores_wallet_label_in_meta(self):
        from tracking.position_manager.registry import LegConfig
        from tracking.position_manager.registry import PositionConfig
        from tracking.position_manager.db_sync import upsert_leg, upsert_position
        con = self._create_db()

        pos = PositionConfig(
            position_id="p1", strategy_type="SPOT_PERP", base="BTC",
            status="OPEN", legs=[]
        )
        upsert_position(con, pos, 1000)

        leg = LegConfig(
            leg_id="l1", venue="hyperliquid", inst_id="BTC",
            side="LONG", qty=1.0, wallet_label="alt"
        )
        upsert_leg(con, "p1", leg, 1000)
        con.commit()

        row = con.execute("SELECT meta_json FROM pm_legs WHERE leg_id='l1'").fetchone()
        meta = json.loads(row[0])
        self.assertEqual(meta.get("wallet_label"), "alt")

    def test_upsert_leg_no_wallet_label(self):
        from tracking.position_manager.registry import LegConfig
        from tracking.position_manager.registry import PositionConfig
        from tracking.position_manager.db_sync import upsert_leg, upsert_position
        con = self._create_db()

        pos = PositionConfig(
            position_id="p1", strategy_type="SPOT_PERP", base="BTC",
            status="OPEN", legs=[]
        )
        upsert_position(con, pos, 1000)

        leg = LegConfig(
            leg_id="l1", venue="hyperliquid", inst_id="BTC",
            side="LONG", qty=1.0
        )
        upsert_leg(con, "p1", leg, 1000)
        con.commit()

        row = con.execute("SELECT meta_json FROM pm_legs WHERE leg_id='l1'").fetchone()
        # meta_json should be None or not contain wallet_label
        if row[0]:
            meta = json.loads(row[0])
            self.assertNotIn("wallet_label", meta)

    def test_list_positions_includes_account_id(self):
        from tracking.position_manager.db_sync import list_positions
        con = self._create_db()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id, meta_json)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, '0xabc', '{"wallet_label":"main"}')
        """)
        con.commit()

        positions = list_positions(con)
        self.assertEqual(len(positions), 1)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg["account_id"], "0xabc")
        self.assertEqual(leg["meta"].get("wallet_label"), "main")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestDbSyncWalletLabel -v`
Expected: FAIL — tests fail because `upsert_leg` doesn't handle `wallet_label` and `list_positions` doesn't return `account_id`

- [ ] **Step 3: Update `upsert_leg()` in `db_sync.py`**

In `tracking/position_manager/db_sync.py`, modify `upsert_leg()` (line 111-149):

Add `wallet_label` to meta_json building (after line 122, the `collateral` block):
```python
    if leg.wallet_label:
        meta["wallet_label"] = leg.wallet_label
```

No other changes to `upsert_leg()` — `account_id` column will be populated by the puller during the pull cycle, not during registry sync (per spec: "account_id transitions from NULL to the resolved address on first pull").

- [ ] **Step 4: Update `list_positions()` in `db_sync.py`**

In `tracking/position_manager/db_sync.py`, modify the leg SQL query (line 188-193):

Change leg_sql to include `account_id`:
```python
    leg_sql = """
    SELECT leg_id, position_id, venue, inst_id, side, size,
           entry_price, current_price, unrealized_pnl, realized_pnl,
           status, opened_at_ms, closed_at_ms, meta_json, account_id
    FROM pm_legs
    ORDER BY position_id, leg_id
    """
```

Update the leg dict construction (after `"meta"` line, around line 213):
```python
            "account_id": row[14],
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestDbSyncWalletLabel -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add tracking/position_manager/db_sync.py scripts/test_multi_wallet.py
git commit -m "feat: upsert_leg stores wallet_label, list_positions returns account_id"
```

---

### Task 5: Connector Credential Overrides

**Files:**
- Modify: `tracking/connectors/private_base.py:13-23`
- Modify: `tracking/connectors/hyperliquid_private.py:99-110`
- Modify: `tracking/connectors/paradex_private.py:58-65`
- Modify: `tracking/connectors/ethereal_private.py:98-106`
- Modify: `tracking/connectors/hyena_private.py:84-89`
- Modify: `tracking/connectors/lighter_private.py:149-162`
- Modify: `tracking/connectors/okx_private.py:48-56`
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for connector credential overrides**

Append to `scripts/test_multi_wallet.py`:

```python
class TestConnectorOverrides(unittest.TestCase):
    """Test connectors accept credential overrides."""

    def test_hyperliquid_address_override(self):
        from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector
        # Should not raise even without env var, because we provide address
        connector = HyperliquidPrivateConnector(address="0xoverride")
        self.assertEqual(connector.address, "0xoverride")

    def test_hyperliquid_env_still_works(self):
        from tracking.connectors.hyperliquid_private import HyperliquidPrivateConnector
        os.environ["HYPERLIQUID_ADDRESS"] = "0xenv"
        try:
            connector = HyperliquidPrivateConnector()
            self.assertEqual(connector.address, "0xenv")
        finally:
            del os.environ["HYPERLIQUID_ADDRESS"]

    def test_hyena_address_override(self):
        from tracking.connectors.hyena_private import HyenaPrivateConnector
        connector = HyenaPrivateConnector(address="0xhyena_override")
        self.assertEqual(connector.address, "0xhyena_override")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestConnectorOverrides -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'address'`

- [ ] **Step 3: No changes to `private_base.py`**

The base class stays unchanged. Each child connector handles its own override parameters directly.

- [ ] **Step 4: Update `HyperliquidPrivateConnector.__init__()`**

In `tracking/connectors/hyperliquid_private.py` (line 99-110):

```python
    def __init__(self, *, address: Optional[str] = None):
        super().__init__("hyperliquid")
        if address:
            self.address = address.strip()
        else:
            self.address = (
                os.environ.get("HYPERLIQUID_ADDRESS")
                or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")
                or ""
            ).strip()
        self.dex = (os.environ.get("HYPERLIQUID_DEX") or DEFAULT_DEX).strip()
        if not self.address:
            raise RuntimeError(
                "Hyperliquid config missing. Set HYPERLIQUID_ADDRESS or (fallback) ETHEREAL_ACCOUNT_ADDRESS."
            )
```

- [ ] **Step 5: Update remaining connectors**

**`paradex_private.py`** — `__init__` (line 58-65):
```python
    def __init__(self, *, jwt: Optional[str] = None, account_address: Optional[str] = None):
        super().__init__("paradex")
        self.jwt = (
            jwt or os.environ.get("PARADEX_JWT") or os.environ.get("PARADEX_READONLY_TOKEN") or ""
        ).strip()
        self.account_address = (
            account_address or os.environ.get("PARADEX_ACCOUNT_ADDRESS") or ""
        ).strip()
        if not self.jwt:
            raise RuntimeError("Paradex credentials missing...")
```

**`ethereal_private.py`** — `__init__` (line 98-106). Note: Ethereal uses `self.sender` (not `self.address`) throughout the class:
```python
    def __init__(self, *, address: Optional[str] = None):
        super().__init__("ethereal")
        self.sender = (
            address
            or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")
            or os.environ.get("ETHEREAL_SENDER")
            or ""
        ).strip()
        self.subaccount_id = os.environ.get("ETHEREAL_SUBACCOUNT_ID", "").strip()
        if not self.sender:
            raise RuntimeError("Ethereal config missing. Set ETHEREAL_ACCOUNT_ADDRESS or ETHEREAL_SENDER.")
```

**`hyena_private.py`** — `__init__` (line 84-89):
```python
    def __init__(self, *, address: Optional[str] = None):
        super().__init__("hyena")
        self.address = (
            address or os.environ.get("HYENA_ADDRESS") or ""
        ).strip()
        self.dex = (os.environ.get("HYENA_DEX") or DEFAULT_DEX).strip()
        if not self.address:
            raise RuntimeError("Hyena config missing. Set HYENA_ADDRESS.")
```

**`lighter_private.py`** — `__init__` (line 149-162):
```python
    def __init__(self, *, address: Optional[str] = None):
        super().__init__("lighter")
        self.l1_address = (
            address
            or os.environ.get("LIGHTER_L1_ADDRESS")
            or os.environ.get("ETHEREAL_ACCOUNT_ADDRESS")
            or ""
        ).strip()
        if not self.l1_address:
            raise RuntimeError("Lighter credentials missing. Set LIGHTER_L1_ADDRESS or (fallback) ETHEREAL_ACCOUNT_ADDRESS.")
        self.readonly_token = os.environ.get("LIGHTER_READONLY_TOKEN", "").strip()
        self._by_market_id, self._by_symbol = _orderbooks_index()
        self._account_index = None  # Lazy fetch
```

**`okx_private.py`** — `__init__` (line 48-56).

**Limitation:** OKX requires 3 credentials (key, secret, passphrase). For multi-wallet OKX, the `OKX_ACCOUNTS_JSON` format would need nested values. For this iteration, OKX multi-wallet is **not supported** — only single-wallet via legacy env vars. The override params are added for future use:
```python
    def __init__(self, *, api_key: Optional[str] = None, api_secret: Optional[str] = None, passphrase: Optional[str] = None):
        super().__init__("okx")
        self.api_key = (api_key or os.environ.get("OKX_API_KEY") or "").strip()
        self.api_secret = (api_secret or os.environ.get("OKX_API_SECRET") or "").strip()
        self.passphrase = (passphrase or os.environ.get("OKX_API_PASSPHRASE") or "").strip()
        if not self.api_key or not self.api_secret:
            raise RuntimeError("OKX credentials missing. Set OKX_API_KEY, OKX_API_SECRET, OKX_API_PASSPHRASE.")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestConnectorOverrides -v`
Expected: All 3 tests PASS

- [ ] **Step 7: Commit**

```bash
git add tracking/connectors/private_base.py tracking/connectors/hyperliquid_private.py tracking/connectors/paradex_private.py tracking/connectors/ethereal_private.py tracking/connectors/hyena_private.py tracking/connectors/lighter_private.py tracking/connectors/okx_private.py scripts/test_multi_wallet.py
git commit -m "feat: add credential override support to all connectors"
```

---

### Task 6: Puller Multi-Wallet Loop

**Files:**
- Modify: `tracking/position_manager/puller.py:49-86` (load_positions_from_db), `tracking/position_manager/puller.py:89-129` (load_positions_from_registry), `tracking/position_manager/puller.py:132-183` (pull_venue_positions), `tracking/position_manager/puller.py:216-269` (write_leg_snapshots), `tracking/position_manager/puller.py:272-461` (run_pull)
- Test: `scripts/test_multi_wallet.py`

This is the largest task. It modifies the core pull loop.

- [ ] **Step 1: Write tests for multi-wallet pull mapping**

Append to `scripts/test_multi_wallet.py`:

```python
class TestPullerMultiWallet(unittest.TestCase):
    """Test puller multi-wallet partition-then-match logic."""

    def _create_db_with_schema(self):
        """Create in-memory DB with full PM schema + account_id columns."""
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_load_positions_from_db_reads_wallet_label(self):
        from tracking.position_manager.puller import load_positions_from_db
        con = self._create_db_with_schema()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id, meta_json)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, '0xabc', '{"wallet_label":"alt"}')
        """)
        con.commit()

        positions = load_positions_from_db(con)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg["wallet_label"], "alt")
        self.assertEqual(leg["account_id"], "0xabc")

    def test_load_positions_from_db_default_wallet_label(self):
        from tracking.position_manager.puller import load_positions_from_db
        con = self._create_db_with_schema()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0)
        """)
        con.commit()

        positions = load_positions_from_db(con)
        leg = positions[0]["legs"][0]
        self.assertEqual(leg.get("wallet_label"), "main")

    def test_write_leg_snapshots_includes_account_id(self):
        from tracking.position_manager.puller import write_leg_snapshots
        con = self._create_db_with_schema()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, account_id)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, '0xabc')
        """)
        con.commit()

        positions = [{
            "leg_id": "l1", "position_id": "p1",
            "inst_id": "BTC", "side": "LONG", "size": 1.0,
            "entry_price": 50000.0, "current_price": 51000.0,
            "unrealized_pnl": 1000.0, "realized_pnl": 0.0,
            "raw_json": {}, "account_id": "0xabc",
        }]
        write_leg_snapshots(con, "hyperliquid", positions, 1000)
        con.commit()

        row = con.execute("SELECT account_id FROM pm_leg_snapshots WHERE leg_id='l1'").fetchone()
        self.assertEqual(row[0], "0xabc")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestPullerMultiWallet -v`
Expected: FAIL — `wallet_label` not in leg dict, `account_id` not written to snapshots

- [ ] **Step 3: Update `load_positions_from_db()`**

In `tracking/position_manager/puller.py`, modify `load_positions_from_db()` (lines 49-86):

Update SQL to include `account_id` and `meta_json`:
```python
    sql = """
    SELECT p.position_id, p.venue, p.status,
           l.leg_id, l.venue as leg_venue, l.inst_id, l.side, l.size,
           l.account_id, l.meta_json
    FROM pm_positions p
    LEFT JOIN pm_legs l ON p.position_id = l.position_id
    WHERE p.status IN ('OPEN', 'PAUSED', 'EXITING')
    """
```

Update row unpacking (line 67):
```python
        position_id, venue, status, leg_id, leg_venue, inst_id, side, size, account_id, meta_json_raw = row
```

Update leg dict construction (lines 78-84):
```python
        if leg_id:
            meta = json.loads(meta_json_raw) if meta_json_raw else {}
            wallet_label = meta.get("wallet_label", "main")
            positions[position_id]["legs"].append({
                "leg_id": leg_id,
                "venue": leg_venue,
                "inst_id": inst_id,
                "side": side,
                "size": size,
                "wallet_label": wallet_label,
                "account_id": account_id,
            })
```

Add `import json` at top if not already present (it is already imported).

- [ ] **Step 4: Update `load_positions_from_registry()`**

In `tracking/position_manager/puller.py`, modify the leg dict in `load_positions_from_registry()` (lines 117-126):

```python
            "legs": [
                {
                    "leg_id": leg.leg_id,
                    "venue": leg.venue,
                    "inst_id": leg.inst_id,
                    "side": leg.side,
                    "size": leg.qty,
                    "wallet_label": leg.wallet_label or "main",
                    "account_id": None,  # Resolved during pull
                }
                for leg in pos.legs
            ],
```

- [ ] **Step 5: Update `write_leg_snapshots()` to include `account_id`**

In `tracking/position_manager/puller.py`, modify `write_leg_snapshots()` (lines 216-249):

Update SQL:
```python
    sql = """
    INSERT INTO pm_leg_snapshots(
      leg_id, position_id, venue, inst_id, ts, side, size,
      entry_price, current_price, unrealized_pnl, realized_pnl,
      raw_json, meta_json, account_id
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
```

Update the execute call (add `account_id` at end):
```python
        con.execute(sql, (
            pos.get("leg_id", ""),
            pos.get("position_id", ""),
            venue,
            pos.get("inst_id", ""),
            ts_ms,
            pos.get("side", ""),
            pos.get("size", 0.0),
            pos.get("entry_price"),
            pos.get("current_price"),
            pos.get("unrealized_pnl"),
            pos.get("realized_pnl"),
            json.dumps(pos.get("raw_json", {}), separators=(",", ":")),
            None,  # meta_json
            pos.get("account_id"),
        ))
```

Also update the best-effort `pm_legs` UPDATE to set `account_id`:
```python
            con.execute(
                """
                UPDATE pm_legs
                SET current_price = COALESCE(?, current_price),
                    unrealized_pnl = COALESCE(?, unrealized_pnl),
                    realized_pnl = COALESCE(?, realized_pnl),
                    account_id = COALESCE(?, account_id)
                WHERE leg_id = ?
                """,
                (
                    pos.get("current_price"),
                    pos.get("unrealized_pnl"),
                    pos.get("realized_pnl"),
                    pos.get("account_id"),
                    pos.get("leg_id", ""),
                ),
            )
```

- [ ] **Step 6: Update `pull_venue_positions()` to accept credential kwargs**

In `tracking/position_manager/puller.py`, modify `pull_venue_positions()` (lines 132-183):

```python
def pull_venue_positions(venue: str, **connector_kwargs) -> Dict:
```

Update connector instantiation (line 155-156):
```python
        connector_class = CONNECTORS[venue]
        connector = connector_class(**connector_kwargs)
```

- [ ] **Step 7: Update `run_pull()` with multi-wallet loop**

In `tracking/position_manager/puller.py`, modify `run_pull()` (lines 272-461). The key change is in the venue loop (lines 351-452). Replace the single-connector pull with a multi-wallet loop.

Import at top of file:
```python
from .accounts import resolve_venue_accounts
from .db_sync import ensure_multi_wallet_columns
```

At the start of `run_pull()`, after opening the DB connection (line 349), add migration call:
```python
    con = connect(db_path)
    ensure_multi_wallet_columns(con)
```

Replace the venue loop body (lines 351-452) with:

```python
    for venue in sorted(venues_to_pull):
        if verbose:
            print(f"  Pulling from {venue}...")

        accounts = resolve_venue_accounts(venue)
        if not accounts:
            # No credentials — try legacy single-connector pull
            accounts = {"main": ""}

        venue_mapped_total = []

        for wallet_label, credential in sorted(accounts.items()):
            if verbose and len(accounts) > 1:
                print(f"    wallet={wallet_label}...", end=" ")

            # Build connector kwargs based on venue
            connector_kwargs = {}
            if credential:
                if venue in ("hyperliquid", "hyena", "ethereal", "lighter"):
                    connector_kwargs["address"] = credential
                elif venue == "paradex":
                    connector_kwargs["account_address"] = credential
                elif venue == "okx":
                    connector_kwargs["api_key"] = credential

            result = pull_venue_positions(venue, **connector_kwargs)

            if not result["success"]:
                error_msg = result.get("error", "")
                error_lower = error_msg.lower()
                if "no connector available" in error_lower or "credentials missing" in error_lower or "config missing" in error_lower:
                    if verbose:
                        label_suffix = f" [{wallet_label}]" if len(accounts) > 1 else ""
                        print(f"SKIPPED{label_suffix} ({error_msg})")
                else:
                    summary["venues_failed"].append(venue)
                    summary["errors"].append(f"{venue}[{wallet_label}]: {error_msg}")
                    summary["success"] = False
                    if verbose:
                        print(f"FAILED [{wallet_label}] ({error_msg})")
                continue

            try:
                # Collect managed legs for this venue+wallet_label only
                has_managed_legs = any(
                    leg.get("venue") == venue and leg.get("wallet_label", "main") == wallet_label
                    for mp in positions
                    for leg in mp.get("legs", [])
                )

                account_id = credential or (result["account_snapshot"] or {}).get("account_id", "")

                if result["account_snapshot"] and has_managed_legs:
                    write_account_snapshot(con, venue, result["account_snapshot"], ts_ms)
                    summary["snapshots_written"] += 1

                mapped = []
                if result["positions"]:
                    venue_positions = result["positions"]

                    # Partition: only managed legs with matching wallet_label
                    managed_legs = []
                    for mp in positions:
                        for leg in mp.get("legs", []):
                            if leg.get("venue") == venue and leg.get("wallet_label", "main") == wallet_label:
                                managed_legs.append(
                                    {
                                        "position_id": mp.get("position_id"),
                                        "leg_id": leg.get("leg_id"),
                                        "inst_id": leg.get("inst_id"),
                                        "side": (leg.get("side") or "").upper(),
                                    }
                                )

                    # Match within partition using (inst_id, side)
                    idx = {}
                    for vp in venue_positions:
                        key = ((vp.get("inst_id") or ""), (vp.get("side") or "").upper())
                        idx.setdefault(key, vp)

                    for ml in managed_legs:
                        key = (ml.get("inst_id") or "", ml.get("side") or "")
                        vp = idx.get(key)
                        if not vp:
                            continue
                        mapped.append(
                            {
                                "leg_id": ml["leg_id"],
                                "position_id": ml["position_id"],
                                "inst_id": vp.get("inst_id"),
                                "side": (vp.get("side") or "").upper(),
                                "size": vp.get("size"),
                                "entry_price": vp.get("entry_price"),
                                "current_price": vp.get("current_price"),
                                "unrealized_pnl": vp.get("unrealized_pnl"),
                                "realized_pnl": vp.get("realized_pnl"),
                                "raw_json": vp.get("raw_json", {}),
                                "account_id": account_id,
                            }
                        )

                    if mapped:
                        write_leg_snapshots(con, venue, mapped, ts_ms)
                        summary["snapshots_written"] += len(mapped)

                venue_mapped_total.extend(mapped)

                if verbose and len(accounts) > 1:
                    print(f"OK ({len(mapped)} legs)")

            except sqlite3.IntegrityError as e:
                summary["venues_failed"].append(venue)
                summary["errors"].append(f"DB integrity error: {e}")
                summary["success"] = False
                if verbose:
                    print(f"FAILED (DB integrity error: {e})")
                continue

        # Commit per venue (all wallets)
        con.commit()

        if venue not in summary["venues_failed"]:
            summary["venues_pulled"].append(venue)
            if verbose:
                total = len(venue_mapped_total)
                wallets = len(accounts) if len(accounts) > 1 else ""
                wallet_str = f" across {wallets} wallets" if wallets else ""
                print(f"  {venue}: OK ({total} managed legs{wallet_str})")
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestPullerMultiWallet -v`
Expected: All 3 tests PASS

- [ ] **Step 9: Commit**

```bash
git add tracking/position_manager/puller.py scripts/test_multi_wallet.py
git commit -m "feat: multi-wallet pull loop with partition-then-match"
```

---

### Task 7: Cashflows Multi-Wallet Support

**Files:**
- Modify: `tracking/position_manager/cashflows.py:98-111` (load_managed_leg_index)
- Modify: `scripts/pm_cashflows.py`
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write tests for updated `load_managed_leg_index()`**

Append to `scripts/test_multi_wallet.py`:

```python
class TestCashflowsMultiWallet(unittest.TestCase):
    """Test cashflows load_managed_leg_index with account_id."""

    def _create_db_with_schema(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_index_includes_account_id(self):
        from tracking.position_manager.cashflows import load_managed_leg_index
        con = self._create_db_with_schema()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, account_id)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, 'OPEN', '0xabc')
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status, account_id)
            VALUES ('l2', 'p1', 'hyperliquid', 'BTC', 'LONG', 2.0, 'OPEN', '0xdef')
        """)
        con.commit()

        idx = load_managed_leg_index(con)
        # Two different entries for same (venue, inst_id, side) but different account_id
        self.assertEqual(idx[("hyperliquid", "0xabc", "BTC", "LONG")], ("p1", "l1"))
        self.assertEqual(idx[("hyperliquid", "0xdef", "BTC", "LONG")], ("p1", "l2"))

    def test_index_null_account_id(self):
        from tracking.position_manager.cashflows import load_managed_leg_index
        con = self._create_db_with_schema()
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status)
            VALUES ('l1', 'p1', 'hyperliquid', 'BTC', 'LONG', 1.0, 'OPEN')
        """)
        con.commit()

        idx = load_managed_leg_index(con)
        # NULL account_id -> empty string in key
        self.assertEqual(idx[("hyperliquid", "", "BTC", "LONG")], ("p1", "l1"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestCashflowsMultiWallet -v`
Expected: FAIL — key tuple has 3 elements, tests expect 4

- [ ] **Step 3: Update `load_managed_leg_index()` in `cashflows.py`**

In `tracking/position_manager/cashflows.py`, modify `load_managed_leg_index()` (lines 98-111):

```python
def load_managed_leg_index(con: sqlite3.Connection) -> Dict[Tuple[str, str, str, str], Tuple[str, str]]:
    """Map (venue, account_id, inst_id, side) -> (position_id, leg_id)."""
    cur = con.execute(
        """
        SELECT leg_id, position_id, venue, inst_id, side, account_id
        FROM pm_legs
        WHERE status='OPEN'
        """
    )
    idx: Dict[Tuple[str, str, str, str], Tuple[str, str]] = {}
    for leg_id, position_id, venue, inst_id, side, account_id in cur.fetchall():
        key = (str(venue), str(account_id or ""), str(inst_id), str(side).upper())
        idx[key] = (str(position_id), str(leg_id))
    return idx
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestCashflowsMultiWallet -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Update `ingest_paradex()` index lookup (line 128)**

Change:
```python
        k = ("paradex", market, side)
```
To:
```python
        k = ("paradex", str(account_id), market, side)
```

- [ ] **Step 6: Update `ingest_ethereal()` index lookup (line 207)**

Change:
```python
        k = ("ethereal", inst_id, side)
```
To:
```python
        k = ("ethereal", str(account_id), inst_id, side)
```

- [ ] **Step 7: Update `ingest_lighter()` index lookup (line 513)**

Change:
```python
        k = ("lighter", inst_id, side)
```
To:
```python
        k = ("lighter", str(account_id), inst_id, side)
```

Also fix Lighter's state key (line 496) to avoid collision across wallets:
```python
        leg_key = str(p.get("leg_id") or f"{account_id}:{inst_id}:{side}")
```

- [ ] **Step 8: Update `ingest_okx()` index lookup (line 598)**

Change:
```python
            k = ("okx", inst_id, side)
```
To:
```python
            k = ("okx", str(account_id), inst_id, side)
```

- [ ] **Step 9: Update `_load_hyperliquid_targets()` to include `account_id` (line 277-310)**

The function must group by `(account_id, dex, coin)` to avoid collisions. Update the SQL to include `account_id` and change the return structure:

```python
def _load_hyperliquid_targets(con: sqlite3.Connection) -> Dict[str, Dict[str, Dict[str, Dict[str, str]]]]:
    """Return account_id -> dex -> coin -> target metadata for OPEN managed Hyperliquid perp legs."""

    cur = con.execute(
        """
        SELECT p.strategy, l.position_id, l.leg_id, l.inst_id, l.side, l.account_id
        FROM pm_legs l
        JOIN pm_positions p ON p.position_id = l.position_id
        WHERE l.venue='hyperliquid' AND l.status='OPEN' AND p.status='OPEN'
        """
    )
    targets: Dict[str, Dict[str, Dict[str, Dict[str, str]]]] = {}
    for strategy, position_id, leg_id, inst_id, side, account_id in cur.fetchall():
        inst = str(inst_id or "")
        side_u = str(side or "").upper()
        acct = str(account_id or "")
        if _is_spot_inst_id(inst):
            continue
        if str(strategy or "").upper() == "SPOT_PERP" and side_u != "SHORT":
            continue
        dex, coin = split_hyperliquid_inst_id(inst)
        coin = strip_coin_namespace(coin)
        if not coin:
            continue
        targets.setdefault(acct, {}).setdefault(dex, {})[coin] = {
            "position_id": str(position_id),
            "leg_id": str(leg_id),
            "inst_id": namespaced_inst_id(dex=dex, coin=coin),
            "side": side_u,
        }
    return targets
```

Then update `ingest_hyperliquid()` (line 313+) to iterate the outer `account_id` layer:

```python
def ingest_hyperliquid(con: sqlite3.Connection, *, since_hours: int = HYPERLIQUID_DEFAULT_SINCE_HOURS) -> int:
    targets_by_account = _load_hyperliquid_targets(con)
    if not targets_by_account:
        return 0

    accounts = resolve_venue_accounts("hyperliquid")
    # ... existing time window setup ...

    total_events = 0
    for account_id_db, targets_by_dex in targets_by_account.items():
        # Find the address to use for API calls
        address = account_id_db
        if not address:
            # Fallback: use first account
            address = next(iter(accounts.values()), "")
        if not address:
            continue

        # Existing dex loop, but using `address` for API calls
        for dex, coins in targets_by_dex.items():
            # ... existing funding/fill ingestion logic, using address for post_info calls ...
            pass

    return total_events
```

- [ ] **Step 10: Refactor `cmd_ingest()` for multi-wallet ingest loop (line 622-641)**

Each `ingest_*` function currently instantiates its own connector. For multi-wallet, `cmd_ingest()` must iterate wallets and pass connector instances. This is a phased approach:

Phase 1 (this task): The index key changes (steps 5-9 above) ensure correct leg matching. The existing single-connector ingest functions work for the "main" wallet. Hyperliquid already uses `_load_hyperliquid_targets` which is now account-aware.

Phase 2 (follow-up): Refactor `ingest_paradex`, `ingest_ethereal`, `ingest_lighter`, `ingest_okx` to accept an explicit connector + account_id parameter, and wrap `cmd_ingest()` in a multi-wallet loop. This can be a separate task/PR since the index key fix prevents data corruption immediately.

Add to `cmd_ingest()`:
```python
    from tracking.position_manager.db_sync import ensure_multi_wallet_columns
    ensure_multi_wallet_columns(con)
```

- [ ] **Step 6: Commit**

```bash
git add tracking/position_manager/cashflows.py scripts/pm_cashflows.py scripts/test_multi_wallet.py
git commit -m "feat: cashflows index key includes account_id for multi-wallet"
```

---

### Task 8: Healthcheck Multi-Wallet Updates

**Files:**
- Modify: `scripts/pm_healthcheck.py:207-226`
- Test: manual verification (healthcheck is integration-heavy)

- [ ] **Step 1: Update wallet mismatch check to iterate all venues/wallets**

In `scripts/pm_healthcheck.py`, modify the Paradex wallet check section (lines 207-226) to be a generic multi-wallet check loop:

```python
    # --- Multi-wallet mismatch checks ---
    from tracking.position_manager.accounts import resolve_venue_accounts
    from tracking.position_manager.puller import CONNECTORS
    for check_venue in ["paradex", "hyperliquid", "hyena", "ethereal", "lighter"]:
        accounts = resolve_venue_accounts(check_venue)
        if not accounts:
            continue
        for wallet_label, expected_addr in accounts.items():
            if not expected_addr:
                continue
            try:
                connector_class = CONNECTORS.get(check_venue)
                if not connector_class:
                    continue
                # Build connector kwargs
                kwargs = {}
                if check_venue in ("hyperliquid", "hyena", "ethereal", "lighter"):
                    kwargs["address"] = expected_addr
                elif check_venue == "paradex":
                    kwargs["account_address"] = expected_addr
                connector = connector_class(**kwargs)
                snap = connector.fetch_account_snapshot() or {}
                actual = str(snap.get("account_id") or "").strip().lower()
                expected_lower = expected_addr.strip().lower()
                if actual and actual != expected_lower:
                    findings.append(Finding(
                        "WARN",
                        f"{check_venue}_wallet_mismatch",
                        f"[{wallet_label}] actual={actual} != expected={expected_lower}"
                    ))
            except Exception:
                pass  # Skip if connector fails
```

- [ ] **Step 2: Verify existing healthcheck still runs without error**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && source .arbit_env && .venv/bin/python scripts/pm_healthcheck.py --db tracking/db/arbit_v3.db 2>&1 | head -20`
Expected: No Python errors. May show WARN/CRITICAL findings (expected).

- [ ] **Step 3: Commit**

```bash
git add scripts/pm_healthcheck.py
git commit -m "feat: healthcheck iterates all wallets for mismatch detection"
```

---

### Task 9: End-to-End Partition-Then-Match Test

**Files:**
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Write end-to-end test for two wallets with same (inst_id, side)**

This is the primary acceptance criterion. Append to `scripts/test_multi_wallet.py`:

```python
from unittest.mock import patch, MagicMock


class TestMultiWalletEndToEnd(unittest.TestCase):
    """Test the core partition-then-match scenario: two wallets, same instrument."""

    def _create_db_with_schema(self):
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys = ON")
        schema_path = Path(__file__).resolve().parent / "tracking" / "sql" / "schema_pm_v3.sql"
        con.executescript(schema_path.read_text())
        from tracking.position_manager.db_sync import ensure_multi_wallet_columns
        ensure_multi_wallet_columns(con)
        return con

    def test_two_wallets_same_instrument_no_collision(self):
        """Two wallets both have BTC SHORT — each maps to correct managed leg."""
        from tracking.position_manager.puller import (
            write_leg_snapshots, load_positions_from_db,
        )
        con = self._create_db_with_schema()

        # Setup: position with 2 legs on different wallets, same inst_id+side
        con.execute("""
            INSERT INTO pm_positions(position_id, venue, status, created_at_ms, updated_at_ms)
            VALUES ('p1', 'hyperliquid', 'OPEN', 0, 0)
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status,
                                account_id, meta_json)
            VALUES ('l_main', 'p1', 'hyperliquid', 'xyz:BTC', 'SHORT', 1.0, 'OPEN',
                    '0xaaa', '{"wallet_label":"main"}')
        """)
        con.execute("""
            INSERT INTO pm_legs(leg_id, position_id, venue, inst_id, side, size, status,
                                account_id, meta_json)
            VALUES ('l_alt', 'p1', 'hyperliquid', 'xyz:BTC', 'SHORT', 2.0, 'OPEN',
                    '0xbbb', '{"wallet_label":"alt"}')
        """)
        con.commit()

        positions = load_positions_from_db(con)

        # Simulate partition for wallet "main"
        main_legs = [
            leg for pos in positions for leg in pos["legs"]
            if leg.get("wallet_label") == "main"
        ]
        self.assertEqual(len(main_legs), 1)
        self.assertEqual(main_legs[0]["leg_id"], "l_main")

        # Simulate partition for wallet "alt"
        alt_legs = [
            leg for pos in positions for leg in pos["legs"]
            if leg.get("wallet_label") == "alt"
        ]
        self.assertEqual(len(alt_legs), 1)
        self.assertEqual(alt_legs[0]["leg_id"], "l_alt")

        # Simulate mapping: venue returns BTC SHORT for each wallet
        # For main wallet
        venue_pos_main = {"inst_id": "xyz:BTC", "side": "SHORT", "size": 1.5,
                          "entry_price": 50000, "current_price": 51000,
                          "unrealized_pnl": -1000, "realized_pnl": 0, "raw_json": {}}
        idx = {("xyz:BTC", "SHORT"): venue_pos_main}
        mapped_main = []
        for ml in main_legs:
            key = (ml["inst_id"], ml["side"])
            vp = idx.get(key)
            if vp:
                mapped_main.append({**vp, "leg_id": ml["leg_id"],
                                    "position_id": "p1", "account_id": "0xaaa"})

        self.assertEqual(len(mapped_main), 1)
        self.assertEqual(mapped_main[0]["leg_id"], "l_main")
        self.assertEqual(mapped_main[0]["account_id"], "0xaaa")

        # Write snapshots
        write_leg_snapshots(con, "hyperliquid", mapped_main, 1000)
        con.commit()

        # Verify correct attribution
        rows = con.execute(
            "SELECT leg_id, account_id FROM pm_leg_snapshots ORDER BY leg_id"
        ).fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "l_main")
        self.assertEqual(rows[0][1], "0xaaa")
```

- [ ] **Step 2: Run test**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py::TestMultiWalletEndToEnd -v`
Expected: PASS (depends on Tasks 3, 6 being complete)

- [ ] **Step 3: Commit**

```bash
git add scripts/test_multi_wallet.py
git commit -m "test: add end-to-end partition-then-match test for multi-wallet"
```

---

### Task 10: Run All Tests and Ensure Backward Compatibility

**Files:**
- Test: `scripts/test_multi_wallet.py`

- [ ] **Step 1: Run full test suite**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && .venv/bin/python -m pytest scripts/test_multi_wallet.py -v`
Expected: All tests PASS

- [ ] **Step 2: Verify backward compat — single wallet still works**

Ensure no `*_ACCOUNTS_JSON` vars are set, only legacy vars:
```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
unset HYPERLIQUID_ACCOUNTS_JSON
source .arbit_env
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid 2>&1 | head -20
```
Expected: Pull succeeds using legacy `HYPERLIQUID_ADDRESS` env var.

- [ ] **Step 3: Verify multi-wallet works (if test wallets available)**

```bash
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"<addr1>","alt":"<addr2>"}'
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
```
Expected: Pulls from both wallets, snapshots written for each.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "test: verify multi-wallet backward compatibility"
```

---

## Task Dependency Graph

```
Task 1 (accounts helper) ─┐
Task 2 (registry)         ─┼── Task 4 (db_sync) ─┐
Task 3 (migration)        ─┘                      ├── Task 6 (puller) ── Task 9 (e2e test)
Task 5 (connectors)       ────────────────────────┤                      │
                                                   ├── Task 7 (cashflows) ├── Task 10 (integration)
                                                   └── Task 8 (healthcheck)┘
```

Tasks 1, 2, 3, 5 can be worked in parallel. Task 4 depends on 2+3. Tasks 6, 7, 8 depend on 4+5. Task 9 depends on 3+6. Task 10 depends on all.

**Note:** OKX multi-wallet is not supported in this iteration (requires nested credential structure). A follow-up task can add full multi-wallet ingest loop refactoring for `pm_cashflows.py` (Phase 2 in Task 7).
