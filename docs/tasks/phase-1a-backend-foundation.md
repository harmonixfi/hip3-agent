# Phase 1a: Backend Foundation

**Goal**: DB schema, fill ingestion pipeline, vault setup, backfill
**Depends on**: Nothing (first phase)

## Tasks

### 1.1 SQL Migration Script
- [ ] Create `tracking/sql/schema_monitoring_v1.sql` with:
  - `PRAGMA journal_mode=WAL`
  - `pm_fills` table (with UNIQUE on venue+account+tid)
  - `pm_entry_prices` table (PK on leg_id)
  - `pm_spreads` table (with long_leg_id/short_leg_id, UNIQUE constraint)
  - `pm_portfolio_snapshots` table (with hourly dedup index)
- [ ] Write migration runner script that applies to `tracking/db/arbit_v3.db`
- [ ] Migrate legacy spot inst_ids: `GOOGL` → `GOOGL/USDC` in pm_legs

### 1.2 Spot Symbol Resolution
- [ ] Implement `spotMeta` API call + cache builder
- [ ] `resolve_spot_coin()`: `@107` → `HYPE/USDC` via spotMeta lookup
- [ ] Builder dex passthrough: `xyz:GOLD` → `xyz:GOLD`
- [ ] Native perp passthrough: `HYPE` → `HYPE`
- [ ] Unit tests for all resolution paths

### 1.3 Fill Ingester (Hyperliquid)
- [ ] Create `tracking/pipeline/fill_ingester.py`
- [ ] Pull fills via `userFillsByTime` for each wallet (main + alt)
- [ ] Watermark tracking: resume from last ingested fill timestamp
- [ ] Resolve coin → inst_id using spotMeta cache
- [ ] Map fill → position_id + leg_id by matching (inst_id, account_id) against pm_legs WHERE position status != 'CLOSED'
- [ ] Handle dedup via UNIQUE constraint (skip on conflict)
- [ ] Store raw_json for forensic recovery
- [ ] Unit tests: ingestion, dedup, symbol resolution, leg mapping

### 1.4 Backfill Script
- [ ] Create `scripts/backfill_fills.py`
- [ ] CLI: `--all`, `--position <id>`, `--since <date>`
- [ ] Uses same fill ingester but with startTime=0 or specified date
- [ ] Run backfill for all 7 closed positions + 4 open positions
- [ ] Verify: correct fill count, correct inst_ids, correct leg mapping
- [ ] Verify: running twice produces no duplicates

### 1.5 Vault Setup
- [ ] Install `age` and `sops` on VPS
- [ ] Generate age identity: `age-keygen -o vault/age-identity.txt`
- [ ] Create `.sops.yaml` config
- [ ] Create `vault/secrets.enc.json` with all current env var secrets
- [ ] Create `vault/.gitignore` (ignore age-identity.txt)
- [ ] Implement `api/vault.py`: `decrypt_secrets()`, `get_secret()`
- [ ] Verify: secrets decrypt correctly
- [ ] Verify: .arbit_env fallback works during migration period

## Acceptance Criteria
- All 11 positions (4 OPEN + 7 CLOSED) have fills in pm_fills
- Spot fills correctly resolved to SYMBOL/USDC format
- No duplicate fills after multiple backfill runs
- Vault decrypts secrets; API code reads from vault
