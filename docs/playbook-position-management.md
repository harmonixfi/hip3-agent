# Position Management Runbook

## Quick Reference

| Operation | Steps |
|---|---|
| Add position (HL) | Edit `positions.json` → `sync-registry` → `pull_positions_v3` → set `created_at_ms` → `pm_cashflows ingest` |
| Add position (Felix) | Edit `positions.json` → `sync-registry` → `pull_felix_market` → set `created_at_ms` → `pm_cashflows ingest` |
| Update qty (rebalance) | Edit qty in `positions.json` → `sync-registry` (sizes auto-sync on next pull) |
| Close position | Set `status: "CLOSED"` → `sync-registry` |
| Pause position | Set `status: "PAUSED"` → `sync-registry` |
| Verify | `pm.py list` → check API → confirm Amount + APR |

---

## 1. `config/positions.json` — Source of Truth

All changes start here. **Never edit the DB directly for position intent.**

### Position Object

```json
{
  "position_id": "pos_xyz_BTC",       // unique, format: pos_{wallet}_{BASE}
  "strategy_type": "SPOT_PERP",       // SPOT_PERP | PERP_PERP
  "base": "BTC",                      // display ticker for dashboard
  "status": "OPEN",                   // OPEN | PAUSED | EXITING | CLOSED
  "legs": [...]
}
```

### Leg Object

```json
{
  "leg_id": "pos_xyz_BTC_SPOT",       // unique, format: {position_id}_{ROLE}
  "venue": "hyperliquid",             // see Venue Reference below
  "inst_id": "BTC",                   // see inst_id conventions below
  "side": "LONG",                     // LONG | SHORT
  "qty": 0.5,                         // token qty (positive). Auto-refreshed by puller after first pull
  "qty_type": "token",
  "wallet_label": "alt"               // optional: "main" (default) | "alt"
}
```

### inst_id Conventions

| Venue | Asset Type | inst_id Format | Example |
|---|---|---|---|
| `hyperliquid` | Spot (native HL) | `{TICKER}/USDC` | `UFART/USDC`, `HYPE/USDC`, `LINK0/USDC` |
| `hyperliquid` | Perp (native) | `{TICKER}` | `FARTCOIN`, `BTC`, `ETH` |
| `hyperliquid` | Perp (xyz builder) | `xyz:{TICKER}` | `xyz:MSTR`, `xyz:MU`, `xyz:GOLD` |
| `hyperliquid` | Perp (hyna builder) | `hyna:{TICKER}` | `hyna:FARTCOIN`, `hyna:HYPE` |
| `felix` | Felix Equities spot | `{Symbol}on/USDC` | `MUon/USDC`, `MSTRon/USDC` |

**Spot leg detection:** any `inst_id` containing `/` is treated as a spot leg by the system.
**HL ticker vs token name:** HL uses its own ticker (e.g. `UFART`) as the coin key in spot balances — use the HL ticker as the prefix in `inst_id`, not the token full name (e.g. not `FARTCOIN/USDC`).

### Wallet Labels

```bash
# .arbit_env:
HYPERLIQUID_ACCOUNTS_JSON='{"main":"0xabc...","alt":"0xdef...","commodity":"0x...","depeg":"0x..."}'
```

Omitting `wallet_label` defaults to `"main"`.

---

## 2. Sync Registry → DB

```bash
source .arbit_env
.venv/bin/python scripts/pm.py sync-registry
.venv/bin/python scripts/pm.py list   # verify
```

**What sync does:**
- `pm_positions`: upserts venue, strategy, status, meta_json
- `pm_legs`: upserts side, size (from `qty`), status, account_id

**What sync preserves (never overwritten):**
- `created_at_ms` — must be set manually after first sync (see §5)
- `current_price`, `unrealized_pnl`, `entry_price` — updated by puller only

---

## 3. Pull Live Data

After sync, pull live data to populate prices, sizes, and snapshots.

### Hyperliquid positions (perp + spot)

```bash
source .arbit_env
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues hyperliquid
```

**What this does:**
- **Perp legs:** matched from `fetch_open_positions()` → live size, mark price, uPnL written to `pm_legs`
- **Spot legs:** size read from live HL wallet balance via `spot_quantities` → `pm_legs.size` auto-updated
- **All legs:** snapshots written to `pm_leg_snapshots`

> After the first pull, `pm_legs.size` reflects the actual exchange balance for all legs.
> The `qty` in `positions.json` is only needed for first `sync-registry`; subsequent sizes come from live data.

### Felix Equities positions

Felix requires **two separate pulls**:

```bash
# 1. Public price API (no JWT) — populates prices_v3 for Felix spot legs
.venv/bin/python scripts/pull_felix_market.py

# 2. Private portfolio API (requires FELIX_EQUITIES_JWT) — updates pm_legs snapshots
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues felix
```

**Felix addresses — two different wallets:**
```
Felix Equities embedded wallet:  0x175e1D4dCc6d3A567ddff95a6F8E6bc7b67d96a2  ← FELIX_WALLET_ADDRESS
HL alt wallet:                   0x3c2c0B452B465c595fE106Ef40c55Bf4383D2453  ← different, do NOT use for Felix
```

**Felix JWT notes:**
- `FELIX_EQUITIES_JWT` expires every ~2h. Refresh manually from Felix UI.
- Set in `.arbit_env`: `export FELIX_EQUITIES_JWT="eyJ..."`
- The private pull (portfolio) is JWT-dependent.
- `pull_felix_market.py` (public) works without JWT — prices remain fresh regardless.
- `pipeline_hourly.py` uses `prices_v3` (from public pull) as primary price source. APR/Amount stay accurate even when JWT is expired.

**How to refresh JWT:**
1. Open https://trade.usefelix.xyz
2. DevTools → Network → any request → copy `Authorization: Bearer eyJ...`
3. Update `.arbit_env` and `source .arbit_env`

### Run computation pipeline

```bash
.venv/bin/python scripts/pipeline_hourly.py --skip-ingest
```

Recomputes: entry VWAP → unrealized PnL → syncs spot sizes from `prices_v3` → spreads → portfolio snapshot.

---

## 4. Ingest Cashflows (Funding + Fees)

Must run after adding a position so APR windows populate.

```bash
source .arbit_env
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid
```

Verify cashflows ingested:
```bash
python3 -c "
import sqlite3, datetime
conn = sqlite3.connect('tracking/db/arbit_v3.db')
rows = conn.execute(\"\"\"
    SELECT cf_type, amount, ts FROM pm_cashflows
    WHERE position_id='pos_xyz_MU' AND cf_type='FUNDING'
    ORDER BY ts ASC LIMIT 5
\"\"\").fetchall()
for r in rows:
    dt = datetime.datetime.fromtimestamp(r[2]/1000, tz=datetime.timezone.utc)
    print(r[0], f'\${r[1]:.4f}', dt.strftime('%Y-%m-%d %H:%M UTC'))
"
```

---

## 5. Set Position Start Time (`created_at_ms`)

`created_at_ms` controls APR window calculations and cashflow filtering.
By default it's set to `now` at first `sync-registry` — wrong if the position was opened earlier.

**When to set:** always after registering a new position, or when migrating a leg (e.g. HL spot → Felix spot).

**Convention:** use the timestamp of the **first FUNDING payment** on the day the position was opened.

```bash
# Step 1: Find first funding cashflow
python3 -c "
import sqlite3, datetime
conn = sqlite3.connect('tracking/db/arbit_v3.db')
rows = conn.execute(\"\"\"
    SELECT ts FROM pm_cashflows
    WHERE position_id='pos_xyz_MU' AND cf_type='FUNDING'
    ORDER BY ts ASC LIMIT 1
\"\"\").fetchall()
for r in rows:
    dt = datetime.datetime.fromtimestamp(r[0]/1000, tz=datetime.timezone.utc)
    print('First funding:', dt.isoformat(), '=', r[0], 'ms')
"

# Step 2: Set created_at_ms
python3 -c "
import sqlite3, datetime
dt = datetime.datetime(2026, 4, 6, 16, 0, 0, tzinfo=datetime.timezone.utc)  # adjust to actual date
start_ms = int(dt.timestamp() * 1000)
conn = sqlite3.connect('tracking/db/arbit_v3.db')
conn.execute(\"UPDATE pm_positions SET created_at_ms=? WHERE position_id='pos_xyz_MU'\", (start_ms,))
conn.commit()
print('Set created_at_ms =', start_ms, '=', dt.isoformat())
"
```

> **Important:** `positions.py` filters cashflows by `ts >= created_at_ms`.
> Setting `created_at_ms` too early includes pre-migration cashflows from closed legs → distorts carry_apr.
> Setting it too late excludes real cashflows → APR windows show `—`.

---

## 6. Full Registration Workflow

### New HL position (spot + perp)

```bash
# 1. Edit config/positions.json — add position object with both legs

# 2. Sync to DB
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry

# 3. Pull live data (sizes auto-populated from HL exchange)
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues hyperliquid

# 4. Ingest cashflows
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid

# 5. Set created_at_ms (see §5)
#    python3 -c "import sqlite3; ..."

# 6. Recompute metrics
.venv/bin/python scripts/pull_hyperliquid_v3.py
.venv/bin/python scripts/pipeline_hourly.py --skip-ingest

# 7. Verify (see §7)
```

### New Felix Equities position (Felix spot + xyz perp)

```bash
# 1. Edit config/positions.json:
#    SPOT leg:  venue="felix",       inst_id="MUon/USDC",  wallet_label="alt"
#    PERP leg:  venue="hyperliquid", inst_id="xyz:MU",     wallet_label="alt"

# 2. Sync
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry

# 3. Pull Felix prices (public — no JWT required)
.venv/bin/python scripts/pull_felix_market.py

# 4. Pull HL perp positions
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues hyperliquid

# 5. Pull Felix portfolio (private — needs fresh JWT in .arbit_env)
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues felix

# 6. Ingest cashflows (funding comes from HL perp)
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid

# 7. Set created_at_ms from first funding payment (see §5)

# 8. Recompute
.venv/bin/python scripts/pipeline_hourly.py --skip-ingest

# 9. Verify (see §7)
```

---

## 7. Verify Registration

```bash
source .arbit_env

# 1. Check pm_legs — sizes must reflect live exchange balance
python3 -c "
import sqlite3
conn = sqlite3.connect('tracking/db/arbit_v3.db')
conn.row_factory = sqlite3.Row
rows = conn.execute(\"SELECT leg_id, size, current_price, status FROM pm_legs WHERE position_id='pos_xyz_MU'\").fetchall()
for r in rows: print(dict(r))
"

# 2. Check API — Amount and APR must be populated
curl -s -H "X-API-Key: \$HARMONIX_API_KEY" http://localhost:8000/api/positions | python3 -c "
import json, sys
data = json.load(sys.stdin)
positions = data if isinstance(data, list) else data.get('positions', data)
for p in positions:
    if p.get('base') in ('MU', 'MSTR'):   # replace with target base
        w = p.get('windowed') or {}
        print(p['base'])
        print('  amount_usd:', p.get('amount_usd'))
        print('  carry_apr:', p.get('carry_apr'), '%')
        print('  incomplete_notional:', w.get('incomplete_notional'))
        print('  missing_leg_ids:', w.get('missing_leg_ids'))
        print('  apr_1d:', w.get('apr_1d'))
        print('  opened_at:', p.get('opened_at'))
"
```

**Expected green state:**
- `amount_usd` — non-zero, matches expected notional
- `incomplete_notional: false` — all legs have prices
- `missing_leg_ids: []` — no legs missing prices
- `apr_1d` — populated after ≥1 day of cashflows
- `carry_apr` — positive for funding-positive positions
- `opened_at` — matches actual open date (not `sync-registry` timestamp)

---

## 8. Update Qty (Rebalance)

```bash
# 1. Edit config/positions.json — update qty for affected legs
# 2. Sync
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
# 3. Pull to confirm live sizes match
.venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json
```

> For HL positions, `pm_legs.size` auto-refreshes from the live exchange on every
> `pull_positions_v3.py` run (every 5 min in production). Updating `qty` in `positions.json`
> keeps the registry consistent but the system corrects sizes from live data regardless.

---

## 9. Close a Position

```bash
# 1. Set status in config/positions.json:  "status": "CLOSED"
# 2. Sync
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
# 3. Verify
.venv/bin/python scripts/pm.py list
```

CLOSED positions:
- Excluded from active position metrics (Amount, APR, `incomplete_notional` checks)
- Still queryable via `GET /api/positions?status=CLOSED`
- `amount_usd` falls back to last known value from `meta_json`

---

## 10. Troubleshooting

### Amount shows wrong value

**Cause:** `pm_legs.size` stale (not yet refreshed by puller after a trade).

**Fix:**
```bash
source .arbit_env && .venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json
```

For Felix spot legs (JWT-dependent): even if JWT is expired, `pipeline_hourly.py` step `sync_leg_prices` updates `pm_legs.current_price` from `prices_v3`. Amount will be correct using this price × size.

### APR shows `—` (incomplete_notional)

| Cause | Fix |
|---|---|
| CLOSED leg in same position (e.g. old HL spot after Felix migration) | Set `status: "CLOSED"` on old leg → `sync-registry` |
| Felix leg has no price in `prices_v3` | Run `pull_felix_market.py` |
| `created_at_ms` not set correctly | Update `pm_positions.created_at_ms` (see §5) |

### Funding shows $0.00 / Carry APR = 0%

**Cause:** No cashflows ingested, or `created_at_ms` filters them out.

```bash
source .arbit_env
.venv/bin/python scripts/pm_cashflows.py ingest --venues hyperliquid
# Then verify created_at_ms is correct (see §5)
```

### Felix pull 401 Unauthorized

JWT expired. Refresh from Felix UI (see §3 Felix JWT notes).

### Perp or spot size in dashboard doesn't match HL

The pull runs every 5 min in production. Wait for next cron cycle, or run manually:
```bash
source .arbit_env && .venv/bin/python scripts/pull_positions_v3.py --registry config/positions.json --venues hyperliquid
```

---

## 11. Source of Truth Order

When debugging mismatches:

1. **`config/positions.json`** — position intent, leg definitions
2. **`pm_positions` / `pm_legs`** — live synced state (size from exchange, not config after first pull)
3. **`pm_leg_snapshots`** — historical snapshots per pull
4. **`pm_cashflows`** — realized funding + fees
5. **`prices_v3`** — latest mark prices by venue + inst_id
6. **API `/api/positions`** — derived output (amount, APR, spreads)

---

## 12. DB Schema Reference

| Table | Updated by | Purpose |
|---|---|---|
| `pm_positions` | `sync-registry`, manual `UPDATE` | Metadata, status, `created_at_ms` |
| `pm_legs` | `sync-registry` + puller | Live leg: size, price, uPnL |
| `pm_leg_snapshots` | puller (append-only) | Historical leg snapshots |
| `pm_account_snapshots` | puller (append-only) | Account balance history |
| `pm_cashflows` | `pm_cashflows.py ingest` | Realized funding + fees |
| `pm_entry_prices` | `pipeline_hourly.py` | VWAP entry prices from fills |
| `prices_v3` | `pull_hyperliquid_v3.py`, `pull_felix_market.py` | Mark prices by venue + inst_id |

**Cashflow sign convention:** positive = credit (funding received), negative = debit (fees paid).

---

## 13. Related Scripts

| Script | Cron schedule | Purpose |
|---|---|---|
| `scripts/pm.py sync-registry` | Manual only | Sync `positions.json` → DB |
| `scripts/pull_positions_v3.py` | Every 5 min | Live sizes + snapshots for all venues |
| `scripts/pull_felix_market.py` | Hourly :22 | Felix public prices → `prices_v3` |
| `scripts/pull_hyperliquid_v3.py` | Hourly :20 | HL mark prices + funding rates |
| `scripts/pull_loris_funding.py` | Every 30 min | Candidate funding data |
| `scripts/pm_cashflows.py ingest` | Hourly :37 | Realized funding + fees |
| `scripts/pipeline_hourly.py` | Hourly :30 | Compute metrics (uPnL, APR, spreads) |
| `scripts/equity_daily.py snapshot` | Daily 02:00 UTC | Daily equity snapshot |
| `scripts/vault_daily_snapshot.py` | Daily 02:05 UTC | Vault NAV snapshot |
| `scripts/export_core_candidates.py` | Daily 00:00 UTC | Candidate export CSV |
