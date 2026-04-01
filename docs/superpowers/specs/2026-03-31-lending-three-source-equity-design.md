# Lending equity — three sources (ERC4626 + HyperLend + HypurrFi)

**Date:** 2026-03-31  
**Status:** Approved for implementation  
**Scope:** `LendingProvider` / Harmonix NAV Postgres reads only; vault snapshot pipeline unchanged except consuming new totals.

## Goal

Expose **one** lending strategy equity scalar (`StrategyEquity.equity_usd`) that is the **sum of three independent legs** (ERC4626 + HyperLend + HypurrFi). Each leg **sums contributions across all addresses** in a **single configured list** — the **same list** is used for:

1. **ERC4626 vaults** (e.g. Felix) — for each `(account, vault)` pair, take the **latest** hourly row, compute `amount_underlying`; then **sum** across all accounts in the list (per vault, then sum vaults; or one SQL that aggregates to the same total).
2. **HyperLend** — Aave-style core pool: **gross supply only** — `a_token_balance_raw_uint` for USDC reserve, `protocol_code = 'HYPERLEND'`. For each address in the list, take the **latest** row for that `(account, protocol)`; **sum** scaled amounts across addresses.
3. **HypurrFi** — same as (2) with `protocol_code = 'HYPURRFI'`.

Borrow fields (`var_debt_balance_raw_uint`, `stable_debt_balance_raw_uint`) are **not** used in the headline total.

## Data source

- **Database:** Harmonix NAV Postgres (`HARMONIX_NAV_DB_URL`).
- **Chain:** `999` (HyperEVM).
- **Accounts:** **Ordered list** of `0x…` addresses (length ≥ 1). **One list applies to all three legs** — no per-source address lists in v1.
- **Configuration:** Env (e.g. comma-separated `HARMONIX_LENDING_ACCOUNT_ADDRESSES` or extend the existing single-account env to accept comma-separated values) and/or `config_json` key `lending_accounts` (JSON array). **Backward compatibility:** if only one address is configured, behavior matches the previous single-wallet spec.

## Decimals and units

| Leg | Raw → amount | Notes |
|-----|----------------|--------|
| ERC4626 | `assets_est_raw_uint / 10^price_decimals` | Unchanged; `price_decimals` from `raw.vault_erc4626_snapshot_hourly` join. |
| HyperLend / HypurrFi | `a_token_balance_raw_uint / 10^6` | **Fixed 6** for this USDC reserve (option A). |

**Important:** The three amounts may be **different units** in strict terms (vault “underlying” vs USDC). Product choice is to **add them into one scalar** for the vault UI, with `meta` declaring mixed components. Label or docs should not claim “all USD” without a future FX pass.

## SQL semantics (Aave leg)

- Filter: `p.chain_id = 999`, `p.protocol_code IN ('HYPERLEND','HYPURRFI')`, `underlying_token_address` = configured USDC address (default `0xb88339CB7199b77E23DB6E890353E22632Ba630f`), `lower(ur.account_address) = ANY(<address list>)`.
- **Latest row per (account, protocol):** `DISTINCT ON (lower(ur.account_address), p.protocol_code) ... ORDER BY lower(ur.account_address), p.protocol_code, ur.snapshot_ts DESC` (or equivalent).
- **Per protocol:** `SUM(a_token_balance_raw_uint / 10^6)` over those latest rows (one row per account per protocol). That yields **two** subtotals (HyperLend total, HypurrFi total) to add to the ERC4626 leg.

## SQL semantics (ERC4626 leg, multi-account)

- Same `account_address` list as Aave.
- **Latest row per (account, vault):** `DISTINCT ON (lower(a.account_address), lower(a.vault_address)) ... ORDER BY ..., a.snapshot_ts DESC` with vault list unchanged.
- **Sum** `amount_underlying` across all resulting rows (all accounts × configured vaults).

## Breakdown and metadata

- `StrategyEquity.breakdown`: **per ERC4626 vault** keys (vault address → **total** `amount_underlying` summed across the account list); add keys **`HYPERLEND`** and **`HYPURRFI`** (floats) for the Aave legs (each already summed across accounts).
- `meta`: `sources: ["erc4626","aave_hyperlend","aave_hypurrfi"]`, `usdc_decimals: 6`, `account_addresses: [...]` (the resolved list), `underlying_token` / `protocol_codes` as needed for debugging.

## Errors and partial data

- If Postgres unavailable: existing behavior (zero + error meta).
- If ERC4626 query succeeds but Aave returns no rows for one protocol: treat that protocol as **0**, log at debug; do not fail the whole leg unless all sources empty and that is invalid for ops.

## Testing

- Mock PG or fixture rows: assert total = ERC4626 sum + HL + HF with fixed 6 decimals; **add a case with two addresses** where per-leg totals are sums of both.
- Regression: existing vault snapshot tests still pass when lending is mocked.

## Out of scope

- Borrow / net exposure, health factors, or liquidation metrics.
- Additional reserves or protocol codes beyond the two listed (extend via config later).

## Related files

- `tracking/vault/providers/lending.py` — implement three-way sum.
- `.arbit_env.example` — document optional USDC address / protocol list if exposed.
