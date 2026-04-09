# Lending — add Morpho Felix USDC ERC4626 vault

**Date:** 2026-04-08  
**Status:** Approved for implementation  
**Scope:** Configuration and documentation only unless Harmonix prerequisite is unmet (no `LendingProvider` logic change required for the happy path).

## Goal

Include the **Morpho Felix USDC** vault on HyperEVM in the **ERC4626 leg** of lending equity so `StrategyEquity.equity_usd` sums underlying across **three** vault contracts for the same `lending_accounts` list, plus unchanged HyperLend and HypurrFi legs.

- **Vault (Morpho UI):** [Felix USDC — HyperEVM](https://app.morpho.org/hyperevm/vault/0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27/felix-usdc)
- **Vault contract:** `0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27`

## Prerequisite (Harmonix NAV)

`LendingProvider` reads **only** Harmonix NAV Postgres (`HARMONIX_NAV_DB_URL`). The ERC4626 leg uses the hourly snapshot pipeline described in [2026-03-31-lending-three-source-equity-design.md](./2026-03-31-lending-three-source-equity-design.md).

**Before this vault contributes a non-zero amount**, Harmonix must ingest **`vault_erc4626_snapshot_hourly`** (or equivalent) rows for:

- **Chain:** `999` (HyperEVM), consistent with `_DEFAULT_CHAIN_ID` / `HARMONIX_LENDING_CHAIN_ID`
- **Vault:** `0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27`
- **Accounts:** addresses in `lending_accounts` (same as existing ERC4626 + Aave legs)

If Harmonix does not yet write rows for this vault, the new leg contributes **$0** until upstream is fixed; other legs are unchanged.

## Configuration approach (chosen)

**Explicit vault list in `config/strategies.json`** under the lending strategy’s `config` object.

Use the key **`erc4626_vault_addresses`** (or **`erc4626_vaults`** — both are read by `LendingProvider._chain_and_vaults` in `tracking/vault/providers/lending.py`).

**Critical:** A non-empty list **replaces** `_DEFAULT_ERC4626_VAULTS` entirely. The array **must** include the **two existing default vaults** plus the new Morpho vault:

| Role | Address |
|------|---------|
| Existing (default 1) | `0x808F72b6Ff632fba005C88b49C2a76AB01CAB545` |
| Existing (default 2) | `0x274f854b2042DB1aA4d6C6E45af73588BEd4Fc9D` |
| **New — Morpho Felix USDC** | `0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27` |

`lending_accounts` remains the single wallet list (unchanged unless business requires another address).

After editing `config/strategies.json`, run the vault registry sync used elsewhere so `vault_strategies.config_json` matches (same pattern as other strategy config).

## Environment override

If a deployment sets **`HARMONIX_LENDING_ERC4626_VAULTS`**, it **replaces** both code defaults and `config_json` vault lists when non-empty. Operators must set a **comma-separated list of all three** vault addresses (same order not required for correctness, but listing all is mandatory).

## Verification

1. **Config:** Confirm `config_json` for strategy `lending` contains three vault addresses after sync.
2. **Post-Harmonix:** Run the vault snapshot pipeline; lending equity should increase once Harmonix supplies rows for the new vault.
3. **Sanity check:** Compare the incremental ERC4626 contribution (or per-vault breakdown in logs/meta if exposed) to Morpho’s displayed balance for that vault, allowing small timing/rounding differences.

## Out of scope

- Changing Harmonix ingestion (separate system).
- New per-vault labels in the UI (unless a follow-up product request).
- Modifying HyperLend / HypurrFi logic or `lending_accounts` semantics.

## Self-review

- **Placeholders:** None; addresses and links are explicit.
- **Consistency:** Aligns with [2026-03-31-lending-three-source-equity-design.md](./2026-03-31-lending-three-source-equity-design.md) multi-vault ERC4626 semantics.
- **Scope:** Single feature — extend configured vault set; no provider refactor.
- **Ambiguity:** “Non-zero contribution” depends on Harmonix; stated explicitly.
