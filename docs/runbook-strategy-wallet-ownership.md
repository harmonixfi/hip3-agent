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
