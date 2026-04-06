# Design: Strategy-Based Manual Deposit / Withdraw (Dual-Write, No Venue)

**Date:** 2026-04-06  
**Status:** Approved for implementation planning  
**Related:** [Vault multi-strategy tracking](./2026-03-31-vault-multi-strategy-tracking-design.md), [Manual cashflows history](./2026-04-05-manual-cashflows-history-design.md)

---

## Problem

Settings **Manual Deposit / Withdraw** uses `POST /api/cashflows/manual`, which records **`venue`** (e.g. Hyperliquid) into `pm_cashflows`. The **Strategies** dashboard and APR math are **strategy-scoped** (`vault_cashflows` + `tracking/vault/snapshot.py`). Manual entries must **attribute capital to a strategy** so per-strategy cashflow-adjusted APR is correct, not only vault totals. The product no longer needs **venue** on this flow.

## Goals

1. Replace **venue** with **`strategy_id`** on manual deposit/withdraw (UI + API). Strategy options come from the vault registry (same universe as Lending, Delta Neutral, future strategies).
2. **Dual-write:** each successful manual entry inserts **both** `vault_cashflows` (strategy attribution, APR inputs) **and** `pm_cashflows` (legacy portfolio net-deposit sums and existing PM tooling).
3. **Remove venue** from the manual API and Settings form — no optional venue, no default venue string in the contract.
4. Preserve **transactional** behavior: both inserts succeed or neither; align **backdated `ts`** behavior with existing vault recalc (`recalc_snapshots`).

## Non-Goals

- Changing **TRANSFER** flows or the separate vault cashflow UI (`CashflowForm` / `/vault/cashflows`) beyond what is needed for shared helpers and consistency.
- Idempotency keys or duplicate-submit protection (add later if needed).
- Automatic dual-write from **every** `POST /api/vault/cashflows` caller in v1 — optional follow-up once manual path is stable.

## Architecture

### Components

| Layer | Responsibility |
|--------|----------------|
| **Settings UI** | Strategy selector (replaces venue); account, type, amount, currency, description. |
| **`POST /api/cashflows/manual`** | Validate `strategy_id`, dual-write in one DB transaction, optional snapshot recalc for backdated `ts`. |
| **Shared helper** | e.g. `record_manual_deposit_withdraw_dual(...)` — insert vault row, insert PM row, commit once; callable from manual router (and later from vault router if desired). |
| **`GET /api/cashflows/manual`** | List manual rows with **`strategy_id`** (from `meta_json` and/or column); **no venue** in API response for new contract. |

### Data flow

1. Client sends `strategy_id`, `account_id`, `cf_type` (DEPOSIT \| WITHDRAW), `amount`, `currency`, optional `ts`, optional `description`.
2. Server validates `strategy_id` against `vault_strategies` (policy: e.g. `ACTIVE` only — exact rule in implementation plan).
3. Insert **`vault_cashflows`** with signed amount (DEPOSIT +, WITHDRAW −), same semantics as `api/routers/vault.py` `create_cashflow`.
4. Insert **`pm_cashflows`** with same `ts`, `cf_type`, signed `amount`, `account_id`, `currency`, `description`; **`venue` removed from user/API** — see schema below.
5. If `ts` is before latest strategy snapshot, invoke existing **recalc** path as vault does today.
6. Return success payload (implementation may expose both row ids or a single primary id — pick one and document in API).

## Data Model

### `vault_cashflows`

No design change: `strategy_id` required for DEPOSIT/WITHDRAW; signing and recalc unchanged.

### `pm_cashflows`

Today `venue` is **`TEXT NOT NULL`** (`tracking/sql/schema_pm_v3.sql`). Removing venue from the product requires a **schema migration**:

- **Chosen direction:** make **`venue` nullable** for rows where strategy-scoped manual cashflows apply; store **`strategy_id`** in **`meta_json`** (e.g. `source: "manual"`, `strategy_id: "<id>"`) for audit and listing.  
- **Existing rows:** keep historical `venue` as-is; new manual dual-write rows use `venue IS NULL` and strategy in `meta_json`.

If listing queries or indexes assume `NOT NULL` venue, update them to handle `NULL` for manual strategy rows only.

**Alternative (if nullable `venue` is undesirable):** add an explicit **`strategy_id`** column on `pm_cashflows` (nullable, FK to `vault_strategies`) and relax or deprecate `venue` usage for DEPOSIT/WITHDRAW manual — implementation plan chooses one approach and applies it consistently.

## API Contract Changes

### `ManualCashflowRequest`

- **Add:** `strategy_id: str` (required).
- **Remove:** `venue`.
- **Keep:** `account_id`, `cf_type`, `amount`, `currency`, optional `ts`, optional `description`.

### `ManualCashflowListItem` / `GET /api/cashflows/manual`

- **Add:** `strategy_id` (from `meta_json` or column).
- **Remove:** `venue` from the response shape **or** keep `venue` as optional legacy for old rows only — prefer **optional `venue`** for backward compatibility in the same endpoint while UI shows strategy first.

## Frontend

- **`ManualCashflowForm`:** drop venue control; load strategy options from vault overview or strategies list endpoint already used elsewhere.
- **`ManualCashflowsTable`:** show **strategy** (and optionally legacy venue for old rows if returned).

## Error Handling

| Case | Behavior |
|------|----------|
| Unknown / invalid `strategy_id` | `400` with clear detail. |
| DB failure mid-transaction | Rollback; no partial dual-write. |
| Backdated `ts` | Same recalc behavior as vault `POST /api/vault/cashflows`. |

## Testing (acceptance scenarios)

1. **Deposit to strategy A** — `vault_cashflows` row tied to A; `_net_external_cashflows_strategy(A, …)` includes the amount; strategy B unchanged for the same window.
2. **Withdraw from strategy A** — negative signed amount in both tables; A’s net external reflects withdrawal.
3. **PM net deposits** — sum of manual DEPOSIT/WITHDRAW in `pm_cashflows` for the test window matches dual-written amounts (portfolio-level math still sees flows).
4. **Backdated `ts`** — recalc path runs (or is asserted) consistent with `tests/test_vault_api.py` / recalc tests.

## Relationship to Manual History Spec

[2026-04-05-manual-cashflows-history-design.md](./2026-04-05-manual-cashflows-history-design.md) defined history from `pm_cashflows` with `venue` in the SELECT. This spec **extends** that: history and API should surface **`strategy_id`** as primary; **`venue`** optional for legacy rows only.

## Self-Review

- **Placeholders:** None; migration is described as nullable `venue` + `meta_json` or explicit column — implementation plan picks one.
- **Consistency:** Dual-write matches user choice (2); vault APR formulas unchanged.
- **Scope:** Single manual entry path + schema + UI + tests; vault-only POST dual-write deferred as non-goal.
- **Ambiguity:** `vault_strategies` status filter for validation — locked in implementation plan (default: ACTIVE).
