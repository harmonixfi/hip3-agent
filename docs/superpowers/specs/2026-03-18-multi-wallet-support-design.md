# Multi-Wallet Support for All Venues — PM v3

**Date:** 2026-03-18
**Status:** Approved

---

## Problem Statement

The position manager currently supports only one wallet/account per venue, configured via single environment variables (`HYPERLIQUID_ADDRESS`, `PARADEX_ACCOUNT_ADDRESS`, etc.). This causes:

- **Missing positions**: Legs on unconfigured wallets produce stale/empty snapshots.
- **Misleading healthcheck/reports**: Open positions appear missing.
- **Collision risk**: Two wallets with same `(inst_id, side)` on the same venue would get wrong attribution.

We need first-class multi-wallet support across all venues in a single DB/workspace.

---

## Current State

### Already account-aware
- `pm_account_snapshots` — has `account_id` column with `(venue, account_id, ts)` index
- `pm_cashflows` — has mandatory `account_id` field with index
- Connectors return `account_id` in `fetch_account_snapshot()`

### Account-unaware (the gap)
- `pm_legs` — no `account_id` column
- `pm_leg_snapshots` — no `account_id` column
- `pm_positions` — no `account_id` (intentional — positions can span wallets via legs)
- Registry (`LegConfig`) — no `wallet_label` field
- Puller mapping — uses `(inst_id, side)` only, one connector per venue
- Connector init — reads single address from env, no override support

---

## Design

### 1. Configuration Layer

**New env var pattern** — per venue:
```bash
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"0xabc...","alt":"0xdef..."}'
export PARADEX_ACCOUNTS_JSON='{"main":"0x123..."}'
```

**Resolution logic** (shared helper):
1. If `{VENUE}_ACCOUNTS_JSON` is set → parse as `Dict[str, str]` (label → address/credential)
2. Else → fall back to legacy single env var with label `"main"`:
   - Hyperliquid: `HYPERLIQUID_ADDRESS` or `ETHEREAL_ACCOUNT_ADDRESS`
   - Paradex: `PARADEX_ACCOUNT_ADDRESS`
   - etc.
3. `HYPERLIQUID_DEX` remains single-valued, applied to all wallets.

### 2. Registry Changes

Add optional field to `LegConfig` dataclass:
```python
wallet_label: Optional[str] = None
```

- If not provided, defaults to `"main"`.
- Freeform string — must match a key in the venue's accounts JSON.

**Example `positions.json` leg:**
```json
{
  "leg_id": "pos_xyz_ORCL_PERP",
  "venue": "hyperliquid",
  "inst_id": "xyz:ORCL",
  "side": "SHORT",
  "qty": 55.774,
  "wallet_label": "alt"
}
```

### 3. DB Schema Changes

**Add column** to `pm_legs`:
```sql
ALTER TABLE pm_legs ADD COLUMN account_id TEXT;
```

**Add column** to `pm_leg_snapshots`:
```sql
ALTER TABLE pm_leg_snapshots ADD COLUMN account_id TEXT;
```

**Add index**:
```sql
CREATE INDEX IF NOT EXISTS idx_pm_leg_snapshots_account ON pm_leg_snapshots(account_id, leg_id);
```

**Migration**: Auto-migrate with `try/except` for "column already exists" — run in puller or db_sync entry point.

**No changes** to `pm_positions` (positions span wallets via legs), `pm_account_snapshots` (already has `account_id`), `pm_cashflows` (already has `account_id`).

### 4. Connector Changes

**Base class** (`private_base.py`): Add optional address/credential override parameter to `__init__`.

**Per connector**:
- `hyperliquid_private.py`: Accept `address` param → override `self.address` (skip env lookup when provided)
- `paradex_private.py`: Accept `account_address` and/or `jwt` param override
- Future connectors follow the same pattern

**Backward compat**: When no override passed, read from env as before.

### 5. Puller Flow Changes

**Current**: One connector per venue → fetch all → match managed legs by `(inst_id, side)`.

**New flow (all venues)**:

1. For each venue in `--venues`:
   - Resolve accounts dict via `{VENUE}_ACCOUNTS_JSON` or legacy fallback → `{"main": "0xabc", "alt": "0xdef"}`
   - Load managed legs from DB
2. **For each (wallet_label, credential)**:
   - Instantiate connector with explicit credential override
   - `fetch_account_snapshot()` → write `pm_account_snapshots` (already works)
   - `fetch_open_positions()` → get venue positions for this wallet
   - **Partition**: Filter managed legs to only those with matching `wallet_label`
   - **Match**: Within partition, use existing `(inst_id, side)` logic
   - Write `pm_leg_snapshots` with `account_id` = resolved address
   - Best-effort update `pm_legs` with current state + `account_id`
3. Legs with no `wallet_label` → default to `"main"`

**Key decision**: Option C — partition legs by wallet_label first, then match `(inst_id, side)` within each partition. No change to core matching logic.

### 6. DB Sync Changes

- `upsert_leg()`: Write `account_id` (resolved address) to new `pm_legs.account_id` column
- Store `wallet_label` in `meta_json` for reference/display
- Resolution (`wallet_label` → address) happens in puller before calling db_sync

### 7. Reporting, Healthcheck & Logging

**Reporting** (`report_daily_funding_with_portfolio.py`):
- Queries are additive — `account_id` column doesn't break existing joins
- No grouping-by-wallet needed for now
- Pre-migration NULL `account_id` treated as legacy, no breakage

**Healthcheck** (`pm_healthcheck.py`):
- Extend wallet mismatch check to iterate all accounts in `{VENUE}_ACCOUNTS_JSON`
- Missing snapshot detection fixes itself — puller now pulls all wallets

**Carry & Risk** (`carry.py`, `risk.py`):
- No changes needed — operate at position/leg level, wallet-agnostic

**Logging**:
- Use `wallet_label` (not full address) in log messages and Discord notifications
- Full address only in DEBUG level or `raw_json`/`meta_json`

---

## Files to Change

| File | Change |
|------|--------|
| `tracking/position_manager/registry.py` | Add `wallet_label` to `LegConfig` |
| `tracking/position_manager/db_sync.py` | Write `account_id` + `wallet_label` in meta_json on upsert |
| `tracking/position_manager/puller.py` | Multi-wallet loop, partition-then-match, account_id in snapshots |
| `tracking/connectors/private_base.py` | Optional credential override in base `__init__` |
| `tracking/connectors/hyperliquid_private.py` | Accept `address` override param |
| `tracking/connectors/paradex_private.py` | Accept credential override params |
| `tracking/sql/schema_pm_v3.sql` | Add `account_id` columns + index (reference) |
| `scripts/pm_healthcheck.py` | Multi-wallet mismatch checks |
| `scripts/report_daily_funding_with_portfolio.py` | Ensure queries handle `account_id` gracefully |

---

## Acceptance Criteria

1. With `{VENUE}_ACCOUNTS_JSON` configured and registry legs tagged with `wallet_label`, `pull_positions_v3.py --venues hyperliquid` correctly pulls from all wallets, writes snapshots per leg under correct wallet, avoids collisions on same `(inst_id, side)`.

2. `pm_healthcheck.py` no longer reports missing snapshots for multi-wallet positions.

3. Daily report continues to work — no "no open positions" when legs exist on any configured wallet.

4. **Backward compatibility**: If `{VENUE}_ACCOUNTS_JSON` is unset, single-wallet flows work exactly as before.

5. **Tests**: Registry parsing with `wallet_label`, db sync writes `account_id`, puller mapping uses wallet partitioning (mock connector responses for two wallets).

---

## Non-Goals

- No UI work
- No multiple dexes simultaneously (single `HYPERLIQUID_DEX`)
- No automatic DB merging across workspaces
- No changes to `pm_positions` table (positions span wallets via legs)

---

## Manual Validation

```bash
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"0x...","alt":"0x..."}'
export HYPERLIQUID_DEX=xyz
source .arbit_env

# Create 2 legs with same inst_id+side but different wallet_label in positions.json
.venv/bin/python scripts/pm.py sync-registry --registry config/positions.json
.venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid

# Verify pm_leg_snapshots has snapshots for both legs, each with correct account_id
```
