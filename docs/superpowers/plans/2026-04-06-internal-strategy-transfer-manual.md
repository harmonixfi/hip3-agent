# Internal Strategy Transfer (Manual Cashflow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or inline execution task-by-task.

**Goal:** Add Settings/API support for internal strategy-to-strategy transfers with vault + pm dual-write, include TRANSFER in per-strategy APR adjustments, and extend the manual cashflow UI.

**Architecture:** One vault `TRANSFER` row (same shape as `POST /api/vault/cashflows`) plus two `pm_cashflows` legs (WITHDRAW/DEPOSIT with `internal_transfer_id` in `meta_json`). Centralize net cashflow math in `net_cashflow_adjustments_strategy()` used by `snapshot.py` and `recalc.py`. Vault-level APR continues to sum only external DEPOSIT/WITHDRAW (TRANSFER excluded).

**Tech stack:** FastAPI, Pydantic v2, SQLite, React/TS frontend.

---

### Task 1: Dual-write helper + net cashflow math

**Files:**
- Modify: `tracking/vault/manual_dual_write.py`
- Modify: `tracking/vault/snapshot.py`
- Modify: `tracking/vault/recalc.py`
- Test: `tests/test_manual_dual_write.py`

- [x] Implement `insert_manual_transfer_dual(...)` → `(vault_id, pm_withdraw_id, pm_deposit_id)` using `uuid.uuid4()` for `internal_transfer_id`; validate both strategies ACTIVE.
- [x] Add `net_cashflow_adjustments_strategy(con, strategy_id, start_ts, end_ts)` in `snapshot.py` (DEPOSIT/WITHDRAW on strategy + TRANSFER legs); use in `_compute_apr_for_strategy`; keep `_compute_vault_apr` unchanged (no TRANSFER in sum).
- [x] Replace `_recompute_strategy_apr` SQL in `recalc.py` with `net_cashflow_adjustments_strategy` import from `snapshot`.

---

### Task 2: API schemas + router

**Files:**
- Modify: `api/models/schemas.py`
- Modify: `api/routers/cashflows.py`
- Test: `tests/test_api.py`

- [x] `ManualCashflowRequest`: optional `strategy_id`, `from_strategy_id`, `to_strategy_id`; pattern includes TRANSFER; `model_validator` for union rules.
- [x] `ManualCashflowResponse`: add `pm_cashflow_ids: list[int]`; keep `cashflow_id` as first pm id.
- [x] `record_manual_cashflow`: branch TRANSFER; list GET: include `internal_transfer_id` from meta; extend SELECT for transfer legs.

---

### Task 3: APR integration tests

**Files:**
- Modify: `tests/test_manual_cashflow_apr.py`

- [x] Transfer scenario (two equal strategies): assert per-strategy and vault APR vs closed form.

---

### Task 4: Frontend

**Files:**
- Modify: `frontend/lib/types.ts`, `frontend/lib/api.ts` if needed
- Modify: `frontend/components/ManualCashflowForm.tsx`

- [x] Type union for manual request; form mode Deposit | Withdraw | Transfer; From/To selects; validation `from !== to`.

---

## Self-review

- Spec coverage: UX, API, dual-write, snapshot+recalc APR, tests, list — mapped to tasks above.
- Vault APR excludes TRANSFER rows (net zero external) — unchanged query.
