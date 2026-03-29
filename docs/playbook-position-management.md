# Position Management Playbook

## Quick Reference

| Operation | Steps |
|-----------|-------|
| Add position | Edit `config/positions.json` → `pm.py sync-registry` |
| Update qty (rebalance) | Edit both legs qty → `pm.py sync-registry` |
| Close position | Set `status: "CLOSED"` → `pm.py sync-registry` |
| Pause position | Set `status: "PAUSED"` → `pm.py sync-registry` |
| Verify in DB | `pm.py list` or query `pm_legs` directly |

---

## 1. Registry: config/positions.json

Source of truth for position intent. All changes start here.

### Required Position Fields

```json
{
  "position_id": "pos_xyz_BTC",       // unique ID
  "strategy_type": "SPOT_PERP",       // SPOT_PERP | PERP_PERP
  "base": "BTC",                      // report ticker
  "status": "OPEN",                   // OPEN | PAUSED | EXITING | CLOSED
  "legs": [...]                       // at least 1 leg
}
```

### Optional Position Fields

- `amount_usd` (float) — gross notional for reporting
- `open_fees_usd` (float) — manual open-cost override
- `thresholds` (object) — per-position risk/rebalance thresholds

### Required Leg Fields

```json
{
  "leg_id": "pos_xyz_BTC_SPOT",     // unique within position
  "venue": "hyperliquid",           // exchange name
  "inst_id": "BTC",                 // instrument ID (namespaced: "xyz:GOLD")
  "side": "LONG",                   // LONG | SHORT
  "qty": 0.5,                       // positive, in base units (tokens, NOT USD)
  "qty_type": "token"               // usually "token" or "base"
}
```

### Optional Leg Fields

- `wallet_label` (string) — `"main"` (default) or `"alt"` for multi-wallet
- `leverage` (float)
- `margin_mode` (string)
- `collateral` (float)

### Validation Rules (enforced at load)

- `qty > 0`
- `strategy_type` in {SPOT_PERP, PERP_PERP}
- `status` in {OPEN, PAUSED, EXITING, CLOSED}
- `side` in {LONG, SHORT}
- `leg_id` unique within position
- At least one leg per position

---

## 2. Sync to Database

Registry → DB via UPSERT (safe, idempotent).

```bash
source .arbit_env
.venv/bin/python scripts/pm.py sync-registry
```

### What sync updates

- `pm_positions`: venue, strategy, status, updated_at_ms, raw_json, meta_json
- `pm_legs`: position_id, venue, inst_id, side, size (from qty), status, meta_json, account_id

### What sync preserves

- `created_at_ms`, `opened_at_ms` — never overwritten
- `entry_price`, `current_price`, `unrealized_pnl`, `realized_pnl` — updated by puller only

### Verify

```bash
# List all positions
.venv/bin/python scripts/pm.py list

# Check specific position in DB
sqlite3 tracking/db/arbit_v3.db \
  "SELECT leg_id, size, status FROM pm_legs WHERE position_id='pos_xyz_ORCL';"
```

---

## 3. Common Operations

### Add a new position

1. Add position object to `config/positions.json`
2. `pm.py sync-registry`
3. `pull_positions_v3.py --db tracking/db/arbit_v3.db --venues hyperliquid` (fetches live prices)

### Reduce size (partial close)

1. Update `qty` in **both** legs (SPOT + PERP) in `positions.json`
2. `pm.py sync-registry`

### Close a position

1. Set `"status": "CLOSED"` in `positions.json`
2. `pm.py sync-registry`
3. Both legs auto-marked CLOSED in DB

### Pause (skip from pulls without closing)

1. Set `"status": "PAUSED"` in `positions.json`
2. `pm.py sync-registry`

---

## 4. Multi-Wallet Support

### Environment

```bash
# Set in .arbit_env
export HYPERLIQUID_ACCOUNTS_JSON='{"main":"0xabc...","alt":"0xdef..."}'
```

### Leg assignment

```json
{ "wallet_label": "alt" }   // uses HYPERLIQUID_ACCOUNTS_JSON["alt"]
```

Omitting `wallet_label` defaults to `"main"`.

During sync, `wallet_label` + venue → resolved to `account_id` stored in `pm_legs.account_id`.

---

## 5. DB Schema (key tables)

| Table | Purpose | Type |
|-------|---------|------|
| `pm_positions` | Position metadata | Mutable (upsert) |
| `pm_legs` | Leg state + live prices | Mutable (upsert + puller updates) |
| `pm_leg_snapshots` | Historical leg snapshots | Append-only |
| `pm_account_snapshots` | Account balance history | Append-only |
| `pm_cashflows` | Funding, fees, realized PnL | Append-only |

### Cashflow sign convention

- Positive = credit (funding received, deposit)
- Negative = debit (fees paid, funding paid)

---

## 6. Source of Truth Order

When debugging mismatches:

1. **config/positions.json** — intent + manual capital metadata
2. **pm_positions / pm_legs** — synced state
3. **pm_leg_snapshots** — historical live data
4. **pm_cashflows** — realized economics
5. **Report scripts** — derived/formatted output

---

## 7. Related Scripts

| Script | Purpose |
|--------|---------|
| `scripts/pm.py` | Position manager CLI (sync-registry, list) |
| `scripts/pull_positions_v3.py` | Fetch live position data from venues |
| `scripts/pm_cashflows.py` | Ingest/report funding + fees |
| `scripts/db_v3_init.py` | Initialize DB with schema |
| `tracking/position_manager/registry.py` | Registry loader + validator |
| `tracking/position_manager/db_sync.py` | Registry → DB sync logic |
| `tracking/position_manager/puller.py` | Live data puller |
| `tracking/position_manager/accounts.py` | Multi-wallet account resolution |
