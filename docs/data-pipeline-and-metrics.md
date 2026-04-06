# Data Pipeline & Metrics: Monitoring Dashboard

## Overview

```
[Data Sources]          [Pull Scripts]           [Computation]         [API]              [Dashboard UI]
HL API: fills      -->  pull_positions_v3.py  -> pipeline_hourly.py -> GET /portfolio  -> Equity, APR
HL API: prices     -->  pull_position_prices  -> entry_price.py     -> GET /positions  -> uPnL, Spreads
HL API: positions  -->  pull_hyperliquid_v3   -> upnl.py            -> GET /closed     -> Realized P&L
HL API: funding    -->  pm_cashflows.py       -> spreads.py         -> GET /health     -> System status
HL API: spotMeta   -->  backfill_fills.py     -> portfolio.py
```

---

## 1. Data Pull Scripts

### `scripts/pull_positions_v3.py`
- **Schedule**: Every 5 minutes
- **Input**: HL API `clearinghouseState` (per dex: native, xyz, hyna) + `spotClearinghouseState` + `webData2`
- **Output tables**:
  - `pm_account_snapshots` — total equity per wallet (perp margins + spot token values)
  - `pm_leg_snapshots` — current size, price, uPnL per position leg
- **Used for**: Total Equity, Wallet Breakdown, position sizes

### `scripts/pull_position_prices.py`
- **Schedule**: Every 5 minutes (offset +2 min)
- **Input**: HL API `l2Book` (spot via @index, native perps) + `allMids` (builder dex perps)
- **Output table**: `prices_v3` — bid, ask, mid per instrument
- **Instruments fetched**: Only those with active position legs (~11)
  - Spot: `HYPE/USDC`, `XAUT0/USDC`, `LINK0/USDC`, `UFART/USDC` (via L2Book @index → bid/ask)
  - Builder dex: `xyz:GOLD`, `hyna:HYPE`, `hyna:FARTCOIN`, `hyna:LINK` (via allMids → mid only)
  - Native perp: `HYPE`, `FARTCOIN`, `LINK` (via L2Book → bid/ask)
- **Used for**: uPnL computation, Exit Spread computation

### `scripts/pull_hyperliquid_v3.py`
- **Schedule**: Hourly at :20
- **Input**: HL API `meta` + `allMids` + `metaAndAssetCtxs` + `spotMeta`
- **Output tables**:
  - `instruments_v3` — perp + spot instrument definitions
  - `prices_v3` — mid prices for all 50 native perps
  - `funding_v3` — hourly funding rates for all perps
- **Used for**: Market data backdrop, funding rate tracking

### `scripts/pm_cashflows.py`
- **Schedule**: Hourly (via existing cron, not in Docker crontab — runs separately)
- **Input (Hyperliquid)**: HL `/info` POST — `userFunding` (windows by time) → **FUNDING**; `userFillsByTime` → per-fill **`fee`** field → **FEE** (stored negative). Other venues have their own ingest paths inside the same script.
- **Output table**: `pm_cashflows` — FUNDING, FEE, DEPOSIT, WITHDRAW events per position/leg
- **Used for**: Funding earned, Fees paid, Carry APR, Net P&L

### `scripts/backfill_fills.py`
- **Schedule**: Manual (one-time or on-demand)
- **Input**: HL API `userFillsByTime` for all managed wallets
- **Output table**: `pm_fills` — raw trade fills with leg mapping
- **Used for**: Historical entry prices, fill history display

---

## 2. Computation Pipeline (`scripts/pipeline_hourly.py`)

**Schedule**: Hourly at :30. Runs these steps in order:

### Step 1: `spot_meta.py` — Spot Symbol Resolution
- Fetches `spotMeta` from HL API
- Builds `@index → SYMBOL/USDC` map (e.g., `@107 → HYPE/USDC`)
- Used by fill ingester to resolve spot fill coins

### Step 2: `fill_ingester.py` — Fill Ingestion
- **Input**: HL API `userFillsByTime` per wallet per dex
- **Output**: `pm_fills` table (new fills only, dedup by venue+account+tid)
- Resolves spot @index coins, maps fills to position legs

### Step 3: `entry_price.py` — VWAP Entry Price
- **Input**: `pm_fills` (opening fills per leg)
- **Output**: `pm_entry_prices` table + updates `pm_legs.entry_price`
- **Formula**: `avg_entry = SUM(px × sz) / SUM(sz)` for opening fills only
  - LONG leg: opening fills = BUY side
  - SHORT leg: opening fills = SELL side

### Step 4: `upnl.py` — Unrealized PnL (ADR-001)
- **Input**: `pm_entry_prices` + `prices_v3` (latest bid/ask)
- **Output**: Updates `pm_legs.unrealized_pnl` and `pm_legs.current_price`
- **Formulas**:
  - LONG uPnL = `(current_bid − avg_entry) × size`
  - SHORT uPnL = `−(current_ask − avg_entry) × size`
  - Fallback: if bid/ask NULL → use mid → use last
- **Position uPnL** = sum of all leg uPnLs

### Step 5: `spreads.py` — Entry/Exit Spread (ADR-008)
- **Input**: `pm_entry_prices` + `prices_v3` (latest bid/ask)
- **Output**: `pm_spreads` table
- **Formulas**:
  - Entry Spread = `long_avg_entry / short_avg_entry − 1`
  - Exit Spread = `long_exit_bid / short_exit_ask − 1`
  - Spread P&L = `(exit_spread − entry_spread) × 10,000` (in bps)
- Split-leg positions (1 spot + N perps) generate N sub-pairs

### Step 6: `portfolio.py` — Portfolio Aggregation
- **Input**: `pm_account_snapshots`, `pm_cashflows`, `pm_legs`, `pm_portfolio_snapshots`
- **Output**: `pm_portfolio_snapshots` table (1 row per hour)
- **Metrics computed**:
  - Total equity (from latest account snapshots)
  - Total unrealized PnL (sum across open legs)
  - Funding today (FUNDING cashflows since UTC midnight)
  - Funding all-time (since tracking start date)
  - Fees all-time (FEE cashflows since tracking start)
  - Daily change = current equity − 24h-ago equity
  - Cashflow-adjusted change = daily change − net deposits
  - APR = `(cashflow_adjusted_change / prior_equity) × 365`

---

## 3. API Endpoints → Dashboard Mapping

### `GET /api/portfolio/overview` → Dashboard top cards
| API Field | DB Source | Dashboard Display |
|-----------|----------|-------------------|
| `total_equity_usd` | `pm_account_snapshots` (latest per account) | **TOTAL EQUITY** card |
| `equity_by_account` | `pm_account_snapshots` (latest per account) | **WALLET BREAKDOWN** table |
| `daily_change_usd` | `pm_portfolio_snapshots` (latest) | "$X.XX (X.XX%) 24h" |
| `cashflow_adjusted_apr` | `pm_portfolio_snapshots` (latest) | "X.X% APR cashflow-adjusted" |
| `funding_today_usd` | `pm_cashflows` (FUNDING, today) | **FUNDING SUMMARY** Funding Today |
| `funding_alltime_usd` | `pm_cashflows` (FUNDING, all-time) | **FUNDING SUMMARY** Funding All-Time |
| `fees_alltime_usd` | `pm_cashflows` (FEE, all-time) | **FUNDING SUMMARY** Fees All-Time |
| `net_pnl_alltime_usd` | funding + fees | **FUNDING SUMMARY** Net P&L |
| `total_unrealized_pnl` | `pm_legs` (sum unrealized_pnl) | "uPnL $X.XX" |
| `open_positions_count` | `pm_positions` (status != CLOSED) | "N open positions" |

#### Funding Summary card — calculation, data source, and API

The **Funding Summary** panel (`frontend/components/FundingSummary.tsx`) is driven entirely by **`GET /api/portfolio/overview`** (see `api/routers/portfolio.py`). The frontend maps JSON fields as follows:

| UI label | Response field | Type |
|----------|----------------|------|
| Funding Today | `funding_today_usd` | `float` |
| Funding All-Time | `funding_alltime_usd` | `float` |
| Fees All-Time | `fees_alltime_usd` | `float` (typically ≤ 0) |
| Net P&L | `net_pnl_alltime_usd` | `float` |
| Footer “Since …” | `tracking_start_date` | `YYYY-MM-DD` string |

**Formulas (server-side)**

**Timezone contract (Funding Summary):** All “day” boundaries for **Funding Today** and the **Since** date semantics are **UTC+0** (UTC calendar dates), not the viewer’s or server’s local timezone. Manual SQL / CSV exports must use the same UTC “start of day” if you want parity with the dashboard.

- **Funding Today** — Sum of `pm_cashflows.amount` where `cf_type = 'FUNDING'` and `ts` is on or after **UTC midnight of the current day**. Implemented with SQLite: `ts >= strftime('%s', 'now', 'start of day') * 1000` (SQLite `now` is UTC). This value is recomputed on each API request (not taken from `pm_portfolio_snapshots`).

- **Funding All-Time** — `SUM(amount)` for `cf_type = 'FUNDING'` with `ts` ≥ **tracking start**. The default tracking start is `DEFAULT_TRACKING_START` (`"2026-01-15"` in `tracking/pipeline/portfolio.py`), persisted on hourly snapshots as `pm_portfolio_snapshots.tracking_start_date`. The API uses that stored date unless the query parameter **`tracking_start=YYYY-MM-DD`** is passed (validated), in which case that date bounds the sums instead.

- **Fees All-Time** — Same time filter as Funding All-Time, but `cf_type = 'FEE'`. Hyperliquid ingest stores fees as **negative** USDC (`-abs(fee)` from each fill), so the rolled-up sum is usually negative.

- **Net P&L (All-Time, funding + fees only)** —

  `net_pnl_alltime_usd = funding_alltime_usd + fees_alltime_usd`

  Example: funding `+165.39` and fees `-49.21` → net `+116.18`. This is **not** total portfolio P&L: it excludes spread / realized trade P&L and uPnL. For closed positions, **Net P&L** on `GET /api/positions/closed` uses a different formula (spread + funding + fees).

**Ledger source (`pm_cashflows`)**

- Rows are written by **`scripts/pm_cashflows.py`** (`ingest` command), scheduled hourly. For **Hyperliquid**, the script calls the HL **`/info`** POST API in time windows (per dex, including native `""` when spot legs exist):
  - **`userFunding`** → events with `cf_type = 'FUNDING'` on **perp legs only** (USDC amount from the payload; signed as returned by the API). SPOT_PERP spot legs do not receive funding rows.
  - **`userFillsByTime`** → each non-zero **`fee`** → `cf_type = 'FEE'` (stored negative). Perp fills attach to the SHORT perp leg; spot fills (including `@{index}` coins) resolve via **`spotMeta`** the same way as `fill_ingester` and attach to the LONG spot leg (`inst_id` like `HYPE/USDC`).

See `ingest_hyperliquid` in `scripts/pm_cashflows.py` and `tracking/pipeline/hl_cashflow_attribution.py` for dex/coin guards and fee resolution.

**Note:** `pm_fills` also stores per-fill **`fee`** for display and analytics; that is separate from the **`pm_cashflows`** FEE ledger (no duplicate rows in `pm_cashflows` for the same fill—dedupe is by venue/account/ts/type/amount/description; spot vs perp legs use different `leg_id`s).

**Hourly snapshot overlap**

`tracking/pipeline/portfolio.py` also computes `total_funding_today`, `total_funding_alltime`, and `total_fees_alltime` into **`pm_portfolio_snapshots`** using the same conceptual definitions (Python UTC day boundary and the same tracking start string). The **overview API** uses live SQL for funding/fees as above so the dashboard stays consistent with the ledger without waiting for the next hourly bucket.

### `GET /api/positions` → Open Positions table
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `base` | `pm_positions.meta_json` | **Base** |
| `status` | `pm_positions.status` | **Status** |
| `amount_usd` | `pm_positions.meta_json` | **Amount** |
| `unrealized_pnl` | `pm_legs.unrealized_pnl` (sum) | **uPnL** |
| `funding_earned` | `pm_cashflows` (FUNDING per position) | **Funding** |
| `carry_apr` | computed: `(net_carry / amount) / days × 365` | **Carry APR** |
| `sub_pairs[].exit_spread_bps` | `pm_spreads.exit_spread × 10000` | **Exit Spread** |
| `sub_pairs[].spread_pnl_bps` | `pm_spreads.spread_pnl_bps` | **Spread P&L** |

### `GET /api/positions/{id}` → Position Detail page
| API Field | DB Source | Dashboard Section |
|-----------|----------|-------------------|
| `legs[]` | `pm_legs` + `pm_entry_prices` | **Legs table** (inst_id, side, size, entry, current, uPnL) |
| `sub_pairs[]` | `pm_spreads` | **Spread Display** (entry/exit/pnl per sub-pair) |
| `fills_summary[]` | `pm_fills` (count, first/last per leg) | **Fills Summary** |
| `cashflows[]` | `pm_cashflows` (per position) | **Cashflow Table** |
| `daily_funding_series[]` | `pm_cashflows` (FUNDING grouped by date) | **Funding Chart** |

### `GET /api/positions/{id}/fills` → Fills tab
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `fills[].inst_id` | `pm_fills.inst_id` | **Instrument** |
| `fills[].side` | `pm_fills.side` | **Side** |
| `fills[].px` | `pm_fills.px` | **Price** |
| `fills[].sz` | `pm_fills.sz` | **Size** |
| `fills[].fee` | `pm_fills.fee` | **Fee** |
| `fills[].ts` | `pm_fills.ts` | **Time** |

### `GET /api/positions/closed` → Closed Positions page
| API Field | DB Source | Dashboard Column |
|-----------|----------|------------------|
| `duration_days` | `closed_at_ms − created_at_ms` | **Duration** |
| `total_funding_earned` | `pm_cashflows` (FUNDING) | **Funding** |
| `total_fees_paid` | `pm_cashflows` (FEE) | **Fees** |
| `realized_spread_pnl` | `pm_fills.closed_pnl` (sum) | **Spread P&L** |
| `net_pnl` | spread + funding + fees | **Net P&L** |
| `net_apr` | `(net_pnl / amount) / days × 365` | **APR** |

### `GET /api/health` → System status bar
| API Field | DB Source | Dashboard Display |
|-----------|----------|-------------------|
| `last_fill_ingestion` | `pm_fills` MAX(ts) | "Fills: Xh ago" |
| `last_price_pull` | `prices_v3` MAX(ts) | "Prices: Xh ago" |
| `last_position_pull` | `pm_leg_snapshots` MAX(ts) | "Positions: Xh ago" |
| `db_size_mb` | File size of arbit_v3.db | "DB: X.X MB" |
| `open_positions` | `pm_positions` count | "N open" |

---

## 4. Data Flow Diagram

```
Every 5 min:
  pull_positions_v3.py ──> pm_account_snapshots (equity)
                       ──> pm_leg_snapshots (position state)

  pull_position_prices.py ──> prices_v3 (bid/ask/mid for position legs)

Hourly at :20:
  pull_hyperliquid_v3.py ──> instruments_v3, prices_v3, funding_v3

Hourly at :30:
  pipeline_hourly.py:
    1. spot_meta         (fetch @index map)
    2. fill_ingester     ──> pm_fills
    3. entry_price       ──> pm_entry_prices + pm_legs.entry_price
    4. upnl              ──> pm_legs.unrealized_pnl, pm_legs.current_price
    5. spreads           ──> pm_spreads
    6. portfolio         ──> pm_portfolio_snapshots

Hourly (separate cron):
  pm_cashflows.py ──> pm_cashflows (FUNDING, FEE events)
```

---

## 5. DB Tables Summary

| Table | Written by | Read by API | Key fields |
|-------|-----------|-------------|------------|
| `pm_positions` | pm.py sync-registry | positions, portfolio | position_id, status, strategy |
| `pm_legs` | pm.py sync + upnl.py | positions | leg_id, inst_id, side, size, entry_price, unrealized_pnl |
| `pm_fills` | fill_ingester.py | positions/{id}/fills | inst_id, side, px, sz, fee, ts, position_id, leg_id |
| `pm_entry_prices` | entry_price.py | positions | leg_id, avg_entry_price, fill_count |
| `pm_spreads` | spreads.py | positions | entry_spread, exit_spread, spread_pnl_bps |
| `pm_portfolio_snapshots` | portfolio.py | portfolio/overview | total_equity, apr_daily, funding_today |
| `pm_account_snapshots` | pull_positions_v3.py | portfolio/overview | account_id, total_balance |
| `pm_cashflows` | pm_cashflows.py | positions, portfolio | cf_type, amount, position_id |
| `prices_v3` | pull_position_prices + pull_hyperliquid_v3 | (via upnl/spreads) | inst_id, bid, ask, mid |
| `instruments_v3` | pull_hyperliquid_v3 | — (FK target) | venue, inst_id |

---

## 6. Hyperliquid funding double-count (builder + native perp legs)

### Symptom

- **Funding Today / All-Time** (and any `SUM(amount)` on `pm_cashflows` where `cf_type = 'FUNDING'`) looks **~2×** too high when the registry has **two** open Hyperliquid perp legs for the same underlying: one on a **builder** dex (e.g. `hyna:LINK`) and one on **native** (e.g. `LINK`).
- You may see **roughly twice** as many FUNDING rows per hour as you have distinct perp legs (e.g. 14/hour instead of 7).

### Root cause

Ingest (`scripts/pm_cashflows.py` → `ingest_hyperliquid`) calls HL `/info` **`userFunding`** (and `userFillsByTime` for fees) **once per dex** (native + each builder). Rows were matched to managed legs using only the **stripped** coin (e.g. `hyna:LINK` and `LINK` both became `LINK`). The **same** API line could therefore be stored on **both** the builder leg and the native leg. Dedupe in `insert_cashflow_events` did not catch this because `description` includes each leg’s `inst_id` and differs between rows.

### Fix in code (ongoing ingest)

Ingest now requires the **coin namespace** in the HL payload to match the leg’s **dex** from `pm_legs.inst_id` (same idea as `split_hyperliquid_inst_id` / `strip_coin_namespace`):

- Unprefixed coin (e.g. `LINK`) → **native** leg only (`dex` empty).
- Prefixed coin (e.g. `hyna:LINK`) → **that builder** leg only.

Fees from fills use the same rule.

### One-time migration: wipe HL funding/fees and backfill (run once)

Historical bad rows stay in `pm_cashflows` until you rebuild them. The script **`scripts/reset_hyperliquid_cashflows.py`**:

1. Deletes **all** rows with `venue = 'hyperliquid'` and `cf_type IN ('FUNDING','FEE')`.
2. Calls **`scripts/hl_reset_backfill.py`** (`run_backfill`) — **not** `pm_cashflows.ingest_hyperliquid`, so the cron cashflow job is unchanged. That module spaces out `/info` POSTs and **retries with backoff** on HTTP **429** (rate limit); see **Rate limits during backfill** below.

**Closed / past instruments:** the hourly job only maps **OPEN** legs. For a one-time reset, edit **`config/hl_cashflow_backfill_extra_targets.json`**: list `include_closed_inst_ids` (e.g. `xyz:CRCL`, `xyz:MSTR`, `XMR`) so **`CLOSED`** rows in `pm_legs` with those `inst_id` values are merged into targets. Optional **`manual_targets`** if there is no `pm_legs` row (provide `account_id` + `inst_id`; `position_id` / `leg_id` optional).

#### Step-by-step (run in order from repo root)

Paths below use the default DB `tracking/db/arbit_v3.db`. Change `--db` if yours differs.

1. **Go to the project root**

   ```bash
   cd /path/to/hip3-agent
   ```

2. **Load environment** (Hyperliquid addresses / multi-wallet JSON live here)

   ```bash
   source .arbit_env
   ```

3. **Ensure `pm_legs` matches your book** (so ingest maps funding to the right legs). If you changed `config/positions.json` recently:

   ```bash
   .venv/bin/python scripts/pm.py sync-registry
   .venv/bin/python scripts/pm.py list
   ```

   Skip if you already synced and positions are current.

4. **Backup the SQLite file** (restore by copying the `.bak` back over the DB if needed)

   ```bash
   cp tracking/db/arbit_v3.db tracking/db/arbit_v3.db.bak
   ```

5. **Dry run** — prints how many HL `FUNDING`+`FEE` rows would be removed; does **not** delete or call the API

   ```bash
   .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db --dry-run
   ```

6. **Delete + backfill** — actually removes those rows and refetches from Hyperliquid for the **default** window (**504h**)

   ```bash
   .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db
   ```

   Wait for `OK: deleted …` and `OK: backfilled …`.

   **Alternative (faster, less history):** only last **168h** (7 days) of funding/fees:

   ```bash
   .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db --since-hours 168
   ```

   **Custom UTC range** (backfill from a specific start; end defaults to **now**):

   ```bash
   .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db \
       --start 2026-03-16T19:00:00Z
   ```

   Optional **`--end`** (ISO `...Z` or epoch **ms**): cap the window (e.g. historical replay). With **`--since-hours`** only, **`--end`** anchors “now” for that window instead of current time.

   **Debug why `MIN(ts)` is still recent:** run with **`--verbose`** (logs to stderr: requested window, per-endpoint API errors, raw `userFunding` row counts vs rows accepted after leg/namespace filters, earliest timestamp seen in API payloads vs events queued, dedupe insert count):

   ```bash
   .venv/bin/python scripts/reset_hyperliquid_cashflows.py --db tracking/db/arbit_v3.db \
       --start 2026-03-01T00:00:00Z --verbose
   ```

   **Rate limits during backfill:** `hl_reset_backfill.py` issues many `/info` calls (`userFunding`, `userFillsByTime` across time windows, accounts, and dexes). Hyperliquid may respond with **429 Too Many Requests**. Each POST goes through a **minimum interval** between calls and **automatic retries** on 429 with exponential backoff and jitter; if the response includes **`Retry-After`**, that hint is used (plus a small random delay).

   Optional environment variables (tune if backfill still hits 429 or you want it slower):

   | Variable | Default | Purpose |
   |----------|---------|---------|
   | `HL_RESET_BACKFILL_MIN_INTERVAL_S` | `0.35` | Minimum seconds between successive `/info` POSTs in this backfill. |
   | `HL_RESET_BACKFILL_MAX_RETRIES` | `12` | Max retry attempts per request when the server returns 429. |

7. **Verify** — duplicate check should return **no rows** (empty result = good):

   ```bash
   sqlite3 tracking/db/arbit_v3.db
   ```

   ```sql
   SELECT venue, account_id, ts, amount, cf_type, COUNT(*) AS n
   FROM pm_cashflows
   WHERE venue = 'hyperliquid' AND cf_type IN ('FUNDING', 'FEE')
   GROUP BY venue, account_id, ts, amount, cf_type
   HAVING COUNT(*) > 1;
   ```

   Type `.quit` to exit `sqlite3`.

8. **Ongoing:** keep your usual cron / manual **`pm_cashflows.py ingest`** with **`hyperliquid`** in `--venues` — do **not** re-run the reset script unless you want another full wipe.

**Staging / testnet:** Use your DB path in every `--db` argument. Set **`HYPERLIQUID_ADDRESS`** / **`HYPERLIQUID_ACCOUNTS_JSON`** for that environment.

**API host:** Defaults to **mainnet** (`https://api.hyperliquid.xyz`). True HL testnet needs a testnet `.../info` base URL in your deployment.

### Quick SQL checks

Approximate hourly FUNDING row counts (Hyperliquid):

```sql
SELECT strftime('%Y-%m-%d %H', ts/1000, 'unixepoch') AS hour_utc, COUNT(*) AS n
FROM pm_cashflows
WHERE venue = 'hyperliquid' AND cf_type = 'FUNDING'
  AND ts >= (strftime('%s','now') - 86400) * 1000
GROUP BY 1 ORDER BY 1;
```

After cleanup + fixed ingest, **n per hour** should align with the number of **economically distinct** perp legs (one funding line per leg per hour per HL behavior), not double that when HYNA+NATIVE duplicates were present.
