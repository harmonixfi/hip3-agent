# Harmonix NAV Postgres — Reader Guide (hip3-agent)

External projects (e.g. **hip3-agent**) connect via `HARMONIX_NAV_DB_URL` (or the same shape as `DATABASE_URL`) to read NAV and lending-related data. This document describes schemas, authoritative columns, identifiers, and copy-paste SQL. **No secrets** — redact host, user, and password in copies.

---

## 1) Connection

**Environment variable:** This repo’s apps use `DATABASE_URL`. If hip3-agent uses `HARMONIX_NAV_DB_URL`, treat it as the same **libpq** connection string the SQLAlchemy/psycopg stack expects.

**Expected URL shape:**

```text
postgresql://USER:PASSWORD@HOST:PORT/DATABASE
```

Example (fake values): `postgresql://harmonix_reader:***@db.example.com:5432/harmonix_nav`

- **SSL:** Not fixed in `.env.example`. For managed Postgres, append `?sslmode=require` (or your provider’s required params) if TLS is mandatory.
- **Database name:** Typically `harmonix_nav` (see `.env.example`).

**Privileges:** A **read-only** role with `SELECT` on `gold.*` (and optionally `raw.*` if you debug) is enough for the queries below. No `INSERT`/`UPDATE`/`DELETE` required.

---

## 2) Schema map

| Schema | Role |
|--------|------|
| **`raw`** | Hourly/protocol ingestion: positions, vault snapshots, exchange rates, Hyperliquid, etc. Source for GOLD transforms. |
| **`gold`** | Reporting dimensions + facts: NAV, position snapshots, cashflows, registry (`dim_*`). **This is where hip3-agent should read “official” NAV.** |
| **`nav`** | Reserved; **currently empty** per `docs/Database Schema.md`. Do not assume tables here. |

### Tables / views relevant to vault equity & lending context

| Full name | One-line purpose | Grain (one row =) |
|-----------|------------------|-------------------|
| **`gold.fact_nav_daily_vault`** | Hourly NAV fact: balances, NAV in base, PPS, APR. | **One row per `(ts_hour_utc, vault_id)`** — each successful GOLD run overwrites the same hour via upsert. |
| **`gold.v_fact_nav_daily_vault`** | **Daily** “official” slice of the table above. | **One row per `(nav_date, vault_id)`** — only the row whose `ts_hour_utc` equals **`nav_date` at 04:00 UTC**. |
| **`gold.dim_vault`** | Vault registry: id, name, on-chain address, cutoff, status. | One row per vault. |
| **`gold.dim_strategy`** | Strategies inside a vault (`strategy_id`, `strategy_type`, `vault_id`). | One row per strategy. |
| **`gold.dim_leg`** | Legs (wallets/protocols) tied to a strategy. | One row per leg. |
| **`gold.fact_position_snapshot_hourly`** | Hourly position economics: `qty`, `price_in_base`, **`value_base`** (HYPE-equivalent in this platform). | **One row per `(ts, leg_id)`**. |
| **`gold.fact_vault_smart_contract_state_hourly`** | Vault contract balances / supply / pending withdraws (feeds NAV). | **One row per `(ts, vault_address)`** (hourly). |
| **`gold.fact_cashflow_event`** | Normalized cashflows (optional for reconciliation). | Event-level. |
| **`gold.fact_lending_apr_snapshot_hourly`** | **Market-level lending APR** (supply/borrow APR by protocol/pair) — **not** vault equity. | One row per `(timestamp_hour, protocol, borrow_asset, pair)`. |

---

## 3) Authoritative numbers

### a) Vault-level total portfolio / NAV

**Computed in code:** `build_fact_nav_daily_vault` (`src/harmonix_nav/flows/nav/build_fact_nav_daily_vault.py`).

- **`total_balance`** (stored on `gold.fact_nav_daily_vault`):  
  **`balance + withdraw_pool + contract`**, where:
  - **`balance`** = sum of **`value_base`** over **all active strategies** for that vault, from **`gold.fact_position_snapshot_hourly`** at the **latest `ts ≤ cutoff`** (same cutoff logic as NAV).
  - **`withdraw_pool`** / contract components come from **`gold.fact_vault_smart_contract_state_hourly`** and optional balance-contract WHYPE/native (see flow).

**Units:** **Not USD.** Amounts are **`NUMERIC`** in the vault’s **base / HYPE-equivalent** convention used in GOLD (`value_base` is documented across the repo as HYPE-equivalent base units for the Harmonix vault). **`dim_vault.base_asset`** describes the vault’s base label (e.g. HYPE).

**Is `total_balance` the right “total equity” column?**  
It is the flow’s **gross** vault aggregate **including** assets notionally in the withdraw pool and contract top-ups. For **share-price–consistent “NAV”**, see **`nav_end_base`** below.

### b) `nav_end_base` vs `total_balance`

From the same flow:

- **`nav_end_base`** = **`effective_nav`** =  
  **`total_balance - withdraw_pool_amount - pending_withdraw_amount`**  
  (i.e. NAV **after** stripping withdraw pool and pending withdraw from the gross total for **effective NAV / PPS** logic).

- **`nav_start_base`** = previous **calendar day’s** **`nav_end_base`** at the **same `ts_hour_utc`** (hour-aligned), when that row exists.

**When to use which for hip3-agent:**

| Column | Use when |
|--------|----------|
| **`total_balance`** | “Everything counted toward gross vault assets” including pool/contract components as defined in the flow. |
| **`nav_end_base`** | “NAV consistent with internal **`price_per_share`**” (effective NAV for shares). |
| **`price_per_share`** | NAV per share in base units when `effective_shares > 0`. |

There is **no separate USD NAV column** in this table; USD would require multiplying base by a price from elsewhere (not in this fact table).

### c) Duplicates / re-runs / “latest” row

- **Primary key:** `(ts_hour_utc, vault_id)`.
- **Upsert:** Re-running the flow for the same hour **replaces** the row (`ON CONFLICT DO UPDATE` in `nav_writers.py`). So there is **at most one row per vault per UTC hour**.
- **`computed_at`:** Timestamp when that row was last written; use for debugging freshness, not as a business key.
- **Daily official row:** Use **`gold.v_fact_nav_daily_vault`**, or filter **`gold.fact_nav_daily_vault`** with  
  `ts_hour_utc = (nav_date::timestamp AT TIME ZONE 'UTC' + interval '4 hours')`  
  (see migration `0025` — **04:00 UTC** snapshot per `nav_date`).

---

## 4) Identifiers

### `vault_id`

- **Type:** `TEXT`, primary key of **`gold.dim_vault`**.
- **Source of truth:** Registry YAML is synced into dimensions via **`sync_dim_registry`**; **`gold.dim_vault`** is what consumers should query.

**List valid vault ids:**

```sql
SELECT vault_id, vault_name, status, base_asset, vault_address
FROM gold.dim_vault
ORDER BY vault_id;
```

Filter **`status = 'active'`** for production NAV.

### “Lending-only” vs whole vault

- **`gold.fact_nav_daily_vault` is whole-vault:** It sums **all** active strategies’ leg `value_base` for that vault (PT, LP, Morpho supply, loops, buffer, reserved fund, etc. — whatever is modeled in GOLD for that vault).
- There is **no** column that isolates “Lending strategy NAV” on this table.

If hip3-agent’s **LENDING** type is supposed to match **only** lending-like sleeves, you must **derive** it from **`gold.fact_position_snapshot_hourly`** joined to **`gold.dim_leg` / `gold.dim_strategy`** and filter by **`gold.dim_strategy.strategy_type`** (and/or `protocol` on legs). Example strategy types in registry YAML include `morpho_supply`, `whype_borrow`, `erc4626_deposit`, `buffer_deposits`, `lst_looped`, etc. — **the product must define which `strategy_type` values count as “Lending”.**

If the product definition is **“use the Harmonix vault headline NAV”** for that LENDING agent, then **whole-vault `nav_end_base` or `total_balance` from `v_fact_nav_daily_vault` is the intentional match** — document that product choice explicitly.

---

## 5) SQL — copy-paste ready

### Query A — One scalar “current” equity for a vault (daily official, recommended)

Uses the **daily view** (04:00 UTC row per `nav_date`). Replace `:vault_id` (use bound parameter or literal in application code).

```sql
SELECT
    f.nav_date,
    f.vault_id,
    f.total_balance,
    f.nav_end_base,
    f.price_per_share,
    f.computed_at
FROM gold.v_fact_nav_daily_vault f
JOIN gold.dim_vault v ON v.vault_id = f.vault_id
WHERE v.status = 'active'
  AND f.vault_id = :vault_id
ORDER BY f.nav_date DESC
LIMIT 1;
```

**Example fake result**

| nav_date   | vault_id        | total_balance | nav_end_base | price_per_share | computed_at |
|------------|-----------------|---------------|--------------|-----------------|-------------|
| 2026-03-31 | hype-vault-001  | 12345678.90 | 12000000.00  | 1.0234          | 2026-03-31T04:16:00Z |

**If you need “as-of latest hour” (not necessarily daily close):**

```sql
SELECT total_balance, nav_end_base, nav_date, ts_hour_utc, computed_at
FROM gold.fact_nav_daily_vault
WHERE vault_id = :vault_id
ORDER BY ts_hour_utc DESC
LIMIT 1;
```

### Query B — Per-strategy breakdown (JSON aggregation example)

Sums **`value_base`** at the latest snapshot **on or before** a cutoff (align cutoff with NAV policy if needed). Replace `:vault_id` and the cutoff timestamp.

```sql
WITH cutoff AS (
  SELECT TIMESTAMPTZ '2026-04-01 04:00:00+00' AS ts  -- example
),
latest_ts AS (
  SELECT MAX(p.ts) AS ts
  FROM gold.fact_position_snapshot_hourly p
  JOIN gold.dim_leg l ON l.leg_id = p.leg_id
  JOIN gold.dim_strategy s ON s.strategy_id = l.strategy_id
  CROSS JOIN cutoff c
  WHERE s.vault_id = :vault_id
    AND s.status = 'active'
    AND p.ts <= c.ts
)
SELECT jsonb_object_agg(s.strategy_id, to_jsonb(x.*))
FROM (
  SELECT
    s.strategy_id,
    s.strategy_name,
    s.strategy_type,
    SUM(COALESCE(p.value_base, 0)) AS value_base_sum
  FROM gold.fact_position_snapshot_hourly p
  JOIN gold.dim_leg l ON l.leg_id = p.leg_id
  JOIN gold.dim_strategy s ON s.strategy_id = l.strategy_id
  JOIN latest_ts lt ON p.ts = lt.ts
  WHERE s.vault_id = :vault_id
    AND s.status = 'active'
  GROUP BY s.strategy_id, s.strategy_name, s.strategy_type
) x
JOIN gold.dim_strategy s ON s.strategy_id = x.strategy_id;
```

Adjust `cutoff` to match `dim_vault` NAV cutoff if you need strict alignment with `build_fact_nav_daily_vault`.

---

## 6) Freshness & ops

| Topic | Detail |
|--------|--------|
| **Schedule** | Prefect deployment **`run-all-gold-flows`**: cron **`15 * * * *`** **UTC** (runs once per hour at **:15**). That run includes **`build_fact_nav_daily_vault`**. See `prefect.yaml`. |
| **RAW vs GOLD** | Hourly RAW ingest runs at **:00** UTC; GOLD at **:15** UTC — NAV facts assume GOLD inputs exist for that hour. |
| **Daily view** | **`v_fact_nav_daily_vault`** exposes the **`nav_date`** row taken at **04:00 UTC** (`ts_hour_utc = nav_date + 4 hours`). |
| **NULL `total_balance`** | Possible if logic fails partially; treat as data issue. Prefer **`nav_end_base`** + **`price_per_share`** sanity checks. |
| **Multiple vaults** | Always filter **`vault_id`**; never assume a single-vault DB. |
| **Test / inactive vaults** | Filter **`gold.dim_vault.status = 'active'`** for production. |

---

## 7) Glossary

| Plain language | Column / object |
|----------------|-----------------|
| **Harmonix vault NAV (effective)** | **`gold.fact_nav_daily_vault.nav_end_base`** (and daily: same column in **`gold.v_fact_nav_daily_vault`**). |
| **Gross vault assets (flow definition)** | **`total_balance`** = positions + withdraw pool + contract component per flow. |
| **Lending sleeve / protocol exposure** | Not a single NAV column; use **`gold.fact_position_snapshot_hourly`** + **`dim_strategy`** / **`dim_leg`**. |
| **Total balance** | **`total_balance`** — gross measure per §3; not USD. |
| **Base / HYPE-equivalent** | **`value_base`**, **`nav_end_base`**, **`total_balance`** in this pipeline are in the **internal base** convention (HYPE-equivalent for Harmonix vault modeling), **not** USD. |
| **Official daily snapshot** | **`gold.v_fact_nav_daily_vault`** (04:00 UTC row per `nav_date`). |
| **Lending market APR** | **`gold.fact_lending_apr_snapshot_hourly`** — rates/liquidity, **not** vault equity. |

---

## Related docs

- `docs/Database Schema.md` — full table list
- `docs/NAV Daily Vault — Dashboard Queries.md` — Metabase-oriented SQL for NAV
- `CLAUDE.md` — points to `docs/` for onboarding

---

**Verification note:** Reading **`gold.fact_nav_daily_vault`** filtered only by **`vault_id`** and “latest row” without using **`v_fact_nav_daily_vault`** or **`ORDER BY ts_hour_utc DESC`** can mix **daily vs hourly** semantics. For **daily “close” equity**, prefer **`gold.v_fact_nav_daily_vault`** + **`MAX(nav_date)`**, or **`ORDER BY nav_date DESC LIMIT 1`** for that vault.
