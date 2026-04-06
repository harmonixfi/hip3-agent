# Design: Internal Strategy Transfer (Settings Manual Cashflow)

**Date:** 2026-04-06  
**Status:** Approved for implementation planning  
**Related:** [Strategy manual deposit/withdraw dual-write](./2026-04-06-strategy-manual-cashflow-dual-write-design.md), [Vault multi-strategy tracking](./2026-03-31-vault-multi-strategy-tracking-design.md)

---

## Problem

Operators can record **external** capital via Settings (**DEPOSIT** / **WITHDRAW**) with dual-write to `vault_cashflows` and `pm_cashflows`. They also need to record **internal** moves: equity **between strategies** (e.g. reallocate from Strategy A to Strategy B) without implying money entered or left the portfolio from outside.

Those moves affect **two** strategies. If they are not reflected in cashflow-adjusted APR inputs, per-strategy APR can mis-attribute equity changes as pure performance. The vault layer already supports **`TRANSFER`** on `vault_cashflows` (`from_strategy_id`, `to_strategy_id`) via `POST /api/vault/cashflows`, but:

1. Settings manual flow does not offer transfer + dual-write to `pm_cashflows`.
2. Per-strategy APR net cashflows in `tracking/vault/snapshot.py` currently sum only **`DEPOSIT` and `WITHDRAW`** rows keyed by `strategy_id`, so **`TRANSFER` rows are excluded** from the adjustment.

---

## Goals

1. **Single primary UX (Settings):** Extend the Manual cashflow form with a third mode — **transfer between strategies** — with **From strategy** and **To strategy** selectors (ACTIVE strategies from the same registry as deposit/withdraw).
2. **Extend `POST /api/cashflows/manual`** to accept **`cf_type: TRANSFER`** with **`from_strategy_id`**, **`to_strategy_id`**, **`amount` > 0**, plus shared fields (`account_id`, `currency`, optional `ts`, optional `description`).
3. **Dual-write in one DB transaction:** Insert the canonical **vault** transfer row (same shape as `POST /api/vault/cashflows` for TRANSFER) **and** insert **portfolio** rows into `pm_cashflows` with a documented convention (see below).
4. **Fix APR inputs:** Include **internal transfers** in per-strategy net cashflow adjustments: for a transfer of amount **X** from **A** to **B**, strategy **A** is treated like **−X** and **B** like **+X** over the relevant window (consistent with withdraw/deposit sign semantics). Vault-total external capital is unchanged (net zero across strategies).
5. **Backdated `ts`:** Preserve the same **recalc_snapshots** behavior as existing manual and vault cashflow POSTs when `ts` is before the latest strategy snapshot.

---

## Non-Goals

- Changing on-chain or exchange balances (this remains a **labeling** / accounting layer, same as external manual rows).
- Auto-detecting transfers from chain or exchange APIs.
- Idempotency keys or duplicate-submit protection (follow-up if needed).
- **Requiring** `POST /api/vault/cashflows` to dual-write to `pm_cashflows` in this phase (optional follow-up: shared helper + parity).

---

## Architecture

| Layer | Responsibility |
|--------|----------------|
| **Settings UI (`ManualCashflowForm`)** | Type: Deposit \| Withdraw \| **Transfer**. Transfer shows From / To strategy dropdowns, amount, currency, account, description, optional timestamp. Validate `from ≠ to` client-side. |
| **`POST /api/cashflows/manual`** | Validate union: DEPOSIT/WITHDRAW require `strategy_id`; TRANSFER requires `from_strategy_id` + `to_strategy_id`, both ACTIVE, distinct. Call shared dual-write helper; commit; optional recalc. |
| **`tracking/vault/manual_dual_write.py` (or adjacent module)** | `insert_manual_transfer_dual(...)`: vault INSERT + two `pm_cashflows` INSERTs (or documented alternative), single transaction, no partial apply. |
| **`tracking/vault/snapshot.py`** | Extend net cashflow query for strategy **S** to include TRANSFER effects: subtract **amount** when `S = from_strategy_id`, add **amount** when `S = to_strategy_id`, for rows in the time window. Align vault-level APR aggregation so internal transfers do not inflate “external” net deposits. |

---

## Data Model

### `vault_cashflows` (TRANSFER)

- **One row** per transfer: `cf_type = 'TRANSFER'`, `amount > 0`, `from_strategy_id`, `to_strategy_id`, `strategy_id` NULL — **same as** existing `api/routers/vault.py` `create_cashflow` for TRANSFER.
- No schema migration required for vault.

### `pm_cashflows` (dual-write)

**Chosen convention:** Insert **two rows** in the same transaction:

1. **WITHDRAW** with signed amount **−amount**, with `meta_json` including `source: "manual"`, `strategy_id: "<from>"`, and a stable **`internal_transfer_id`** (e.g. UUID or shared string) linking the pair.
2. **DEPOSIT** with signed amount **+amount**, with `meta_json` including `source: "manual"`, `strategy_id: "<to>"`, same **`internal_transfer_id`**.

Rationale: reuses existing `cf_type` values and sign conventions; portfolio sums that net DEPOSIT+WITHDRAW remain interpretable; `meta_json` distinguishes **internal** pairs from true external flows for reporting and `GET /api/cashflows/manual` display.

**Alternative (not chosen for v1):** a single `pm_cashflows` row with `cf_type = 'TRANSFER'` — requires consumers that today assume DEPOSIT/WITHDRAW for manual listing to be updated more broadly.

### APR / snapshot math

- **`_net_external_cashflows_strategy` naming:** Either rename to **`_net_cashflow_adjustments_strategy`** or document that “external” in comments means “non-PnL cashflow adjustments including internal transfers.” Implementation must **add** transfer legs:

  - For each `vault_cashflows` row with `cf_type = 'TRANSFER'` and `ts` in `[start_ts, end_ts]`:
    - If `from_strategy_id = S`: contribution **−amount**
    - If `to_strategy_id = S`: contribution **+amount**

- **Vault-level APR** (`_compute_vault_apr`): Sum of adjustments across all strategies for transfers is **zero**; ensure the vault-level query does **not** double-count or exclude transfers in a way that breaks total-vault APR. (Concrete SQL in implementation: either include TRANSFER-derived legs in the same way as strategy-level, or rely on DEPOSIT+WITHDRAW-only at vault level if total equity already aggregates all strategies — **implementation plan must verify** against `cashflow_adjusted_apr` expectations.)

---

## API Contract

### `ManualCashflowRequest`

- `cf_type`: pattern **`^(DEPOSIT|WITHDRAW|TRANSFER)$`**
- **DEPOSIT | WITHDRAW:** `strategy_id` required; `from_strategy_id` / `to_strategy_id` must be absent.
- **TRANSFER:** `from_strategy_id` and `to_strategy_id` required; `strategy_id` absent (or ignored); `amount` > 0.
- **`account_id`:** Required for all types; one value applies to **both** `pm_cashflows` legs for TRANSFER unless a later revision adds `to_account_id`.

### `ManualCashflowResponse`

- Return **`vault_cashflow_id`** (single vault row).
- Return **`pm_cashflow_ids`** as a **list** (two ids for TRANSFER) **or** document primary + `secondary_pm_cashflow_id` — pick one shape in implementation and keep stable.

### `GET /api/cashflows/manual`

- List rows used for history: include TRANSFER-related **pm** rows with clear typing via `cf_type` + `meta_json` (`internal_transfer_id`), or collapse display in the UI as one logical “Internal transfer” line (UI can group by `internal_transfer_id` in a follow-up; v1 may show two lines).

---

## Frontend

- **Type** control: Deposit | Withdraw | **Transfer between strategies**.
- **Deposit/Withdraw:** Single strategy select (unchanged).
- **Transfer:** From strategy, To strategy (ACTIVE list from `fetchVaultOverview` or equivalent), amount, currency, account, description, optional timestamp.
- **Validation:** Block submit when from === to; show error string.
- **Copy:** Clear labels so operators do not confuse internal transfer with external deposit/withdraw.

---

## Testing

- API: TRANSFER success path; `from === to` → 400; unknown or inactive strategy → 400; assert vault row + two pm rows; assert snapshot recalc when backdated.
- APR: extend coverage (e.g. alongside `tests/test_manual_cashflow_apr.py`) so a transfer does not skew per-strategy cashflow-adjusted APR incorrectly vs. expected netting.
- Regression: vault TRANSFER row shape matches existing `POST /api/vault/cashflows` insert.

---

## Spec self-review

| Check | Result |
|--------|--------|
| Placeholders | None intentional; vault-level APR SQL left as “verify in implementation plan” to avoid wrong SQL in spec. |
| Consistency | Dual-write uses two pm legs + one vault row; APR reads vault TRANSFER rows. |
| Scope | Focused on Settings + manual API + snapshot APR + tests. |
| Ambiguity | `account_id` single for both legs; response uses list of pm ids or documented alternative. |

---

## Implementation next step

After this spec is reviewed, use the **writing-plans** skill to produce a step-by-step implementation plan (API, dual-write helper, snapshot changes, frontend, tests).
