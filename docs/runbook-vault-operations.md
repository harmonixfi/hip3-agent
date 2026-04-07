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

---

## Remote Server: Position Updates (trading-sandbox)

SSH config (`~/.ssh/config`):
```
Host trading-sandbox
   HostName ec2-54-251-223-39.ap-southeast-1.compute.amazonaws.com
   User ubuntu
   IdentityFile ~/.ssh/har_sandbox_trading
```

Remote workspace: `/home/ubuntu/hip3-agent`

> **Note:** The remote server uses system `python3`, not `.venv/bin/python`.

### Update a Position Leg Size

**Step 1 — Edit `positions.json` remotely** (use a Python script to avoid JSON corruption):

```bash
ssh trading-sandbox "cd /home/ubuntu/hip3-agent && python3 -c \"
import json
with open('config/positions.json') as f:
    data = json.load(f)
for pos in data:
    for leg in pos.get('legs', []):
        if leg.get('inst_id') == 'hyna:FARTCOIN':
            print('Before:', leg['qty'])
            leg['qty'] = 51590.2
            print('After:', leg['qty'])
with open('config/positions.json', 'w') as f:
    json.dump(data, f, indent=2)
\""
```

**Step 2 — Sync to DB:**

```bash
ssh trading-sandbox "cd /home/ubuntu/hip3-agent && bash -c 'source .arbit_env && python3 scripts/pm.py sync-registry'"
# Expected output: OK: synced registry -> N positions, M legs
```

**Step 3 — Verify in DB:**

```bash
ssh trading-sandbox "cd /home/ubuntu/hip3-agent && sqlite3 tracking/db/arbit_v3.db 'SELECT leg_id, inst_id, size FROM pm_legs WHERE inst_id LIKE \"%FARTCOIN%\"'"
```

### Key schema note

The `pm_legs` table uses `size` (not `qty`) as the column name.

```sql
-- pm_legs columns: leg_id, position_id, venue, inst_id, side, size, entry_price,
--                  current_price, unrealized_pnl, realized_pnl, status,
--                  opened_at_ms, closed_at_ms, raw_json, meta_json, account_id
```

### List all positions (remote)

```bash
ssh trading-sandbox "cd /home/ubuntu/hip3-agent && bash -c 'source .arbit_env && python3 scripts/pm.py list'"
```

---

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
