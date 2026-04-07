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