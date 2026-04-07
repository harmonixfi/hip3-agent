# Strategy Wallet Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all wallet ownership from `.arbit_env` into `config/strategies.json`, making each strategy declare its own wallets with direct addresses, and filter Dashboard/Fund Utilization to show only Delta Neutral wallets.

**Architecture:** `config/strategies.json` becomes the single source of truth for wallet ownership. `resolve_venue_accounts()` reads from it (not env). `get_strategy_wallets(strategy_id)` is the new API for strategy-scoped wallet queries. Dashboard portfolio snapshot and fund utilization filter `pm_account_snapshots` by DN wallet addresses. Providers prefer `address` field directly from `strategies.json.wallets[]`. Migration script handles idempotent rollout.

**Tech Stack:** Python, SQLite, JSON config, pytest, FastAPI.

**Spec:** `docs/superpowers/specs/2026-04-07-strategy-wallet-ownership-design.md`

---

## File Structure

| File | Responsibility | Change |
|------|----------------|--------|
| `config/strategies.json` | Source of truth for strategies + wallet ownership | Add `wallets[]` with `{label, venue, address}` per strategy |
| `tracking/position_manager/accounts.py` | Wallet label → address resolver | Read from strategies.json; add `get_strategy_wallets()`; remove `HYPERLIQUID_ACCOUNTS_JSON` env handling; keep legacy single-var fallback |
| `tracking/vault/providers/delta_neutral.py` | DN equity provider | Prefer `address` from wallet dict before resolver lookup |
| `tracking/vault/providers/depeg.py` | Depeg equity provider | Same as DN provider |
| `tracking/pipeline/portfolio.py` | Portfolio snapshot writer | `_get_total_equity()` filters `pm_account_snapshots` by DN addresses only |
| `api/routers/portfolio.py` | Dashboard API | `_compute_fund_utilization()` and `portfolio_overview()` filter to DN wallets; `_account_label()` reads from strategies.json |
| `.arbit_env` | Env vars | Remove `HYPERLIQUID_ACCOUNTS_JSON` line |
| `.arbit_env.example` | Env vars template | Remove `HYPERLIQUID_ACCOUNTS_JSON` example; document legacy fallback |
| `scripts/migrate_strategy_wallets.py` | New: idempotent migration script | Validate + sync-registry + pull + recompute + report |
| `docs/runbook-strategy-wallet-ownership.md` | New: team-facing doc | TL;DR, before/after, how-to, troubleshooting |
| `tests/test_accounts_strategies.py` | New: accounts.py tests | Verify strategies.json reading, fallback, uniqueness |
| `tests/test_portfolio_dn_filter.py` | New: portfolio.py tests | Verify DN-only filter |
| `tests/test_migrate_script.py` | New: migration script tests | Dry-run, idempotency, validation failures |

---

## Constants and Conventions

**Repo root:** `/Users/beannguyen/Development/OpenClawAgents/hip3-agent`
**Env:** `source .arbit_env` before every Python command
**Python:** `.venv/bin/python`
**DB:** `tracking/db/arbit_v3.db`
**Config paths used in code:** resolved from repo root via `Path(__file__).resolve().parent.parent.parent / "config" / "strategies.json"`

---

### Task 1: Add wallets[] to config/strategies.json

**Files:**
- Modify: `config/strategies.json`

- [ ] **Step 1: Replace strategies.json contents**

Replace the entire file `config/strategies.json` with:

```json
{
  "vault_name": "OpenClaw Vault",
  "strategies": [
    {
      "strategy_id": "lending",
      "name": "Lending",
      "type": "LENDING",
      "status": "ACTIVE",
      "wallets": [],
      "target_weight_pct": 50.0,
      "config": {
        "lending_accounts": ["0x0BdFcFbd77c0f3170aC5231480BbB1E45eEBa9ae"]
      }
    },
    {
      "strategy_id": "delta_neutral",
      "name": "Delta Neutral",
      "type": "DELTA_NEUTRAL",
      "status": "ACTIVE",
      "wallets": [
        {"label": "alt",  "venue": "hyperliquid", "address": "0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453"},
        {"label": "main", "venue": "hyperliquid", "address": "0x4Fde618c143640638433a1f00431C6B49bb08322"}
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
        {"label": "depeg", "venue": "hyperliquid", "address": "0x0BdFcFbd77c0f3170aC5231480BbB1E45eEBa9ae"}
      ],
      "target_weight_pct": 5.0,
      "config": {}
    }
  ]
}
```

- [ ] **Step 2: Validate JSON parses**

Run:
```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
source .arbit_env && .venv/bin/python -c "import json; json.load(open('config/strategies.json')); print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add config/strategies.json
git commit -m "config(strategies): add wallets[] with addresses per strategy"
```

---

### Task 2: Refactor accounts.py to read from strategies.json

**Files:**
- Modify: `tracking/position_manager/accounts.py`
- Create: `tests/test_accounts_strategies.py`

- [ ] **Step 1: Create failing test file**

Create `tests/test_accounts_strategies.py`:

```python
"""Tests for tracking/position_manager/accounts.py reading from strategies.json.

Run: .venv/bin/python -m pytest tests/test_accounts_strategies.py -v
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.position_manager import accounts as accounts_mod


_STRATEGIES_FIXTURE = {
    "vault_name": "Test Vault",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "Delta Neutral",
            "type": "DELTA_NEUTRAL",
            "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0xALT"},
                {"label": "main", "venue": "hyperliquid", "address": "0xMAIN"},
            ],
            "target_weight_pct": 45.0,
            "config": {},
        },
        {
            "strategy_id": "depeg",
            "name": "Depeg",
            "type": "DEPEG",
            "status": "ACTIVE",
            "wallets": [
                {"label": "depeg", "venue": "hyperliquid", "address": "0xDEPEG"},
            ],
            "target_weight_pct": 5.0,
            "config": {},
        },
        {
            "strategy_id": "lending",
            "name": "Lending",
            "type": "LENDING",
            "status": "ACTIVE",
            "wallets": [],
            "target_weight_pct": 50.0,
            "config": {"lending_accounts": ["0xLENDING"]},
        },
    ],
}


@pytest.fixture
def tmp_strategies(monkeypatch):
    """Write strategies fixture to a temp file and point accounts module at it."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_STRATEGIES_FIXTURE, f)
        path = Path(f.name)
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", path)
    accounts_mod._CACHE.clear()
    yield path
    path.unlink(missing_ok=True)
    accounts_mod._CACHE.clear()


def test_resolve_venue_accounts_reads_from_strategies_json(tmp_strategies, monkeypatch):
    monkeypatch.delenv("HYPERLIQUID_ACCOUNTS_JSON", raising=False)
    monkeypatch.delenv("HYPERLIQUID_ADDRESS", raising=False)

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert result == {"alt": "0xALT", "main": "0xMAIN", "depeg": "0xDEPEG"}


def test_resolve_venue_accounts_ignores_hyperliquid_accounts_json_env(tmp_strategies, monkeypatch):
    """HYPERLIQUID_ACCOUNTS_JSON env var MUST be ignored — strategies.json wins."""
    monkeypatch.setenv("HYPERLIQUID_ACCOUNTS_JSON", json.dumps({"phantom": "0xPHANTOM"}))

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert "phantom" not in result
    assert "alt" in result


def test_resolve_venue_accounts_falls_back_to_legacy_address(monkeypatch, tmp_path):
    """When strategies.json has no wallets for a venue, fall back to HYPERLIQUID_ADDRESS."""
    empty_strategies = {
        "vault_name": "Empty",
        "strategies": [
            {
                "strategy_id": "delta_neutral",
                "name": "DN",
                "type": "DELTA_NEUTRAL",
                "status": "ACTIVE",
                "wallets": [],
                "target_weight_pct": 100.0,
                "config": {},
            }
        ],
    }
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps(empty_strategies))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", p)
    accounts_mod._CACHE.clear()

    monkeypatch.delenv("HYPERLIQUID_ACCOUNTS_JSON", raising=False)
    monkeypatch.setenv("HYPERLIQUID_ADDRESS", "0xFALLBACK")

    result = accounts_mod.resolve_venue_accounts("hyperliquid")

    assert result == {"main": "0xFALLBACK"}


def test_get_strategy_wallets_returns_only_own_wallets(tmp_strategies):
    result = accounts_mod.get_strategy_wallets("delta_neutral")

    assert len(result) == 2
    labels = {w["label"] for w in result}
    assert labels == {"alt", "main"}
    addresses = {w["address"] for w in result}
    assert addresses == {"0xALT", "0xMAIN"}


def test_get_strategy_wallets_returns_empty_for_lending(tmp_strategies):
    """Lending strategy has wallets=[] (reads from external NAV DB)."""
    result = accounts_mod.get_strategy_wallets("lending")
    assert result == []


def test_get_strategy_wallets_raises_keyerror_for_unknown(tmp_strategies):
    with pytest.raises(KeyError):
        accounts_mod.get_strategy_wallets("nonexistent")


def test_duplicate_labels_across_strategies_rejected(tmp_path, monkeypatch):
    """Labels must be globally unique across all strategies."""
    dup_strategies = {
        "vault_name": "Dup",
        "strategies": [
            {
                "strategy_id": "a",
                "name": "A", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
                "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x1"}],
                "target_weight_pct": 50.0, "config": {},
            },
            {
                "strategy_id": "b",
                "name": "B", "type": "DEPEG", "status": "ACTIVE",
                "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x2"}],
                "target_weight_pct": 50.0, "config": {},
            },
        ],
    }
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps(dup_strategies))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", p)
    accounts_mod._CACHE.clear()

    with pytest.raises(ValueError, match="duplicate.*label.*main"):
        accounts_mod.resolve_venue_accounts("hyperliquid")
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
source .arbit_env && .venv/bin/python -m pytest tests/test_accounts_strategies.py -v 2>&1 | tail -30
```

Expected: FAIL (module has no `_STRATEGIES_PATH`, no `_CACHE`, no `get_strategy_wallets`).

- [ ] **Step 3: Replace accounts.py with new implementation**

Replace the entire contents of `tracking/position_manager/accounts.py` with:

```python
"""Multi-wallet account resolution.

Single source of truth: config/strategies.json.

Priority:
1. config/strategies.json → union of all strategies' wallets[] filtered by venue
2. Legacy single env var (HYPERLIQUID_ADDRESS etc.) → returns {"main": address}

HYPERLIQUID_ACCOUNTS_JSON is NO LONGER read. Delete it from .arbit_env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional


_LEGACY_ENV = {
    "hyperliquid": ["HYPERLIQUID_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "paradex": ["PARADEX_ACCOUNT_ADDRESS"],
    "ethereal": ["ETHEREAL_ACCOUNT_ADDRESS", "ETHEREAL_SENDER"],
    "hyena": ["HYENA_ADDRESS"],
    "lighter": ["LIGHTER_L1_ADDRESS", "ETHEREAL_ACCOUNT_ADDRESS"],
    "okx": ["OKX_API_KEY"],
}

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_STRATEGIES_PATH = _REPO_ROOT / "config" / "strategies.json"

# mtime-based cache: {"mtime": float, "strategies": list[dict]}
_CACHE: Dict[str, object] = {}


def _load_strategies_cached() -> List[dict]:
    """Load strategies.json with mtime-based cache invalidation.

    Returns list of strategy dicts (empty list if file missing/invalid).
    Validates that labels are globally unique across all wallets.

    Raises:
        ValueError: if duplicate labels found across strategies.
    """
    path = _STRATEGIES_PATH
    if not path.exists():
        return []

    try:
        mtime = path.stat().st_mtime
    except OSError:
        return []

    cached_mtime = _CACHE.get("mtime")
    if cached_mtime == mtime and "strategies" in _CACHE:
        return _CACHE["strategies"]  # type: ignore[return-value]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []

    strategies = data.get("strategies", []) if isinstance(data, dict) else []
    if not isinstance(strategies, list):
        strategies = []

    # Validate global label uniqueness
    seen_labels: Dict[str, str] = {}  # label -> strategy_id
    for s in strategies:
        if not isinstance(s, dict):
            continue
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            label = w.get("label")
            if not label:
                continue
            sid = s.get("strategy_id", "")
            if label in seen_labels and seen_labels[label] != sid:
                raise ValueError(
                    f"duplicate label '{label}' across strategies "
                    f"'{seen_labels[label]}' and '{sid}' — labels must be globally unique"
                )
            seen_labels[label] = sid

    _CACHE["mtime"] = mtime
    _CACHE["strategies"] = strategies
    return strategies


def resolve_venue_accounts(venue: str) -> Dict[str, str]:
    """Resolve wallet labels → addresses for a venue.

    Priority:
    1. config/strategies.json → union of all strategies' wallets for this venue
    2. Legacy single env var (HYPERLIQUID_ADDRESS etc.) → {"main": address}

    Returns:
        Dict mapping wallet_label -> address/credential.
        Empty dict if nothing configured.
    """
    strategies = _load_strategies_cached()

    result: Dict[str, str] = {}
    for s in strategies:
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            if (w.get("venue") or "").strip().lower() != venue.strip().lower():
                continue
            label = w.get("label")
            address = w.get("address")
            if label and address:
                result[str(label)] = str(address)

    if result:
        return result

    # Fallback: legacy single env var
    for env_key in _LEGACY_ENV.get(venue, []):
        val = os.environ.get(env_key, "").strip()
        if val:
            return {"main": val}

    return {}


def get_strategy_wallets(strategy_id: str) -> List[Dict[str, str]]:
    """Return list of wallets for a specific strategy.

    Returns list of dicts with keys: label, venue, address.
    Returns empty list if strategy has no wallets (e.g. lending reads from external NAV DB).

    Raises:
        KeyError: if strategy_id not found in strategies.json.
    """
    strategies = _load_strategies_cached()
    for s in strategies:
        if s.get("strategy_id") == strategy_id:
            wallets = s.get("wallets", []) or []
            return [
                {
                    "label": str(w.get("label", "")),
                    "venue": str(w.get("venue", "")),
                    "address": str(w.get("address", "")),
                }
                for w in wallets
                if isinstance(w, dict)
            ]
    raise KeyError(f"strategy not found: {strategy_id}")
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_accounts_strategies.py -v 2>&1 | tail -20
```

Expected: all 7 tests PASS.

- [ ] **Step 5: Run full test suite — verify no regressions**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass (note: `test_manual_cashflow_apr.py` is a pre-existing failure from vault/apr.py — ignore it).

- [ ] **Step 6: Commit**

```bash
git add tracking/position_manager/accounts.py tests/test_accounts_strategies.py
git commit -m "feat(accounts): read wallet config from strategies.json, add get_strategy_wallets()"
```

---

### Task 3: Update DN and Depeg providers to prefer address from wallet dict

**Files:**
- Modify: `tracking/vault/providers/delta_neutral.py`
- Modify: `tracking/vault/providers/depeg.py`

- [ ] **Step 1: Update DeltaNeutralProvider**

Replace the contents of `tracking/vault/providers/delta_neutral.py` with:

```python
"""Delta Neutral equity provider — reads pm_account_snapshots for strategy wallets."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}

        for wallet in wallets:
            # Prefer address directly from strategy config; fall back to resolver lookup
            address = wallet.get("address")
            venue = wallet.get("venue", "hyperliquid")
            label = wallet.get("label") or wallet.get("wallet_label", "main")

            if not address:
                accounts = resolve_venue_accounts(venue)
                address = accounts.get(label)

            if not address:
                continue

            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (address, venue),
            ).fetchone()

            if row:
                equity = float(row[0]) if row[0] is not None else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
```

- [ ] **Step 2: Update DepegProvider**

Replace the contents of `tracking/vault/providers/depeg.py` with:

```python
"""Depeg equity provider — reads pm_account_snapshots for the depeg wallet."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DepegProvider(EquityProvider):
    """Reads depeg wallet equity from pm_account_snapshots (same source as DN)."""

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}

        for wallet in wallets:
            address = wallet.get("address")
            venue = wallet.get("venue", "hyperliquid")
            label = wallet.get("label") or wallet.get("wallet_label", "depeg")

            if not address:
                accounts = resolve_venue_accounts(venue)
                address = accounts.get(label)

            if not address:
                continue

            row = db.execute(
                """
                SELECT total_balance FROM pm_account_snapshots
                WHERE account_id = ? AND venue = ?
                ORDER BY ts DESC LIMIT 1
                """,
                (address, venue),
            ).fetchone()

            if row:
                equity = float(row[0]) if row[0] is not None else 0.0
                total_equity += equity
                breakdown[label] = {"address": address, "equity_usd": equity, "venue": venue}

        return StrategyEquity(
            equity_usd=total_equity,
            breakdown=breakdown,
            timestamp_ms=int(time.time() * 1000),
        )
```

- [ ] **Step 3: Smoke test — run vault recalc**

```bash
source .arbit_env && .venv/bin/python scripts/vault.py sync-registry 2>&1 | tail -10
```

Expected: sync succeeds without error. (This pushes the updated `wallets_json` — including `address` field — into `vault_strategies` table.)

- [ ] **Step 4: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add tracking/vault/providers/delta_neutral.py tracking/vault/providers/depeg.py
git commit -m "feat(vault): providers prefer address from strategy wallet dict"
```

---

### Task 4: Filter pipeline portfolio_snapshot to DN wallets only

**Files:**
- Modify: `tracking/pipeline/portfolio.py:42-59`
- Create: `tests/test_portfolio_dn_filter.py`

- [ ] **Step 1: Create failing test**

Create `tests/test_portfolio_dn_filter.py`:

```python
"""Test that _get_total_equity() only includes Delta Neutral strategy wallets.

Run: .venv/bin/python -m pytest tests/test_portfolio_dn_filter.py -v
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.pipeline import portfolio as portfolio_mod
from tracking.position_manager import accounts as accounts_mod

_SCHEMA = """
CREATE TABLE pm_account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
  total_balance REAL, available_balance REAL, margin_balance REAL,
  unrealized_pnl REAL, position_value REAL, raw_json TEXT
);
"""

_STRATEGIES_FIXTURE = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0xALT"},
                {"label": "main", "venue": "hyperliquid", "address": "0xMAIN"},
            ],
            "target_weight_pct": 45.0, "config": {},
        },
        {
            "strategy_id": "depeg",
            "name": "Depeg", "type": "DEPEG", "status": "ACTIVE",
            "wallets": [{"label": "depeg", "venue": "hyperliquid", "address": "0xDEPEG"}],
            "target_weight_pct": 5.0, "config": {},
        },
    ],
}


@pytest.fixture
def tmp_strategies(monkeypatch):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(_STRATEGIES_FIXTURE, f)
        path = Path(f.name)
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", path)
    accounts_mod._CACHE.clear()
    yield path
    path.unlink(missing_ok=True)
    accounts_mod._CACHE.clear()


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(_SCHEMA)
    return con


def test_get_total_equity_only_dn_wallets(tmp_strategies):
    """pm_account_snapshots has alt, main, AND depeg. _get_total_equity returns only alt+main."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT",   1000, 50000.0),
            ("hyperliquid", "0xMAIN",  1000,   500.0),
            ("hyperliquid", "0xDEPEG", 1000,  5000.0),  # must NOT be included
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 50500.0  # alt + main only
    assert "0xALT" in result["equity_by_account"]
    assert "0xMAIN" in result["equity_by_account"]
    assert "0xDEPEG" not in result["equity_by_account"]


def test_get_total_equity_picks_latest_ts(tmp_strategies):
    """When multiple snapshots exist for same account, use latest."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT", 1000, 40000.0),  # old
            ("hyperliquid", "0xALT", 2000, 55000.0),  # latest
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 55000.0


def test_get_total_equity_returns_zero_when_no_dn_wallets_in_db(tmp_strategies):
    """When no DN wallet snapshots exist yet, return 0 (not an error)."""
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [("hyperliquid", "0xDEPEG", 1000, 5000.0)],  # only depeg
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 0.0
    assert result["equity_by_account"] == {}
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_portfolio_dn_filter.py -v 2>&1 | tail -20
```

Expected: `test_get_total_equity_only_dn_wallets` FAILS (depeg is included in total).

- [ ] **Step 3: Update _get_total_equity in tracking/pipeline/portfolio.py**

Find the `_get_total_equity` function (starts around line 42). Replace it with:

```python
def _get_total_equity(con: sqlite3.Connection) -> Dict[str, Any]:
    """Return Delta Neutral portfolio equity only.

    Filters pm_account_snapshots to addresses owned by the delta_neutral strategy.
    Other strategy wallets (depeg, lending) are tracked separately via vault providers.
    """
    from tracking.position_manager.accounts import get_strategy_wallets

    try:
        dn_wallets = get_strategy_wallets("delta_neutral")
    except KeyError:
        dn_wallets = []

    dn_addresses = [w["address"] for w in dn_wallets if w.get("address")]
    if not dn_addresses:
        return {"total_equity_usd": 0.0, "equity_by_account": {}}

    placeholders = ",".join(["?"] * len(dn_addresses))
    sql = f"""
        SELECT a.account_id, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) as max_ts
            FROM pm_account_snapshots
            WHERE account_id IN ({placeholders})
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
    """
    rows = con.execute(sql, dn_addresses).fetchall()

    equity_by_account: Dict[str, float] = {}
    total = 0.0
    for account_id, balance in rows:
        if balance is not None:
            equity_by_account[account_id] = float(balance)
            total += float(balance)
    return {"total_equity_usd": total, "equity_by_account": equity_by_account}
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_portfolio_dn_filter.py -v 2>&1 | tail -20
```

Expected: all 3 tests PASS.

- [ ] **Step 5: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tracking/pipeline/portfolio.py tests/test_portfolio_dn_filter.py
git commit -m "fix(portfolio): filter total_equity to delta_neutral strategy wallets only"
```

---

### Task 5: Filter fund_utilization and account_label to DN wallets

**Files:**
- Modify: `api/routers/portfolio.py:38-121` (`_compute_fund_utilization`)
- Modify: `api/routers/portfolio.py:140-160` (portfolio_overview account query)
- Modify: `api/routers/portfolio.py:294-321` (`_account_label`)

- [ ] **Step 1: Update _account_label to read from strategies.json**

Find the `_account_label` function (around line 294). Replace it with:

```python
def _account_label(account_id: str) -> str:
    """Derive a human-friendly label from account_id.

    Reads from config/strategies.json via get_strategy_wallets. Falls back to
    truncated address if no match found.
    """
    from tracking.position_manager.accounts import _load_strategies_cached

    try:
        strategies = _load_strategies_cached()
    except Exception:
        strategies = []

    for s in strategies:
        for w in s.get("wallets", []) or []:
            if not isinstance(w, dict):
                continue
            addr = w.get("address", "")
            if isinstance(addr, str) and addr.lower() == account_id.lower():
                return str(w.get("label", account_id[:10]))

    return account_id[:10]
```

- [ ] **Step 2: Add DN address filter to _compute_fund_utilization**

Find `_compute_fund_utilization` (around line 38). After loading `acct_detail_rows` (around line 61), add filtering. Replace the block from the function definition through the end of step 1 with:

```python
def _compute_fund_utilization(
    db: sqlite3.Connection,
    total_equity: float,
) -> FundUtilization:
    """Compute leverage, deployed/available capital from live DB data.

    Filters to delta_neutral strategy wallets only — lending/depeg tracked separately.
    """
    from tracking.position_manager.accounts import get_strategy_wallets

    try:
        dn_wallets = get_strategy_wallets("delta_neutral")
    except KeyError:
        dn_wallets = []
    dn_addresses = {w["address"].lower() for w in dn_wallets if w.get("address")}

    # 1. Per-account available/margin from latest snapshots (already fetched in caller
    #    but we need extra columns, so re-query with full columns)
    acct_detail_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance,
               a.available_balance, a.margin_balance, a.position_value
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    # Filter to DN wallets only
    if dn_addresses:
        acct_detail_rows = [r for r in acct_detail_rows if (r["account_id"] or "").lower() in dn_addresses]
```

Keep the rest of the function unchanged (per-account notional, aggregation, return).

- [ ] **Step 3: Filter portfolio_overview account_rows to DN wallets**

Find `portfolio_overview` (around line 125). Locate the block that loads `account_rows` (around line 143-153). Immediately after that block, add the same filter. Change:

```python
    # 2. Latest account snapshots (equity per wallet)
    account_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()
```

to:

```python
    # 2. Latest account snapshots (equity per wallet), filtered to DN wallets only
    from tracking.position_manager.accounts import get_strategy_wallets
    try:
        _dn_wallets = get_strategy_wallets("delta_neutral")
    except KeyError:
        _dn_wallets = []
    _dn_addresses = {w["address"].lower() for w in _dn_wallets if w.get("address")}

    account_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    if _dn_addresses:
        account_rows = [r for r in account_rows if (r["account_id"] or "").lower() in _dn_addresses]
```

- [ ] **Step 4: Smoke-test the API endpoint**

Start the API in the background and curl it:

```bash
source .arbit_env && .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 > /tmp/api.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8001/portfolio/overview 2>&1 | python3 -m json.tool | head -40
kill %1 2>/dev/null || true
```

Expected:
- `accounts` list contains only `alt` and `main` labels (NOT `depeg`)
- No duplicate labels
- `fund_utilization.accounts` has same filter applied

- [ ] **Step 5: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add api/routers/portfolio.py
git commit -m "fix(api): filter portfolio overview and fund_utilization to DN wallets only"
```

---

### Task 6: Remove HYPERLIQUID_ACCOUNTS_JSON from .arbit_env

**Files:**
- Modify: `.arbit_env`
- Modify: `.arbit_env.example`

- [ ] **Step 1: Remove the env var line from .arbit_env**

Find the line in `.arbit_env` that looks like:
```bash
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"0x4Fde...","alt":"0x3c2c...", "depeg": "0x0BdF...", "lending": "0x0BdF..."}'
```

Replace it with:
```bash
# HYPERLIQUID_ACCOUNTS_JSON removed — wallet config is now in config/strategies.json
# Legacy fallback: HYPERLIQUID_ADDRESS (used only if strategies.json has no wallets for hyperliquid)
```

Keep any other exports untouched.

- [ ] **Step 2: Update .arbit_env.example**

Find `HYPERLIQUID_ACCOUNTS_JSON` in `.arbit_env.example`. Replace the line with:

```bash
# HYPERLIQUID_ACCOUNTS_JSON is NO LONGER used — define wallets in config/strategies.json
# Legacy single-wallet fallback (optional, for bootstrap scenarios):
# export HYPERLIQUID_ADDRESS="0x..."
```

- [ ] **Step 3: Re-source env and verify var is gone**

```bash
source .arbit_env && echo "HYPERLIQUID_ACCOUNTS_JSON=[$HYPERLIQUID_ACCOUNTS_JSON]"
```

Expected output:
```
HYPERLIQUID_ACCOUNTS_JSON=[]
```

(Empty — the variable is unset from the current env.)

Note: if your shell had the variable set from a previous session, you may need to `unset HYPERLIQUID_ACCOUNTS_JSON` explicitly, then re-source.

- [ ] **Step 4: Verify accounts.py still resolves correctly from strategies.json**

```bash
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python -c "
from tracking.position_manager.accounts import resolve_venue_accounts, get_strategy_wallets
print('resolve_venue_accounts:', resolve_venue_accounts('hyperliquid'))
print('DN wallets:', get_strategy_wallets('delta_neutral'))
print('depeg wallets:', get_strategy_wallets('depeg'))
print('lending wallets:', get_strategy_wallets('lending'))
"
```

Expected:
```
resolve_venue_accounts: {'alt': '0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453', 'main': '0x4Fde618c143640638433a1f00431C6B49bb08322', 'depeg': '0x0BdFcFbd77c0f3170aC5231480BbB1E45eEBa9ae'}
DN wallets: [{'label': 'alt', 'venue': 'hyperliquid', 'address': '0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453'}, {'label': 'main', 'venue': 'hyperliquid', 'address': '0x4Fde618c143640638433a1f00431C6B49bb08322'}]
depeg wallets: [{'label': 'depeg', 'venue': 'hyperliquid', 'address': '0x0BdFcFbd77c0f3170aC5231480BbB1E45eEBa9ae'}]
lending wallets: []
```

- [ ] **Step 5: Commit**

```bash
git add .arbit_env .arbit_env.example
git commit -m "chore(env): remove HYPERLIQUID_ACCOUNTS_JSON, wallet config now in strategies.json"
```

---

### Task 7: Create migration script scripts/migrate_strategy_wallets.py

**Files:**
- Create: `scripts/migrate_strategy_wallets.py`
- Create: `tests/test_migrate_script.py`

- [ ] **Step 1: Create failing test file**

Create `tests/test_migrate_script.py`:

```python
"""Tests for scripts/migrate_strategy_wallets.py.

Run: .venv/bin/python -m pytest tests/test_migrate_script.py -v
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


_VALID_STRATEGIES = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "delta_neutral",
            "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [
                {"label": "alt", "venue": "hyperliquid", "address": "0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453"},
            ],
            "target_weight_pct": 95.0, "config": {},
        },
        {
            "strategy_id": "lending",
            "name": "Lending", "type": "LENDING", "status": "ACTIVE",
            "wallets": [],
            "target_weight_pct": 5.0, "config": {"lending_accounts": ["0x1"]},
        },
    ],
}

_DUPLICATE_LABEL_STRATEGIES = {
    "vault_name": "Test",
    "strategies": [
        {
            "strategy_id": "a", "name": "A", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x1"}],
            "target_weight_pct": 50.0, "config": {},
        },
        {
            "strategy_id": "b", "name": "B", "type": "DEPEG", "status": "ACTIVE",
            "wallets": [{"label": "main", "venue": "hyperliquid", "address": "0x2"}],
            "target_weight_pct": 50.0, "config": {},
        },
    ],
}


@pytest.fixture
def tmp_repo(tmp_path, monkeypatch):
    """Create a temp repo structure with strategies.json and empty DB."""
    (tmp_path / "config").mkdir()
    (tmp_path / "tracking" / "db").mkdir(parents=True)

    strategies_path = tmp_path / "config" / "strategies.json"
    db_path = tmp_path / "tracking" / "db" / "arbit_v3.db"

    # Create minimal DB schema
    con = sqlite3.connect(str(db_path))
    con.executescript("""
    CREATE TABLE pm_positions (
      position_id TEXT PRIMARY KEY, venue TEXT NOT NULL, strategy TEXT,
      status TEXT NOT NULL, created_at_ms INTEGER NOT NULL, updated_at_ms INTEGER NOT NULL,
      closed_at_ms INTEGER, raw_json TEXT, meta_json TEXT
    );
    CREATE TABLE pm_legs (
      leg_id TEXT PRIMARY KEY, position_id TEXT NOT NULL, venue TEXT NOT NULL,
      inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL NOT NULL,
      entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
      status TEXT NOT NULL, opened_at_ms INTEGER NOT NULL, closed_at_ms INTEGER,
      raw_json TEXT, meta_json TEXT, account_id TEXT
    );
    CREATE TABLE pm_account_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
      total_balance REAL, available_balance REAL, margin_balance REAL,
      unrealized_pnl REAL, position_value REAL, raw_json TEXT
    );
    """)
    con.commit()
    con.close()

    yield {"root": tmp_path, "strategies": strategies_path, "db": db_path}


def test_migrate_validates_strategies_structure(tmp_repo, monkeypatch, capsys):
    """Dry-run with valid strategies passes validation."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_VALID_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 0
    captured = capsys.readouterr().out
    assert "VALIDATE" in captured or "validate" in captured.lower()


def test_migrate_rejects_duplicate_labels(tmp_repo, monkeypatch, capsys):
    """Migration fails fast when strategies.json has duplicate labels."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_DUPLICATE_LABEL_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 1
    captured = capsys.readouterr().out + capsys.readouterr().err
    assert "duplicate" in captured.lower() or "FAIL" in captured


def test_migrate_rejects_invalid_address_format(tmp_repo, monkeypatch, capsys):
    """Migration fails when address is not a valid 0x... hex string."""
    from tracking.position_manager import accounts as accounts_mod

    bad = {
        "vault_name": "Test",
        "strategies": [{
            "strategy_id": "dn", "name": "DN", "type": "DELTA_NEUTRAL", "status": "ACTIVE",
            "wallets": [{"label": "alt", "venue": "hyperliquid", "address": "not_an_address"}],
            "target_weight_pct": 100.0, "config": {},
        }],
    }
    tmp_repo["strategies"].write_text(json.dumps(bad))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])

    exit_code = mig.main(dry_run=True, skip_recompute=True)

    assert exit_code == 1


def test_migrate_dry_run_does_not_write_to_db(tmp_repo, monkeypatch):
    """Dry-run must not insert rows into pm_account_snapshots."""
    from tracking.position_manager import accounts as accounts_mod

    tmp_repo["strategies"].write_text(json.dumps(_VALID_STRATEGIES))
    monkeypatch.setattr(accounts_mod, "_STRATEGIES_PATH", tmp_repo["strategies"])
    accounts_mod._CACHE.clear()

    import scripts.migrate_strategy_wallets as mig
    monkeypatch.setattr(mig, "STRATEGIES_PATH", tmp_repo["strategies"])
    monkeypatch.setattr(mig, "DB_PATH", tmp_repo["db"])

    mig.main(dry_run=True, skip_recompute=True)

    con = sqlite3.connect(str(tmp_repo["db"]))
    count = con.execute("SELECT COUNT(*) FROM pm_account_snapshots").fetchone()[0]
    con.close()
    assert count == 0
```

- [ ] **Step 2: Run tests — verify they FAIL**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_script.py -v 2>&1 | tail -20
```

Expected: FAIL (module doesn't exist).

- [ ] **Step 3: Create scripts/migrate_strategy_wallets.py**

Create the file with the following contents:

```python
#!/usr/bin/env python3
"""Idempotent migration script for strategy wallet ownership refactor.

Validates config/strategies.json, runs sync-registry, pulls fresh snapshots,
and recomputes portfolio/vault snapshots. Safe to re-run.

Usage:
    .venv/bin/python scripts/migrate_strategy_wallets.py [--dry-run] [--skip-recompute]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STRATEGIES_PATH = ROOT / "config" / "strategies.json"
POSITIONS_PATH = ROOT / "config" / "positions.json"
DB_PATH = ROOT / "tracking" / "db" / "arbit_v3.db"

_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def _fail(msg: str) -> int:
    print(f"FAIL: {msg}", file=sys.stderr)
    return 1


def validate_strategies() -> Optional[dict]:
    """Step 1: Validate config/strategies.json structure.

    Returns parsed dict on success, None on failure.
    """
    _print_section("STEP 1: VALIDATE strategies.json")

    if not STRATEGIES_PATH.exists():
        print(f"FAIL: {STRATEGIES_PATH} not found")
        return None

    try:
        data = json.loads(STRATEGIES_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON in {STRATEGIES_PATH}: {e}")
        return None

    if not isinstance(data, dict):
        print("FAIL: strategies.json must be a JSON object")
        return None

    strategies = data.get("strategies", [])
    if not isinstance(strategies, list) or not strategies:
        print("FAIL: 'strategies' must be a non-empty list")
        return None

    seen_labels: dict = {}  # label -> strategy_id
    errors: List[str] = []

    for i, s in enumerate(strategies):
        sid = s.get("strategy_id", f"<index {i}>")
        wallets = s.get("wallets", [])
        if not isinstance(wallets, list):
            errors.append(f"{sid}: 'wallets' must be a list")
            continue
        for j, w in enumerate(wallets):
            if not isinstance(w, dict):
                errors.append(f"{sid}/wallet[{j}]: must be a dict")
                continue
            label = w.get("label")
            venue = w.get("venue")
            address = w.get("address")
            if not label:
                errors.append(f"{sid}/wallet[{j}]: missing 'label'")
            if not venue:
                errors.append(f"{sid}/wallet[{j}]: missing 'venue'")
            if not address:
                errors.append(f"{sid}/wallet[{j}]: missing 'address'")
            elif not _ADDRESS_RE.match(address):
                errors.append(f"{sid}/wallet[{j}]: invalid address format '{address}' (expected 0x + 40 hex chars)")
            if label:
                if label in seen_labels and seen_labels[label] != sid:
                    errors.append(f"duplicate label '{label}' in strategies '{seen_labels[label]}' and '{sid}'")
                seen_labels[label] = sid

    if errors:
        for e in errors:
            print(f"  - {e}")
        return None

    print(f"  OK: {len(strategies)} strategies, {len(seen_labels)} unique labels")
    return data


def validate_env() -> None:
    """Step 2: Warn if HYPERLIQUID_ACCOUNTS_JSON is still set in env."""
    _print_section("STEP 2: VALIDATE env")

    legacy = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "").strip()
    if legacy:
        print("  WARNING: HYPERLIQUID_ACCOUNTS_JSON is still set in env but IS NO LONGER USED.")
        print("  Remove this line from .arbit_env after verifying strategies.json is correct.")
    else:
        print("  OK: HYPERLIQUID_ACCOUNTS_JSON not set (correct)")


def validate_positions(strategies_data: dict) -> bool:
    """Step 3: Validate positions.json wallet_labels resolve.

    FAIL on any OPEN/PAUSED/EXITING position with unknown wallet_label.
    INFO only for CLOSED positions.
    """
    _print_section("STEP 3: VALIDATE positions.json wallet_labels")

    if not POSITIONS_PATH.exists():
        print(f"  INFO: {POSITIONS_PATH} not found — skipping position validation")
        return True

    try:
        positions = json.loads(POSITIONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"FAIL: invalid JSON in {POSITIONS_PATH}: {e}")
        return False

    # Build label set from strategies
    known_labels = set()
    for s in strategies_data.get("strategies", []):
        for w in s.get("wallets", []):
            if isinstance(w, dict) and w.get("label"):
                known_labels.add(w["label"])

    blocking_errors: List[str] = []
    info_messages: List[str] = []

    for p in positions:
        pid = p.get("position_id", "?")
        status = p.get("status", "OPEN")
        for leg in p.get("legs", []):
            label = leg.get("wallet_label", "main")
            leg_id = leg.get("leg_id", "?")
            if label not in known_labels:
                msg = f"{pid}/{leg_id}: wallet_label='{label}' not in any strategy (known: {sorted(known_labels)})"
                if status in ("OPEN", "PAUSED", "EXITING"):
                    blocking_errors.append(msg)
                else:
                    info_messages.append(f"[CLOSED] {msg}")

    for m in info_messages:
        print(f"  INFO: {m}")
    for e in blocking_errors:
        print(f"  FAIL: {e}")

    if blocking_errors:
        return False

    print(f"  OK: all OPEN/PAUSED/EXITING positions have valid wallet_labels")
    return True


def run_sync_registry() -> bool:
    """Step 4: Run pm.py sync_registry to update pm_legs.meta_json."""
    _print_section("STEP 4: SYNC registry")
    try:
        import scripts.pm as pm_mod
        con = sqlite3.connect(str(DB_PATH))
        con.execute("PRAGMA foreign_keys = ON")
        try:
            result = pm_mod.sync_registry(con, POSITIONS_PATH)
            con.commit()
        finally:
            con.close()
        print(f"  OK: synced {result}")
        return True
    except Exception as e:
        print(f"  FAIL: sync_registry error: {e}")
        return False


def run_pull() -> bool:
    """Step 5: Pull fresh account snapshots."""
    _print_section("STEP 5: REFRESH account snapshots")
    try:
        from tracking.position_manager.puller import run_pull as pull_fn
        summary = pull_fn(
            db_path=DB_PATH,
            registry_path=None,
            venues_filter={"hyperliquid"},
            verbose=False,
        )
        print(f"  OK: snapshots_written={summary.get('snapshots_written', 0)}")
        return True
    except Exception as e:
        print(f"  FAIL: pull error: {e}")
        return False


def recompute_portfolio() -> bool:
    """Step 6: Recompute pm_portfolio_snapshots with DN-only filter."""
    _print_section("STEP 6: RECOMPUTE portfolio snapshot")
    try:
        from tracking.pipeline.portfolio import compute_portfolio_snapshot
        con = sqlite3.connect(str(DB_PATH))
        try:
            result = compute_portfolio_snapshot(con)
            con.commit()
        finally:
            con.close()
        total = result.get("total_equity_usd", 0) if isinstance(result, dict) else 0
        print(f"  OK: total_equity_usd=${total:,.2f}")
        return True
    except Exception as e:
        print(f"  FAIL: portfolio recompute error: {e}")
        return False


def recompute_vault() -> bool:
    """Step 7: Recompute vault_strategy_snapshots."""
    _print_section("STEP 7: RECOMPUTE vault snapshots")
    try:
        from tracking.vault.snapshot import compute_vault_snapshot
        con = sqlite3.connect(str(DB_PATH))
        try:
            result = compute_vault_snapshot(con)
            con.commit()
        finally:
            con.close()
        print(f"  OK: vault snapshot computed")
        return True
    except Exception as e:
        print(f"  WARNING: vault recompute skipped or failed: {e}")
        print("  (Non-fatal — vault snapshots are recomputed by the hourly cron)")
        return True  # non-fatal


def report_final_state() -> None:
    """Step 8: Print final per-strategy equity report."""
    _print_section("STEP 8: REPORT")
    try:
        con = sqlite3.connect(str(DB_PATH))
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT total_equity_usd, equity_by_account_json FROM pm_portfolio_snapshots ORDER BY ts DESC LIMIT 1"
        ).fetchone()
        con.close()
        if rows:
            total = rows["total_equity_usd"] or 0
            breakdown = json.loads(rows["equity_by_account_json"] or "{}")
            print(f"  Dashboard total_equity_usd (DN only): ${total:,.2f}")
            print(f"  Wallet breakdown:")
            for addr, eq in breakdown.items():
                print(f"    {addr[:20]}...  ${eq:,.2f}")
    except Exception as e:
        print(f"  (skipped: {e})")


def main(dry_run: bool = False, skip_recompute: bool = False) -> int:
    """Run migration. Returns exit code."""
    print(f"Strategy Wallet Ownership Migration")
    print(f"  dry_run={dry_run}, skip_recompute={skip_recompute}")

    strategies_data = validate_strategies()
    if strategies_data is None:
        return 1

    validate_env()

    if not validate_positions(strategies_data):
        return 1

    if dry_run:
        print("\n(dry-run — stopping before write operations)")
        return 0

    if not run_sync_registry():
        return 1

    if not run_pull():
        return 1

    if not skip_recompute:
        if not recompute_portfolio():
            return 1
        recompute_vault()  # non-fatal

    report_final_state()
    print("\n=== MIGRATION COMPLETE ===")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strategy wallet ownership migration")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, no writes")
    parser.add_argument("--skip-recompute", action="store_true", help="Skip portfolio/vault recompute")
    args = parser.parse_args()
    sys.exit(main(dry_run=args.dry_run, skip_recompute=args.skip_recompute))
```

- [ ] **Step 4: Run tests — verify they PASS**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_migrate_script.py -v 2>&1 | tail -30
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Smoke test the script — dry run on real repo**

```bash
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python scripts/migrate_strategy_wallets.py --dry-run 2>&1 | tail -30
```

Expected output includes:
- `STEP 1: VALIDATE strategies.json` → `OK: 3 strategies, 3 unique labels`
- `STEP 2: VALIDATE env` → `OK: HYPERLIQUID_ACCOUNTS_JSON not set (correct)`
- `STEP 3: VALIDATE positions.json wallet_labels` → either `OK:` or `INFO` for CLOSED positions
- Exit code 0

- [ ] **Step 6: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/migrate_strategy_wallets.py tests/test_migrate_script.py
git commit -m "feat(migrate): add scripts/migrate_strategy_wallets.py idempotent migration"
```

---

### Task 8: Create team runbook doc

**Files:**
- Create: `docs/runbook-strategy-wallet-ownership.md`

- [ ] **Step 1: Create the runbook**

Create `docs/runbook-strategy-wallet-ownership.md` with:

````markdown
# Strategy Wallet Ownership Runbook

> **Status:** Current as of 2026-04-07
> **Audience:** Engineering team, ops

## TL;DR

- **Single source of truth:** `config/strategies.json`. Each strategy declares its own wallets with direct addresses.
- **Removed:** `HYPERLIQUID_ACCOUNTS_JSON` env var — do not use it.
- **Dashboard "Total Equity"** shows Delta Neutral portfolio only (alt + main wallets). Other strategies are tracked separately.
- **Vault page** shows per-strategy equity: Lending (from external NAV DB) + Delta Neutral + Depeg.

---

## Before & After

### Before (fragile, two places):

```bash
# .arbit_env
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"0x...","alt":"0x...","depeg":"0x...","lending":"0x..."}'
```

```json
// config/strategies.json
{ "strategy_id": "delta_neutral", "wallets": [{"wallet_label": "alt"}] }
```

Problems:
- Adding a wallet to env silently pulled it into aggregations
- No ownership model — which strategy owns which wallet?
- `lending` and `depeg` shared an address and showed as duplicate rows
- Dashboard "Total Equity" summed ALL wallets, not just Delta Neutral

### After (single file, explicit ownership):

```bash
# .arbit_env — HYPERLIQUID_ACCOUNTS_JSON removed
```

```json
// config/strategies.json
{
  "strategy_id": "delta_neutral",
  "wallets": [
    {"label": "alt",  "venue": "hyperliquid", "address": "0x3c2c..."},
    {"label": "main", "venue": "hyperliquid", "address": "0x4Fde..."}
  ]
}
```

---

## How to add a new wallet

1. Edit `config/strategies.json` and append `{label, venue, address}` to the target strategy's `wallets[]`:

```json
{
  "strategy_id": "delta_neutral",
  "wallets": [
    {"label": "alt",  "venue": "hyperliquid", "address": "0x..."},
    {"label": "main", "venue": "hyperliquid", "address": "0x..."},
    {"label": "new_wallet", "venue": "hyperliquid", "address": "0xNEW..."}
  ]
}
```

2. Sync registry and pull:
```bash
source .arbit_env
.venv/bin/python scripts/pm.py sync-registry
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
.venv/bin/python scripts/pipeline_hourly.py --skip-ingest
```

3. Verify in dashboard / vault page.

**Label uniqueness:** labels must be globally unique across all strategies (not just within one strategy). `resolve_venue_accounts()` raises `ValueError` if duplicates found.

---

## How to add a new strategy

1. Add strategy block to `config/strategies.json`:

```json
{
  "strategy_id": "new_strategy",
  "name": "New Strategy",
  "type": "NEW_TYPE",
  "status": "ACTIVE",
  "wallets": [
    {"label": "new_main", "venue": "hyperliquid", "address": "0x..."}
  ],
  "target_weight_pct": 10.0,
  "config": {}
}
```

2. Adjust `target_weight_pct` of other strategies so the total ≤ 100%.

3. Create a new provider in `tracking/vault/providers/new_strategy.py` (copy from `delta_neutral.py`).

4. Register the provider in `tracking/vault/providers/__init__.py`.

5. Run `scripts/vault.py sync-registry` to push the new strategy into `vault_strategies` table.

---

## "Dashboard Total Equity" explained

The Dashboard `Total Equity` card and `/portfolio/overview` API endpoint show **Delta Neutral portfolio equity only** — the sum of wallets owned by the `delta_neutral` strategy. This does NOT include:
- Lending strategy (tracked separately via external NAV DB)
- Depeg strategy (tracked separately in Vault page)

For a cross-strategy view, use the **Vault page** (`/vault/overview`).

This split reflects how the trading team thinks about the system: the Dashboard is the operator's view of the DN strategy, while the Vault page is the investor/finance view of the whole product.

---

## Lending vs Depeg share address — why it's intentional

The lending strategy and depeg strategy both use wallet `0x0BdFcFbd77c0f3170aC5231480BbB1E45eEBa9ae`. This is intentional:

- **Lending strategy equity** = queries external Postgres NAV DB (HyperEVM ERC4626 + Aave positions). ~$29K.
- **Depeg strategy equity** = reads `pm_account_snapshots` for that address on Hyperliquid native (idle USDC sitting on HL). ~$5K.

These are logically separate positions that happen to live at the same address. The strategies config reflects this:

```json
{
  "strategy_id": "lending",
  "wallets": [],                                      // No HL native tracking
  "config": {"lending_accounts": ["0x0BdF...a9ae"]}   // NAV DB query uses this
},
{
  "strategy_id": "depeg",
  "wallets": [{"label": "depeg", "venue": "hyperliquid", "address": "0x0BdF...a9ae"}]
}
```

**Implication:** Only the depeg strategy appears in `resolve_venue_accounts("hyperliquid")` output for this address. The lending strategy does not — it's a "virtual" wallet that only exists in the lending provider's view.

---

## Troubleshooting

### `WARNING: wallet_label='X' not in any strategy` during `pm.py sync-registry`

Cause: a position in `positions.json` references a wallet_label that isn't defined in any strategy.

Fix:
- If the position is OPEN: add the label to the target strategy's `wallets[]`
- If the position is CLOSED: the warning is informational only, no action needed

### `ValueError: duplicate label 'main' across strategies 'a' and 'b'`

Cause: two strategies declared wallets with the same label.

Fix: rename one of them. Labels must be globally unique.

### Dashboard shows wrong "Total Equity" number

Checklist:
1. Is `HYPERLIQUID_ACCOUNTS_JSON` still set in env? `echo $HYPERLIQUID_ACCOUNTS_JSON` — should be empty.
2. Are DN wallet snapshots fresh?
   ```bash
   .venv/bin/python -c "
   import sqlite3
   con = sqlite3.connect('tracking/db/arbit_v3.db')
   for row in con.execute('SELECT account_id, total_balance, ts FROM pm_account_snapshots ORDER BY ts DESC LIMIT 10'):
       print(row)
   "
   ```
3. Did `pipeline_hourly.py` run? Check `pm_portfolio_snapshots` latest ts.
4. Force recompute: `.venv/bin/python scripts/pipeline_hourly.py --skip-ingest`

### Vault page shows stale strategy equity

Cause: `vault_strategy_snapshots` table not refreshed.

Fix: run `scripts/vault.py recalc` or wait for hourly cron.

### Migration script fails with "invalid address format"

Cause: an address in `strategies.json` is not a valid `0x` + 40 hex chars.

Fix: check the address — must match `^0x[a-fA-F0-9]{40}$`.

---

## Reference files

- `config/strategies.json` — source of truth
- `config/positions.json` — positions, reference wallets by label
- `tracking/position_manager/accounts.py` — `resolve_venue_accounts()`, `get_strategy_wallets()`
- `scripts/pm.py sync-registry` — syncs positions.json into DB
- `scripts/migrate_strategy_wallets.py` — idempotent migration script
- `tracking/vault/providers/` — per-strategy equity providers
- `tracking/pipeline/portfolio.py` — Dashboard portfolio snapshot
- `api/routers/portfolio.py` — `/portfolio/overview` endpoint
````

- [ ] **Step 2: Commit**

```bash
git add docs/runbook-strategy-wallet-ownership.md
git commit -m "docs: add team runbook for strategy wallet ownership"
```

---

### Task 9: End-to-end smoke test on local DB

**Files:** (no file changes — verification only)

- [ ] **Step 1: Run the migration script (full, not dry-run)**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python scripts/migrate_strategy_wallets.py 2>&1 | tail -40
```

Expected: exits with code 0, reports:
- DN total_equity_usd in range $55,000 – $57,000 (alt ≈ $56,486 + main ≈ $89)
- Wallet breakdown shows 2 addresses (alt, main) — NOT depeg

- [ ] **Step 2: Verify the API endpoint**

Start API in background and curl:

```bash
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 > /tmp/api.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8001/portfolio/overview | python3 -m json.tool > /tmp/portfolio_overview.json
cat /tmp/portfolio_overview.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('total_equity_usd:', d.get('total_equity_usd'))
print('accounts:')
for a in d.get('accounts', []):
    print(f'  {a[\"label\"]:15s} {a[\"address\"][:15]}...  \${a[\"equity_usd\"]:,.2f}')
print('fund_utilization.accounts:')
for a in (d.get('fund_utilization') or {}).get('accounts', []):
    print(f'  {a[\"label\"]:15s}  \${a[\"equity_usd\"]:,.2f}  leverage={a[\"leverage\"]}x')
"
kill %1 2>/dev/null || true
```

Expected:
- `total_equity_usd` ≈ $56,575 (DN only)
- `accounts` has exactly 2 entries: `alt` and `main`, NO `depeg`
- `fund_utilization.accounts` has exactly 2 entries, NO duplicate labels

- [ ] **Step 3: Verify vault page numbers**

```bash
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001 > /tmp/api.log 2>&1 &
sleep 3
curl -s http://127.0.0.1:8001/vault/overview 2>&1 | python3 -m json.tool | head -50
kill %1 2>/dev/null || true
```

Expected (approximate — real values depend on market):
- Lending strategy equity ≈ $29,101 (unchanged, external NAV)
- Delta Neutral strategy equity ≈ $56,575 (was $34,223 stale)
- Depeg strategy equity ≈ $5,018 (was $0)

- [ ] **Step 4: Double-run migration — verify idempotent**

```bash
source .arbit_env && unset HYPERLIQUID_ACCOUNTS_JSON && .venv/bin/python scripts/migrate_strategy_wallets.py 2>&1 | tail -10
```

Expected: exit code 0, same total reported, no errors.

- [ ] **Step 5: Run full test suite one more time**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py --ignore=tests/test_manual_cashflow_apr.py 2>&1 | tail -20
```

Expected: all tests pass (except the pre-existing `test_manual_cashflow_apr.py` failure which is unrelated).

- [ ] **Step 6: No-op commit (documentation of verification)**

Skip — no files changed in this task. Task 9 is purely verification.

---

## Self-Review

**1. Spec coverage:**
- ✅ Config model with wallets[] in strategies.json → Task 1
- ✅ accounts.py reads from strategies.json, adds `get_strategy_wallets`, label uniqueness → Task 2
- ✅ DN + Depeg providers prefer address from wallet dict → Task 3
- ✅ `_get_total_equity` filters to DN only → Task 4
- ✅ `_compute_fund_utilization` + `portfolio_overview` + `_account_label` filter → Task 5
- ✅ `.arbit_env` removes HYPERLIQUID_ACCOUNTS_JSON → Task 6
- ✅ Migration script with --dry-run, idempotent → Task 7
- ✅ Team runbook doc → Task 8
- ✅ Smoke test with expected numbers → Task 9

**2. Placeholder scan:** No TBD/TODO. All code blocks are complete.

**3. Type consistency:**
- `get_strategy_wallets()` returns `List[Dict[str, str]]` consistently
- `_STRATEGIES_PATH`, `_CACHE` symbols referenced consistently in tests and module
- `dn_addresses` is a list in Task 4, set in Task 5 — justified because Task 4 uses SQL IN() (order doesn't matter but needs positional params), Task 5 does Python membership check (set is faster). Both correct for context.
- Wallet dict shape `{label, venue, address}` consistent across all tasks.
