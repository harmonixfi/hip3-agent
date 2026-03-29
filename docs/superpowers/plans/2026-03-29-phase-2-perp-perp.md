# Phase 2: PERP_PERP Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extend the monitoring system to fully support PERP_PERP delta-neutral positions (long perp + short perp) with dual-funding tracking.

**Architecture:** Minimal code changes — Phase 1 was designed with generic long/short semantics. This phase verifies, tests, fixes labels, and removes any SPOT_PERP-only assumptions.

**Tech Stack:** Python 3.11+, SQLite3, Next.js (label changes only)

**References:**
- Architecture spec: `docs/PLAN.md` sections 3.6, Phase 2
- Decisions: `docs/DECISIONS.md` ADR-009
- Task checklist: `docs/tasks/phase-2-perp-perp.md`
- Phase 1a plan: `docs/superpowers/plans/2026-03-29-phase-1a-backend-foundation.md`

---

## Context: What Phase 1 Already Handles

Phase 1 was designed generically. Before writing new code, verify these existing behaviors:

| Component | How it works | PERP_PERP compatible? |
|-----------|-------------|----------------------|
| `fill_ingester.py` | Maps fills by `(inst_id, account_id)` — no spot/perp distinction | Yes — both perp legs have unique `inst_id` |
| `entry_price.py` | VWAP per `leg_id` — instrument-type agnostic | Yes — no change needed |
| `upnl.py` | `compute_leg_upnl(side, avg_entry, exit_price, size)` — uses `side` to pick bid/ask | Yes — LONG leg uses bid, SHORT leg uses ask regardless of instrument type |
| `spreads.py` | `entry_spread(long_avg_entry, short_avg_entry)` / `exit_spread(long_bid, short_ask)` — named generically | Yes — same formula, different underlying instrument |
| `portfolio.py` | Sums all `FUNDING` cashflows per position by `leg_id` | Yes — net funding = long_funding + short_funding automatically |
| DB schema | `pm_fills`, `pm_entry_prices`, `pm_spreads` all use `leg_id` keys, not instrument type | Yes — no migration needed (ADR-009) |

**This phase is primarily:** verification + test coverage + frontend label fixes + removing any `SPOT_PERP`-only guards.

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Verify/Fix | `tracking/pipeline/upnl.py` | Confirm price lookup works for perp inst_ids (not just spot) |
| Verify/Fix | `tracking/pipeline/spreads.py` | Confirm sub-pair generation when no spot leg exists |
| Verify/Fix | `tracking/pipeline/portfolio.py` | Confirm net funding sums both legs for PERP_PERP |
| Create | `tests/test_perp_perp.py` | Unit + integration tests for PERP_PERP path |
| Edit | `frontend/components/PositionDetail.tsx` | "Long Leg" / "Short Leg" labels instead of "Spot" / "Perp" |
| Edit | `frontend/components/FundingRow.tsx` (or equivalent) | Show funding for BOTH legs, not just short |
| Edit | `config/positions.json` | Add sample PERP_PERP test position (temp, for E2E verification) |

---

## Task 1: Verify Fill Ingestion for Both PERP_PERP Legs

**Files:**
- Verify: `tracking/pipeline/fill_ingester.py`
- Create: `tests/test_perp_perp.py` (fill ingestion section)

### Background

For SPOT_PERP, the long leg has a spot `inst_id` (e.g., `HYPE/USDC`) and the short leg has a perp `inst_id` (e.g., `HYPE`). For PERP_PERP, both legs are perps — typically on different venues (e.g., `hyna:HYPE` for the long leg on Hyena, `HYPE` for the short leg on HL native). The `map_fill_to_leg` function matches on `(inst_id, account_id)`, which is sufficient to disambiguate since different venues produce different `inst_id` namespaces.

**No code changes are expected here.** The verification step confirms this is correct.

- [ ] **Step 1: Write failing test for PERP_PERP fill mapping**

Create `tests/test_perp_perp.py`:

```python
#!/usr/bin/env python3
"""Tests for PERP_PERP position support.

Verifies that fill ingestion, uPnL, spreads, and portfolio aggregation
all work correctly for perp-long + perp-short positions.
"""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared test DB helpers
# ---------------------------------------------------------------------------

def _create_test_db(db_path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(db_path))
    con.executescript("""
        CREATE TABLE pm_positions(
          position_id TEXT PRIMARY KEY,
          venue TEXT NOT NULL,
          strategy TEXT,
          status TEXT NOT NULL,
          created_at_ms INTEGER NOT NULL,
          updated_at_ms INTEGER NOT NULL,
          closed_at_ms INTEGER,
          raw_json TEXT,
          meta_json TEXT
        );
        CREATE TABLE pm_legs (
            leg_id TEXT PRIMARY KEY,
            position_id TEXT NOT NULL,
            venue TEXT NOT NULL,
            inst_id TEXT NOT NULL,
            side TEXT NOT NULL,
            size REAL NOT NULL,
            entry_price REAL,
            current_price REAL,
            unrealized_pnl REAL,
            realized_pnl REAL,
            status TEXT NOT NULL,
            opened_at_ms INTEGER NOT NULL,
            closed_at_ms INTEGER,
            account_id TEXT NOT NULL,
            raw_json TEXT,
            meta_json TEXT
        );
        CREATE TABLE pm_fills (
            fill_id INTEGER PRIMARY KEY AUTOINCREMENT,
            venue TEXT NOT NULL,
            account_id TEXT NOT NULL,
            tid TEXT NOT NULL,
            oid TEXT,
            inst_id TEXT NOT NULL,
            side TEXT NOT NULL,
            px REAL NOT NULL,
            sz REAL NOT NULL,
            fee REAL,
            fee_currency TEXT,
            ts INTEGER NOT NULL,
            closed_pnl REAL,
            dir TEXT,
            builder_fee REAL,
            position_id TEXT,
            leg_id TEXT,
            raw_json TEXT,
            meta_json TEXT,
            UNIQUE(venue, account_id, tid)
        );
        CREATE TABLE pm_entry_prices (
            leg_id TEXT NOT NULL PRIMARY KEY,
            position_id TEXT NOT NULL,
            avg_entry_price REAL NOT NULL,
            total_filled_qty REAL NOT NULL,
            total_cost REAL NOT NULL,
            fill_count INTEGER NOT NULL,
            first_fill_ts INTEGER,
            last_fill_ts INTEGER,
            computed_at_ms INTEGER NOT NULL,
            method TEXT NOT NULL DEFAULT 'VWAP',
            meta_json TEXT
        );
        CREATE TABLE pm_cashflows(
          cashflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
          position_id TEXT,
          leg_id TEXT,
          venue TEXT NOT NULL,
          account_id TEXT NOT NULL,
          ts INTEGER NOT NULL,
          cf_type TEXT NOT NULL,
          amount REAL NOT NULL,
          currency TEXT NOT NULL,
          description TEXT,
          raw_json TEXT,
          meta_json TEXT
        );
    """)
    return con


def _seed_perp_perp_position(con: sqlite3.Connection) -> None:
    """Seed a PERP_PERP position: long hyna:HYPE (0xdef) + short HYPE (0xabc)."""
    now_ms = 1711900000000
    con.executemany(
        """INSERT INTO pm_positions
           (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            ("pos_hype_pp", "hyperliquid", "PERP_PERP", "OPEN", now_ms, now_ms, "{}"),
        ],
    )
    con.executemany(
        """INSERT INTO pm_legs
           (leg_id, position_id, venue, inst_id, side, size, entry_price,
            current_price, unrealized_pnl, realized_pnl, status, opened_at_ms,
            closed_at_ms, account_id, raw_json, meta_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            # Long leg: hyna:HYPE on Hyena, account 0xdef
            ("hype_long_hyna", "pos_hype_pp", "hyena", "hyna:HYPE", "LONG",
             100.0, None, None, None, 0.0, "OPEN", now_ms, None, "0xdef", "{}", "{}"),
            # Short leg: HYPE on HL native, account 0xabc
            ("hype_short_hl", "pos_hype_pp", "hyperliquid", "HYPE", "SHORT",
             100.0, None, None, None, 0.0, "OPEN", now_ms, None, "0xabc", "{}", "{}"),
        ],
    )
    con.commit()


# ---------------------------------------------------------------------------
# 1. Fill Ingestion Tests
# ---------------------------------------------------------------------------

def test_perp_perp_fill_mapping_long_leg():
    """Long perp fill maps to long leg by (inst_id, account_id)."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        result = map_fill_to_leg("hyna:HYPE", "0xdef", targets)

        assert result is not None
        assert result["leg_id"] == "hype_long_hyna"
        assert result["side"] == "LONG"

        con.close()


def test_perp_perp_fill_mapping_short_leg():
    """Short perp fill maps to short leg by (inst_id, account_id)."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        result = map_fill_to_leg("HYPE", "0xabc", targets)

        assert result is not None
        assert result["leg_id"] == "hype_short_hl"
        assert result["side"] == "SHORT"

        con.close()


def test_perp_perp_no_cross_account_mapping():
    """Fill from wrong account does not match even if inst_id matches."""
    from tracking.pipeline.fill_ingester import load_fill_targets, map_fill_to_leg

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        targets = load_fill_targets(con)
        # HYPE fill but wrong account — should not match
        result = map_fill_to_leg("HYPE", "0xdef", targets)
        assert result is None

        con.close()


# ---------------------------------------------------------------------------
# 2. uPnL Tests
# ---------------------------------------------------------------------------

def test_perp_perp_upnl_long_uses_bid():
    """Long perp uPnL is computed using bid price."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Long perp: entry at 25.00, current bid 26.00, size 100
    # Expected: (26.00 - 25.00) * 100 = +100.0
    pnl = compute_leg_upnl(side="LONG", avg_entry=25.00, exit_price=26.00, size=100.0)
    assert pnl == 100.0


def test_perp_perp_upnl_short_uses_ask():
    """Short perp uPnL is computed using ask price."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Short perp: entry at 25.00, current ask 24.00, size 100
    # Expected: -(24.00 - 25.00) * 100 = +100.0
    pnl = compute_leg_upnl(side="SHORT", avg_entry=25.00, exit_price=24.00, size=100.0)
    assert pnl == 100.0


def test_perp_perp_upnl_net_negative_when_spread_moves_against():
    """Net uPnL is negative when spread moves against position."""
    from tracking.pipeline.upnl import compute_leg_upnl

    # Long at 25.00, now bid is 24.50 (moved down) -> -50
    long_pnl = compute_leg_upnl(side="LONG", avg_entry=25.00, exit_price=24.50, size=100.0)
    # Short at 25.00, now ask is 25.50 (moved up, bad for short) -> -50
    short_pnl = compute_leg_upnl(side="SHORT", avg_entry=25.00, exit_price=25.50, size=100.0)
    assert long_pnl == -50.0
    assert short_pnl == -50.0
    assert long_pnl + short_pnl == -100.0  # net loss when spread widens against you


# ---------------------------------------------------------------------------
# 3. Spread Tests
# ---------------------------------------------------------------------------

def test_perp_perp_entry_spread():
    """Entry spread = long_avg_entry / short_avg_entry - 1."""
    from tracking.pipeline.spreads import entry_spread

    # Long entered at 25.00, short at 25.50
    # Spread = 25.00 / 25.50 - 1 = -0.01961... (long at discount to short)
    spread = entry_spread(long_avg_entry=25.00, short_avg_entry=25.50)
    assert abs(spread - (25.00 / 25.50 - 1.0)) < 1e-9


def test_perp_perp_exit_spread():
    """Exit spread = long_perp_bid / short_perp_ask - 1."""
    from tracking.pipeline.spreads import exit_spread

    # Long leg bid: 25.20, Short leg ask: 25.30
    # Spread = 25.20 / 25.30 - 1 = -0.00395...
    spread = exit_spread(long_bid=25.20, short_ask=25.30)
    assert abs(spread - (25.20 / 25.30 - 1.0)) < 1e-9


def test_perp_perp_spread_pnl_bps():
    """Spread P&L in bps: positive means spread tightened (favorable for long/short)."""
    from tracking.pipeline.spreads import spread_pnl_bps

    entry = 25.00 / 25.50 - 1.0   # ~-196 bps
    exit_ = 25.20 / 25.10 - 1.0   # ~+40 bps — spread flipped to long premium
    bps = spread_pnl_bps(entry=entry, exit=exit_)
    # exit > entry => bps > 0 => favorable
    assert bps > 0


# ---------------------------------------------------------------------------
# 4. Net Funding Tests
# ---------------------------------------------------------------------------

def test_perp_perp_net_funding_sums_both_legs():
    """Net funding = long_funding + short_funding (long is typically negative)."""
    from tracking.pipeline.portfolio import compute_position_net_funding

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        now_ms = 1711900000000
        # Long leg funding: -15 USDC (pays funding, negative)
        # Short leg funding: +40 USDC (receives funding, positive)
        con.executemany(
            """INSERT INTO pm_cashflows
               (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms - 3600000, "FUNDING", -15.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms - 3600000, "FUNDING", +40.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms,           "FUNDING", -12.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms,           "FUNDING", +38.0, "USDC", "{}"),
            ],
        )
        con.commit()

        net = compute_position_net_funding(con, "pos_hype_pp")
        # Expected: -15 + 40 + -12 + 38 = +51
        assert abs(net - 51.0) < 1e-9

        con.close()


def test_perp_perp_long_funding_reduces_carry():
    """Long funding (negative) reduces carry vs SPOT_PERP which has no long funding cost."""
    from tracking.pipeline.portfolio import compute_position_net_funding

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        con = _create_test_db(db_path)
        _seed_perp_perp_position(con)

        now_ms = 1711900000000
        con.executemany(
            """INSERT INTO pm_cashflows
               (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency, meta_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                ("pos_hype_pp", "hype_long_hyna", "hyperliquid", "0xdef", now_ms, "FUNDING", -20.0, "USDC", "{}"),
                ("pos_hype_pp", "hype_short_hl",  "hyperliquid", "0xabc", now_ms, "FUNDING", +60.0, "USDC", "{}"),
            ],
        )
        con.commit()

        net = compute_position_net_funding(con, "pos_hype_pp")
        # Net = +40 (not +60 — long funding cost reduces carry)
        assert abs(net - 40.0) < 1e-9

        con.close()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_perp_perp_fill_mapping_long_leg,
        test_perp_perp_fill_mapping_short_leg,
        test_perp_perp_no_cross_account_mapping,
        test_perp_perp_upnl_long_uses_bid,
        test_perp_perp_upnl_short_uses_ask,
        test_perp_perp_upnl_net_negative_when_spread_moves_against,
        test_perp_perp_entry_spread,
        test_perp_perp_exit_spread,
        test_perp_perp_spread_pnl_bps,
        test_perp_perp_net_funding_sums_both_legs,
        test_perp_perp_long_funding_reduces_carry,
    ]
    for t in tests:
        t()
        print(f"PASS: {t.__name__}")
    print(f"\nAll {len(tests)} PERP_PERP tests passed!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run tests to confirm they fail (Phase 1 not yet implemented)**

```bash
source .arbit_env && .venv/bin/python tests/test_perp_perp.py
```

Expected: `ImportError` — `tracking.pipeline.fill_ingester` etc. don't exist until Phase 1 is complete. Record which imports fail.

- [ ] **Step 3: After Phase 1 complete — run tests again to find actual failures**

```bash
source .arbit_env && .venv/bin/python tests/test_perp_perp.py
```

For each failure: investigate `tracking/pipeline/` source, fix the specific PERP_PERP assumption, re-run.

- [ ] **Step 4: Commit test file**

```bash
git add tests/test_perp_perp.py
git commit -m "test: add PERP_PERP unit tests for fill mapping, uPnL, spreads, net funding"
```

---

## Task 2: Verify and Fix Pipeline Modules

This task runs **after Phase 1 is complete**. The tests from Task 1 drive the verification.

### 2a — `tracking/pipeline/upnl.py`

- [ ] **Step 1: Read `compute_leg_upnl` — confirm it is side-based, not instrument-based**

The function signature from PLAN.md section 4.3:
```python
def compute_leg_upnl(side: str, avg_entry: float, exit_price: float, size: float) -> float:
```

This is already generic. The caller must pass the correct `exit_price` (bid for LONG, ask for SHORT).

- [ ] **Step 2: Check price lookup function**

Locate the function that fetches bid/ask from `prices_v3` for a given `inst_id`. Verify it handles perp `inst_id` formats: `HYPE`, `hyna:HYPE`, `xyz:GOLD`. These are stored in `prices_v3` (populated by `pull_hyperliquid_market.py`).

If the price lookup assumes a `/USDC` suffix for the long leg (spot assumption), fix it to look up by `inst_id` directly regardless of format.

- [ ] **Step 3: Run uPnL tests from Task 1**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_perp_perp.py -k "upnl" -v
```

Fix any failures before proceeding.

### 2b — `tracking/pipeline/spreads.py`

- [ ] **Step 1: Read `spreads.py` — confirm sub-pair generation for PERP_PERP**

For SPOT_PERP, sub-pairs are generated as `(spot_leg, perp_leg)`. For PERP_PERP, there is no spot leg — sub-pairs should be `(long_perp_leg, short_perp_leg)`.

Check the sub-pair generation logic. If it filters legs by `inst_id` containing `/USDC` or by `side == 'LONG'` plus an instrument-type check, fix it to use `side` alone.

Expected correct logic:
```python
long_legs = [l for l in legs if l["side"] == "LONG"]
short_legs = [l for l in legs if l["side"] == "SHORT"]
sub_pairs = [(ll, sl) for ll in long_legs for sl in short_legs]
```

- [ ] **Step 2: Run spread tests from Task 1**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_perp_perp.py -k "spread" -v
```

Fix any failures before proceeding.

### 2c — `tracking/pipeline/portfolio.py`

- [ ] **Step 1: Verify `compute_position_net_funding` sums ALL funding cashflows**

The function should query:
```sql
SELECT SUM(amount) FROM pm_cashflows
WHERE position_id = ? AND cf_type = 'FUNDING'
```

This is instrument-agnostic — it sums funding from all legs. If the function filters by `leg_id` type or has a `AND side = 'SHORT'` guard anywhere, remove it.

- [ ] **Step 2: Verify carry APR uses net funding (both legs)**

Confirm the carry APR computation uses the result of `compute_position_net_funding` (both legs) rather than querying only `SHORT` leg cashflows.

- [ ] **Step 3: Run funding tests from Task 1**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_perp_perp.py -k "funding" -v
```

Fix any failures before proceeding.

- [ ] **Step 4: Run full test suite**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_perp_perp.py -v
```

All 11 tests must pass.

- [ ] **Step 5: Commit any pipeline fixes**

```bash
git add tracking/pipeline/
git commit -m "fix: ensure upnl/spreads/portfolio handle PERP_PERP legs generically"
```

---

## Task 3: Frontend Label Fixes

**Context:** The PLAN.md specifies the frontend labels currently use "Spot" and "Perp" for the position detail view. For PERP_PERP, these labels are wrong — there is no spot leg. Labels should reflect position strategy dynamically.

**Files to edit:** `frontend/` — exact component paths depend on Phase 1c (frontend build). Locate them after Phase 1c is complete.

- [ ] **Step 1: Find label strings in frontend**

```bash
grep -r "Spot" frontend/src --include="*.tsx" -l
grep -r "\"Perp\"" frontend/src --include="*.tsx" -l
```

- [ ] **Step 2: Fix position detail labels**

The position detail component should render leg labels based on `strategy` from the API response:

```typescript
const getLegLabel = (side: "LONG" | "SHORT", strategy: string): string => {
  if (strategy === "PERP_PERP") {
    return side === "LONG" ? "Long Leg" : "Short Leg";
  }
  // SPOT_PERP default
  return side === "LONG" ? "Spot" : "Perp";
};
```

Apply this helper wherever leg labels are rendered.

- [ ] **Step 3: Fix funding display for PERP_PERP**

For SPOT_PERP, only the short (perp) leg shows funding earned. For PERP_PERP, both legs must show funding. Find the funding display component and ensure it renders funding for all legs that have `FUNDING` cashflows, not just the leg with `side === "SHORT"` or `instrument_type === "PERP"`.

Expected PERP_PERP position detail:
```
Long Leg (hyna:HYPE):  uPnL: +$X.XX  |  Funding: -$Y.YY  |  Entry: $Z.ZZ
Short Leg (HYPE):      uPnL: +$A.AA  |  Funding: +$B.BB  |  Entry: $C.CC
Net Funding:           +$D.DD
```

- [ ] **Step 4: Verify in browser with PERP_PERP test position**

Add test position to `config/positions.json` (see Task 4), run pipeline, open dashboard, confirm:
1. Labels show "Long Leg" / "Short Leg" (not "Spot" / "Perp")
2. Both legs show their individual funding amounts
3. Net funding row shows correct sum

- [ ] **Step 5: Commit frontend changes**

```bash
git add frontend/
git commit -m "feat: use dynamic leg labels for PERP_PERP (Long/Short instead of Spot/Perp)"
```

---

## Task 4: E2E Verification with Test Position

- [ ] **Step 1: Add sample PERP_PERP position to `config/positions.json`**

Add a test PERP_PERP position (use a real but small position, or a clearly labeled test entry):

```json
{
  "position_id": "pos_hype_perp_perp_test",
  "strategy": "PERP_PERP",
  "asset": "HYPE",
  "status": "OPEN",
  "legs": [
    {
      "leg_id": "hype_pp_long",
      "venue": "hyena",
      "inst_id": "hyna:HYPE",
      "side": "LONG",
      "size": 10.0,
      "wallet_label": "alt"
    },
    {
      "leg_id": "hype_pp_short",
      "venue": "hyperliquid",
      "inst_id": "HYPE",
      "side": "SHORT",
      "size": 10.0,
      "wallet_label": "main"
    }
  ]
}
```

- [ ] **Step 2: Sync registry**

```bash
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
```

Verify: `pm_positions` and `pm_legs` have the new rows.

- [ ] **Step 3: Run fill ingestion**

```bash
source .arbit_env && .venv/bin/python scripts/cron_data_pipeline.py --once
```

Or trigger just fill ingestion:

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3
from tracking.pipeline.fill_ingester import ingest_hyperliquid_fills
from tracking.pipeline.spot_meta import fetch_spot_index_map
con = sqlite3.connect('tracking/db/arbit_v3.db')
cache = fetch_spot_index_map()
n = ingest_hyperliquid_fills(con, cache)
print(f'Ingested {n} fills')
"
```

- [ ] **Step 4: Compute metrics and verify output**

```bash
source .arbit_env && .venv/bin/python -c "
import sqlite3, json
con = sqlite3.connect('tracking/db/arbit_v3.db')

# Entry prices
rows = con.execute(\"SELECT leg_id, avg_entry_price, total_filled_qty FROM pm_entry_prices WHERE position_id = 'pos_hype_perp_perp_test'\").fetchall()
print('Entry prices:')
for r in rows: print(f'  {r[0]}: avg={r[1]:.4f}, qty={r[2]}')

# Spreads
rows = con.execute(\"SELECT long_leg_id, short_leg_id, entry_spread, exit_spread FROM pm_spreads WHERE position_id = 'pos_hype_perp_perp_test'\").fetchall()
print('Spreads:')
for r in rows: print(f'  {r[0]} / {r[1]}: entry={r[2]:.4f}, exit={r[3]:.4f}')

# Net funding
rows = con.execute(\"SELECT leg_id, SUM(amount) FROM pm_cashflows WHERE position_id = 'pos_hype_perp_perp_test' AND cf_type = 'FUNDING' GROUP BY leg_id\").fetchall()
print('Funding by leg:')
for r in rows: print(f'  {r[0]}: {r[1]:.4f} USD')
total = con.execute(\"SELECT SUM(amount) FROM pm_cashflows WHERE position_id = 'pos_hype_perp_perp_test' AND cf_type = 'FUNDING'\").fetchone()[0]
print(f'Net funding: {total:.4f} USD')
"
```

Expected:
- Both legs have `avg_entry_price` populated
- `pm_spreads` has one row with `long_leg_id = hype_pp_long`, `short_leg_id = hype_pp_short`
- `pm_cashflows` shows funding for both legs; net = long_funding + short_funding

- [ ] **Step 5: Verify API response**

```bash
curl http://localhost:8000/api/positions/pos_hype_perp_perp_test | python3 -m json.tool
```

Verify:
- `strategy: "PERP_PERP"`
- Two legs present, both with `unrealized_pnl` computed
- `net_funding_usd` = sum of both legs
- `carry_apr` reflects dual-funding net

- [ ] **Step 6: Verify frontend display**

Open dashboard in browser. Navigate to the PERP_PERP test position detail. Verify labels and funding display per Task 3 Step 4.

- [ ] **Step 7: Remove test position or set to CLOSED**

After verification, either remove the test entry from `positions.json` or set `"status": "CLOSED"` to prevent it from appearing in live monitoring.

```bash
source .arbit_env && .venv/bin/python scripts/pm.py sync-registry
```

- [ ] **Step 8: Final commit**

```bash
git add config/positions.json
git commit -m "test: verify PERP_PERP E2E pipeline then close test position"
```

---

## Acceptance Criteria

All items must pass before Phase 2 is considered complete.

| # | Criterion | Verify with |
|---|-----------|-------------|
| 1 | `tests/test_perp_perp.py` all 11 tests pass | `pytest tests/test_perp_perp.py -v` |
| 2 | Fill ingestion maps both perp legs correctly | E2E: both legs have fills in `pm_fills` |
| 3 | `pm_entry_prices` populated for both legs | SQL query in Task 4 Step 4 |
| 4 | `pm_spreads` uses `long_leg_id` / `short_leg_id` generically (no spot assumption) | `pm_spreads` row exists for test position |
| 5 | Net funding = long_funding + short_funding | `SUM(amount)` per leg in `pm_cashflows` |
| 6 | Carry APR reflects dual-funding net | `/api/positions/:id` response `carry_apr` |
| 7 | Frontend labels: "Long Leg" / "Short Leg" for PERP_PERP | Browser visual check |
| 8 | Frontend funding: both legs show individual funding amounts | Browser visual check |
| 9 | No regressions in existing SPOT_PERP positions | Run full test suite + check GOLD position |

---

## Rollout Notes

- **Phase dependency:** This phase requires Phase 1a (fill ingestion) and Phase 1b (computation layer) to be complete and tested first. Do not start Task 2 until Phase 1 tests are green.
- **No schema migration needed:** ADR-009 — schema was designed to support PERP_PERP from day one.
- **Low risk:** Most changes are in the test file and frontend labels. Pipeline changes (if any) are narrowly scoped to remove instrument-type guards.
- **Feature flag:** If a PERP_PERP position is encountered before this phase is complete, `portfolio.py` should log a warning and skip that position rather than producing incorrect metrics. Remove the skip after Phase 2 acceptance criteria pass.
