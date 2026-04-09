# DN Equity — Config-Driven Only (Remove Felix) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove Felix wallet from Delta Neutral equity calculation so DN total equity only includes wallets defined in `strategies.json` under `delta_neutral.wallets`.

**Architecture:** Three surgical removals — (1) `DeltaNeutralProvider.get_equity()` in `delta_neutral.py`, (2) `get_delta_neutral_equity_account_ids()` in `accounts.py`, (3) Felix label fallback in `api/routers/portfolio.py`. Tests updated to assert Felix is excluded. No schema changes.

**Tech Stack:** Python, SQLite, pytest

---

## File Map

| File | Change |
|------|--------|
| `tracking/vault/providers/delta_neutral.py` | Remove `_felix_open_leg_notional_usd()` + Felix injection block (lines 75–101) + Felix import |
| `tracking/position_manager/accounts.py` | Remove Felix injection from `get_delta_neutral_equity_account_ids()` (lines 184–187) + update docstring |
| `api/routers/portfolio.py` | Remove Felix label fallback in `_account_label()` (lines 328–332) |
| `tests/test_portfolio_dn_filter.py` | Replace Felix-inclusion test with Felix-exclusion test |
| `tests/test_accounts_strategies.py` | Replace Felix-merge tests with Felix-exclusion tests |
| `docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md` | Add superseded notice at top |

---

## Task 1: Update `accounts.py` — remove Felix from `get_delta_neutral_equity_account_ids()`

**Files:**
- Modify: `tracking/position_manager/accounts.py:159-189`
- Test: `tests/test_accounts_strategies.py`

- [ ] **Step 1: Write the failing tests first**

Replace the two Felix tests at lines ~206–219 in `tests/test_accounts_strategies.py`:

```python
def test_get_delta_neutral_equity_account_ids_excludes_felix(tmp_strategies, monkeypatch):
    """FELIX_WALLET_ADDRESS set in env must NOT appear in DN account ids."""
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xFELIX")
    ids = accounts_mod.get_delta_neutral_equity_account_ids()
    assert "0xALT" in ids
    assert "0xMAIN" in ids
    assert "0xfelix" not in ids
    assert "0xFELIX" not in ids


def test_get_delta_neutral_equity_account_ids_no_felix_when_env_unset(tmp_strategies, monkeypatch):
    """Without FELIX_WALLET_ADDRESS, DN ids are exactly the strategy wallet addresses."""
    monkeypatch.delenv("FELIX_WALLET_ADDRESS", raising=False)
    ids = accounts_mod.get_delta_neutral_equity_account_ids()
    assert ids == ["0xALT", "0xMAIN"]
```

Remove the old tests `test_get_delta_neutral_equity_account_ids_merges_felix` and `test_get_delta_neutral_equity_account_ids_dedupes_felix_with_strategy_wallet` (lines ~206–219).

- [ ] **Step 2: Run tests to confirm they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_accounts_strategies.py::test_get_delta_neutral_equity_account_ids_excludes_felix tests/test_accounts_strategies.py::test_get_delta_neutral_equity_account_ids_no_felix_when_env_unset -v
```

Expected: Both FAIL — current implementation includes Felix.

- [ ] **Step 3: Remove Felix injection from `get_delta_neutral_equity_account_ids()` in `accounts.py`**

Replace the entire function (lines 159–189) with:

```python
def get_delta_neutral_equity_account_ids() -> List[str]:
    """Account ids used for delta-neutral equity (``pm_account_snapshots`` / DN totals).

    Returns every non-empty ``address`` from ``get_strategy_wallets("delta_neutral")``.
    De-duplicates by lower-case so the same address is not double-counted.
    """
    try:
        dn = get_strategy_wallets("delta_neutral")
    except KeyError:
        dn = []

    seen_lower: Set[str] = set()
    out: List[str] = []

    for w in dn:
        a = (w.get("address") or "").strip()
        if not a:
            continue
        key = a.lower()
        if key in seen_lower:
            continue
        seen_lower.add(key)
        out.append(a)

    return out
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_accounts_strategies.py::test_get_delta_neutral_equity_account_ids_excludes_felix tests/test_accounts_strategies.py::test_get_delta_neutral_equity_account_ids_no_felix_when_env_unset -v
```

Expected: Both PASS.

- [ ] **Step 5: Run full accounts test suite to check for regressions**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_accounts_strategies.py -v
```

Expected: All pass.

- [ ] **Step 6: Commit**

```bash
git add tracking/position_manager/accounts.py tests/test_accounts_strategies.py
git commit -m "fix(accounts): remove Felix from get_delta_neutral_equity_account_ids

DN equity account ids now strictly reflect strategies.json wallets.
Felix belongs to Lending/Depeg, not Delta Neutral."
```

---

## Task 2: Update `delta_neutral.py` — remove Felix injection block

**Files:**
- Modify: `tracking/vault/providers/delta_neutral.py`
- Test: `tests/test_puller_equity.py` (verify Felix pull still works separately)

- [ ] **Step 1: Remove `_felix_open_leg_notional_usd()` function and Felix block from `delta_neutral.py`**

Replace the entire file content with:

```python
"""Delta Neutral equity provider — reads pm_account_snapshots for strategy wallets."""

from __future__ import annotations

import json
import sqlite3
import time

from tracking.position_manager.accounts import resolve_venue_accounts

from .base import EquityProvider, StrategyEquity


class DeltaNeutralProvider(EquityProvider):
    """Reads DN strategy equity from existing pm_account_snapshots.

    Only includes wallets defined in strategies.json under delta_neutral.wallets.
    Felix and other external wallets are excluded — they belong to other strategies.
    """

    def get_equity(self, strategy: dict, db: sqlite3.Connection) -> StrategyEquity:
        wallets = json.loads(strategy["wallets_json"]) if strategy["wallets_json"] else []

        total_equity = 0.0
        breakdown: dict = {}
        counted_lower: set[str] = set()

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

            counted_lower.add(str(address).lower())

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

- [ ] **Step 2: Run the puller equity test to confirm Felix pull still works (unaffected)**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_puller_equity.py -v
```

Expected: All pass — Felix snapshot pull is in `puller.py`, not `delta_neutral.py`.

- [ ] **Step 3: Commit**

```bash
git add tracking/vault/providers/delta_neutral.py
git commit -m "fix(delta-neutral): remove Felix env-var injection from DN equity provider

DeltaNeutralProvider now strictly reads from strategies.json wallets.
Felix belongs to Lending/Depeg strategies."
```

---

## Task 3: Update `api/routers/portfolio.py` — remove Felix label fallback

**Files:**
- Modify: `api/routers/portfolio.py:328-332`

- [ ] **Step 1: Remove the Felix label fallback block from `_account_label()`**

In `api/routers/portfolio.py`, replace the `_account_label` function (lines 307–334):

```python
def _account_label(account_id: str) -> str:
    """Derive a human-friendly label from account_id.

    Reads from config/strategies.json via _load_strategies_cached. Falls back to
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

- [ ] **Step 2: Commit**

```bash
git add api/routers/portfolio.py
git commit -m "fix(portfolio): remove Felix label fallback from _account_label

Felix is no longer part of DN wallet breakdown, so the fallback label
resolution for the Felix env address is no longer needed."
```

---

## Task 4: Update `test_portfolio_dn_filter.py` — replace Felix-inclusion test

**Files:**
- Modify: `tests/test_portfolio_dn_filter.py:122-139`

- [ ] **Step 1: Replace `test_get_total_equity_includes_felix_when_env_configured` with exclusion test**

Replace lines 122–139 with:

```python
def test_get_total_equity_excludes_felix_even_when_env_set(tmp_strategies, monkeypatch):
    """FELIX_WALLET_ADDRESS in env must NOT be included in DN equity totals."""
    monkeypatch.setenv("FELIX_WALLET_ADDRESS", "0xFELIX")
    con = _make_db()
    con.executemany(
        "INSERT INTO pm_account_snapshots(venue, account_id, ts, total_balance) VALUES (?, ?, ?, ?)",
        [
            ("hyperliquid", "0xALT", 1000, 50000.0),
            ("hyperliquid", "0xMAIN", 1000, 500.0),
            ("felix", "0xfelix", 1000, 999.0),  # must NOT be included
        ],
    )
    con.commit()

    result = portfolio_mod._get_total_equity(con)

    assert result["total_equity_usd"] == 50500.0  # alt + main only, no felix
    assert "0xfelix" not in result["equity_by_account"]
    assert "0xFELIX" not in result["equity_by_account"]
```

- [ ] **Step 2: Run the full dn_filter test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_portfolio_dn_filter.py -v
```

Expected: All pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_portfolio_dn_filter.py
git commit -m "test(portfolio): assert Felix excluded from DN equity totals

Replaces the old Felix-inclusion assertion with the correct
Felix-exclusion assertion per updated business logic."
```

---

## Task 5: Run full test suite + mark old spec as superseded

**Files:**
- Test: all test files
- Modify: `docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md`

- [ ] **Step 1: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/ -v
```

Expected: All pass. If any test fails due to Felix references, fix inline before proceeding.

- [ ] **Step 2: Add superseded notice to old spec**

Prepend to `docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md`:

```markdown
> **SUPERSEDED** by `docs/superpowers/specs/2026-04-09-dn-equity-config-driven-design.md` (2026-04-09).
> Felix is NOT part of Delta Neutral strategy — it belongs to Lending/Depeg.
> The Felix-in-DN approach described below was implemented then reverted.

---

```

- [ ] **Step 3: Final commit**

```bash
git add docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md
git commit -m "docs: mark 2026-04-07 felix-equity spec as superseded"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| Remove `_felix_open_leg_notional_usd()` | Task 2 |
| Remove Felix injection block in `delta_neutral.py` | Task 2 |
| Remove Felix import in `delta_neutral.py` | Task 2 |
| Remove Felix injection from `get_delta_neutral_equity_account_ids()` | Task 1 |
| Update docstring | Task 1 |
| Remove Felix label fallback in `api/routers/portfolio.py` | Task 3 |
| Replace Felix-inclusion test in `test_portfolio_dn_filter.py` | Task 4 |
| Update `test_accounts_strategies.py` Felix tests | Task 1 |
| Add superseded notice to old spec | Task 5 |
| Felix pull still runs (puller.py untouched) | Verified in Task 2 Step 2 |

All spec requirements covered. No placeholders. Type/method names consistent across all tasks.
