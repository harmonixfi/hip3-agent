# Vault Operations Runbook

## Overview

The vault system tracks equity and APR across multiple strategies (Lending, Delta Neutral, Depeg).
Data flows: `config/strategies.json` → `vault_strategies` (DB) → daily snapshots → API → dashboard.

## Common Operations

### Add a New Strategy

1. Edit `config/strategies.json` — add a new strategy object.
2. Sync to DB:

   ```bash
   source .arbit_env && .venv/bin/python scripts/vault.py sync-registry
   ```

3. Verify:

   ```bash
   .venv/bin/python scripts/vault.py list
   ```

4. If a new wallet label is needed, add it to `HYPERLIQUID_ACCOUNTS_JSON` in `.arbit_env`.

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

```bash
source .arbit_env && .venv/bin/python scripts/vault.py cashflow \
  --type DEPOSIT --amount 5000 --strategy lending \
  --ts 1743383400000 \
  --description "Bridge from Arbitrum (logged late)"
```

The system auto-detects backdated entries and recalculates APR for affected snapshots.

### Manual Recalculation

```bash
source .arbit_env && .venv/bin/python scripts/vault.py recalc --since 2026-03-30
source .arbit_env && .venv/bin/python scripts/vault.py recalc --all
```

**What recalc does:** Recomputes APR fields on `vault_strategy_snapshots` and `vault_snapshots` from the given timestamp forward, using the current `vault_cashflows` ledger. Equity columns are not changed.

### Run Daily Snapshot Manually

```bash
source .arbit_env && .venv/bin/python scripts/vault.py snapshot
```

Or:

```bash
source .arbit_env && .venv/bin/python scripts/vault_daily_snapshot.py
```

### View Current State

```bash
source .arbit_env && .venv/bin/python scripts/vault.py list
source .arbit_env && .venv/bin/python scripts/vault.py list --json
```

## Cron Setup

```cron
5 2 * * * cd /path/to/workspace && source .arbit_env && .venv/bin/python scripts/vault_daily_snapshot.py >> logs/vault_daily.log 2>&1
```

## Troubleshooting

### "No provider for strategy type X"

Add an `EquityProvider` in `tracking/vault/providers/` and register it in `tracking/vault/providers/__init__.py`.

### "HARMONIX_NAV_DB_URL not set"

Set the harmonix-nav-platform PostgreSQL URL in `.arbit_env` for lending equity.

### APR looks wrong after a deposit or withdrawal

Run `vault.py recalc --since YYYY-MM-DD`.

### Snapshot shows 0 equity for DN or Depeg

Confirm the wallet label exists in `HYPERLIQUID_ACCOUNTS_JSON` and that `pm_account_snapshots` has rows for that account.

### Lending shows 0

Check Postgres connectivity and that the placeholder query in `tracking/vault/providers/lending.py` matches the real harmonix-nav-platform schema.
