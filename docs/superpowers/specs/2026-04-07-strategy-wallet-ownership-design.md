# Strategy Wallet Ownership — Design Spec

**Date:** 2026-04-07
**Status:** Approved for implementation
**Scope:** HL wallet config refactor. Felix ingestion is OUT OF SCOPE (tracked separately).

---

## Problem

The current wallet config is split across two files with fragile implicit coupling:

1. `.arbit_env` → `HYPERLIQUID_ACCOUNTS_JSON='{"main":"0x...","alt":"0x...","depeg":"0x...","lending":"0x..."}'` — defines wallet labels → addresses.
2. `config/strategies.json` → each strategy references `wallet_label` that must exist in the env var.
3. `config/positions.json` → each leg references the same `wallet_label`.

This causes real bugs:

- **Dashboard "Total Equity" card shows $66,612** (sum of ALL HL wallets including lending/depeg), but logically it should only be the Delta Neutral portfolio total ≈ $56,575.
- **Vault Delta Neutral row shows stale $34,223** while the actual alt wallet is $56,486 — caused by a silent data loss bug already fixed in commit `989b390` but the stale row persists until recompute.
- **Vault Depeg row shows $0** while the depeg wallet actually holds $5,018 in idle USDC.
- **Fund Utilization shows duplicate "depeg" rows** because `lending` and `depeg` share address `0x0BdFcFbd...a9ae` and the label resolver returns "depeg" for both.
- **Adding a new wallet tag to `HYPERLIQUID_ACCOUNTS_JSON`** accidentally includes it in equity aggregations without anyone's intent — no ownership model.

## Goals

1. **Single source of truth** for wallet ownership: `config/strategies.json`.
2. **Dashboard "Total Equity"** represents Delta Neutral portfolio total only (DN wallets).
3. **Vault page** correctly shows per-strategy equity: Lending (NAV DB), DN (HL alt+main wallets), Depeg (HL depeg wallet).
4. **No duplicate rows** in Fund Utilization (only DN wallets shown).
5. **Backward-compatible bootstrap** — legacy env vars (`HYPERLIQUID_ADDRESS`) still work as fallback if `strategies.json.wallets` is empty.
6. **Idempotent migration script** to roll out safely on server.

## Non-Goals

- Schema change to DB (no migration of tables).
- Felix venue ingestion (separate spec).
- Changing `config/positions.json` format (still uses `wallet_label`).
- Changing how Lending strategy queries external NAV DB.

---

## Architecture

### Config model

`config/strategies.json` is the single source of truth for:
- Strategy definitions
- Which wallets belong to which strategy
- Wallet addresses per venue

```json
{
  "vault_name": "OpenClaw Vault",
  "strategies": [
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
    },
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
    }
  ]
}
```

**Key decisions:**

- `main` wallet belongs to `delta_neutral` strategy (alongside `alt`). This covers historical CLOSED positions (`pos_xyz_GOOGL`, `pos_xyz_MSFT`, etc.) that use `wallet_label: "main"` — those stay as-is, no data deletion.
- `lending.wallets` is an **empty array**. The lending strategy reads equity from an external Postgres NAV DB (HyperEVM ERC4626 + Aave positions), not from HL native equity. The address `0x0BdF...` is stored in `config.lending_accounts` to query the NAV DB, which keeps the existing lending provider behavior untouched.
- `depeg.wallets` owns address `0x0BdFcFbd...` for HL native equity only (~$5,018 idle USDC). This is logically separate from the lending strategy's NAV even though they share the same address.
- **Labels must be globally unique** across all strategies' `wallets[]` (validated on load).
- `.arbit_env` drops `HYPERLIQUID_ACCOUNTS_JSON` entirely. Legacy `HYPERLIQUID_ADDRESS` remains as a fallback-only env var for bootstrap (fresh clones with empty `strategies.json.wallets`).

### Data flow after refactor

```
config/strategies.json  (source of truth)
        │
        ├─► resolve_venue_accounts("hyperliquid")
        │      → {"alt":"0x3c2c...", "main":"0x4Fde...", "depeg":"0x0BdF..."}
        │         (union of all strategies.wallets filtered by venue)
        │
        ├─► get_strategy_wallets("delta_neutral")
        │      → [{"label":"alt","address":"0x3c2c..."}, {"label":"main","address":"0x4Fde..."}]
        │
        ▼
puller.py iterate wallets → write pm_account_snapshots (keyed by address)
        │
        ├─► pipeline_hourly.portfolio_snapshot
        │      (sum equity WHERE account_id IN get_strategy_wallets("delta_neutral"))
        │      → pm_portfolio_snapshots.total_equity_usd = DN wallets only
        │
        ├─► DeltaNeutralProvider → reads strategy.wallets → sum ≈ $56,575
        │
        ├─► DepegProvider → reads strategy.wallets → sum ≈ $5,018
        │
        └─► LendingProvider → reads external NAV DB via config.lending_accounts → $29,101
```

### Numbers before/after (using current live data)

| Metric | Before | After | Source |
|--------|--------|-------|--------|
| Dashboard "Total Equity" | $66,612 (all HL wallets) | **$56,575** (alt + main) | `pm_portfolio_snapshots.total_equity_usd` filtered to DN |
| Vault Delta Neutral | $34,223 (stale) | **$56,575** | DN provider sums DN wallets |
| Vault Depeg | $0 | **$5,018** | Depeg provider reads HL depeg address |
| Vault Lending | $29,101 | **$29,101** (unchanged) | External NAV DB |
| Vault Total | $63,324 | **$90,694** = 56,575 + 5,018 + 29,101 | Sum of strategies |
| Fund Utilization rows | 4 (depeg×2, alt, main) | **2** (alt, main) | Filter to DN wallets only |

---

## Components

### Unit: `tracking/position_manager/accounts.py`

**Responsibility:** Resolve wallet addresses from `config/strategies.json` with legacy env fallback.

**Interface:**

```python
def resolve_venue_accounts(venue: str) -> Dict[str, str]:
    """Read config/strategies.json → return {label: address} for this venue.

    Iterates all strategies in strategies.json, collects wallets where
    wallet.venue == venue, returns {label: address}.

    Fallback: if strategies.json has no wallets for venue, falls back to
    legacy env vars (HYPERLIQUID_ADDRESS, etc.) returning {"main": address}.
    """

def get_strategy_wallets(strategy_id: str) -> List[Dict[str, str]]:
    """NEW: return [{label, venue, address}, ...] for the given strategy.

    Raises KeyError if strategy_id not found.
    Returns empty list if strategy has no wallets (e.g. lending).
    """

def _load_strategies_cached() -> List[dict]:
    """Load and cache strategies.json. Cache is invalidated on file mtime change."""
```

**Internal:** Reads `config/strategies.json` once per process with mtime-based cache invalidation. Validates labels globally unique on load — raises `ValueError` with clear message if duplicates found.

**Removed:** `_LEGACY_ENV` dict's `HYPERLIQUID_ACCOUNTS_JSON` handling. Other legacy per-venue single-address fallbacks kept.

### Unit: `tracking/position_manager/puller.py`

**No logic change.** `puller.py` already calls `resolve_venue_accounts()` and iterates the returned labels. Once `resolve_venue_accounts` reads from `strategies.json`, the puller automatically pulls equity for exactly the wallets in strategies.json.

### Unit: `tracking/pipeline/portfolio.py`

**Responsibility:** Compute portfolio-level aggregation.

**Change:** `_get_total_equity()` now filters `pm_account_snapshots` to only include addresses owned by the `delta_neutral` strategy.

**New interface:**

```python
def _get_total_equity(con: sqlite3.Connection) -> Dict[str, Any]:
    """Return DN-only equity summary.

    Reads get_strategy_wallets("delta_neutral") → list of addresses →
    SELECT total_balance FROM pm_account_snapshots WHERE account_id IN (...)
    """
```

`equity_by_account` still returns per-account breakdown, but only DN accounts.

### Unit: `tracking/vault/providers/delta_neutral.py`

**No logic change.** Already reads `strategy["wallets_json"]` and resolves label → address. The wallets now come from `strategies.json` directly (with `address` field already populated), so the resolver still works but prefers the address from the strategy definition if present. Minor change: if wallet dict contains `address` field, skip `resolve_venue_accounts()` lookup.

```python
for wallet in wallets:
    address = wallet.get("address")
    if not address:
        label = wallet.get("wallet_label") or wallet.get("label", "main")
        venue = wallet.get("venue", "hyperliquid")
        accounts = resolve_venue_accounts(venue)
        address = accounts.get(label)
    if not address:
        continue
    # ... same as before
```

### Unit: `tracking/vault/providers/depeg.py`

Same change as `delta_neutral.py` (prefer `address` from strategy wallet dict).

### Unit: `tracking/vault/registry.py`

**Change:** When loading strategies into `vault_strategies` table, serialize `wallets` array to `wallets_json` column. The `wallets` array now contains dicts with `{label, venue, address}`. The existing `wallets_json` column stores the full array as-is — providers can read it directly.

### Unit: `api/routers/portfolio.py` — `_compute_fund_utilization()`

**Responsibility:** Fund utilization computation for dashboard.

**Change:** Filter `acct_detail_rows` to only include addresses owned by `delta_neutral` strategy.

```python
dn_addresses = {w["address"] for w in get_strategy_wallets("delta_neutral")}
acct_detail_rows = [r for r in acct_detail_rows if r["account_id"] in dn_addresses]
```

This fixes the duplicate "depeg" issue automatically because lending/depeg addresses are no longer in the filter.

### Unit: `scripts/pm.py` — `sync_registry()`

**No change.** Already calls `resolve_venue_accounts()` for validation (from Task 2 of previous session). Automatically picks up the new source.

### Unit: `config/strategies.json`

Add `wallets[]` array to each strategy with `{label, venue, address}` dicts per section above. Lending's `wallets[]` remains empty.

### Unit: `.arbit_env` and `.arbit_env.example`

Remove `HYPERLIQUID_ACCOUNTS_JSON`. Keep `HYPERLIQUID_ADDRESS` as commented-out legacy fallback example.

### Unit: `scripts/migrate_strategy_wallets.py` (NEW)

**Responsibility:** Idempotent migration script to roll out safely on server.

**Interface:**

```
Usage: python scripts/migrate_strategy_wallets.py [--dry-run] [--skip-recompute]
```

**Steps:**

1. **VALIDATE strategies.json**
   - Load `config/strategies.json`
   - Each strategy's `wallets[]` entries have `{label, venue, address}`
   - Labels globally unique across all strategies
   - Addresses match `^0x[a-fA-F0-9]{40}$` format
   - On failure: print error with specific strategy/label/reason, exit 1

2. **VALIDATE env**
   - Check if `HYPERLIQUID_ACCOUNTS_JSON` still set in env
   - If yes, parse it and compare with `strategies.json` addresses
   - Print mismatches with "WARNING:" prefix
   - Print "Remove HYPERLIQUID_ACCOUNTS_JSON from .arbit_env after verifying"

3. **VALIDATE positions.json**
   - Load `config/positions.json`
   - For each leg, resolve `wallet_label` via new `resolve_venue_accounts`
   - CLOSED positions with unresolvable label → print "INFO: CLOSED position X uses label Y which has no current mapping — historical data preserved"
   - OPEN/PAUSED/EXITING positions with unresolvable label → print "FAIL: ..." and exit 1

4. **SYNC REGISTRY** (skip if `--dry-run`)
   - Call `scripts.pm.sync_registry(con, 'config/positions.json')`
   - This updates `pm_legs.meta_json` with correct `wallet_label` and `account_id`

5. **REFRESH snapshots** (skip if `--dry-run`)
   - Call `tracking.position_manager.puller.run_pull(db_path, venues_filter={"hyperliquid"})`
   - Writes fresh rows to `pm_account_snapshots`

6. **RECOMPUTE portfolio snapshot** (skip if `--dry-run` or `--skip-recompute`)
   - Call `tracking.pipeline.portfolio.compute_portfolio_snapshot(con)`
   - Writes fresh row to `pm_portfolio_snapshots` with DN-only total

7. **RECOMPUTE vault snapshots** (skip if `--dry-run` or `--skip-recompute`)
   - Call `scripts.vault.recalc_all()` equivalent
   - Refreshes `vault_strategy_snapshots` and `vault_snapshots`

8. **REPORT**
   - Print before/after table for each strategy
   - Print new Vault total
   - Exit 0 on success

**Idempotency:** Running twice produces the same state. No deletes, only inserts/upserts. Old rows in `pm_account_snapshots` are preserved (keyed by `(account_id, ts)`).

### Unit: `docs/runbook-strategy-wallet-ownership.md` (NEW)

**Responsibility:** Team-facing human-readable doc explaining the new data flow.

**Structure (1–2 pages):**

1. **TL;DR** — 3–4 bullets: single source of truth is `strategies.json`, env var removed, Dashboard "Total Equity" = DN portfolio only, Vault Total = sum of strategies.

2. **Before & After diagram** — two config blocks showing the old (env + strategies.json with labels) vs new (strategies.json with addresses inline).

3. **How to add a new wallet**:
   ```
   1. Edit config/strategies.json → append {label, venue, address} to the target strategy's wallets[]
   2. Run: .venv/bin/python scripts/pm.py sync-registry
   3. Run: .venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
   ```

4. **How to add a new strategy**: template + required fields + where providers live.

5. **"Dashboard Total Equity" explained** — DN portfolio total, not all HL wallets. Points to Vault page for cross-strategy view.

6. **Lending vs Depeg share address** — explanation of why this is intentional: two different equity sources (NAV DB vs HL native), logically separate.

7. **Troubleshooting**:
   - `WARNING: wallet_label='X' not in any strategy` → add X to a strategy's wallets[] OR mark position CLOSED
   - `ValueError: duplicate label 'main' across strategies` → labels must be globally unique
   - Equity number doesn't match expectation → run `pull_positions_v3.py` then `pipeline_hourly.py --skip-ingest`
   - Vault page shows stale number → run `scripts/vault.py recalc`

8. **Reference files** — links to `strategies.json`, `positions.json`, `pm.py`, `migrate_strategy_wallets.py`, `accounts.py`.

---

## Testing

### Unit tests

- **`tests/test_accounts_strategies.py` (new)**
  - `test_resolve_venue_accounts_reads_from_strategies_json` — verify label→address map matches strategies.json
  - `test_resolve_venue_accounts_falls_back_to_env` — fresh bootstrap case
  - `test_get_strategy_wallets_returns_only_own_wallets` — delta_neutral returns alt+main, not depeg
  - `test_duplicate_labels_rejected` — ValueError on load
  - `test_lending_strategy_returns_empty_wallets` — empty wallets array handled

- **`tests/test_portfolio_dn_filter.py` (new)**
  - `test_portfolio_total_equity_only_dn_wallets` — pm_account_snapshots has 3 rows (alt, main, depeg), total returns only alt+main sum

- **`tests/test_migrate_script.py` (new)**
  - `test_migrate_dry_run_reports_expected_changes` — run with `--dry-run`, no DB writes, correct report
  - `test_migrate_idempotent` — run twice, same final state
  - `test_migrate_fails_on_duplicate_labels` — exit 1 with clear error

### Smoke tests (manual, after migration runs on server)

- `curl http://localhost:8000/portfolio/overview` → `total_equity_usd` ≈ $56,575
- `curl http://localhost:8000/vault/overview` → DN equity ≈ $56,575, Depeg ≈ $5,018, Lending ≈ $29,101
- Dashboard UI Fund Utilization shows 2 rows (alt, main)
- Dashboard UI Wallet Breakdown shows alt, main (depeg wallet moved out, since it's not in DN)

---

## Rollout

**Pre-deploy:**
1. Merge PR on feature branch → main after code review.
2. CI runs full test suite (including new tests).

**Server deploy:**
```bash
cd /home/node/.openclaw/workspace-harmonix-delta-neutral
git pull

# 1. Dry-run migration (validate only, no writes)
source .arbit_env
.venv/bin/python scripts/migrate_strategy_wallets.py --dry-run

# 2. Manually remove HYPERLIQUID_ACCOUNTS_JSON from .arbit_env
vim .arbit_env
source .arbit_env

# 3. Apply migration
.venv/bin/python scripts/migrate_strategy_wallets.py

# 4. Verify
.venv/bin/python scripts/pm.py list
curl http://localhost:8000/portfolio/overview | jq '.total_equity_usd'
curl http://localhost:8000/vault/overview | jq '.strategies'
```

**Rollback:**
1. `git revert` the deployment commit
2. Restore `HYPERLIQUID_ACCOUNTS_JSON` in `.arbit_env`
3. `source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py --skip-ingest`
4. `scripts/vault.py recalc` if needed
5. Old rows in `pm_account_snapshots` and `pm_portfolio_snapshots` were not deleted — querying by `ORDER BY ts DESC` will pick up the old behavior's snapshots as the new latest.

---

## Open Questions

None. Decisions locked in:
- Approach: A (addresses directly in strategies.json)
- Position reference: A (keep `wallet_label`, unique globally)
- Felix scope: excluded
- "main" label: added to delta_neutral for historical CLOSED positions
- Migration script: required, idempotent, with `--dry-run` flag
- Team doc: required as deliverable
