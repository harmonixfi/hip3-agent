# Session handoff — 2026-04-09 (Vault / Lending / Felix / Dashboard)

For the next engineer or chat session: what we did, what’s left, and how to operate this stack.

---

## 1. Goals addressed

- **Lending:** Include **Morpho Felix USDC** (`0x8A862fD6c12f9ad34C9c2ff45AB2b6712e8CEa27`) in the ERC4626 vault set so `LendingProvider` sums three vaults (two existing defaults + Morpho). Spec: `docs/superpowers/specs/2026-04-08-lending-felix-usdc-morpho-vault-design.md`.
- **Harmonix NAV DB:** Fix local connection and clarify that **lending equity is read from Postgres**, not “ingested” by hip3-agent into NAV.
- **Dashboard:** Explain why UI showed $0 / wrong numbers vs SQLite; align **API**, **`.env`**, and **DB path**.
- **Felix:** Register Felix in `strategies.json`, fix `pm_legs` missing `account_id`, document pull vs `pipeline_hourly`, JWT expiry.
- **Delta Neutral:** Show Felix in DN breakdown; `DeltaNeutralProvider` updated so Felix wallets from `strategies.json` are always included (with leg fallback when snapshot missing).

---

## 2. Config & code changes (repo)

| Area | Change |
|------|--------|
| `config/strategies.json` | Lending: `erc4626_vault_addresses` — **three** vaults (must replace full default set). DN: added `{"label":"felix","venue":"felix","address":\<FELIX_WALLET_ADDRESS\>}`. |
| `config/positions.json` | Felix legs `pos_xyz_MU_FELIX`, `pos_xyz_MSTR_FELIX`: `wallet_label` **`felix`** (was `alt`) so `pm.py sync-registry` sets `account_id`. |
| `tracking/vault/providers/delta_neutral.py` | Felix from strategy wallets: always include in breakdown; snapshot **or** `_felix_open_leg_notional_usd` fallback; HL wallets unchanged (snapshot required). |
| `scripts/diagnose_lending_equity.py` | **New:** prints resolved chain/accounts/vaults and row counts vs Harmonix `raw.*` tables + `get_equity()`. |

After editing `strategies.json`: **`source .arbit_env && .venv/bin/python scripts/vault.py sync-registry`**.

After editing `positions.json`: **`source .arbit_env && .venv/bin/python scripts/pm.py sync-registry`**.

---

## 3. Environment / ops lessons

### `HARMONIX_NAV_DB_URL`

- Must be valid `postgresql://user:pass@host:port/db` (there was a bad `postgresql://"//...` typo once).
- Local Docker Postgres may listen on **15432**, not 5432 — `ss` can misleadingly match `15432` if you `grep 5432`.

### Lending pipeline

- **Harmonix** fills `raw.vault_erc4626_*` / `raw.aave_*`. hip3-agent **only reads** Postgres at vault snapshot time.
- **Refresh app DB:** `source .arbit_env && .venv/bin/python scripts/vault.py snapshot` (or full `scripts/pipeline_hourly.py`, whose **step 7** is the same vault snapshot).

### Cron (production)

- **`docker/crontab`**: `pipeline_hourly.py` runs **hourly at :30** → includes vault snapshot. No need to run `vault.py snapshot` manually unless you want an **immediate** refresh.
- **Felix account data** comes from **`pull_positions_v3.py`** (every 5 min in cron), **not** from `pipeline_hourly.py`.

### Frontend + API

- Next.js server components call **`API_BASE_URL`** + **`API_KEY`** from **`frontend/.env.local`** — must match **`HARMONIX_API_KEY`** on the FastAPI process.
- If API returns `500` “API key not configured”, set **`HARMONIX_API_KEY`** for uvicorn. If `401`, align **`API_KEY`** in Next with that value.

### Felix JWT

- **`FELIX_EQUITIES_JWT`** expires; **401** on portfolio → refresh JWT in `.arbit_env`, re-run **`pull_positions_v3.py`** (with `--venues felix` or full pull).

### Fill ingest warnings (`None`, `dex=''`, 422)

- Caused by **`pm_legs.account_id` NULL** for open legs (was Felix legs before `wallet_label` + `strategies.json` fix). After fix: **`pm.py sync-registry`** and re-run pipeline or fill ingest.

---

## 4. Follow-ups / known gaps

1. **Felix breakdown `equity_usd` still 0 in UI while pull prints ~10.5k `total_balance`**  
   Likely **`account_id` case mismatch**: puller stores **lowercase** in `pm_account_snapshots`; `DeltaNeutralProvider` may query with **checksummed** address from JSON — SQLite `=` is case-sensitive. **Next step:** normalize to `lower()` in SQL or Python when querying `pm_account_snapshots` (and/or when comparing `counted_lower`).

2. **`pipeline_hourly.py` does not pull Felix** — keep **`pull_positions_v3.py`** on schedule for Felix + HL snapshots.

3. **Precedence:** `HARMONIX_LENDING_ERC4626_VAULTS` vs `config_json` — confirm intended order (spec says env overrides all; code may apply config after env — verify if operators rely on env-only overrides).

---

## 5. Command cheat sheet

```bash
source .arbit_env   # always first for Python scripts

# Registry → SQLite
.venv/bin/python scripts/vault.py sync-registry
.venv/bin/python scripts/pm.py sync-registry

# Felix + HL positions → pm_account_snapshots / pm_legs
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json

# Vault strategy equity (lending from NAV DB + others from SQLite)
.venv/bin/python scripts/vault.py snapshot

# Full hourly (includes vault snapshot step 7)
.venv/bin/python scripts/pipeline_hourly.py

# Lending debug vs Harmonix
.venv/bin/python scripts/diagnose_lending_equity.py
```

**Verify lending in SQLite:**

```bash
sqlite3 tracking/db/arbit_v3.db \
  "SELECT equity_usd, meta_json FROM vault_strategy_snapshots WHERE strategy_id='lending' ORDER BY ts DESC LIMIT 1;"
```

**Verify Felix snapshots:**

```bash
sqlite3 tracking/db/arbit_v3.db \
  "SELECT account_id, venue, total_balance FROM pm_account_snapshots WHERE venue='felix' ORDER BY ts DESC LIMIT 3;"
```

---

## 6. Key files

- Lending provider: `tracking/vault/providers/lending.py`
- DN provider: `tracking/vault/providers/delta_neutral.py`
- Vault snapshot: `tracking/vault/snapshot.py`, CLI `scripts/vault.py`
- Hourly orchestrator: `scripts/pipeline_hourly.py`
- Cron: `docker/crontab`
- Morpho spec: `docs/superpowers/specs/2026-04-08-lending-felix-usdc-morpho-vault-design.md`

---

*End of handoff — 2026-04-09.*
