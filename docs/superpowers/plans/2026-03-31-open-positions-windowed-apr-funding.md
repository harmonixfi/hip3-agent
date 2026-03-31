# Open Positions — Windowed APR & Funding Columns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two grouped columns — APR (realized) and Funding $ (realized) at 1d/3d/7d/14d windows — to the Open Positions table in the dashboard.

**Architecture:** Add `WindowedMetrics` Pydantic schema to `schemas.py`, implement `_windowed_metrics()` in the API router using a single batched SQL query against `pm_cashflows`, then surface the data in the frontend as two grouped `<td>` cells with a 4-column sub-grid layout.

**Tech Stack:** Python 3.9, FastAPI, Pydantic v2, SQLite, Next.js 14, TypeScript, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-31-open-positions-windowed-apr-funding-design.md`

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `api/models/schemas.py` | Modify | Add `WindowedMetrics` class; add `windowed` field to `PositionSummary` |
| `api/routers/positions.py` | Modify | Add `_windowed_metrics()`; call it in `_build_position_summary()` |
| `tests/test_api.py` | Modify | Add cashflow fixtures for windowed tests; add 3 new test functions |
| `frontend/lib/types.ts` | Modify | Add `WindowedMetrics` interface; add `windowed` field to `Position` |
| `frontend/components/PositionsTable.tsx` | Modify | Add 2 grouped columns with sub-value grid and warning state |

---

## Task 1: Add `WindowedMetrics` schema

**Files:**
- Modify: `api/models/schemas.py`

- [ ] **Step 1: Add `WindowedMetrics` class and wire into `PositionSummary`**

Open `api/models/schemas.py`. After the `SubPairSpread` class (line 56) and before `PositionSummary`, insert:

```python
class WindowedMetrics(BaseModel):
    funding_1d:          Optional[float] = None
    funding_3d:          Optional[float] = None
    funding_7d:          Optional[float] = None
    funding_14d:         Optional[float] = None
    apr_1d:              Optional[float] = None  # percent form e.g. 38.5 means 38.5%
    apr_3d:              Optional[float] = None
    apr_7d:              Optional[float] = None
    apr_14d:             Optional[float] = None
    incomplete_notional: bool = False
    missing_leg_ids:     list[str] = []
```

Then add `windowed` as the last field of `PositionSummary`:

```python
class PositionSummary(BaseModel):
    position_id: str
    base: str
    strategy: str
    status: str
    amount_usd: Optional[float] = Field(...)
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    funding_earned: Optional[float] = None
    fees_paid: Optional[float] = None
    net_carry: Optional[float] = None
    carry_apr: Optional[float] = None
    sub_pairs: list[SubPairSpread] = []
    legs: list[LegDetail] = []
    opened_at: Optional[str] = None
    windowed: Optional[WindowedMetrics] = None  # None if amount_usd unavailable
```

- [ ] **Step 2: Verify schema imports cleanly**

```bash
source .arbit_env && .venv/bin/python -c "from api.models.schemas import WindowedMetrics, PositionSummary; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/models/schemas.py
git commit -m "feat: add WindowedMetrics schema to PositionSummary"
```

---

## Task 2: Implement `_windowed_metrics()` in the API router

**Files:**
- Modify: `api/routers/positions.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Open `tests/test_api.py`. Find `_setup_test_db()`. After the existing cashflow inserts (around line 166), add two more FUNDING cashflows to give the test position data across multiple windows:

```python
# 2nd funding payment: 3 hours ago (within 1d/3d/7d/14d)
con.execute(
    """
    INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
     now_ms - 3 * 3600000, "FUNDING", 5.00, "USDC"),
)
# 3rd funding payment: 5 days ago (within 7d/14d but NOT 3d)
con.execute(
    """
    INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
     now_ms - 5 * 86400000, "FUNDING", 25.00, "USDC"),
)
```

Also add a position with a price-missing leg for the incomplete_notional test:

```python
# Position with missing spot leg price (for incomplete_notional test)
con.execute(
    """
    INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_ETH_WARN", "hyperliquid", "SPOT_PERP", "OPEN",
     day_ago_ms, now_ms,
     json.dumps({"base": "ETH", "strategy_type": "SPOT_PERP"})),
)
# Spot leg: size set but all prices are NULL
con.execute(
    """
    INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                         entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_ETH_WARN_SPOT", "pos_test_ETH_WARN", "hyperliquid", "ETH/USDC",
     "LONG", 1.0, None, None, None, "OPEN", day_ago_ms, "0xtest123"),
)
# Perp leg: has price (so partial notional available)
con.execute(
    """
    INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size,
                         entry_price, current_price, unrealized_pnl, status, opened_at_ms, account_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_ETH_WARN_PERP", "pos_test_ETH_WARN", "hyperliquid", "ETH",
     "SHORT", 1.0, 3000.0, 3100.0, -100.0, "OPEN", day_ago_ms, "0xtest123"),
)
con.execute(
    """
    INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """,
    ("pos_test_ETH_WARN", "pos_test_ETH_WARN_PERP", "hyperliquid", "0xtest123",
     now_ms - 3600000, "FUNDING", 10.0, "USDC"),
)
```

Now add three test functions at the end of `tests/test_api.py`:

```python
def test_positions_windowed_metrics_present(client: TestClient):
    """windowed field is present in /api/positions response."""
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    positions = resp.json()
    btc = next(p for p in positions if p["position_id"] == "pos_test_BTC")
    assert btc["windowed"] is not None
    w = btc["windowed"]
    assert "funding_1d" in w
    assert "funding_3d" in w
    assert "funding_7d" in w
    assert "funding_14d" in w
    assert "apr_1d" in w
    assert "apr_3d" in w
    assert "apr_7d" in w
    assert "apr_14d" in w
    assert "incomplete_notional" in w
    assert "missing_leg_ids" in w


def test_positions_windowed_funding_windows(client: TestClient):
    """Windowed funding sums respect time boundaries.

    Cashflows for pos_test_BTC:
      - 5.25 at now - 1h   (in 1d, 3d, 7d, 14d)
      - 5.00 at now - 3h   (in 1d, 3d, 7d, 14d)
      - 25.0 at now - 5d   (in 7d, 14d only — NOT 1d or 3d)

    amount_usd_raw = 0.1 * 60500 (spot) + 0.1 * 60500 (perp) = 12100.0
    """
    import pytest
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    btc = next(p for p in resp.json() if p["position_id"] == "pos_test_BTC")
    w = btc["windowed"]

    assert w["incomplete_notional"] is False
    assert w["missing_leg_ids"] == []

    # Funding windows
    assert w["funding_1d"]  == pytest.approx(10.25, abs=0.01)   # 5.25 + 5.00
    assert w["funding_3d"]  == pytest.approx(10.25, abs=0.01)   # 5.25 + 5.00
    assert w["funding_7d"]  == pytest.approx(35.25, abs=0.01)   # 5.25 + 5.00 + 25.0
    assert w["funding_14d"] == pytest.approx(35.25, abs=0.01)   # same

    # APR for 1d: (10.25 / 1) * 365 / 12100 * 100
    expected_apr_1d = (10.25 / 1) * 365 / 12100 * 100
    assert w["apr_1d"] == pytest.approx(expected_apr_1d, rel=0.001)

    # APR for 7d: (35.25 / 7) * 365 / 12100 * 100
    expected_apr_7d = (35.25 / 7) * 365 / 12100 * 100
    assert w["apr_7d"] == pytest.approx(expected_apr_7d, rel=0.001)


def test_positions_windowed_incomplete_notional(client: TestClient):
    """incomplete_notional=True when a leg has no price; apr_* are None, funding_* still present."""
    resp = client.get("/api/positions?status=OPEN", headers=_headers())
    assert resp.status_code == 200
    eth = next(p for p in resp.json() if p["position_id"] == "pos_test_ETH_WARN")
    w = eth["windowed"]

    assert w["incomplete_notional"] is True
    assert "pos_test_ETH_WARN_SPOT" in w["missing_leg_ids"]

    # APR fields must all be None when notional is incomplete
    assert w["apr_1d"]  is None
    assert w["apr_3d"]  is None
    assert w["apr_7d"]  is None
    assert w["apr_14d"] is None

    # Funding $ fields still populated (cashflows are trustworthy)
    assert w["funding_1d"] == pytest.approx(10.0, abs=0.01)
```

Check that the test file needs a `client` fixture. Look near the top of `tests/test_api.py` — if no `client` fixture exists, add it:

```python
import pytest

@pytest.fixture
def client():
    db_path = _setup_test_db()
    os.environ["HARMONIX_DB_PATH"] = str(db_path)
    from api.main import app
    with TestClient(app) as c:
        yield c
    Path(db_path).unlink(missing_ok=True)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py::test_positions_windowed_metrics_present tests/test_api.py::test_positions_windowed_funding_windows tests/test_api.py::test_positions_windowed_incomplete_notional -v
```

Expected: 3 FAILs — `KeyError: 'windowed'` or `AssertionError`.

- [ ] **Step 3: Implement `_windowed_metrics()`**

Open `api/routers/positions.py`. Add this function after `_gross_notional_usd_from_leg_rows()` (after line ~60):

```python
def _windowed_metrics(
    db: sqlite3.Connection,
    position_id: str,
    amount_usd_raw: Optional[float],
    leg_rows: list[sqlite3.Row],
    now_ms: int,
) -> Optional[object]:
    """Compute realized windowed funding and APR from pm_cashflows.

    Returns None if amount_usd_raw is unavailable.
    APR values are in percent form (e.g. 38.5 means 38.5%).
    All apr_* are None when incomplete_notional=True (unreliable denominator).
    funding_* are None when the window sum is 0.0 (no cashflows in that period).
    """
    from api.models.schemas import WindowedMetrics

    # Step 1: detect incomplete notional (mirror _gross_notional_usd_from_leg_rows logic)
    missing_leg_ids: list[str] = []
    for lr in leg_rows:
        px = lr["current_price"]
        if px is None:
            px = lr["avg_entry_price"]
        if px is None:
            px = lr["entry_price"]
        sz = lr["size"]
        if px is None or sz is None:
            missing_leg_ids.append(lr["leg_id"])

    incomplete_notional = len(missing_leg_ids) > 0

    if amount_usd_raw is None or amount_usd_raw <= 0:
        return None

    # Step 2: single batched funding query (positional ? placeholders)
    ms_1d  = now_ms - 1  * 86400 * 1000
    ms_3d  = now_ms - 3  * 86400 * 1000
    ms_7d  = now_ms - 7  * 86400 * 1000
    ms_14d = now_ms - 14 * 86400 * 1000

    row = db.execute(
        """
        SELECT
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_1d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_3d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_7d,
          SUM(CASE WHEN ts >= ? THEN amount ELSE 0 END) AS funding_14d
        FROM pm_cashflows
        WHERE position_id = ? AND cf_type = 'FUNDING'
        """,
        (ms_1d, ms_3d, ms_7d, ms_14d, position_id),
    ).fetchone()

    def _to_funding(v: Optional[float]) -> Optional[float]:
        """0.0 treated as None — no cashflows in this window."""
        if v is None or v == 0.0:
            return None
        return round(v, 4)

    funding_1d  = _to_funding(row["funding_1d"]  if row else None)
    funding_3d  = _to_funding(row["funding_3d"]  if row else None)
    funding_7d  = _to_funding(row["funding_7d"]  if row else None)
    funding_14d = _to_funding(row["funding_14d"] if row else None)

    # Step 3: derive APR (percent form). All None if incomplete_notional.
    def _apr(funding: Optional[float], days: int) -> Optional[float]:
        if incomplete_notional or funding is None:
            return None
        return round((funding / days) * 365 / amount_usd_raw * 100, 4)

    return WindowedMetrics(
        funding_1d=funding_1d,
        funding_3d=funding_3d,
        funding_7d=funding_7d,
        funding_14d=funding_14d,
        apr_1d=_apr(funding_1d, 1),
        apr_3d=_apr(funding_3d, 3),
        apr_7d=_apr(funding_7d, 7),
        apr_14d=_apr(funding_14d, 14),
        incomplete_notional=incomplete_notional,
        missing_leg_ids=missing_leg_ids,
    )
```

- [ ] **Step 4: Wire `_windowed_metrics()` into `_build_position_summary()`**

In `_build_position_summary()`, find where `carry_apr` is computed (around line 155). Add `now_ms` computation and the `_windowed_metrics` call directly before the `return PositionSummary(...)` line:

```python
    # Windowed realized metrics
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    windowed = _windowed_metrics(db, position_id, amount_usd, leg_rows, now_ms)

    return PositionSummary(
        position_id=position_id,
        base=base,
        strategy=strategy,
        status=pos["status"],
        amount_usd=round(amount_usd, 2) if amount_usd else None,
        unrealized_pnl=round(total_upnl, 2) if total_upnl else None,
        unrealized_pnl_pct=round(upnl_pct, 2) if upnl_pct is not None else None,
        funding_earned=round(funding, 2),
        fees_paid=round(fees, 2),
        net_carry=round(net_carry, 2),
        carry_apr=carry_apr,
        sub_pairs=sub_pairs,
        legs=legs,
        opened_at=_ts_to_iso(pos["created_at_ms"]),
        windowed=windowed,
    )
```

Note: `amount_usd` here is the raw value from `_gross_notional_usd_from_leg_rows()` — it is passed to `_windowed_metrics` before rounding.

- [ ] **Step 5: Run tests to verify they pass**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py::test_positions_windowed_metrics_present tests/test_api.py::test_positions_windowed_funding_windows tests/test_api.py::test_positions_windowed_incomplete_notional -v
```

Expected: 3 PASSes.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
source .arbit_env && .venv/bin/python -m pytest tests/test_api.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add api/routers/positions.py tests/test_api.py
git commit -m "feat: add _windowed_metrics() to positions API with batched SQL query"
```

---

## Task 3: Add `WindowedMetrics` TypeScript type

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Add `WindowedMetrics` interface and `windowed` field to `Position`**

Open `frontend/lib/types.ts`. After the `SubPair` interface (around line 37), insert:

```typescript
export interface WindowedMetrics {
  funding_1d:          number | null;
  funding_3d:          number | null;
  funding_7d:          number | null;
  funding_14d:         number | null;
  apr_1d:              number | null;  // percent form e.g. 38.5 means 38.5%
  apr_3d:              number | null;
  apr_7d:              number | null;
  apr_14d:             number | null;
  incomplete_notional: boolean;
  missing_leg_ids:     string[];
}
```

Then add `windowed` as the last field of the `Position` interface:

```typescript
export interface Position {
  position_id: string;
  base: string;
  strategy: "SPOT_PERP" | "PERP_PERP";
  status: "OPEN" | "PAUSED" | "EXITING" | "CLOSED";
  amount_usd: number;
  unrealized_pnl: number | null;
  unrealized_pnl_pct: number | null;
  funding_earned: number;
  fees_paid: number;
  net_carry: number;
  carry_apr: number | null;
  sub_pairs: SubPair[];
  legs: Leg[];
  opened_at: string;
  windowed: WindowedMetrics | null;
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors (empty output).

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat: add WindowedMetrics type to Position"
```

---

## Task 4: Add grouped columns to `PositionsTable`

**Files:**
- Modify: `frontend/components/PositionsTable.tsx`

- [ ] **Step 1: Add the two new column headers**

Open `frontend/components/PositionsTable.tsx`. In `<thead>`, after the `<SortHeader label="Carry APR" ... />` line (line 114), insert the two `TooltipHeader` calls:

```tsx
<TooltipHeader
  label="APR (realized)"
  tooltip={`Realized APR from pm_cashflows.\nAnnualized from actual funding earned per window.\nNot a market rate.`}
/>
<TooltipHeader
  label="Funding $ (realized)"
  tooltip={`Realized funding cashflows from pm_cashflows.\n1d / 3d / 7d / 14d cumulative totals.`}
/>
```

Final column order becomes: Base | Status | Amount | uPnL | Funding | Carry APR | **APR (realized)** | **Funding $ (realized)** | Exit Spread | Spread P&L

- [ ] **Step 2: Add helper components for the sub-value grid cells**

Inside the `PositionsTable` component body (before the `return`), add two helper components:

```tsx
function WindowedAprCell({ w }: { w: WindowedMetrics | null }) {
    if (!w) {
      return <td className="text-right tabular-nums text-gray-600">—</td>;
    }

    if (w.incomplete_notional) {
      const tipText = `APR unavailable — spot leg price missing.\nAffected legs: ${w.missing_leg_ids.join(", ")}`;
      return (
        <td className="text-right tabular-nums">
          <span className="relative group inline-flex items-center gap-1 justify-end">
            <svg
              className="w-3.5 h-3.5 text-yellow-400 group-hover:text-yellow-300 cursor-help"
              viewBox="0 0 16 16"
              fill="currentColor"
              aria-hidden="true"
            >
              <path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm0 2a1 1 0 1 1 0 2 1 1 0 0 1 0-2zm-.25 3.5h.5a.75.75 0 0 1 .75.75v3.5a.25.25 0 0 0 .25.25h.25v1h-3v-1h.25a.25.25 0 0 0 .25-.25v-2.5a.25.25 0 0 0-.25-.25H6.5v-1h1.25z" />
            </svg>
            <div className="absolute bottom-full right-0 mb-2 z-50 hidden group-hover:block pointer-events-none">
              <div className="bg-gray-900 border border-gray-700 rounded px-3 py-2 text-xs text-gray-200 whitespace-pre-line w-64 shadow-lg text-left">
                {tipText}
              </div>
              <div className="w-2 h-2 bg-gray-900 border-r border-b border-gray-700 rotate-45 ml-auto mr-2 -mt-1" />
            </div>
          </span>
        </td>
      );
    }

    const windows: Array<{ label: string; value: number | null }> = [
      { label: "1d",  value: w.apr_1d  },
      { label: "3d",  value: w.apr_3d  },
      { label: "7d",  value: w.apr_7d  },
      { label: "14d", value: w.apr_14d },
    ];

    return (
      <td className="tabular-nums">
        <div className="grid grid-cols-4 gap-x-2 text-xs min-w-[140px]">
          {windows.map(({ label }) => (
            <span key={label} className="text-gray-500 text-center">{label}</span>
          ))}
          {windows.map(({ label, value }) => (
            <span key={label} className={`text-center ${pnlColor(value)}`}>
              {formatPct(value, 1)}
            </span>
          ))}
        </div>
      </td>
    );
  }

  function WindowedFundingCell({ w }: { w: WindowedMetrics | null }) {
    if (!w) {
      return <td className="text-right tabular-nums text-gray-600">—</td>;
    }

    const windows: Array<{ label: string; value: number | null }> = [
      { label: "1d",  value: w.funding_1d  },
      { label: "3d",  value: w.funding_3d  },
      { label: "7d",  value: w.funding_7d  },
      { label: "14d", value: w.funding_14d },
    ];

    return (
      <td className="tabular-nums">
        <div className="grid grid-cols-4 gap-x-2 text-xs min-w-[160px]">
          {windows.map(({ label }) => (
            <span key={label} className="text-gray-500 text-center">{label}</span>
          ))}
          {windows.map(({ label, value }) => (
            <span key={label} className="text-center text-gray-200">
              {formatUSD(value)}
            </span>
          ))}
        </div>
      </td>
    );
  }
```

- [ ] **Step 3: Add the import for `WindowedMetrics`**

At the top of `PositionsTable.tsx`, update the type import:

```tsx
import type { Position, WindowedMetrics } from "@/lib/types";
```

- [ ] **Step 4: Render the two new cells in each row**

In the `<tbody>` row map (after the `carry_apr` `<td>`, before the `avgExitSpread` `<td>`), insert:

```tsx
<WindowedAprCell w={p.windowed} />
<WindowedFundingCell w={p.windowed} />
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 6: Check the dashboard renders in the browser**

Open `http://localhost:3000`. The Open Positions table should now show 10 columns. If you have open positions with cashflows, the new cells show the 4-window sub-grid. If no positions exist, the table renders empty rows cleanly.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/PositionsTable.tsx frontend/lib/types.ts
git commit -m "feat: add APR (realized) and Funding $ (realized) grouped columns to Open Positions table"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|-----------------|------|
| `WindowedMetrics` Pydantic schema with 8 funding/APR fields + `incomplete_notional` + `missing_leg_ids` | Task 1 |
| Add `windowed` to `PositionSummary` | Task 1 |
| `_windowed_metrics()` with single batched SQL query | Task 2 |
| Skip logic mirrors `_gross_notional_usd_from_leg_rows` (size=None OR all prices=None) | Task 2, Step 3 |
| `amount_usd_raw` passed before rounding | Task 2, Step 4 |
| `now_ms` computed by caller | Task 2, Step 4 |
| `0.0` funding treated as `None` | Task 2, Step 3 (`_to_funding`) |
| APR formula: `(funding/X) * 365 / amount_usd_raw * 100` (no `* 2`) | Task 2, Step 3 (`_apr`) |
| All `apr_*` = `None` when `incomplete_notional=True` | Task 2, Step 3 |
| `PositionDetail` inherits `windowed` automatically | Covered — no extra task needed |
| TypeScript `WindowedMetrics` interface | Task 3 |
| `windowed` field on `Position` | Task 3 |
| Two `TooltipHeader` columns after Carry APR | Task 4, Step 1 |
| Final column order: 10 columns explicit | Task 4, Step 1 |
| Sub-value 4-column grid layout | Task 4, Step 2 |
| APR values use `pnlColor()` + `formatPct(v, 1)` | Task 4, Step 2 |
| Funding values use `formatUSD(v)` | Task 4, Step 2 |
| Warning state uses SVG icon (not emoji) | Task 4, Step 2 |
| Warning tooltip lists `missing_leg_ids` | Task 4, Step 2 |
| `windowed=null` renders `—` | Task 4, Step 2 |

All requirements covered. No gaps.
