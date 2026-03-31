# Vault Multi-Strategy Performance Tracking — Design Spec

**Date**: 2026-03-31
**Approach**: Strategy Registry Pattern (Approach A)

## Problem

The system currently tracks only delta-neutral (spot-perp) positions. Capital is allocated across multiple strategies (Lending ~50%, Delta Neutral ~45%, Depeg ~5%), but there is no unified tracking of total vault NAV, per-strategy equity, weighted APR, or cashflows between strategies. This data is currently maintained in a manual spreadsheet.

## Goals

1. Track equity and APR for each strategy independently
2. Roll up to a vault-level total NAV and weighted-average APR
3. Track cashflows: external deposits/withdrawals AND inter-strategy transfers
4. Automate data collection per strategy type via provider plugins
5. Display all metrics in the dashboard
6. Handle retroactive cashflow entries gracefully (late logging)
7. Extensible for future strategy types (spot-perp arb, PERP_PERP, etc.)

## Non-Goals

- Real-time (sub-hourly) strategy tracking — daily snapshots are sufficient
- Automated rebalancing between strategies — manual decision, manual execution
- Strategy-specific APR formulas — unified cashflow-based APR for all

## Architecture

### Hierarchy

```
Vault
  └── config/strategies.json (source of truth)
       ├── Strategy: lending (type: LENDING)
       │     └── Multi-protocol: HyperLend + Felix + HypurrFi (equity from harmonix-nav-platform Postgres)
       ├── Strategy: delta_neutral (type: DELTA_NEUTRAL)
       │     └── Wallet: alt @ hyperliquid (equity from pm_account_snapshots)
       └── Strategy: depeg_usde (type: DEPEG)
             └── Wallet: depeg @ hyperliquid (dedicated wallet, equity from HL API)
```

### Relationship to Existing System

The existing `pm_*` tables (positions, legs, fills, cashflows, snapshots) are **untouched**. The `DELTA_NEUTRAL` equity provider reads from them in a read-only relationship. No migration or modification of existing schema.

## Data Model

### Config: `config/strategies.json`

```json
{
  "vault_name": "OpenClaw Vault",
  "strategies": [
    {
      "strategy_id": "lending",
      "name": "Lending",
      "type": "LENDING",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "lending", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 50.0,
      "config": {}
    },
    {
      "strategy_id": "delta_neutral",
      "name": "Delta Neutral",
      "type": "DELTA_NEUTRAL",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "alt", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 45.0,
      "config": {}
    },
    {
      "strategy_id": "depeg_usde",
      "name": "Stablecoin Depeg",
      "type": "DEPEG",
      "status": "ACTIVE",
      "wallets": [
        {"wallet_label": "depeg", "venue": "hyperliquid"}
      ],
      "target_weight_pct": 5.0,
      "config": {}
    }
  ]
}
```

### Database Tables

#### `vault_strategies`

Synced from `strategies.json` via `vault.py sync-registry`.

```sql
CREATE TABLE vault_strategies (
  strategy_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  type TEXT NOT NULL,                    -- LENDING, DELTA_NEUTRAL, DEPEG, ...
  status TEXT NOT NULL DEFAULT 'ACTIVE'
    CHECK (status IN ('ACTIVE', 'PAUSED', 'CLOSED')),
  wallets_json TEXT,                     -- JSON array of wallet configs
  target_weight_pct REAL,
  config_json TEXT,                      -- strategy-type-specific config
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);
```

#### `vault_strategy_snapshots`

Daily equity + APR per strategy.

```sql
CREATE TABLE vault_strategy_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  strategy_id TEXT NOT NULL,
  ts INTEGER NOT NULL,                   -- epoch ms UTC
  equity_usd REAL NOT NULL,
  equity_breakdown_json TEXT,            -- per-wallet or per-asset breakdown
  apr_since_inception REAL,
  apr_30d REAL,
  apr_7d REAL,
  meta_json TEXT,
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id),
  UNIQUE (strategy_id, CAST(ts / 86400000 AS INTEGER))
);

CREATE INDEX idx_vault_strat_snap_strategy ON vault_strategy_snapshots(strategy_id);
CREATE INDEX idx_vault_strat_snap_ts ON vault_strategy_snapshots(ts);
```

#### `vault_cashflows`

External deposits/withdrawals and inter-strategy transfers.

```sql
CREATE TABLE vault_cashflows (
  cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,                   -- epoch ms UTC
  cf_type TEXT NOT NULL
    CHECK (cf_type IN ('DEPOSIT', 'WITHDRAW', 'TRANSFER')),
  amount REAL NOT NULL,                  -- positive = credit for DEPOSIT/TRANSFER, negative for WITHDRAW
  currency TEXT NOT NULL DEFAULT 'USDC',
  strategy_id TEXT,                      -- target for DEPOSIT/WITHDRAW (NULL = vault-level unallocated)
  from_strategy_id TEXT,                 -- source for TRANSFER
  to_strategy_id TEXT,                   -- destination for TRANSFER
  description TEXT,
  meta_json TEXT,
  created_at_ms INTEGER NOT NULL,        -- when this row was inserted (for audit)
  FOREIGN KEY (strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (from_strategy_id) REFERENCES vault_strategies(strategy_id),
  FOREIGN KEY (to_strategy_id) REFERENCES vault_strategies(strategy_id)
);

CREATE INDEX idx_vault_cf_ts ON vault_cashflows(ts);
CREATE INDEX idx_vault_cf_strategy ON vault_cashflows(strategy_id);
CREATE INDEX idx_vault_cf_type ON vault_cashflows(cf_type);
```

#### `vault_snapshots`

Daily vault-level rollup.

```sql
CREATE TABLE vault_snapshots (
  snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts INTEGER NOT NULL,                   -- epoch ms UTC
  total_equity_usd REAL NOT NULL,
  strategy_weights_json TEXT,            -- {"lending_hyperlend": 50.2, "delta_neutral": 44.8, ...}
  total_apr REAL,                        -- weighted-average APR
  apr_30d REAL,
  apr_7d REAL,
  net_deposits_alltime REAL,
  meta_json TEXT,
  UNIQUE (CAST(ts / 86400000 AS INTEGER))
);

CREATE INDEX idx_vault_snap_ts ON vault_snapshots(ts);
```

## Equity Provider Plugin System

### Base Interface

```python
# tracking/vault/providers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

@dataclass
class StrategyEquity:
    equity_usd: float
    breakdown: dict            # per-wallet or per-asset
    timestamp_ms: int
    meta: dict = field(default_factory=dict)

class EquityProvider(ABC):
    @abstractmethod
    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        """Fetch current equity for this strategy."""
        pass
```

### Provider Implementations

**`DeltaNeutralProvider`**: Reads `pm_account_snapshots` for wallets tagged to this strategy (wallet "alt"). Sums their equity. Already computed by the existing hourly pipeline.

**`LendingProvider`**: Reads from **harmonix-nav-platform PostgreSQL database** (remote). This external system already has Prefect flows that pull on-chain lending data for multiple protocols (HyperLend, Felix, HypurrFi). Our provider queries total lending equity across all protocols.

- **Data source**: Remote PostgreSQL (harmonix-nav-platform)
- **Connection**: Via `HARMONIX_NAV_DB_URL` env var (connection string)
- **Query**: Hardcoded in provider — aggregate equity across all lending protocols
- **No per-protocol config needed** — the provider knows how to query harmonix-nav-platform
- **No on-chain calls needed** — harmonix-nav-platform handles all on-chain data pulling via Prefect

```python
class LendingProvider(EquityProvider):
    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        # 1. Connect to harmonix-nav-platform Postgres via HARMONIX_NAV_DB_URL
        # 2. Query total lending equity across all protocols (hyperlend, felix, hypurrfi)
        # 3. Return StrategyEquity with per-protocol breakdown
        pass
```

**`DepegProvider`**: Reads HL account equity for a **dedicated depeg wallet** (separate from DN's "alt" wallet). Calls `spotClearinghouseState` + `clearinghouseState` for that wallet — same mechanism as DN but for a different account.

- **Data source**: Hyperliquid API (same as DN)
- **Wallet**: Dedicated wallet (not "main" or "alt" — a third wallet label, e.g., "depeg")
- **Equity**: Total account equity of the depeg wallet (spot + any perp margin)

```python
class DepegProvider(EquityProvider):
    def get_equity(self, strategy: dict, db) -> StrategyEquity:
        # 1. Resolve wallet address from wallet_label via HYPERLIQUID_ACCOUNTS_JSON
        # 2. Call HL clearinghouseState + spotClearinghouseState
        # 3. Sum total equity across spot + perp accounts
        # 4. Return StrategyEquity
        pass
```

**`GenericProvider`** (future): Manual equity entry fallback for unsupported venues.

### Registry

```python
PROVIDER_REGISTRY = {
    "DELTA_NEUTRAL": DeltaNeutralProvider,
    "LENDING": LendingProvider,
    "DEPEG": DepegProvider,
}
```

## Cashflow Model

### Types and Sign Convention

| cf_type | amount | strategy_id | from/to | Vault-level effect |
|---------|--------|-------------|---------|-------------------|
| DEPOSIT | positive | target strategy | — | +equity |
| WITHDRAW | negative | source strategy | — | -equity |
| TRANSFER | positive | — | from + to set | net zero |

### APR Exclusion Rules

- **Strategy APR**: excludes TRANSFER cashflows (they're not organic returns)
- **Vault APR**: only uses DEPOSIT/WITHDRAW (transfers cancel out at vault level)

## APR Calculation

### Unified Formula (all levels)

```python
def cashflow_adjusted_apr(
    current_equity: float,
    prior_equity: float,
    net_external_cashflows: float,
    period_days: float
) -> float:
    if prior_equity <= 0 or period_days <= 0:
        return 0.0
    organic_change = (current_equity - prior_equity) - net_external_cashflows
    return (organic_change / prior_equity) / period_days * 365
```

### Strategy-Level APR

- `net_external_cashflows` = DEPOSIT amounts + WITHDRAW amounts for this strategy (transfers excluded)
- Computed for windows: since inception, 30d, 7d
- Prior equity looked up from `vault_strategy_snapshots`

### Vault-Level APR

- `net_external_cashflows` = all DEPOSIT + WITHDRAW amounts (transfers cancel out)
- Same windows: inception, 30d, 7d

### Weighted-Average APR (display metric)

```python
total_apr = sum(strategy.actual_weight_pct * strategy.apr for s in strategies) / 100
# where actual_weight_pct = strategy_equity / total_equity * 100
```

## Daily Snapshot Pipeline

### Script: `scripts/vault_daily_snapshot.py`

Cron: `5 2 * * *` (02:05 UTC / 09:05 ICT)

```
1. Load active strategies from vault_strategies
2. For each ACTIVE strategy:
   a. Instantiate EquityProvider via PROVIDER_REGISTRY[strategy.type]
   b. Call provider.get_equity() → StrategyEquity
   c. Query vault_cashflows for this strategy to compute net_external_cashflows
   d. Query vault_strategy_snapshots for prior equity at each window (7d, 30d, inception)
   e. Compute APR for each window
   f. INSERT INTO vault_strategy_snapshots
3. Vault rollup:
   a. total_equity = SUM(strategy equities)
   b. weights = each / total
   c. total_apr = weighted average
   d. INSERT INTO vault_snapshots
4. Log summary
```

### Retroactive Recalculation

When a cashflow is inserted with `ts < latest_snapshot.ts`:

1. Equity values in affected snapshots stay unchanged (they were correct at that time)
2. APR fields are recalculated with the corrected cashflow ledger
3. Auto-triggered by `POST /api/vault/cashflows` endpoint
4. Also available via CLI: `vault.py recalc --since DATE`

```python
def recalc_snapshots(db, since_ts: int):
    """Re-compute APR fields for all snapshots from since_ts forward."""
    # 1. Find all vault_strategy_snapshots with ts >= since_ts
    # 2. For each snapshot, re-query cashflows up to that ts
    # 3. Recompute APR fields
    # 4. UPDATE vault_strategy_snapshots SET apr_* = new values
    # 5. Recompute vault_snapshots (weighted APR) for affected days
```

## CLI Tooling: `scripts/vault.py`

### Commands

```bash
# Registry
vault.py sync-registry          # strategies.json → vault_strategies
vault.py list                   # show all strategies with latest equity

# Cashflow
vault.py cashflow --type DEPOSIT --amount 5000 --strategy lending_hyperlend \
  --description "Bridge from Arbitrum"
vault.py cashflow --type TRANSFER --amount 2000 \
  --from lending_hyperlend --to delta_neutral \
  --description "Rebalance Q1"
vault.py cashflow --type WITHDRAW --amount 1000 --strategy delta_neutral \
  --description "Profit withdrawal"

# Recalculation
vault.py recalc --since 2026-03-30    # recalc from date
vault.py recalc --all                  # recalc everything

# Snapshot (manual trigger)
vault.py snapshot                      # run daily snapshot now
```

## API Endpoints

### `GET /api/vault/overview`

```json
{
  "vault_name": "OpenClaw Vault",
  "total_equity_usd": 98390.76,
  "total_apr": 6.56,
  "apr_30d": 5.80,
  "apr_7d": 7.20,
  "net_deposits_alltime": 90000.0,
  "strategies": [
    {
      "strategy_id": "lending_hyperlend",
      "name": "HyperLend USDC",
      "type": "LENDING",
      "equity_usd": 49061.30,
      "weight_pct": 49.86,
      "target_weight_pct": 50.0,
      "apr": 5.09,
      "status": "ACTIVE"
    }
  ],
  "as_of": "2026-03-31T02:05:00Z"
}
```

### `GET /api/vault/strategies`

Returns all strategies with latest snapshot data.

### `GET /api/vault/strategies/{id}`

Returns strategy detail with equity history, APR windows, and cashflows.

### `GET /api/vault/snapshots?from=&to=&limit=`

Historical vault snapshots for charting.

### `GET /api/vault/strategies/{id}/snapshots?from=&to=&limit=`

Historical strategy snapshots for charting.

### `GET /api/vault/cashflows?strategy_id=&cf_type=&from=&to=`

List vault cashflows with filters.

### `POST /api/vault/cashflows`

Create cashflow entry. Auto-triggers recalc if backdated.

Request:
```json
{
  "cf_type": "DEPOSIT",
  "amount": 5000.0,
  "strategy_id": "lending_hyperlend",
  "ts": 1743382200000,
  "description": "Bridge from Arbitrum"
}
```

Response:
```json
{
  "cashflow_id": 42,
  "recalculated": true,
  "recalc_snapshots_affected": 3
}
```

## Frontend

### Updated Dashboard (`/`)

Add vault summary section at top of existing dashboard:
- **VaultSummary card**: Total NAV, 24h change, Total APR
- **AllocationBar**: Visual weight breakdown (Lending 50%, DN 45%, Depeg 5%)
- **StrategyTable**: Name, equity, APR, weight (actual vs target), status

Existing position table remains below, scoped to DN strategy.

### New: `/vault`

Detailed vault analytics:
- Equity over time (line chart, daily points)
- Strategy equity stacked area chart
- APR trend chart (vault + per-strategy lines)
- Weight drift chart (actual vs target)

### New: `/vault/cashflows`

Cashflow management:
- **CashflowForm**: Type (select), Amount, Strategy (select), From/To (for transfers), DateTime (backdatable), Description
- **Cashflow history table**: Filterable by type, strategy, date range
- "Recalculated" badge on entries that triggered a recalc

### New: `/vault/strategies/{id}`

Strategy drill-down:
- Equity history chart
- APR windows (7d, 30d, inception)
- Cashflow history for this strategy
- For DN: links to existing position detail pages

## File Structure

```
# New files
config/strategies.json

tracking/vault/
  __init__.py
  registry.py                    # Load & validate strategies.json
  db_sync.py                     # Sync registry to vault_strategies
  snapshot.py                    # Daily snapshot orchestrator
  recalc.py                      # Retroactive recalculation
  providers/
    __init__.py
    base.py                      # EquityProvider ABC + StrategyEquity
    delta_neutral.py
    lending.py
    depeg.py

tracking/sql/schema_vault.sql    # All vault_* table definitions

scripts/vault.py                 # CLI: sync-registry, list, cashflow, recalc, snapshot
scripts/vault_daily_snapshot.py  # Cron job

api/routers/vault.py             # All /api/vault/* endpoints
api/models/vault_schemas.py      # Pydantic models for vault API

frontend/app/vault/
  page.tsx                       # Vault overview
  cashflows/page.tsx             # Cashflow entry + history
  strategies/[id]/page.tsx       # Strategy detail

frontend/components/
  VaultSummary.tsx
  StrategyTable.tsx
  CashflowForm.tsx
  EquityChart.tsx
  AprChart.tsx
  AllocationBar.tsx
```

## Testing Strategy

- Unit tests for APR calculation (edge cases: zero equity, zero period, negative cashflows)
- Unit tests for recalc logic (verify APR changes but equity stays same)
- Integration test for full snapshot pipeline (mock providers)
- Integration test for backdated cashflow → auto-recalc flow
- Manual verification against spreadsheet data for first few days

## Migration / Rollout

1. Create `vault_*` tables (new schema file, no migration of existing tables)
2. Create `config/strategies.json` with current 3 strategies
3. Implement providers (DN first — can verify against existing data)
4. Run first manual snapshot, verify against spreadsheet
5. Enable cron job
6. Build API endpoints
7. Build frontend pages
8. Write runbook for vault CLI operations
