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