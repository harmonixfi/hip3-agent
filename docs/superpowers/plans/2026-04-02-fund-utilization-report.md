# Fund Utilization Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add fund utilization metrics (leverage, deployed/available capital, allocation %) to the dashboard.

**Architecture:** Extend the existing `/api/portfolio/overview` endpoint with a `fund_utilization` field computed on-the-fly from `pm_account_snapshots` and `pm_legs`. Add a new `FundUtilizationCard` frontend component and an "Alloc %" column to `PositionsTable`.

**Tech Stack:** Python/FastAPI (backend), Next.js/React/TypeScript (frontend), SQLite (data)

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `api/models/schemas.py` | Add `AccountUtilization`, `FundUtilization` models; extend `PortfolioOverview` |
| Modify | `api/routers/portfolio.py` | Compute fund utilization data from DB |
| Modify | `frontend/lib/types.ts` | Add TS interfaces for new API fields |
| Create | `frontend/components/FundUtilizationCard.tsx` | New card component |
| Modify | `frontend/app/page.tsx` | Add card to dashboard layout |
| Modify | `frontend/components/PositionsTable.tsx` | Add "Alloc %" column |

---

### Task 1: Backend — Add Pydantic Models

**Files:**
- Modify: `api/models/schemas.py`

- [ ] **Step 1: Add new models and extend PortfolioOverview**

Add after the `AccountEquity` class (line 22) and before `PortfolioOverview`:

```python
class AccountUtilization(BaseModel):
    label: str
    venue: str
    equity_usd: float
    margin_used_usd: float
    available_usd: float
    position_value_usd: float
    leverage: float


class FundUtilization(BaseModel):
    total_equity_usd: float
    total_notional_usd: float
    total_deployed_usd: float
    total_available_usd: float
    leverage: float
    deployed_pct: float
    accounts: list[AccountUtilization]
```

Then add to the `PortfolioOverview` class, after `as_of`:

```python
    fund_utilization: Optional[FundUtilization] = None
```

- [ ] **Step 2: Verify models parse correctly**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && source .arbit_env && .venv/bin/python -c "from api.models.schemas import FundUtilization, AccountUtilization, PortfolioOverview; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add api/models/schemas.py
git commit -m "feat(api): add FundUtilization and AccountUtilization models"
```

---

### Task 2: Backend — Compute Fund Utilization in Portfolio Endpoint

**Files:**
- Modify: `api/routers/portfolio.py`

- [ ] **Step 1: Update imports**

Add `AccountUtilization` and `FundUtilization` to the import from `api.models.schemas`:

```python
from api.models.schemas import AccountEquity, AccountUtilization, FundUtilization, PortfolioOverview
```

- [ ] **Step 2: Add `_compute_fund_utilization` function**

Add this function before the `portfolio_overview` route handler (before line 38):

```python
def _compute_fund_utilization(
    db: sqlite3.Connection,
    total_equity: float,
    account_rows: list[sqlite3.Row],
) -> FundUtilization:
    """Compute leverage, deployed/available capital from live DB data.

    Multi-venue ready: queries are filtered by venue and account_id from
    pm_account_snapshots. Adding a new venue only requires populating
    the same snapshot tables.
    """
    # 1. Per-account available/margin from latest snapshots (already fetched in caller
    #    but we need extra columns, so re-query with full columns)
    acct_detail_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance,
               a.available_balance, a.margin_balance, a.position_value
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    # 2. Per-account notional from OPEN/PAUSED/EXITING legs
    leg_notional_rows = db.execute(
        """
        SELECT l.account_id,
               SUM(ABS(l.size * COALESCE(l.current_price, ep.avg_entry_price, l.entry_price))) AS notional
        FROM pm_legs l
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        INNER JOIN pm_positions p ON p.position_id = l.position_id
        WHERE p.status IN ('OPEN', 'PAUSED', 'EXITING')
          AND l.size IS NOT NULL
        GROUP BY l.account_id
        """
    ).fetchall()

    acct_notional_map: dict[str, float] = {}
    for row in leg_notional_rows:
        aid = row["account_id"] or "__unknown__"
        acct_notional_map[aid] = row["notional"] or 0.0

    # 3. Build per-account utilization
    accounts: list[AccountUtilization] = []
    total_notional = 0.0
    total_available = 0.0

    for arow in acct_detail_rows:
        aid = arow["account_id"]
        label = _account_label(aid)
        equity = arow["total_balance"] or 0.0
        available = arow["available_balance"] or 0.0
        margin_used = arow["margin_balance"] or 0.0
        pos_value = acct_notional_map.get(aid, 0.0)

        acct_leverage = pos_value / equity if equity > 0 else 0.0
        total_notional += pos_value
        total_available += available

        accounts.append(AccountUtilization(
            label=label,
            venue=arow["venue"],
            equity_usd=round(equity, 2),
            margin_used_usd=round(margin_used, 2),
            available_usd=round(available, 2),
            position_value_usd=round(pos_value, 2),
            leverage=round(acct_leverage, 2),
        ))

    # 4. Aggregate
    leverage = total_notional / total_equity if total_equity > 0 else 0.0
    deployed_pct = (total_notional / total_equity * 100) if total_equity > 0 else 0.0

    return FundUtilization(
        total_equity_usd=round(total_equity, 2),
        total_notional_usd=round(total_notional, 2),
        total_deployed_usd=round(total_notional, 2),
        total_available_usd=round(total_available, 2),
        leverage=round(leverage, 2),
        deployed_pct=round(deployed_pct, 1),
        accounts=accounts,
    )
```

- [ ] **Step 3: Call the function in `portfolio_overview` and include in response**

Inside the `portfolio_overview` handler, after the `net_pnl` computation (after line 182) and before the `return PortfolioOverview(...)`:

```python
    fund_util = _compute_fund_utilization(db, total_equity, account_rows)
```

Then add to the return statement, after `as_of=...`:

```python
        fund_utilization=fund_util,
```

- [ ] **Step 4: Verify API response includes fund_utilization**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && source .arbit_env && .venv/bin/python -c "
import sqlite3, json
from api.routers.portfolio import _compute_fund_utilization, _account_label

db = sqlite3.connect('tracking/db/arbit_v3.db')
db.row_factory = sqlite3.Row

# Quick check
rows = db.execute('SELECT a.account_id, a.venue, a.total_balance FROM pm_account_snapshots a INNER JOIN (SELECT account_id, MAX(ts) AS max_ts FROM pm_account_snapshots GROUP BY account_id) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts').fetchall()
total_eq = sum(r['total_balance'] or 0 for r in rows)
result = _compute_fund_utilization(db, total_eq, rows)
print(json.dumps(result.model_dump(), indent=2))
"`

Expected: JSON output with leverage, deployed_pct, accounts array.

- [ ] **Step 5: Commit**

```bash
git add api/routers/portfolio.py
git commit -m "feat(api): compute fund utilization in portfolio overview"
```

---

### Task 3: Frontend — Add TypeScript Types

**Files:**
- Modify: `frontend/lib/types.ts`

- [ ] **Step 1: Add interfaces and extend PortfolioOverview**

Add before the `// Positions` section comment (before line 27):

```typescript
export interface AccountUtilization {
  label: string;
  venue: string;
  equity_usd: number;
  margin_used_usd: number;
  available_usd: number;
  position_value_usd: number;
  leverage: number;
}

export interface FundUtilization {
  total_equity_usd: number;
  total_notional_usd: number;
  total_deployed_usd: number;
  total_available_usd: number;
  leverage: number;
  deployed_pct: number;
  accounts: AccountUtilization[];
}
```

Then add to the `PortfolioOverview` interface, after `as_of: string;`:

```typescript
  fund_utilization: FundUtilization | null;
```

- [ ] **Step 2: Commit**

```bash
git add frontend/lib/types.ts
git commit -m "feat(frontend): add FundUtilization TypeScript types"
```

---

### Task 4: Frontend — Create FundUtilizationCard Component

**Files:**
- Create: `frontend/components/FundUtilizationCard.tsx`

- [ ] **Step 1: Create the component**

```tsx
import { formatUSD } from "@/lib/format";
import type { FundUtilization } from "@/lib/types";

interface Props {
  data: FundUtilization | null;
}

function leverageColor(leverage: number): string {
  if (leverage < 1) return "text-green-400";
  if (leverage <= 2) return "text-gray-200";
  if (leverage <= 3) return "text-yellow-400";
  return "text-red-400";
}

export default function FundUtilizationCard({ data }: Props) {
  if (!data) {
    return (
      <div className="card">
        <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
          Fund Utilization
        </div>
        <div className="text-gray-600">No data</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-3">
        Fund Utilization
      </div>

      {/* Summary metrics */}
      <div className="space-y-2 mb-4">
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Leverage</span>
          <span className={`text-lg font-bold tabular-nums ${leverageColor(data.leverage)}`}>
            {data.leverage.toFixed(2)}x
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Deployed</span>
          <span className="text-sm text-gray-200 tabular-nums">
            {formatUSD(data.total_deployed_usd)}{" "}
            <span className="text-gray-500">{data.deployed_pct.toFixed(0)}%</span>
          </span>
        </div>
        <div className="flex justify-between items-baseline">
          <span className="text-xs text-gray-500">Available</span>
          <span className="text-sm text-gray-200 tabular-nums">
            {formatUSD(data.total_available_usd)}
          </span>
        </div>
      </div>

      {/* Per-account breakdown */}
      {data.accounts.length > 0 && (
        <div className="border-t border-gray-800 pt-3">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500">
                <th className="text-left font-normal pb-1">Account</th>
                <th className="text-right font-normal pb-1">Equity</th>
                <th className="text-right font-normal pb-1">Leverage</th>
              </tr>
            </thead>
            <tbody>
              {data.accounts.map((acct) => (
                <tr key={acct.label} className="text-gray-300">
                  <td className="py-0.5">{acct.label}</td>
                  <td className="text-right tabular-nums">{formatUSD(acct.equity_usd)}</td>
                  <td className={`text-right tabular-nums ${leverageColor(acct.leverage)}`}>
                    {acct.leverage.toFixed(2)}x
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/components/FundUtilizationCard.tsx
git commit -m "feat(frontend): add FundUtilizationCard component"
```

---

### Task 5: Frontend — Add Card to Dashboard Layout

**Files:**
- Modify: `frontend/app/page.tsx`

- [ ] **Step 1: Import the new component**

Add after the `FundingSummary` import (line 4):

```typescript
import FundUtilizationCard from "@/components/FundUtilizationCard";
```

- [ ] **Step 2: Change the grid from 3 to 4 columns and add the card**

Replace the top-row grid section (lines 75-80):

```tsx
      {/* Top row: Equity + Wallets + Funding + Utilization */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <EquityCard data={portfolioData} />
        <WalletBreakdown data={portfolioData} />
        <FundingSummary data={portfolioData} />
        <FundUtilizationCard data={portfolioData.fund_utilization} />
      </div>
```

- [ ] **Step 3: Verify build compiles**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx next build 2>&1 | tail -20`

Expected: Build succeeds with no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app/page.tsx
git commit -m "feat(frontend): add FundUtilizationCard to dashboard layout"
```

---

### Task 6: Frontend — Add Allocation Column to PositionsTable

**Files:**
- Modify: `frontend/components/PositionsTable.tsx`

- [ ] **Step 1: Add `alloc_pct` to SortKey union**

Change the `SortKey` type (line 14):

```typescript
type SortKey =
  | "base"
  | "amount_usd"
  | "alloc_pct"
  | "unrealized_pnl"
  | "funding_earned"
  | "carry_apr"
  | "exit_spread";
```

- [ ] **Step 2: Compute total notional and add allocation helper**

Inside the component function, after the `const [sortAsc, setSortAsc] = useState(true);` line (after line 23), add:

```typescript
  const totalNotional = positions.reduce((sum, p) => sum + (p.amount_usd ?? 0), 0);

  function getAllocPct(p: Position): number {
    if (!totalNotional || p.amount_usd == null) return 0;
    return (p.amount_usd / totalNotional) * 100;
  }

  function allocColor(pct: number): string {
    if (pct > 50) return "text-red-400";
    if (pct >= 40) return "text-yellow-400";
    return "";
  }
```

- [ ] **Step 3: Add alloc_pct case to getSortValue**

Add a case in the `getSortValue` switch, after `case "amount_usd":`:

```typescript
      case "alloc_pct":
        return getAllocPct(p);
```

- [ ] **Step 4: Add column header in thead**

After the Amount `SortHeader` (line 192), add:

```tsx
              <SortHeader label="Alloc %" sortId="alloc_pct" />
```

- [ ] **Step 5: Add allocation cell in tbody**

After the Amount `<td>` (after line 244), add:

```tsx
                  <td className={`text-right tabular-nums ${allocColor(getAllocPct(p))}`}>
                    {getAllocPct(p).toFixed(1)}%
                  </td>
```

- [ ] **Step 6: Verify build compiles**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx next build 2>&1 | tail -20`

Expected: Build succeeds with no type errors.

- [ ] **Step 7: Commit**

```bash
git add frontend/components/PositionsTable.tsx
git commit -m "feat(frontend): add Alloc % column to PositionsTable"
```

---

### Task 7: End-to-End Verification

- [ ] **Step 1: Start the backend and verify API response**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent && source .arbit_env && .venv/bin/python -m uvicorn api.main:app --port 8000 &`

Then: `curl -s http://localhost:8000/api/portfolio/overview | python3 -m json.tool | grep -A 20 fund_utilization`

Expected: `fund_utilization` object with `leverage`, `deployed_pct`, `accounts` array.

- [ ] **Step 2: Verify frontend build**

Run: `cd /Users/beannguyen/Development/OpenClawAgents/hip3-agent/frontend && npx next build 2>&1 | tail -20`

Expected: Build succeeds, no errors.

- [ ] **Step 3: Kill the test server**

Run: `kill %1 2>/dev/null || true`

- [ ] **Step 4: Final commit (if any fixups needed)**

```bash
git add -u
git commit -m "fix: fund utilization report fixups"
```
