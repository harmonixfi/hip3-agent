# Vault Multi-Strategy Performance Tracking

**Date**: 2026-03-31
**Status**: Design approved, pending implementation

## Context

Our system runs multiple strategies in parallel:
- **Lending** (~50% allocation, ~4% APR) — on-chain lending (HyperLend)
- **Delta Neutral** (~45% allocation, variable APR) — spot-perp funding arbitrage (existing system)
- **Depeg** (~5% allocation) — buying depegged stablecoins, holding for repeg

We need to track all strategy performance at both **strategy level** and **vault level** (total NAV), with the ability to extend for future strategies (spot-perp arbitrage, PERP_PERP, etc.).

Goal: replicate the tracking in our Google Sheets spreadsheet — per-strategy equity, APR, weights, and vault total — but automated and in the dashboard.

---

## Decisions Made

### D1: Approach — Strategy Registry Pattern

**Options considered:**
1. **Strategy Registry Pattern** — new `vault_*` tables + provider plugins on top of existing `pm_*` tables
2. **Extend existing PM schema** — add `strategy_id` to `pm_positions`, shoehorn lending/depeg into position model
3. **Separate microservice** — new module/DB that aggregates from existing system

**Decision: Option 1 (Strategy Registry Pattern)**

**Rationale:** The existing `pm_*` schema is clean and purpose-built for position tracking (legs, fills, spreads). Lending and depeg don't have "legs" or "fills" — forcing them into the position model would muddy it. A parallel `vault_*` layer keeps both models clean. The DN equity provider reads from `pm_*` tables (read-only relationship), so zero risk to existing code.

### D2: Data Source — Automated where possible

Each strategy type gets its own **equity provider** plugin that fetches data automatically:
- **DeltaNeutralProvider**: reads from existing `pm_account_snapshots` + `pm_legs` (wallet "alt")
- **LendingProvider**: reads from **harmonix-nav-platform** remote PostgreSQL DB. This external system already has Prefect flows that pull on-chain lending data for multiple protocols (HyperLend, Felix, HypurrFi). Our provider queries total lending equity across all protocols — logic hardcoded in provider, no per-protocol config needed.
- **DepegProvider**: reads HL account equity for a **dedicated depeg wallet** (separate from DN). Same HL API calls as DN (`clearinghouseState` + `spotClearinghouseState`) but for a different wallet.

Manual entry is a fallback for unsupported venues, not the default.

### D2a: Wallet Assignment

Each strategy uses a **dedicated wallet** — no sharing:
- **Lending**: wallet "lending" — multi-protocol (HyperLend, Felix, HypurrFi), tracked via harmonix-nav-platform
- **Delta Neutral**: wallet "alt" on Hyperliquid (tracked via existing pm_* pipeline)
- **Depeg**: wallet "depeg" on Hyperliquid (dedicated third wallet)

This means `HYPERLIQUID_ACCOUNTS_JSON` needs additional entries: `{"main":"0x...","alt":"0x...","lending":"0x...","depeg":"0x..."}`

### D3: APR — Unified cashflow-based formula

**Options considered:**
1. Strategy-specific APR calculators (different formula per type)
2. Unified cashflow-based APR (same formula everywhere)
3. Hybrid (unified + strategy-specific enrichment)

**Decision: Option 2 (Unified)**

**Formula** (same at strategy and vault level):
```
organic_change = (current_equity - prior_equity) - net_external_cashflows
apr = (organic_change / prior_equity) / period_days * 365
```

**Rationale:** One formula is simpler to implement, debug, and explain. Works for all strategy types because it only needs equity snapshots + cashflow events. Strategy-specific enrichment (e.g., show protocol yield rate for lending) can be added later without changing the core APR logic.

### D4: Cashflow tracking — Both external and inter-strategy transfers

**Options considered:**
1. Inter-strategy transfers tracked explicitly
2. External cashflows only (rebalancing is implicit in equity changes)
3. Both

**Decision: Option 3 (Both)**

- `DEPOSIT` / `WITHDRAW`: external capital in/out of vault or strategy
- `TRANSFER`: move capital between strategies (records `from_strategy_id` and `to_strategy_id`)

At vault level, transfers cancel out (net = 0). At strategy level, transfers are excluded from APR calculation (they're not organic returns).

### D5: Snapshot frequency — Daily

**Decision: Daily snapshots** for strategy-level equity, matching the spreadsheet cadence.

The existing DN hourly pipeline continues unchanged — the DN equity provider reads the latest hourly data when the daily vault snapshot runs.

### D6: Retroactive recalculation for late cashflow entries

**Problem:** Cashflows will often be logged after the daily snapshot has already run (e.g., snapshot at 02:00 UTC, user logs cashflow at 02:15 UTC for something that happened at 01:30).

**Solution:** When a cashflow is inserted with a timestamp before the latest snapshot:
1. The equity value in affected snapshots stays unchanged (it was correct)
2. Only APR fields are recalculated with the corrected cashflow ledger
3. Auto-triggered by the API endpoint, also available via CLI (`vault.py recalc`)

---

## Architecture

### Hierarchy

```
Vault (OpenClaw Vault)
  ├── Strategy: Lending (HyperLend + Felix + HypurrFi)
  │     └── Multi-protocol (equity from harmonix-nav-platform Postgres)
  ├── Strategy: Delta Neutral
  │     └── Wallet: alt @ hyperliquid (equity from pm_account_snapshots)
  └── Strategy: Depeg (Stablecoin)
        └── Wallet: depeg @ hyperliquid (dedicated wallet, equity from HL API)
```

### Data Model

**Config**: `config/strategies.json` — source of truth (like `positions.json`)

**New DB tables:**
- `vault_strategies` — strategy metadata (synced from strategies.json)
- `vault_strategy_snapshots` — daily equity + APR per strategy
- `vault_cashflows` — deposits, withdrawals, inter-strategy transfers
- `vault_snapshots` — daily vault-level rollup (total NAV, weighted APR)

**Relationship to existing tables:**
- `pm_*` tables are untouched
- `DeltaNeutralProvider` reads from `pm_account_snapshots`, `pm_legs`, `pm_cashflows` (read-only)

### Equity Provider Plugin System

```
EquityProvider (ABC)
  ├── DeltaNeutralProvider  — reads pm_account_snapshots (wallet "alt")
  ├── LendingProvider       — reads harmonix-nav-platform Postgres (multi-protocol aggregate)
  ├── DepegProvider         — reads HL API for dedicated "depeg" wallet
  └── GenericProvider       — manual entry fallback (future)

PROVIDER_REGISTRY = {
    "DELTA_NEUTRAL": DeltaNeutralProvider,
    "LENDING": LendingProvider,
    "DEPEG": DepegProvider,
}
```

Adding a new strategy type = implement a new provider + register it.

### Cashflow Model

| cf_type | amount sign | strategy_id | from/to |
|---------|-------------|-------------|---------|
| DEPOSIT | positive | target strategy | — |
| WITHDRAW | negative | source strategy | — |
| TRANSFER | positive | — | from + to set |

### APR Calculation

```python
def cashflow_adjusted_apr(current_equity, prior_equity, net_external_cashflows, period_days):
    organic_change = (current_equity - prior_equity) - net_external_cashflows
    return (organic_change / prior_equity) / period_days * 365
```

- **Strategy APR**: strategy snapshots + external cashflows to that strategy (transfers excluded)
- **Vault APR**: vault snapshots + DEPOSIT/WITHDRAW only (transfers cancel out)
- **Weighted APR**: `sum(strategy.actual_weight * strategy.apr)` — displayed as "Total APR"
- **Windows**: since inception, 30d, 7d

### Daily Pipeline

Script: `scripts/vault_daily_snapshot.py` — runs at 02:05 UTC (09:05 ICT)

```
1. Load active strategies from DB
2. For each: call EquityProvider.get_equity() → insert vault_strategy_snapshots
3. Compute vault rollup → insert vault_snapshots
```

### CLI Tooling

```bash
# Registry management (like pm.py)
vault.py sync-registry    # strategies.json → DB
vault.py list             # show all strategies

# Cashflow entry
vault.py cashflow --type DEPOSIT --amount 5000 --strategy lending_hyperlend
vault.py cashflow --type TRANSFER --amount 2000 --from lending_hyperlend --to delta_neutral

# Recalculation (see runbook)
vault.py recalc --since 2026-03-30
vault.py recalc --all
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/vault/overview` | GET | Total equity, APR, strategy weights |
| `/api/vault/strategies` | GET | All strategies with latest metrics |
| `/api/vault/strategies/{id}` | GET | Strategy detail + history |
| `/api/vault/snapshots` | GET | Historical vault snapshots |
| `/api/vault/strategies/{id}/snapshots` | GET | Historical strategy snapshots |
| `/api/vault/cashflows` | GET | List cashflows (filterable) |
| `/api/vault/cashflows` | POST | Create cashflow (auto-recalc if backdated) |

### Frontend Pages

- **Dashboard (`/`)**: Add vault summary card + strategy allocation bar at top
- **`/vault`**: Equity over time chart, strategy stacked area, APR trends, weight drift
- **`/vault/cashflows`**: Cashflow entry form + history table
- **`/vault/strategies/{id}`**: Strategy drill-down with equity history, APR, cashflows

### New File Structure

```
tracking/vault/
  __init__.py
  registry.py
  db_sync.py
  snapshot.py
  recalc.py
  providers/
    base.py
    delta_neutral.py
    lending.py
    depeg.py

scripts/
  vault.py
  vault_daily_snapshot.py

api/routers/
  vault.py

frontend/app/vault/
  page.tsx
  cashflows/page.tsx
  strategies/[id]/page.tsx

frontend/components/
  VaultSummary.tsx
  StrategyTable.tsx
  CashflowForm.tsx
  EquityChart.tsx
  AprChart.tsx
  AllocationBar.tsx
```
