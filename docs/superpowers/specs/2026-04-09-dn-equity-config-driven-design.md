# DN Equity — Config-Driven Only (Remove Felix) — Design Spec

**Date:** 2026-04-09  
**Supersedes:** `docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md`  
**Status:** Approved

## Problem

`DeltaNeutralProvider.get_equity()` currently injects Felix wallet equity via `FELIX_WALLET_ADDRESS` env var, causing Felix to appear in DN total equity on the dashboard ($10,511.54 shown under "felix" label). Felix is NOT a delta-neutral strategy — it belongs to Lending and Depeg. This is a categorization bug introduced in commit `4c44e09`.

**Impact:**
- DN total equity ($85,273.54) is inflated by ~$10,500 (Felix balance)
- APR denominator is wrong (based on inflated equity)
- Wallet Breakdown shows a "felix" row under DN dashboard

**APR/cashflow NOT affected** — `vault_cashflows` filters by `strategy_id = 'delta_neutral'` and Felix transactions are never written with that strategy_id. Only equity calculation is wrong.

## Decision

`strategies.json` is the single source of truth for DN equity. DN wallets = exactly what is listed under `delta_neutral.wallets` in config. No env var can inject additional wallets into DN equity.

Felix wallet continues to be pulled (account snapshots written to `pm_account_snapshots` with `venue='felix'`), but those rows are excluded from DN equity calculation.

## Changes

### 1. `tracking/vault/providers/delta_neutral.py`

- Remove `_felix_open_leg_notional_usd()` function entirely
- Remove Felix injection block (lines 75–95):
  ```python
  felix_addr = get_felix_wallet_address_from_env()
  if felix_addr and felix_addr not in counted_lower:
      ...
  ```
- Remove `get_felix_wallet_address_from_env` from imports

`DeltaNeutralProvider.get_equity()` will only iterate `strategy.wallets_json` — exactly the 3 DN wallets (alt, commodity, main).

### 2. `tracking/position_manager/accounts.py`

- Remove Felix injection from `get_delta_neutral_equity_account_ids()` (lines 184–187):
  ```python
  felix = get_felix_wallet_address_from_env()
  if felix and felix not in seen_lower:
      seen_lower.add(felix)
      out.append(felix)
  ```
- Update the function docstring to remove Felix mention
- Keep `get_felix_wallet_address_from_env()` function — still used by `puller.py`, `felix_jwt_refresh.py`, connector

### 3. `api/routers/portfolio.py`

- Remove Felix label fallback in wallet-label resolution function (lines 328–332):
  ```python
  from tracking.position_manager.accounts import get_felix_wallet_address_from_env
  fx = get_felix_wallet_address_from_env()
  if fx and account_id.lower() == fx:
      return "felix"
  ```
  This block was only needed to label Felix rows in DN breakdown — no longer relevant.

### 4. Tests

**`tests/test_portfolio_dn_filter.py`**
- Remove `test_get_total_equity_includes_felix_when_env_configured` — this test asserted the (now-incorrect) behavior that Felix is included in DN totals.
- Add replacement test: `test_get_total_equity_excludes_felix_even_when_env_set` — Felix wallet set in env, Felix snapshot exists in DB, assert Felix is NOT counted in DN total.

**`tests/test_accounts_strategies.py`**
- Update test at line ~207 (`test_get_delta_neutral_equity_account_ids_includes_felix`) — assert Felix is NOT in the returned list even when `FELIX_WALLET_ADDRESS` is set.

### 5. Docs

- Prepend a `> **SUPERSEDED** by...` notice to `docs/superpowers/specs/2026-04-07-delta-neutral-felix-equity-design.md`

## What does NOT change

- Felix pull pipeline in `puller.py` — still fetches Felix snapshots and writes `pm_account_snapshots(venue='felix')` rows
- `get_felix_wallet_address_from_env()` function — kept, used by puller and connectors
- APR/cashflow logic — already correct
- `strategies.json` — no changes needed
- Schema — no migration needed

## Data Flow After Fix

```
strategies.json delta_neutral.wallets (alt, commodity, main)
  → DeltaNeutralProvider.get_equity()
  → pm_account_snapshots WHERE account_id IN (alt_addr, commodity_addr, main_addr)
  → DN total equity (Felix excluded)

FELIX_WALLET_ADDRESS + FELIX_EQUITIES_JWT
  → puller.py → pm_account_snapshots (venue='felix')   ← still written, just not counted in DN
```

## Success Criteria

- Dashboard DN total equity = sum of alt + commodity + main wallets only
- "felix" row absent from DN Wallet Breakdown
- `get_delta_neutral_equity_account_ids()` returns 3 addresses (not 4) regardless of `FELIX_WALLET_ADDRESS` env
- Felix pull still runs successfully and writes to `pm_account_snapshots`
- All tests pass
