# Project Lessons Log

> Rules: Read this file at the START OF EVERY SESSION. Log a new entry when a mistake
> costs >5 min of debugging or when you receive a correction from the user.
> Each entry MUST have concrete Wrong/Right code patterns (copy-pasteable).
> When file exceeds 40 entries → consolidate (see CLAUDE.md section 3).

---

## Categories
<!-- Add new categories as needed, keep prefix consistent -->
<!-- [env] [async] [database] [api] [config] [position] [error-handling] [testing] [deployment] [defi] -->

---

## Active Lessons

### [env] ENV-001: Always source .arbit_env before running python commands
- **Context:** Running scripts/pm.py without sourcing env → crash due to missing env vars
- **Wrong:** `.venv/bin/python scripts/pm.py sync-registry`
- **Right:** `source .arbit_env && .venv/bin/python scripts/pm.py sync-registry`
- **Root cause:** No pre-check for required env vars in entrypoint
- **Last violated:** —

### [config] CFG-001: positions.json is source of truth — never edit DB directly
- **Context:** Wanted to update qty quickly → edited DB directly → state drift with config file
- **Wrong:** `UPDATE positions SET qty = ... WHERE id = ...`
- **Right:** Edit `config/positions.json` → `pm.py sync-registry` → verify
- **Root cause:** Skipped workflow for perceived speed
- **Last violated:** —

### [database] DB-001: sync-registry must be re-run after adding wallet_label to positions.json — and pm.py must include wallet_label in meta_json
- **Context:** wallet_label added to positions.json for OPEN legs, but pm_legs.meta_json stayed NULL → puller defaulted all legs to wallet_label="main" → alt wallet has_managed_legs=False → equity snapshot skipped → 7-day stale data showing $34K vs actual $56K
- **Wrong:** Edit positions.json → assume DB auto-updates; or run sync-registry without wallet_label in meta_json dict
- **Right:** Edit positions.json → `pm.py sync-registry` (which now includes wallet_label in meta_json) → verify: `SELECT leg_id, meta_json FROM pm_legs WHERE position_id IN (SELECT position_id FROM pm_positions WHERE status='OPEN')`
- **Root cause:** `scripts/pm.py:sync_registry` built meta_json for pm_legs without `wallet_label` field; puller reads wallet_label from meta_json defaulting to "main", making alt-wallet legs invisible
- **Fix location:** `scripts/pm.py` line ~158 — add `"wallet_label": leg.wallet_label` to the meta_json dict
- **Last violated:** 2026-04-07

### [api] API-001: Hyperliquid unified-account mode shares collateral across dexes — don't sum accountValue
- **Context:** Pull script summed `accountValue` from native + each builder dex, producing $26,889 vs user's $19,955 on wallet 0xd4737 (a `unifiedAccount`). Unified mode returns the SAME shared pool for every `dex=` query, so summing double-counts collateral.
- **Wrong:** `total = perp_native + sum(builder_dex accountValue) + spot_equity` for every account
- **Right:** Detect mode via `POST /info {"type":"userAbstraction","user":addr}`. For `unifiedAccount`/`portfolioMargin`: `total = spot_equity + Σ(unrealizedPnl across dexes)`. For `disabled`/`default`: keep legacy sum.
- **Root cause:** Builder dex API on unified accounts returns master collateral + that dex's uPnL as `accountValue`; summing across dexes duplicates the shared pool.
- **Fix location:** `tracking/connectors/hyperliquid_private.py::fetch_account_snapshot`
- **Last violated:** 2026-04-17

### [correctness] AGENT-001: Trust user-provided ground truth (exchange UI) over DB-derived numbers
- **Context:** User provided wallet balance $19,955 from exchange. DB pull showed $26,889. Agent first-impulse was to explain DB as correct and reconcile via classification. User corrected: "bạn phải trust số mình gửi để QC chứ sao lại trust số db".
- **Wrong:** Treat DB as authoritative; justify mismatch by reframing user's number as "subset view"
- **Right:** Treat user's exchange-observed number as ground truth; inspect DB computation for bugs when they diverge >1% drift
- **Root cause:** DB is derived state; exchange is source of truth. When they diverge, the computation is suspect.
- **Last violated:** 2026-04-17

### [correctness] AGENT-002: Never infer financial transaction amounts — ask the user
- **Context:** Agent derived a $2,370.09 WITHDRAW amount from `old_snapshot - new_snapshot` delta and tried to insert it. Harness blocked the action (User Intent Rule #4).
- **Wrong:** `INSERT INTO pm_cashflows ... amount=<delta inferred from snapshots>`
- **Right:** Report the observed delta to the user and request the exact amount + asset before any financial-record insert
- **Root cause:** Snapshot deltas conflate trading PnL, deposits, withdrawals, and price drift — inferring a specific transaction from them risks mis-attribution
- **Last violated:** 2026-04-17

### [database] DB-002: finalize_trade commits internally — skip it in dry-run paths
- **Context:** Migration script called finalize_trade inside a dry-run branch, expecting final con.rollback() to clean up. But finalize_trade calls con.commit() internally, so position/leg inserts leaked into the DB even with commit=False.
- **Wrong:** `finalize_trade(con, t["trade_id"])` then `con.rollback()` at end (commit already happened)
- **Right:** Guard finalize_trade behind the commit flag: `if commit: finalize_trade(con, t["trade_id"])`. In dry-run only call create_draft_trade (which does NOT commit), then rollback at the end.
- **Root cause:** finalize_trade calls con.commit() at the end to update leg sizes + position status — it was not designed to be called inside a larger un-committed transaction.
- **Last violated:** 2026-04-17

### [template] XXX-000: Short title describing the lesson
- **Context:** What you were doing when the issue occurred
- **Wrong:** Bad code/command/approach (copy-pasteable)
- **Right:** Correct code/command/approach (copy-pasteable)
- **Root cause:** Why the wrong approach is wrong — the actual underlying reason
- **Last violated:** YYYY-MM-DD

---

## Archived
<!-- Move entries not violated in 5+ consecutive sessions here -->
<!-- Format: ID — one-line summary — archived date -->