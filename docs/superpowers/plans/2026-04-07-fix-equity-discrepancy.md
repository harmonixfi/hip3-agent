# Fix Equity Discrepancy (HL $56K vs UI $34K) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix stale alt-wallet equity snapshot so the UI shows the correct ~$52–56K instead of stale $34K.

**Architecture:** The puller skips writing an account snapshot when `has_managed_legs=False`. The bug is `meta_json=NULL` in `pm_legs` for all 9 open legs, causing every leg to default to `wallet_label="main"`. This makes `has_managed_legs=False` for the `alt` wallet. Fix = re-run `sync-registry` so `meta_json` gets the correct `wallet_label="alt"`, then re-pull.

**Tech Stack:** SQLite (`tracking/db/arbit_v3.db`), Python scripts (`scripts/pm.py`, `scripts/pull_positions_v3.py`, `scripts/pipeline_hourly.py`), `tracking/position_manager/db_sync.py` (`upsert_leg`).

---

## Diagnosis Summary

| What | Value |
|------|-------|
| HL UI total equity (alt wallet) | $56,987 |
| Our UI total equity | $34,310 |
| Gap | ~$22,677 |
| Alt wallet last snapshot | 2026-03-31 (stale 7+ days) |
| Alt wallet actual equity (live API) | Native $6,685 + Hyna $14,519 + XYZ $10,092 + Spot ~$21,700 ≈ **$53,000** |
| Root cause | `pm_legs.meta_json = NULL` → all legs default to `wallet_label="main"` → `has_managed_legs=False` for alt → snapshot skipped |
| equity_config.json | Already correct: `builder_dexes: ["xyz","hyna"]`, spot exclusions for alt address |

---

### Task 1: Verify the bug in DB

**Files:**
- Read: `tracking/db/arbit_v3.db`

- [ ] **Step 1: Confirm all open legs have NULL meta_json**

```bash
source .arbit_env && python3 -c "
import sqlite3, json
con = sqlite3.connect('tracking/db/arbit_v3.db')
rows = con.execute(\"SELECT leg_id, meta_json FROM pm_legs WHERE position_id IN (SELECT position_id FROM pm_positions WHERE status='OPEN')\").fetchall()
for leg_id, meta_json in rows:
    meta = json.loads(meta_json) if meta_json else {}
    wl = meta.get('wallet_label', '<MISSING>')
    print(f'{leg_id:50s} wallet_label={wl}')
"
```

Expected: all 9 legs show `wallet_label=<MISSING>`.

---

### Task 2: Fix — sync wallet_label to DB

**Files:**
- Execute: `scripts/pm.py sync-registry`

- [ ] **Step 1: Run sync-registry to propagate wallet_label into meta_json**

```bash
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
```

Expected output: "Synced N positions" with no errors.

- [ ] **Step 2: Verify meta_json now has wallet_label**

```bash
source .arbit_env && python3 -c "
import sqlite3, json
con = sqlite3.connect('tracking/db/arbit_v3.db')
rows = con.execute(\"SELECT leg_id, meta_json FROM pm_legs WHERE position_id IN (SELECT position_id FROM pm_positions WHERE status='OPEN')\").fetchall()
for leg_id, meta_json in rows:
    meta = json.loads(meta_json) if meta_json else {}
    wl = meta.get('wallet_label', '<MISSING>')
    print(f'{leg_id:50s} wallet_label={wl}')
"
```

Expected: all 9 legs now show `wallet_label=alt`.

---

### Task 3: Re-pull positions to write fresh equity snapshot

**Files:**
- Execute: `scripts/pull_positions_v3.py`

- [ ] **Step 1: Pull positions — expect "Snapshots written: 2" (main + alt)**

```bash
source .arbit_env && .venv/bin/python scripts/pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid
```

Expected output includes:
```
wallet=alt... OK (N legs)
...
Snapshots written: 2
```

- [ ] **Step 2: Verify new alt snapshot in DB with correct equity**

```bash
source .arbit_env && python3 -c "
import sqlite3
from datetime import datetime, timezone
con = sqlite3.connect('tracking/db/arbit_v3.db')
rows = con.execute('SELECT account_id, total_balance, ts FROM pm_account_snapshots ORDER BY ts DESC LIMIT 6').fetchall()
for account_id, balance, ts in rows:
    dt = datetime.fromtimestamp(ts/1000, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f'{account_id[:20]}...  balance=\${balance:,.2f}  ts={dt}')
"
```

Expected: `0x3c2c...2453` (alt) shows balance ~$50,000+ with today's timestamp.

---

### Task 4: Refresh portfolio snapshot

**Files:**
- Execute: `scripts/pipeline_hourly.py`

- [ ] **Step 1: Run pipeline with skip-ingest to recompute portfolio snapshot**

```bash
source .arbit_env && .venv/bin/python scripts/pipeline_hourly.py --skip-ingest
```

Expected: `portfolio_snapshot` step shows `total_equity_usd` around $52,000–56,000.

- [ ] **Step 2: Check UI total equity matches HL (~$52K+)**

Open the dashboard and confirm:
- Total Equity card shows ~$52K–56K
- Wallet breakdown shows alt wallet with ~$52K

---

### Task 5: Document fix in lessons.md

**Files:**
- Modify: `docs/tasks/lessons.md`

- [ ] **Step 1: Add lesson entry**

Add to `docs/tasks/lessons.md` under Active Lessons:

```markdown
### [database] DB-001: sync-registry must be re-run after adding wallet_label to positions.json
- **Context:** wallet_label added to config/positions.json but pm_legs.meta_json stayed NULL → puller defaulted all legs to wallet_label="main" → alt wallet equity snapshot skipped → 7-day stale data
- **Wrong:** Edit positions.json → expect DB to auto-update
- **Right:** Edit positions.json → `pm.py sync-registry` → verify meta_json in pm_legs
- **Root cause:** `upsert_leg` writes wallet_label to meta_json but only on INSERT/UPDATE via sync_registry
- **Last violated:** 2026-04-07
```

- [ ] **Step 2: Commit**

```bash
git add docs/tasks/lessons.md
git commit -m "docs: add DB-001 lesson — sync-registry required after positions.json wallet_label changes"
```
