# Trade Aggregation Layer — Design Spec

**Date:** 2026-04-17
**Status:** Draft for review
**Author:** OpenClaw brainstorming session

## 1. Problem

Current execution flow splits a large delta-neutral deploy (e.g., $10k notional each leg) into many small chunk fills (e.g., 100 × $100). All fills land in `pm_fills`, and `pm_entry_prices` computes a single VWAP across **all opening fills for a leg across all time**. This smears distinct deploy batches (e.g., "day 1 open $10k" vs "day 2 add $5k") into one averaged entry price. When partial closes happen, the system cannot attribute exit spread correctly to the matching open cohort, leading to imprecise spread/realized-P&L accounting and making per-batch audit impossible.

## 2. Goal

Introduce an explicit **Trade** layer between Position and Fill. A Trade is a user-defined cohort of fills bounded by `[start_ts, end_ts, wallet]` and linked to a Position and its two legs (long + short). Each Trade aggregates fills into delta-neutral-pair columns and computes its own entry/exit spread. A Position is the rollup of its Trades. This makes per-batch spread accurate, realized P&L attributable per unwind, and audit traceable to the raw fills of each batch.

## 3. Scope (v1)

- **Venues:** Hyperliquid + Felix (existing connectors), schema extensible for future venues.
- **Strategy types:** `SPOT_PERP` and `PERP_PERP`. Unified by long-leg/short-leg generalization.
- **Fees:** raw VWAP prices in aggregate columns + separate `*_fees` columns. Realized P&L computed with fees subtracted downstream.
- **Out of scope (v1):** LENDING strategies, multi-wallet trades (each leg still has single wallet via Position config), automated trade suggestion.

## 4. Key decisions (from brainstorming)

| # | Decision |
|---|---|
| 1 | Trade types: `OPEN` and `CLOSE` only. ADD = another OPEN; REDUCE = another CLOSE. |
| 2 | Fill-to-Trade binding: **materialized link** (`pm_trade_fills`) with cached aggregates in `pm_trades`. |
| 3 | CLOSE trade stores `realized_pnl_bps` computed via **weighted-avg across all FINALIZED OPEN trades of the Position** (weight = long_size). |
| 4 | Trade layer becomes source-of-truth for `pm_legs.qty` and `pm_positions.status`. `positions.json` deprecated. |
| 5 | Position creation moves to UI. `positions.json` backed up to `.bak` and all consumers migrated. |
| 6 | Trade lifecycle has two states: `DRAFT` (mutable, auto-reconciles late fills) and `FINALIZED` (locked snapshot; late fills raise warning only). |
| 7 | Spread formula universal: `spread_bps = (long_avg_px / short_avg_px - 1) × 10_000`. |
| 8 | UI: new global `/trades` page + embedded "Trades" tab inside `/positions/:id`. |

## 5. Data model

### New tables (`tracking/sql/schema_monitoring_v2.sql`)

```sql
CREATE TABLE pm_trades (
  trade_id        TEXT PRIMARY KEY,
  position_id     TEXT NOT NULL REFERENCES pm_positions(position_id),
  trade_type      TEXT NOT NULL CHECK (trade_type IN ('OPEN','CLOSE')),
  state           TEXT NOT NULL CHECK (state IN ('DRAFT','FINALIZED')),
  start_ts        INTEGER NOT NULL,
  end_ts          INTEGER NOT NULL,
  note            TEXT,

  long_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  long_size       REAL,
  long_notional   REAL,
  long_avg_px     REAL,
  long_fees       REAL,
  long_fill_count INTEGER,

  short_leg_id     TEXT NOT NULL REFERENCES pm_legs(leg_id),
  short_size       REAL,
  short_notional   REAL,
  short_avg_px     REAL,
  short_fees       REAL,
  short_fill_count INTEGER,

  spread_bps        REAL,
  realized_pnl_bps  REAL,  -- NULL for OPEN

  created_at_ms     INTEGER NOT NULL,
  finalized_at_ms   INTEGER,
  computed_at_ms    INTEGER NOT NULL,

  UNIQUE (position_id, trade_type, start_ts, end_ts)
);

CREATE INDEX idx_pm_trades_position ON pm_trades(position_id);
CREATE INDEX idx_pm_trades_window ON pm_trades(start_ts, end_ts);
CREATE INDEX idx_pm_trades_state ON pm_trades(state);

CREATE TABLE pm_trade_fills (
  trade_id  TEXT NOT NULL REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  fill_id   INTEGER NOT NULL REFERENCES pm_fills(fill_id),
  leg_side  TEXT NOT NULL CHECK (leg_side IN ('LONG','SHORT')),
  PRIMARY KEY (trade_id, fill_id)
);

CREATE INDEX idx_pm_trade_fills_fill ON pm_trade_fills(fill_id);

CREATE TABLE pm_trade_reconcile_warnings (
  trade_id          TEXT PRIMARY KEY REFERENCES pm_trades(trade_id) ON DELETE CASCADE,
  unassigned_count  INTEGER NOT NULL,
  first_seen_ms     INTEGER NOT NULL,
  last_checked_ms   INTEGER NOT NULL
);
```

### Changes to existing tables

- `pm_positions`: add `base TEXT`, `strategy_type TEXT CHECK (strategy_type IN ('SPOT_PERP','PERP_PERP'))`. Both nullable for migration; required for new positions created via UI.
- `pm_legs`: no schema change. `qty` and `entry_price` become derived fields updated by Trade finalize hook.
- `pm_entry_prices`, `pm_spreads`: unchanged schema. Compute logic refactored to consume from `pm_trades` instead of scanning `pm_fills` directly. Fallback: if Position has zero trades, compute over all fills (legacy behavior) to keep rollout incremental.

### Invariants

- A fill belongs to at most one Trade (`pm_trade_fills` composite PK).
- A FINALIZED trade cannot have its `pm_trade_fills` rows modified (enforced by API, not DB trigger — app-level guard).
- Two FINALIZED trades on the same Position with the same `trade_type` cannot have overlapping `[start_ts, end_ts]` windows. DRAFT overlaps allowed to let user experiment; Finalize blocks on overlap conflict.
- Trade ID format: `trd_<base>_<YYYYMMDDHHmm>_<open|close>[_<suffix>]`.

## 6. Ingestion & reconcile flow

### Trade creation

1. API `POST /api/trades/preview` (dry-run) or `POST /api/trades` (persist DRAFT):
2. Validate position exists (not CLOSED), window sane, no FINALIZED overlap.
3. Resolve legs from Position config → `{long_leg_id, short_leg_id}`.
4. Scan `pm_fills` per leg with side filter:

    | trade_type | leg_side | fill side |
    |---|---|---|
    | OPEN | LONG | BUY |
    | OPEN | SHORT | SELL |
    | CLOSE | LONG | SELL |
    | CLOSE | SHORT | BUY |

5. Insert `pm_trade_fills` rows; skip fills already bound to another trade.
6. Compute aggregates: `size=SUM(sz)`, `notional=SUM(px*sz)`, `avg_px=notional/size`, `fees=SUM(fee)`.
7. Compute `spread_bps = (long_avg_px / short_avg_px - 1) × 10_000`.
8. If CLOSE: `realized_pnl_bps = (weighted_avg_open_spread − close_spread) × 10_000`, where weighted_avg_open_spread is size-weighted across all FINALIZED OPEN trades of the Position.
9. INSERT `pm_trades` with `state='DRAFT'`.

### Finalize

1. App-level check: no FINALIZED overlap on same legs.
2. UPDATE `pm_trades.state='FINALIZED'`, set `finalized_at_ms`.
3. Recompute `pm_legs.qty = SUM(finalized_open.size) − SUM(finalized_close.size)` for both legs.
4. Recompute `pm_legs.entry_price` via VWAP across FINALIZED OPEN trades.
5. Recompute `pm_positions.status`:
   - net size > 0 on any leg AND has ≥1 OPEN trade → `OPEN`
   - net size = 0 on all legs AND has ≥1 FINALIZED CLOSE trade → `CLOSED`
   - `PAUSED`, `EXITING` remain manual override (not derived)
6. Trigger `pm_spreads` recompute for Position.

### Reopen (FINALIZED → DRAFT)

Mirror of Finalize: state back to DRAFT, clear `finalized_at_ms`, leg qty and position status recomputed after re-finalize.

### Reconcile (called from `fill_ingester` cron post-run)

1. For each DRAFT trade with `end_ts >= now − 24h`:
   - Re-scan `pm_fills` for newly ingested fills matching window + leg + side.
   - Insert to `pm_trade_fills` (idempotent via PK).
   - Recompute aggregates, `spread_bps`, `realized_pnl_bps`.
2. For each FINALIZED trade:
   - Count unassigned fills matching its window + legs + sides.
   - If > 0: UPSERT `pm_trade_reconcile_warnings`.
   - UI badges the trade row with "⚠ N late fills — reopen to reconcile".

### Failure modes

| Failure | Handling |
|---|---|
| Ingester lag | DRAFT auto-reconciles; FINALIZED gets non-silent warning badge. |
| User creates overlapping windows | DRAFT allowed (experiment); Finalize rejected with 409. |
| Trade deleted | CASCADE on `pm_trade_fills`; fills return to unassigned pool (pm_fills untouched). |
| Concurrent finalize on same position | Serialize via DB transaction + row lock on `pm_positions`. |
| Zero FINALIZED OPEN trades when finalizing a CLOSE | Reject finalize with 422 (can't realize P&L without opens). DRAFT creation allowed; `realized_pnl_bps` stays NULL until a matching OPEN is finalized. |

## 7. UI surface

### `/positions` (extended)

- New columns: Net Size, Open Trades count, Avg Entry Spread (bps), Last Trade timestamp.
- "+ New Position" button → modal: `base`, `strategy_type`, long_leg `{venue, inst_id, wallet_label}`, short_leg `{venue, inst_id, wallet_label}`.

### `/positions/:id` (new detail page)

- Header: base, strategy_type, status, derived net sizes, weighted-avg entry spread.
- Tabs:
  - **Trades**: embedded Trades table scoped to position + "+ New Trade" button.
  - **Legs**: leg configs + current fills count + unassigned fills warning.
  - **Cashflows**: existing `pm_cashflows` filtered.

### `/trades` (new global)

Filters: position, type, state, wallet, date range.

Columns:
```
trade_id | position | type | state | window
| long_symbol | long_size | long_notional | long_avg_px
| short_symbol | short_size | short_notional | short_avg_px
| spread_bps | realized_pnl_bps | long_fees | short_fees | fill_count
```

Row click → detail drawer (aggregates + linked fills table).
Badges: `DRAFT` pill, `⚠ N late fills` for FINALIZED with warnings.

### New Trade modal

```
Position:    [dropdown — filter by state rule above]
Type:        ( ) OPEN   ( ) CLOSE
Start (ICT): [datetime picker, default = now - 1h]
End (ICT):   [datetime picker, default = now]
Note:        [textarea, optional]

[Preview] → shows per-leg aggregation + size delta warning if |Δ|/avg > 0.5%
           shows spread_bps (OPEN) or realized_pnl_bps (CLOSE)

[Save as DRAFT] [Finalize now] [Cancel]
```

### Detail drawer actions

- DRAFT: `Edit window`, `Recompute`, `Delete`, `Finalize`.
- FINALIZED: `Reopen to edit`, view linked fills (read-only), `Delete` (confirm dialog).
- Download CSV of linked fills.

### API endpoints

New router `api/routers/trades.py`:

```
POST   /api/trades               # create DRAFT
POST   /api/trades/preview       # dry-run aggregation
GET    /api/trades               # list with filters
GET    /api/trades/:id           # detail + linked fills
PATCH  /api/trades/:id           # edit DRAFT
POST   /api/trades/:id/finalize
POST   /api/trades/:id/reopen
POST   /api/trades/:id/recompute
DELETE /api/trades/:id
GET    /api/positions/:id/trades
```

Extend `api/routers/positions.py`:

```
POST   /api/positions            # NEW — create position
GET    /api/positions/:id        # extended with derived qty/status/spread
```

## 8. Migration plan

### Phase 1: Schema + code additive (non-breaking)

- New tables in `schema_monitoring_v2.sql`.
- Add `base`, `strategy_type` to `pm_positions` (nullable).
- New module `tracking/pipeline/trades.py`.
- New router + frontend pages.
- Feature flag: env `TRADES_LAYER_ENABLED=false` by default.
- Existing `pm.py sync-registry`, `pm_entry_prices`, `pm_spreads` remain functional (legacy fallback when no trades exist).

### Phase 2: Backfill `positions.json` → DB

- Script `scripts/migrate_positions_to_db.py` (dry-run + `--commit` flag):
  - Read `config/positions.json`.
  - INSERT OR IGNORE into `pm_positions` with `base`, `strategy_type` lifted from JSON.
  - For each position with existing fills in `pm_fills`: synthesize OPEN (and CLOSE if status=CLOSED) DRAFT trades using `[MIN(ts), MAX(ts)]` of matching fills → auto-finalize.
  - Dry-run prints plan and diff vs `positions.json.qty` (tolerance 0.01%).
- Validation: assert `pm_legs.qty` post-migration matches `positions.json.qty` within tolerance; print mismatch report.

### Phase 3: Deprecate `positions.json`

- Rename `config/positions.json` → `config/positions.json.bak`.
- Update `pm.py sync-registry` to print deprecation warning and no-op.
- Audit and update:
  - `docs/playbook-position-management.md`: replace JSON-edit flow with UI flow.
  - `CLAUDE.md` "Position Management Workflow" section.
  - `tracking/position_manager/registry.py`: remove JSON read paths.
  - Any other caller of `config/positions.json` found by grep.

### Phase 4: Cleanup (follow-up PR, not v1)

- Remove `pm.py sync-registry` command.
- Remove legacy compute paths in `pm_entry_prices`, `pm_spreads` that fall back to raw fills.

### Blast-radius control

- Phases 1–2 behind feature flag; flag flip after validation.
- Rollback: drop new tables, unset flag, `positions.json` untouched during phases 1–2.

## 9. Testing

### Unit (`tests/pipeline/test_trades.py`)

- `aggregate_fills_for_trade`: VWAP, fees sum, empty window, single fill.
- `compute_spread_bps`: positive/negative spread, zero denominator guard.
- `compute_realized_pnl_bps`: 1 OPEN × 2 CLOSE, 2 OPEN × 1 CLOSE, zero OPEN rejection.
- `validate_trade_overlap`: DRAFT allowed, FINALIZED rejected.
- `side_mapping`: all 4 combinations of `trade_type × leg_side → fill_side`.
- `resolve_trade_id`: collision suffixing.

### Integration (sqlite in-memory)

- E2E: seed fills → create DRAFT → aggregates correct → finalize → pm_legs.qty and pm_positions.status updated.
- Reopen FINALIZED → edit → re-finalize; assert spread recomputed.
- Reconcile: late fill arrives → DRAFT auto-picks up; FINALIZED raises warning row.
- Delete DRAFT → `pm_trade_fills` cascade → fills unassigned.
- Status transitions: first OPEN → `OPEN`; full CLOSE → `CLOSED`.
- Overlap rejection: FINALIZED + FINALIZED overlap on same leg → 409.

### Migration tests

- Golden: seed DB with production-like `positions.json` + `pm_fills` → run migration → `pm_trades` populated, `pm_legs.qty` within 0.01% of JSON.
- Idempotency: run migration twice → second run no-op.

### Manual UI smoke (before merge)

- Dev server: create position via UI, create DRAFT trade from existing fills, preview, finalize. Hand-check spread vs manual calc.
- Reopen, edit window, re-finalize.
- Delete DRAFT; verify fills back to unassigned pool.

## 10. Open questions for later phases

- Multi-wallet single-trade (one leg on wallet `main`, other on `alt` within same trade row): covered by Position-level leg wallet config, but flag for v2 review.
- Cross-venue trades (HL spot vs Felix perp): requires unified wallet semantics; deferred.
- Automated trade suggestion from fill clustering: explicit non-goal for v1 (keeps user in control).
