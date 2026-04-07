# Decouple Equity Tracking from Position Meta Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the silent failure mode where equity snapshots are skipped when `pm_legs.meta_json` is missing or incorrect.

**Architecture:** Two independent fixes. (1) Remove the `has_managed_legs` guard from `puller.py` so equity is always written for every wallet in `HYPERLIQUID_ACCOUNTS_JSON` — no dependency on DB leg state. (2) Add an explicit warning in `pm.py sync-registry` that fires immediately when a position's `wallet_label` is not in the env accounts JSON, so misconfiguration is caught at sync time rather than silently corrupting equity data.

**Tech Stack:** Python, SQLite, pytest, `tracking/position_manager/puller.py`, `scripts/pm.py`, `tracking/position_manager/accounts.py`.

---

## Root Cause Summary

```
.arbit_env (HYPERLIQUID_ACCOUNTS_JSON)
    ↓
positions.json (wallet_label per leg)
    ↓
pm_legs.meta_json (wallet_label synced by pm.py)    ← bug was here (omitted field)
    ↓
has_managed_legs check in puller.py                 ← bug amplified here (silent skip)
    ↓
pm_account_snapshots written (or not)
```

Break any link → equity silently stale. The fix eliminates the bottom two links as failure points.

---

## File Map

| File | Change |
|------|--------|
| `tracking/position_manager/puller.py` | Remove `and has_managed_legs` from equity write guard; remove unused variable |
| `scripts/pm.py` | Add wallet_label validation after leg upserts in `sync_registry` |
| `tests/test_puller_equity.py` | New: test equity written for wallet with no managed legs |
| `tests/test_pm_validate.py` | New: test sync-registry warns on unknown wallet_label |

---

### Task 1: Always write equity for all env-configured wallets

**Context:** `puller.py` iterates every wallet from `resolve_venue_accounts(venue)`. Currently only writes `pm_account_snapshots` if `has_managed_legs=True`. Removing this condition means equity is always tracked for every wallet in env — even wallets with no open positions.

**Files:**
- Test: `tests/test_puller_equity.py` (create)
- Modify: `tracking/position_manager/puller.py:440-451`

- [ ] **Step 1: Create failing test**

Create `tests/test_puller_equity.py`:

```python
"""Test that equity snapshots are written for all env-configured wallets,
regardless of whether managed legs exist for that wallet.

Run: .venv/bin/python -m pytest tests/test_puller_equity.py -v
"""

import json
import os
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.position_manager.puller import write_account_snapshot, run_pull

_SCHEMA = """
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
  raw_json TEXT, meta_json TEXT, account_id TEXT,
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);
CREATE TABLE pm_account_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  venue TEXT NOT NULL, account_id TEXT NOT NULL, ts INTEGER NOT NULL,
  total_balance REAL, available_balance REAL, margin_balance REAL,
  unrealized_pnl REAL, position_value REAL, raw_json TEXT
);
CREATE TABLE pm_leg_snapshots (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  leg_id TEXT NOT NULL, position_id TEXT, venue TEXT NOT NULL,
  inst_id TEXT NOT NULL, side TEXT NOT NULL, size REAL,
  entry_price REAL, current_price REAL, unrealized_pnl REAL, realized_pnl REAL,
  ts INTEGER NOT NULL, account_id TEXT, raw_json TEXT
);
"""


def _make_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(_SCHEMA)
    return con


def _fake_snapshot(address: str) -> dict:
    return {
        "account_id": address,
        "dex": "",
        "total_balance": 12345.67,
        "available_balance": 10000.0,
        "margin_balance": 12345.67,
        "unrealized_pnl": None,
        "position_value": None,
        "raw_json": {},
    }


def test_equity_written_for_wallet_with_no_managed_legs():
    """Equity snapshot must be written for every wallet in env, even if no
    managed legs exist for that wallet in the DB (e.g. wallet with only
    closed positions, or a cash-only wallet)."""
    con = _make_db()
    # DB has NO open positions at all
    assert con.execute("SELECT COUNT(*) FROM pm_positions").fetchone()[0] == 0

    fake_accounts = {
        "main": "0xMAINADDRESS",
        "alt":  "0xALTADDRESS",
    }
    fake_snapshot_main = _fake_snapshot("0xMAINADDRESS")
    fake_snapshot_alt = _fake_snapshot("0xALTADDRESS")

    with patch("tracking.position_manager.puller.resolve_venue_accounts", return_value=fake_accounts), \
         patch("tracking.position_manager.puller.pull_venue_positions") as mock_pull, \
         patch("tracking.position_manager.puller.load_positions_from_db", return_value=[]), \
         patch("tracking.position_manager.puller.ensure_multi_wallet_columns"):

        call_count = [0]
        def side_effect(venue, **kwargs):
            addr = kwargs.get("address", "")
            snap = fake_snapshot_main if addr == "0xMAINADDRESS" else fake_snapshot_alt
            call_count[0] += 1
            return {"success": True, "account_snapshot": snap, "positions": [], "error": None}

        mock_pull.side_effect = side_effect

        run_pull(
            db_path=Path(":memory:"),
            registry_path=None,
            venues_filter={"hyperliquid"},
            verbose=False,
            _con_override=con,  # inject our in-memory DB
        )

    rows = con.execute("SELECT account_id, total_balance FROM pm_account_snapshots ORDER BY account_id").fetchall()
    account_ids = [r[0] for r in rows]

    assert "0xMAINADDRESS" in account_ids, f"main wallet equity not written — got {account_ids}"
    assert "0xALTADDRESS" in account_ids, f"alt wallet equity not written — got {account_ids}"
    for account_id, balance in rows:
        assert balance == 12345.67, f"Wrong balance for {account_id}: {balance}"
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent
source .arbit_env && .venv/bin/python -m pytest tests/test_puller_equity.py -v 2>&1 | tail -20
```

Expected: test FAILS (equity not written for wallets with no managed legs, OR `_con_override` not supported yet).

- [ ] **Step 3: Add `_con_override` parameter to `run_pull` and remove `has_managed_legs` guard**

Modify `tracking/position_manager/puller.py`.

Find the `run_pull` function signature (around line 310). Add `_con_override=None` parameter:

```python
def run_pull(
    db_path: Path,
    registry_path: Optional[Path] = None,
    venues_filter: Optional[Set[str]] = None,
    verbose: bool = True,
    _con_override: Optional[sqlite3.Connection] = None,
) -> Dict:
```

Find where the connection is opened (around line 395):
```python
    con = connect(db_path)
    ensure_multi_wallet_columns(con)
```
Replace with:
```python
    con = _con_override if _con_override is not None else connect(db_path)
    if _con_override is None:
        ensure_multi_wallet_columns(con)
```

Find lines 440-451 (the `has_managed_legs` block):
```python
            try:
                has_managed_legs = any(
                    leg.get("venue") == venue and leg.get("wallet_label", "main") == wallet_label
                    for mp in positions
                    for leg in mp.get("legs", [])
                )

                account_id = credential or (result["account_snapshot"] or {}).get("account_id", "")

                if result["account_snapshot"] and has_managed_legs:
                    write_account_snapshot(con, venue, result["account_snapshot"], ts_ms)
                    summary["snapshots_written"] += 1
```

Replace with:
```python
            try:
                account_id = credential or (result["account_snapshot"] or {}).get("account_id", "")

                if result["account_snapshot"]:
                    write_account_snapshot(con, venue, result["account_snapshot"], ts_ms)
                    summary["snapshots_written"] += 1
```

- [ ] **Step 4: Run test — verify it PASSES**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_puller_equity.py -v 2>&1 | tail -20
```

Expected: `PASSED`.

- [ ] **Step 5: Run full test suite — verify no regressions**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py -x 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add tracking/position_manager/puller.py tests/test_puller_equity.py
git commit -m "fix(puller): always write equity for all env-configured wallets, remove has_managed_legs guard"
```

---

### Task 2: Fail fast on unknown wallet_label in sync-registry

**Context:** `pm.py sync-registry` should immediately warn if a position's `wallet_label` is not in the corresponding `{VENUE}_ACCOUNTS_JSON`. Currently it silently sets `account_id=None` and continues. The warning must go to stdout so it's visible in the daily run log.

**Files:**
- Test: `tests/test_pm_validate.py` (create)
- Modify: `scripts/pm.py:sync_registry` — after the legs loop, add validation

- [ ] **Step 1: Create failing test**

Create `tests/test_pm_validate.py`:

```python
"""Test that pm.py sync-registry warns when wallet_label is unknown.

Run: .venv/bin/python -m pytest tests/test_pm_validate.py -v
"""

import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))


_SCHEMA = """
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
  raw_json TEXT, meta_json TEXT, account_id TEXT,
  FOREIGN KEY (position_id) REFERENCES pm_positions(position_id)
);
"""

_REGISTRY_KNOWN = [
    {
        "position_id": "pos_test_HYPE",
        "strategy_type": "SPOT_PERP",
        "base": "HYPE",
        "status": "OPEN",
        "amount_usd": 1000.0,
        "legs": [
            {"leg_id": "pos_test_HYPE_SPOT", "venue": "hyperliquid", "inst_id": "HYPE/USDC", "side": "LONG", "qty": 10.0, "wallet_label": "alt"},
            {"leg_id": "pos_test_HYPE_PERP", "venue": "hyperliquid", "inst_id": "HYPE", "side": "SHORT", "qty": 10.0, "wallet_label": "alt"},
        ],
    }
]

_REGISTRY_UNKNOWN = [
    {
        "position_id": "pos_test_HYPE",
        "strategy_type": "SPOT_PERP",
        "base": "HYPE",
        "status": "OPEN",
        "amount_usd": 1000.0,
        "legs": [
            {"leg_id": "pos_test_HYPE_SPOT", "venue": "hyperliquid", "inst_id": "HYPE/USDC", "side": "LONG", "qty": 10.0, "wallet_label": "unknown_wallet"},
            {"leg_id": "pos_test_HYPE_PERP", "venue": "hyperliquid", "inst_id": "HYPE", "side": "SHORT", "qty": 10.0, "wallet_label": "unknown_wallet"},
        ],
    }
]


def _run_sync(registry: list, env_accounts: dict) -> str:
    """Run sync_registry with given registry and accounts env, return captured stdout."""
    import scripts.pm as pm_mod

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(registry, f)
        registry_path = Path(f.name)

    con = sqlite3.connect(":memory:")
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(_SCHEMA)

    env_json = json.dumps(env_accounts)
    captured = io.StringIO()

    with patch.dict(os.environ, {"HYPERLIQUID_ACCOUNTS_JSON": env_json}), \
         patch("sys.stdout", captured):
        pm_mod.sync_registry(con, registry_path)

    registry_path.unlink(missing_ok=True)
    return captured.getvalue()


def test_no_warning_when_wallet_label_known():
    """No WARNING lines when all wallet_labels exist in env accounts."""
    output = _run_sync(
        _REGISTRY_KNOWN,
        {"main": "0xMAIN", "alt": "0xALT"},
    )
    warnings = [line for line in output.splitlines() if "WARNING" in line]
    assert warnings == [], f"Unexpected warnings: {warnings}"


def test_warning_when_wallet_label_unknown():
    """A WARNING line is printed when wallet_label is not in HYPERLIQUID_ACCOUNTS_JSON."""
    output = _run_sync(
        _REGISTRY_UNKNOWN,
        {"main": "0xMAIN", "alt": "0xALT"},
    )
    warnings = [line for line in output.splitlines() if "WARNING" in line]
    assert len(warnings) > 0, f"Expected WARNING about 'unknown_wallet', got no warnings.\nOutput:\n{output}"
    combined = " ".join(warnings)
    assert "unknown_wallet" in combined, f"WARNING should mention 'unknown_wallet': {combined}"
    assert "hyperliquid" in combined.lower(), f"WARNING should mention venue: {combined}"
```

- [ ] **Step 2: Run test — verify it FAILS**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_pm_validate.py -v 2>&1 | tail -20
```

Expected: `test_warning_when_wallet_label_unknown` FAILS (no warning printed).

- [ ] **Step 3: Add validation in `scripts/pm.py:sync_registry`**

Find the end of the `for leg in p.legs:` loop in `sync_registry` (around line 165, after `n_legs += 1`). Add a validation block immediately after the legs loop (still inside `for p in positions:`):

```python
        # Validate wallet_labels: warn immediately if label not in env accounts
        _venue_accounts_cache: Dict[str, Dict[str, str]] = {}
        for leg in p.legs:
            if p.status not in ("OPEN", "PAUSED", "EXITING"):
                continue
            if leg.venue not in _venue_accounts_cache:
                _venue_accounts_cache[leg.venue] = resolve_venue_accounts(leg.venue)
            accounts = _venue_accounts_cache[leg.venue]
            label = leg.wallet_label or "main"
            if accounts and label not in accounts:
                known = sorted(accounts.keys())
                print(
                    f"WARNING: {p.position_id}/{leg.leg_id}: wallet_label='{label}' not in "
                    f"{leg.venue.upper()}_ACCOUNTS_JSON (known labels: {known}). "
                    f"This wallet's equity will not be tracked until fixed."
                )
```

Also add the import at the top of `sync_registry` (or top of file if not already present):
```python
from tracking.position_manager.accounts import resolve_venue_accounts
```

Check if `resolve_venue_accounts` is already imported in `scripts/pm.py`:
```bash
grep -n "resolve_venue_accounts" scripts/pm.py
```
If not present, add this import near the top of the file (after other imports):
```python
from tracking.position_manager.accounts import resolve_venue_accounts
```

- [ ] **Step 4: Run test — verify it PASSES**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_pm_validate.py -v 2>&1 | tail -20
```

Expected: both tests PASS.

- [ ] **Step 5: Manual smoke test — run sync-registry on current positions.json**

```bash
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
```

Expected: no WARNING lines (all wallet_labels are "alt" and "alt" is in HYPERLIQUID_ACCOUNTS_JSON). Output ends with: `OK: synced registry -> 11 positions, 25 legs`

- [ ] **Step 6: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v --ignore=tests/test_felix_auth.py --ignore=tests/test_felix_private.py -x 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add scripts/pm.py tests/test_pm_validate.py
git commit -m "fix(pm): warn on unknown wallet_label during sync-registry to catch misconfiguration early"
```

---

## Self-Review

**Spec coverage:**
- ✅ Equity always written for all env-configured wallets → Task 1
- ✅ Immediate warning on unknown wallet_label → Task 2
- ✅ Tests for both → Tasks 1 & 2
- ✅ No regression → both tasks run full suite

**Placeholder scan:** None found. All code blocks are complete and runnable.

**Type consistency:**
- `run_pull` parameter `_con_override: Optional[sqlite3.Connection]` — matches SQLite type used throughout
- `_fake_snapshot` returns same shape as real `fetch_account_snapshot` output
- `_run_sync` pattern matches existing test patterns (in-memory DB, tempfile registry)

**What this does NOT fix:**
- The `meta_json` fix for `wallet_label` in `scripts/pm.py` (line ~158) is already done in the previous session and committed. This plan builds on top of that.
- This plan does not change the equity_config.json or builder_dex fetching — that is already correct.
