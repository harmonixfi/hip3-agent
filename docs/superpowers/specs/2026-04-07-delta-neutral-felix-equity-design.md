# Delta-Neutral Equity — Hyperliquid + Felix — Design Spec

**Date:** 2026-04-07  
**Goal:** Include Felix equities account value in delta-neutral total equity alongside Hyperliquid, using two addresses when needed, with manual JWT (no automated Turnkey refresh in the pull path).

## Summary

1. **Pull pipeline** — Register `felix` in `tracking/position_manager/puller.py` and fetch account snapshots via `FelixPrivateConnector`, using env-only credentials.
2. **Credentials** — `FELIX_WALLET_ADDRESS` + `FELIX_EQUITIES_JWT` (manual rotation; user updates env when the token fails).
3. **Portfolio / DN filtering** — Introduce a small helper that unions `get_strategy_wallets("delta_neutral")` addresses with `FELIX_WALLET_ADDRESS` when set, and use it wherever DN equity is filtered from `pm_account_snapshots` so Felix rows are not dropped.
4. **Position ingestion — registry-first (approved)** — Felix long legs are **declared in `config/positions.json`** next to Hyperliquid short legs (same `position_id` per name). `scripts/pm.py sync-registry` writes `pm_positions` / `pm_legs`; the puller maps Felix API lines to those legs and fills `pm_leg_snapshots` and live fields on `pm_legs`. No auto-creation of legs solely from the Felix API without a registry row.
5. **Out of scope** — Turnkey `stamp_login`, `felix_jwt_refresh.py`, and encrypted session files are not required for this path (see `docs/felix-turnkey-auth-handoff.md`).

## 1. Problem

Delta-neutral equity today sums latest `pm_account_snapshots.total_balance` for accounts listed under `delta_neutral` in `config/strategies.json` (typically Hyperliquid only). Felix exposes portfolio value via `GET /v1/portfolio/{address}`; `FelixPrivateConnector` already maps `accountValue` → `total_balance`, but the main puller does not write `venue='felix'` snapshots. DN may use a **different** EVM address for Felix than for Hyperliquid.

## 2. Configuration

| Variable | Purpose |
|----------|---------|
| `FELIX_WALLET_ADDRESS` | EVM address for Felix API calls and `pm_account_snapshots.account_id` (authoritative for Felix pulls). |
| `FELIX_EQUITIES_JWT` | Bearer token for `FelixPrivateConnector`; user replaces when expired or on 401. |

Hyperliquid addresses continue to come from `config/strategies.json` (`delta_neutral.wallets`, `venue: hyperliquid`) and existing `accounts.py` legacy fallbacks.

**Optional later:** Add a `venue: felix` row under `delta_neutral.wallets` for vault weighting / UI; if present, implementation should validate `address` equals `FELIX_WALLET_ADDRESS` (case-insensitive) to avoid drift. Initial implementation does not require a JSON row if the merge helper includes the env address.

## 3. Pull pipeline behavior

- Add `felix` → `FelixPrivateConnector` to the venue connector map.
- For Felix, use a **dedicated branch** (not only `resolve_venue_accounts("felix")`): build the connector with `jwt` from `FELIX_EQUITIES_JWT` and `wallet_address` from `FELIX_WALLET_ADDRESS` (normalized lower-case).
- If either env var is missing or empty, **skip** Felix for that run with a short log reason (no JWT body in logs).
- On API failure (e.g. 401), record failure like other venues; user rotates `FELIX_EQUITIES_JWT` manually.
- Write rows to `pm_account_snapshots` with `venue='felix'` and `account_id` = Felix wallet address.

Hyperliquid pull logic stays unchanged.

## 4. Delta-neutral account set (merge helper)

Call sites that filter “DN wallets” using only `get_strategy_wallets("delta_neutral")` would **exclude** Felix if the Felix address exists only in env. Add a function (exact name TBD in implementation) that returns the set (or list) of account ids used for DN equity:

- All addresses from `get_strategy_wallets("delta_neutral")` with non-empty `address`.
- Plus `FELIX_WALLET_ADDRESS` (normalized) when the env var is set and non-empty.

Replace or wrap existing filters in `tracking/pipeline/portfolio.py`, `api/routers/portfolio.py`, `tracking/vault/providers/delta_neutral.py`, and any other DN-specific snapshot filtering so behavior is consistent.

**Note:** `DeltaNeutralProvider` currently iterates strategy wallets including `venue`; for Felix-from-env, either invoke the merge helper for the address list or add a synthetic Felix entry when env is set—implementation chooses the smallest consistent change.

## 5. Data flow

```
strategies.json (HL) → Hyperliquid connector → pm_account_snapshots (venue=hyperliquid)
FELIX_WALLET_ADDRESS + FELIX_EQUITIES_JWT → Felix connector → pm_account_snapshots (venue=felix)
pm_account_snapshots + merged DN account ids → total DN equity, overview, fund utilization
```

### 5.1 Registry-first Felix legs (dashboard / PM tables)

For each delta-neutral name that is **long Felix tokenized stock + short HL perp**, the registry is the source of truth:

1. **`config/positions.json`** — For a given `position_id`, include:
   - One leg: `venue: "felix"`, `side: "LONG"`, `inst_id` matching the **normalized** instrument id produced by `FelixPrivateConnector` (e.g. Ondo symbols like `MSTRon` → `MSTRon/USDC` per existing `_normalize_felix_inst_id` rules).
   - One or more legs: `venue: "hyperliquid"`, short perp(s), as today.
2. **`pm.py sync-registry`** — Upserts `pm_positions` and `pm_legs` (playbook workflow unchanged).
3. **Puller** — On Felix pull, match API portfolio lines to registry legs by `(inst_id, side)`; write **`pm_leg_snapshots`** and **`UPDATE pm_legs`** (`current_price`, `unrealized_pnl`, `account_id`) for matched legs only.
4. **Account snapshot** — Same run still writes **`pm_account_snapshots`** for `venue=felix` (wallet-level equity).

Downstream (existing jobs):

- **`pm_entry_prices` / fills** — Unchanged contract; Felix **fills** remain the responsibility of `felix_fill_ingester` when wired to cron. Entry spread math in `compute_spreads` requires **`pm_entry_prices`** for both long and short legs; if Felix entries are missing until fills backfill, entry/exit spread may be incomplete until those rows exist.
- **`pm_spreads` / `compute_spreads`** — Exit spread uses **`prices_v3`** bid/ask per `(venue, inst_id)`. If Felix instruments are not in `prices_v3`, implementation may add a **narrow fallback** (e.g. use **mark from `pm_legs.current_price`** for `venue=felix` when the order book row is absent). Without that fallback, spread columns on the dashboard may stay empty for the Felix long leg even when notionals are correct.

**Explicit non-goal:** Automatically discovering Felix positions and inserting `pm_legs` rows **without** a corresponding `positions.json` entry.

## 6. Error handling and safety

- Do not log JWTs or full auth headers.
- Missing env: skip Felix; do not fail entire pull unless product requires hard-fail (default: soft skip).
- Optional: document in `.arbit_env` example comments that Felix JWT is short-lived and must be updated manually.

## 7. Testing

- Unit tests: merge helper with/without `FELIX_WALLET_ADDRESS`; connector kwargs for felix pull branch (mock env).
- Integration or connector tests: snapshot write path for `venue=felix` with mocked HTTP (existing `FelixPrivateConnector` tests can be extended if needed).

## 8. Non-goals

- Automatic JWT refresh via Turnkey (`felix_auth.refresh_session`, `scripts/felix_jwt_refresh.py`).
- Changing Hyperliquid credential resolution.
- **API-only leg discovery** — no creating `pm_legs` solely from Felix portfolio without registry rows.
- Felix **fills** ingestion (`felix_fill_ingester`) remains a separate pipeline unless a follow-up ties it to the same cron; registry-first **position** pulls do not replace fill ingestion for `pm_fills`.

## 9. Success criteria

- With valid env and API, latest DN total equity includes Hyperliquid + Felix account values when both are configured.
- Portfolio overview and other DN-filtered metrics include Felix snapshot rows for the env-configured address.
- With Felix env unset, behavior matches pre-change for HL-only setups.
- For positions that declare **Felix + HL** legs in `positions.json`, a successful Felix pull **updates `pm_legs`** for the Felix long leg and writes **`pm_leg_snapshots`**, so the dashboard **Amount / uPnL** path can use the same APIs as HL-only legs (subject to parser and price availability).

## 10. API response alignment

Production Felix portfolio JSON may use fields such as `stablecoinBalance`, `positions[].quantity`, `costBasisUsd`, etc., rather than `accountValue` / `currentPrice` alone. The connector’s `_parse_portfolio_response` (and any rollup used for `total_balance`) must match the **live** contract so `pm_account_snapshots.total_balance` and per-leg marks are correct. Tests should include a fixture shaped like the real payload.
