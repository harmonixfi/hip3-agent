# Phase 1c: FastAPI REST API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a FastAPI application serving REST endpoints for the monitoring dashboard. The API is a thin read layer over SQLite — all computation is done by Phase 1b modules. The API reads from pre-computed tables and formats JSON responses.

**Architecture:** FastAPI app under `api/` with router-per-domain structure. SQLite connections via dependency injection (read-only for GET, writable for POST cashflow). X-API-Key auth middleware on all `/api/*` routes. CORS configured for Vercel frontend domain.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, Pydantic v2, SQLite3 (stdlib). No ORM — raw SQL consistent with existing codebase.

**References:**
- Architecture spec: `docs/PLAN.md` sections 4.1–4.3
- Task checklist: `docs/tasks/phase-1c-api-endpoints.md`
- Decisions: `docs/DECISIONS.md` (ADR-006 Next.js+FastAPI, ADR-010 manual deposit, ADR-003 Cloudflare Tunnel)
- DB schema: `tracking/sql/schema_pm_v3.sql`, `tracking/sql/schema_monitoring_v1.sql` (from Phase 1a)
- Existing patterns: `scripts/pm.py` (connect, `_q1`), `tracking/position_manager/registry.py` (data models)
- Vault interface: `vault/vault.py` (`get_secret_with_env_fallback`)

**Depends on:** Phase 1a (schema + vault), Phase 1b (computed metrics in `pm_entry_prices`, `pm_spreads`, `pm_portfolio_snapshots`).

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `api/__init__.py` | Package init |
| Create | `api/main.py` | FastAPI app, CORS, lifespan, auth middleware |
| Create | `api/config.py` | Settings: DB path, API key, CORS origins |
| Create | `api/deps.py` | Dependency injection: DB connections |
| Create | `api/routers/__init__.py` | Package init |
| Create | `api/routers/portfolio.py` | GET /api/portfolio/overview |
| Create | `api/routers/positions.py` | GET /api/positions, /{id}, /{id}/fills, /closed |
| Create | `api/routers/cashflows.py` | POST /api/cashflows/manual |
| Create | `api/routers/health.py` | GET /api/health |
| Create | `api/models/__init__.py` | Package init |
| Create | `api/models/schemas.py` | Pydantic response/request models |
| Create | `tests/test_api.py` | FastAPI TestClient integration tests |
| Modify | `requirements.txt` | Add fastapi, uvicorn |

---

## Task 1: Dependencies and Project Scaffold

**Files:**
- Modify: `requirements.txt`
- Create: `api/__init__.py`, `api/routers/__init__.py`, `api/models/__init__.py`
- Create: `api/config.py`

- [ ] **Step 1: Add dependencies to requirements.txt**

Append to `requirements.txt`:

```
fastapi>=0.115
uvicorn[standard]>=0.34
```

Note: Pydantic v2 comes as a transitive dependency of FastAPI. No separate entry needed.

- [ ] **Step 2: Install dependencies**

Run:
```bash
source .arbit_env && .venv/bin/pip install -r requirements.txt
```

Expected: FastAPI + uvicorn installed successfully.

- [ ] **Step 3: Create package init files**

Create `api/__init__.py`:
```python
```

Create `api/routers/__init__.py`:
```python
```

Create `api/models/__init__.py`:
```python
```

- [ ] **Step 4: Create config module**

Create `api/config.py`:

```python
"""API configuration — settings loaded from vault with env fallback."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import lru_cache
from pydantic import BaseModel

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class Settings(BaseModel):
    """Application settings.

    Loaded once at startup. API key comes from vault with env fallback.
    """

    db_path: Path = ROOT / "tracking" / "db" / "arbit_v3.db"
    api_key: str = ""
    cors_origins: list[str] = [
        "http://localhost:3000",           # local Next.js dev
        "https://localhost:3000",
    ]
    # Additional Vercel domains added via HARMONIX_CORS_ORIGINS env var
    # Format: comma-separated URLs


@lru_cache
def get_settings() -> Settings:
    """Build settings, resolving API key from vault then env."""
    # Resolve API key: vault first, then env fallback
    api_key = ""
    try:
        from vault.vault import get_secret_with_env_fallback

        api_key = get_secret_with_env_fallback(
            key="api_key",
            env_var="HARMONIX_API_KEY",
        ) or ""
    except Exception:
        # Vault not available — try pure env
        api_key = os.environ.get("HARMONIX_API_KEY", "")

    # Resolve CORS origins
    cors_origins = Settings().cors_origins.copy()
    extra = os.environ.get("HARMONIX_CORS_ORIGINS", "")
    if extra:
        cors_origins.extend(
            origin.strip() for origin in extra.split(",") if origin.strip()
        )

    # Resolve DB path override
    db_path = Path(os.environ.get("HARMONIX_DB_PATH", str(Settings().db_path)))

    return Settings(
        db_path=db_path,
        api_key=api_key,
        cors_origins=cors_origins,
    )
```

- [ ] **Step 5: Verify config loads**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from api.config import get_settings
s = get_settings()
print(f'DB path: {s.db_path}')
print(f'API key set: {bool(s.api_key)}')
print(f'CORS origins: {s.cors_origins}')
print('OK: config loads')
"
```

Expected: Config loads, DB path points to `tracking/db/arbit_v3.db`.

---

## Task 2: Pydantic Response/Request Models

**Files:**
- Create: `api/models/schemas.py`

- [ ] **Step 1: Create all Pydantic models**

Create `api/models/schemas.py`:

```python
"""Pydantic models for API request/response schemas.

All response models match the specs in docs/PLAN.md section 4.2.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Portfolio
# ============================================================

class AccountEquity(BaseModel):
    address: str
    equity_usd: float
    venue: str


class PortfolioOverview(BaseModel):
    total_equity_usd: float
    equity_by_account: dict[str, AccountEquity]
    daily_change_usd: float
    daily_change_pct: float
    cashflow_adjusted_apr: float
    funding_today_usd: float
    funding_alltime_usd: float
    fees_alltime_usd: float
    net_pnl_alltime_usd: float
    tracking_start_date: str
    open_positions_count: int
    total_unrealized_pnl: float
    as_of: str  # ISO 8601


# ============================================================
# Positions
# ============================================================

class LegDetail(BaseModel):
    leg_id: str
    venue: str
    inst_id: str
    side: str
    size: float
    avg_entry_price: Optional[float] = None
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    account_id: Optional[str] = None


class SubPairSpread(BaseModel):
    spot_leg_id: str
    perp_leg_id: str
    entry_spread_bps: Optional[float] = None
    exit_spread_bps: Optional[float] = None
    spread_pnl_bps: Optional[float] = None


class PositionSummary(BaseModel):
    position_id: str
    base: str
    strategy: str
    status: str
    amount_usd: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    funding_earned: Optional[float] = None
    fees_paid: Optional[float] = None
    net_carry: Optional[float] = None
    carry_apr: Optional[float] = None
    sub_pairs: list[SubPairSpread] = []
    legs: list[LegDetail] = []
    opened_at: Optional[str] = None  # ISO 8601


class FillsSummaryItem(BaseModel):
    leg_id: str
    fill_count: int
    first_fill: Optional[str] = None  # ISO 8601
    last_fill: Optional[str] = None   # ISO 8601


class CashflowItem(BaseModel):
    cashflow_id: int
    cf_type: str
    amount: float
    currency: str
    ts: str  # ISO 8601
    description: Optional[str] = None


class DailyFundingItem(BaseModel):
    date: str  # YYYY-MM-DD
    amount: float


class PositionDetail(PositionSummary):
    """Extended position with fills summary, cashflows, and daily funding."""
    fills_summary: list[FillsSummaryItem] = []
    cashflows: list[CashflowItem] = []
    daily_funding_series: list[DailyFundingItem] = []


# ============================================================
# Fills
# ============================================================

class FillItem(BaseModel):
    fill_id: int
    leg_id: Optional[str] = None
    inst_id: str
    side: str
    px: float
    sz: float
    fee: Optional[float] = None
    ts: int  # epoch ms
    dir: Optional[str] = None
    tid: Optional[str] = None


class FillsResponse(BaseModel):
    position_id: str
    fills: list[FillItem]
    total: int
    limit: int
    offset: int


# ============================================================
# Closed Positions
# ============================================================

class ClosedPositionAnalysis(BaseModel):
    position_id: str
    base: str
    status: str = "CLOSED"
    opened_at: Optional[str] = None
    closed_at: Optional[str] = None
    duration_days: Optional[int] = None
    amount_usd: Optional[float] = None
    realized_spread_pnl: Optional[float] = None
    total_funding_earned: Optional[float] = None
    total_fees_paid: Optional[float] = None
    net_pnl: Optional[float] = None
    net_apr: Optional[float] = None
    entry_spread_bps: Optional[float] = None
    exit_spread_bps: Optional[float] = None


# ============================================================
# Cashflow (manual input)
# ============================================================

class ManualCashflowRequest(BaseModel):
    account_id: str
    venue: str
    cf_type: str = Field(..., pattern=r"^(DEPOSIT|WITHDRAW)$")
    amount: float = Field(..., gt=0)
    currency: str = "USDC"
    ts: Optional[int] = None  # epoch ms, defaults to now
    description: Optional[str] = None


class ManualCashflowResponse(BaseModel):
    cashflow_id: int
    message: str = "Cashflow recorded"


# ============================================================
# Health
# ============================================================

class HealthResponse(BaseModel):
    status: str
    db_size_mb: float
    last_fill_ingestion: Optional[str] = None
    last_price_pull: Optional[str] = None
    last_position_pull: Optional[str] = None
    felix_jwt_expires_at: Optional[str] = None
    open_positions: int
    uptime_seconds: float
```

- [ ] **Step 2: Verify models import cleanly**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from api.models.schemas import (
    PortfolioOverview, PositionSummary, PositionDetail,
    FillsResponse, ClosedPositionAnalysis,
    ManualCashflowRequest, ManualCashflowResponse, HealthResponse,
)
print('OK: all schema models import')
"
```

---

## Task 3: Dependency Injection (DB Connection)

**Files:**
- Create: `api/deps.py`

- [ ] **Step 1: Create deps module**

Create `api/deps.py`:

```python
"""Dependency injection for FastAPI.

Provides SQLite connections as async generator dependencies.
Read-only connections for GET endpoints, writable for POST.
"""

from __future__ import annotations

import sqlite3
from typing import Generator

from api.config import get_settings


def _connect(readonly: bool = True) -> sqlite3.Connection:
    """Open a SQLite connection.

    Args:
        readonly: If True, open with uri mode ?mode=ro for safety.
    """
    settings = get_settings()
    db_path = str(settings.db_path)

    if readonly:
        # SQLite URI mode for read-only access
        uri = f"file:{db_path}?mode=ro"
        con = sqlite3.connect(uri, uri=True)
    else:
        con = sqlite3.connect(db_path)

    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row  # dict-like access
    return con


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Read-only DB connection for GET endpoints."""
    con = _connect(readonly=True)
    try:
        yield con
    finally:
        con.close()


def get_db_writable() -> Generator[sqlite3.Connection, None, None]:
    """Writable DB connection for POST endpoints (cashflow insert)."""
    con = _connect(readonly=False)
    try:
        yield con
    finally:
        con.close()
```

- [ ] **Step 2: Verify deps work**

Run:
```bash
source .arbit_env && .venv/bin/python -c "
from api.deps import _connect
con = _connect(readonly=True)
row = con.execute('SELECT COUNT(*) FROM pm_positions').fetchone()
print(f'Positions in DB: {row[0]}')
con.close()
print('OK: DB dependency works')
"
```

Expected: Shows the count of positions in the database.

---

## Task 4: FastAPI App with Auth Middleware and CORS

**Files:**
- Create: `api/main.py`

- [ ] **Step 1: Create the main FastAPI app**

Create `api/main.py`:

```python
"""FastAPI application — entrypoint for the monitoring dashboard API.

Run: uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.config import get_settings

# Track server start time for uptime calculation
_start_time: float = 0.0


def get_uptime() -> float:
    """Return seconds since server start."""
    return time.time() - _start_time


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    global _start_time
    _start_time = time.time()

    settings = get_settings()
    if not settings.api_key:
        import warnings
        warnings.warn(
            "HARMONIX_API_KEY is not set. API will reject all requests. "
            "Set via vault or HARMONIX_API_KEY env var.",
            stacklevel=2,
        )

    yield  # app runs here

    # Shutdown: nothing to clean up (SQLite connections are per-request)


app = FastAPI(
    title="Harmonix Monitoring API",
    description="Delta-neutral funding arbitrage monitoring dashboard API",
    version="0.1.0",
    lifespan=lifespan,
)

# -------------------------------------------------------------------
# CORS
# -------------------------------------------------------------------
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-API-Key", "Content-Type"],
)


# -------------------------------------------------------------------
# Auth middleware — X-API-Key on all /api/* routes
# -------------------------------------------------------------------
@app.middleware("http")
async def api_key_auth(request: Request, call_next) -> Response:
    """Validate X-API-Key header on /api/* routes."""
    if request.url.path.startswith("/api/"):
        expected_key = get_settings().api_key
        if not expected_key:
            return JSONResponse(
                status_code=500,
                content={"detail": "API key not configured on server"},
            )

        provided_key = request.headers.get("X-API-Key", "")
        if provided_key != expected_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key"},
            )

    return await call_next(request)


# -------------------------------------------------------------------
# Register routers
# -------------------------------------------------------------------
from api.routers import portfolio, positions, cashflows, health  # noqa: E402

app.include_router(portfolio.router)
app.include_router(positions.router)
app.include_router(cashflows.router)
app.include_router(health.router)


# -------------------------------------------------------------------
# Root redirect
# -------------------------------------------------------------------
@app.get("/")
async def root():
    return {"message": "Harmonix Monitoring API", "docs": "/docs"}
```

- [ ] **Step 2: Defer verification until routers are implemented (Task 5–8)**

---

## Task 5: Portfolio Router

**Files:**
- Create: `api/routers/portfolio.py`

- [ ] **Step 1: Implement portfolio overview endpoint**

Create `api/routers/portfolio.py`:

```python
"""Portfolio overview endpoint.

GET /api/portfolio/overview — aggregate portfolio metrics.

Reads from pm_portfolio_snapshots (latest), pm_account_snapshots (latest per account),
pm_cashflows (funding/fees aggregation), and pm_positions (open count).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from api.deps import get_db
from api.models.schemas import AccountEquity, PortfolioOverview

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def _ts_to_iso(ts_ms: Optional[int]) -> str:
    """Convert epoch ms to ISO 8601 string."""
    if ts_ms is None:
        return datetime.now(timezone.utc).isoformat()
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


@router.get("/overview", response_model=PortfolioOverview)
def portfolio_overview(
    tracking_start: Optional[str] = Query(
        None, description="Override tracking start date (YYYY-MM-DD)"
    ),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return aggregate portfolio metrics.

    Reads the latest pm_portfolio_snapshots row for pre-computed metrics.
    Supplements with live account equity from pm_account_snapshots and
    position/cashflow counts from source tables.
    """
    # 1. Latest portfolio snapshot (pre-computed by Phase 1b cron)
    snap = db.execute(
        "SELECT * FROM pm_portfolio_snapshots ORDER BY ts DESC LIMIT 1"
    ).fetchone()

    # 2. Latest account snapshots (equity per wallet)
    account_rows = db.execute(
        """
        SELECT a.account_id, a.venue, a.total_balance
        FROM pm_account_snapshots a
        INNER JOIN (
            SELECT account_id, MAX(ts) AS max_ts
            FROM pm_account_snapshots
            GROUP BY account_id
        ) latest ON a.account_id = latest.account_id AND a.ts = latest.max_ts
        """
    ).fetchall()

    # 3. Open positions count
    open_count = db.execute(
        "SELECT COUNT(*) FROM pm_positions WHERE status IN ('OPEN', 'PAUSED')"
    ).fetchone()[0]

    # 4. Funding today (UTC day)
    today_start_sql = "strftime('%s', 'now', 'start of day') * 1000"
    funding_today = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0)
        FROM pm_cashflows
        WHERE cf_type = 'FUNDING' AND ts >= ({today_start_sql})
        """
    ).fetchone()[0]

    # 5. All-time funding and fees (with optional tracking_start override)
    tracking_filter = ""
    tracking_date = ""
    if tracking_start:
        tracking_date = tracking_start
        tracking_filter = f"AND ts >= (strftime('%s', '{tracking_start}') * 1000)"
    elif snap and snap["tracking_start_date"]:
        tracking_date = snap["tracking_start_date"]
        tracking_filter = (
            f"AND ts >= (strftime('%s', '{snap['tracking_start_date']}') * 1000)"
        )

    funding_alltime = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows
        WHERE cf_type = 'FUNDING' {tracking_filter}
        """
    ).fetchone()[0]

    fees_alltime = db.execute(
        f"""
        SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows
        WHERE cf_type = 'FEE' {tracking_filter}
        """
    ).fetchone()[0]

    # Build equity_by_account
    equity_by_account: dict[str, AccountEquity] = {}
    total_equity = 0.0
    for row in account_rows:
        label = _account_label(row["account_id"])
        eq = row["total_balance"] or 0.0
        equity_by_account[label] = AccountEquity(
            address=row["account_id"],
            equity_usd=round(eq, 2),
            venue=row["venue"],
        )
        total_equity += eq

    # Use snapshot values if available, else compute from components
    daily_change = snap["daily_change_usd"] if snap else 0.0
    apr = snap["apr_daily"] if snap else 0.0
    total_upnl = snap["total_unrealized_pnl"] if snap else 0.0
    snap_ts = snap["ts"] if snap else None

    # Override total_equity from snapshot if no live account data
    if not account_rows and snap:
        total_equity = snap["total_equity_usd"] or 0.0
        # Try to parse equity_by_account from snapshot
        if snap["equity_by_account_json"]:
            try:
                eq_json = json.loads(snap["equity_by_account_json"])
                for label, val in eq_json.items():
                    if isinstance(val, (int, float)):
                        equity_by_account[label] = AccountEquity(
                            address=label, equity_usd=round(val, 2), venue="hyperliquid"
                        )
            except (json.JSONDecodeError, TypeError):
                pass

    net_pnl = funding_alltime + fees_alltime
    daily_change_pct = (
        (daily_change / (total_equity - daily_change) * 100)
        if total_equity and total_equity != daily_change
        else 0.0
    )

    return PortfolioOverview(
        total_equity_usd=round(total_equity, 2),
        equity_by_account=equity_by_account,
        daily_change_usd=round(daily_change, 2),
        daily_change_pct=round(daily_change_pct, 2),
        cashflow_adjusted_apr=round(apr, 2) if apr else 0.0,
        funding_today_usd=round(funding_today, 2),
        funding_alltime_usd=round(funding_alltime, 2),
        fees_alltime_usd=round(fees_alltime, 2),
        net_pnl_alltime_usd=round(net_pnl, 2),
        tracking_start_date=tracking_date,
        open_positions_count=open_count,
        total_unrealized_pnl=round(total_upnl, 2) if total_upnl else 0.0,
        as_of=_ts_to_iso(snap_ts),
    )


def _account_label(account_id: str) -> str:
    """Derive a human-friendly label from account_id.

    Checks HYPERLIQUID_ACCOUNTS_JSON env var for label mapping.
    Falls back to truncated address.
    """
    import os

    accounts_json = os.environ.get("HYPERLIQUID_ACCOUNTS_JSON", "")
    if accounts_json:
        try:
            accounts = json.loads(accounts_json)
            for acct in accounts:
                if acct.get("address", "").lower() == account_id.lower():
                    return acct.get("label", account_id[:10])
        except (json.JSONDecodeError, TypeError):
            pass
    return account_id[:10]
```

---

## Task 6: Positions Router

**Files:**
- Create: `api/routers/positions.py`

- [ ] **Step 1: Implement all position endpoints**

Create `api/routers/positions.py`:

```python
"""Position endpoints.

GET /api/positions           — list positions with computed metrics
GET /api/positions/closed    — closed position P&L analysis
GET /api/positions/{id}      — single position detail
GET /api/positions/{id}/fills — trade fills for a position
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from api.deps import get_db
from api.models.schemas import (
    ClosedPositionAnalysis,
    CashflowItem,
    DailyFundingItem,
    FillItem,
    FillsResponse,
    FillsSummaryItem,
    LegDetail,
    PositionDetail,
    PositionSummary,
    SubPairSpread,
)

router = APIRouter(prefix="/api/positions", tags=["positions"])


def _ts_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _build_position_summary(
    pos: sqlite3.Row, db: sqlite3.Connection
) -> PositionSummary:
    """Build a PositionSummary from a pm_positions row + joined data."""
    position_id = pos["position_id"]

    # Parse meta_json for base and strategy
    meta = {}
    if pos["meta_json"]:
        try:
            meta = json.loads(pos["meta_json"])
        except (json.JSONDecodeError, TypeError):
            pass

    base = meta.get("base", position_id)
    strategy = meta.get("strategy_type", pos["strategy"] if "strategy" in pos.keys() else "SPOT_PERP")
    amount_usd = meta.get("amount_usd")

    # Legs
    leg_rows = db.execute(
        """
        SELECT l.*, ep.avg_entry_price
        FROM pm_legs l
        LEFT JOIN pm_entry_prices ep ON ep.leg_id = l.leg_id
        WHERE l.position_id = ?
        """,
        (position_id,),
    ).fetchall()

    legs = []
    total_upnl = 0.0
    for lr in leg_rows:
        upnl = lr["unrealized_pnl"] or 0.0
        total_upnl += upnl
        legs.append(
            LegDetail(
                leg_id=lr["leg_id"],
                venue=lr["venue"],
                inst_id=lr["inst_id"],
                side=lr["side"],
                size=lr["size"],
                avg_entry_price=lr["avg_entry_price"],
                current_price=lr["current_price"],
                unrealized_pnl=round(upnl, 4) if upnl else None,
                account_id=lr["account_id"],
            )
        )

    # Sub-pair spreads
    spread_rows = db.execute(
        "SELECT * FROM pm_spreads WHERE position_id = ?", (position_id,)
    ).fetchall()

    sub_pairs = []
    for sr in spread_rows:
        sub_pairs.append(
            SubPairSpread(
                spot_leg_id=sr["long_leg_id"],
                perp_leg_id=sr["short_leg_id"],
                entry_spread_bps=(
                    round(sr["entry_spread"] * 10000, 1) if sr["entry_spread"] is not None else None
                ),
                exit_spread_bps=(
                    round(sr["exit_spread"] * 10000, 1) if sr["exit_spread"] is not None else None
                ),
                spread_pnl_bps=(
                    round(sr["spread_pnl_bps"], 1) if sr["spread_pnl_bps"] is not None else None
                ),
            )
        )

    # Funding and fees for this position
    funding = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
        (position_id,),
    ).fetchone()[0]

    fees = db.execute(
        "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FEE'",
        (position_id,),
    ).fetchone()[0]

    net_carry = funding + fees
    upnl_pct = (total_upnl / amount_usd * 100) if amount_usd and amount_usd > 0 else None

    # Carry APR: annualized from position open date
    carry_apr = None
    if amount_usd and amount_usd > 0 and pos["created_at_ms"]:
        days_open = (
            datetime.now(timezone.utc).timestamp() * 1000 - pos["created_at_ms"]
        ) / (86400 * 1000)
        if days_open > 0:
            carry_apr = round((net_carry / amount_usd) / days_open * 365 * 100, 2)

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
    )


# -------------------------------------------------------------------
# IMPORTANT: /closed must be defined BEFORE /{position_id}
# so FastAPI matches it literally, not as a path parameter.
# -------------------------------------------------------------------

@router.get("/closed", response_model=list[ClosedPositionAnalysis])
def list_closed_positions(
    db: sqlite3.Connection = Depends(get_db),
):
    """Return closed position P&L analysis."""
    rows = db.execute(
        "SELECT * FROM pm_positions WHERE status = 'CLOSED' ORDER BY closed_at_ms DESC"
    ).fetchall()

    results = []
    for pos in rows:
        position_id = pos["position_id"]
        meta = {}
        if pos["meta_json"]:
            try:
                meta = json.loads(pos["meta_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        base = meta.get("base", position_id)
        amount_usd = meta.get("amount_usd")

        # Funding and fees
        funding = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FUNDING'",
            (position_id,),
        ).fetchone()[0]

        fees = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM pm_cashflows WHERE position_id = ? AND cf_type = 'FEE'",
            (position_id,),
        ).fetchone()[0]

        # Realized spread PnL from closed fills
        realized_spread = db.execute(
            "SELECT COALESCE(SUM(closed_pnl), 0) FROM pm_fills WHERE position_id = ?",
            (position_id,),
        ).fetchone()[0]

        net_pnl = realized_spread + funding + fees

        # Duration
        duration_days = None
        if pos["created_at_ms"] and pos["closed_at_ms"]:
            duration_days = int(
                (pos["closed_at_ms"] - pos["created_at_ms"]) / (86400 * 1000)
            )

        # APR
        net_apr = None
        if amount_usd and amount_usd > 0 and duration_days and duration_days > 0:
            net_apr = round((net_pnl / amount_usd) / duration_days * 365 * 100, 2)

        # Entry/exit spreads (avg across sub-pairs)
        spread_row = db.execute(
            """
            SELECT AVG(entry_spread), AVG(exit_spread)
            FROM pm_spreads WHERE position_id = ?
            """,
            (position_id,),
        ).fetchone()

        entry_spread_bps = (
            round(spread_row[0] * 10000, 1) if spread_row and spread_row[0] is not None else None
        )
        exit_spread_bps = (
            round(spread_row[1] * 10000, 1) if spread_row and spread_row[1] is not None else None
        )

        results.append(
            ClosedPositionAnalysis(
                position_id=position_id,
                base=base,
                opened_at=_ts_to_iso(pos["created_at_ms"]),
                closed_at=_ts_to_iso(pos["closed_at_ms"]),
                duration_days=duration_days,
                amount_usd=round(amount_usd, 2) if amount_usd else None,
                realized_spread_pnl=round(realized_spread, 2),
                total_funding_earned=round(funding, 2),
                total_fees_paid=round(fees, 2),
                net_pnl=round(net_pnl, 2),
                net_apr=net_apr,
                entry_spread_bps=entry_spread_bps,
                exit_spread_bps=exit_spread_bps,
            )
        )

    return results


@router.get("", response_model=list[PositionSummary])
def list_positions(
    status: str = Query("OPEN", description="Filter: OPEN, CLOSED, PAUSED, ALL"),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return all positions with computed metrics."""
    if status.upper() == "ALL":
        rows = db.execute(
            "SELECT * FROM pm_positions ORDER BY created_at_ms DESC"
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT * FROM pm_positions WHERE status = ? ORDER BY created_at_ms DESC",
            (status.upper(),),
        ).fetchall()

    return [_build_position_summary(row, db) for row in rows]


@router.get("/{position_id}", response_model=PositionDetail)
def get_position(
    position_id: str,
    db: sqlite3.Connection = Depends(get_db),
):
    """Return detailed position with legs, spreads, cashflows, fills summary."""
    pos = db.execute(
        "SELECT * FROM pm_positions WHERE position_id = ?", (position_id,)
    ).fetchone()

    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    # Build base summary
    summary = _build_position_summary(pos, db)

    # Fills summary per leg
    fills_summary_rows = db.execute(
        """
        SELECT leg_id, COUNT(*) AS fill_count,
               MIN(ts) AS first_fill_ts, MAX(ts) AS last_fill_ts
        FROM pm_fills
        WHERE position_id = ? AND leg_id IS NOT NULL
        GROUP BY leg_id
        """,
        (position_id,),
    ).fetchall()

    fills_summary = [
        FillsSummaryItem(
            leg_id=r["leg_id"],
            fill_count=r["fill_count"],
            first_fill=_ts_to_iso(r["first_fill_ts"]),
            last_fill=_ts_to_iso(r["last_fill_ts"]),
        )
        for r in fills_summary_rows
    ]

    # Cashflows for this position
    cf_rows = db.execute(
        """
        SELECT cashflow_id, cf_type, amount, currency, ts, description
        FROM pm_cashflows
        WHERE position_id = ?
        ORDER BY ts DESC
        """,
        (position_id,),
    ).fetchall()

    cashflows = [
        CashflowItem(
            cashflow_id=r["cashflow_id"],
            cf_type=r["cf_type"],
            amount=round(r["amount"], 4),
            currency=r["currency"],
            ts=_ts_to_iso(r["ts"]),
            description=r["description"],
        )
        for r in cf_rows
    ]

    # Daily funding series (last 7 days)
    daily_funding_rows = db.execute(
        """
        SELECT DATE(ts / 1000, 'unixepoch') AS day, SUM(amount) AS daily_amount
        FROM pm_cashflows
        WHERE position_id = ? AND cf_type = 'FUNDING'
          AND ts >= (strftime('%s', 'now', '-7 days') * 1000)
        GROUP BY day
        ORDER BY day
        """,
        (position_id,),
    ).fetchall()

    daily_funding = [
        DailyFundingItem(date=r["day"], amount=round(r["daily_amount"], 4))
        for r in daily_funding_rows
    ]

    return PositionDetail(
        **summary.model_dump(),
        fills_summary=fills_summary,
        cashflows=cashflows,
        daily_funding_series=daily_funding,
    )


@router.get("/{position_id}/fills", response_model=FillsResponse)
def get_position_fills(
    position_id: str,
    leg_id: Optional[str] = Query(None, description="Filter by leg_id"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: sqlite3.Connection = Depends(get_db),
):
    """Return paginated trade fills for a position."""
    # Verify position exists
    pos = db.execute(
        "SELECT position_id FROM pm_positions WHERE position_id = ?", (position_id,)
    ).fetchone()
    if not pos:
        raise HTTPException(status_code=404, detail=f"Position {position_id} not found")

    # Build query
    where = "WHERE position_id = ?"
    params: list = [position_id]

    if leg_id:
        where += " AND leg_id = ?"
        params.append(leg_id)

    # Total count
    total = db.execute(
        f"SELECT COUNT(*) FROM pm_fills {where}", params
    ).fetchone()[0]

    # Paginated results
    rows = db.execute(
        f"""
        SELECT fill_id, leg_id, inst_id, side, px, sz, fee, ts, dir, tid
        FROM pm_fills {where}
        ORDER BY ts DESC
        LIMIT ? OFFSET ?
        """,
        params + [limit, offset],
    ).fetchall()

    fills = [
        FillItem(
            fill_id=r["fill_id"],
            leg_id=r["leg_id"],
            inst_id=r["inst_id"],
            side=r["side"],
            px=r["px"],
            sz=r["sz"],
            fee=r["fee"],
            ts=r["ts"],
            dir=r["dir"],
            tid=r["tid"],
        )
        for r in rows
    ]

    return FillsResponse(
        position_id=position_id,
        fills=fills,
        total=total,
        limit=limit,
        offset=offset,
    )
```

---

## Task 7: Cashflows Router

**Files:**
- Create: `api/routers/cashflows.py`

- [ ] **Step 1: Implement manual cashflow endpoint**

Create `api/routers/cashflows.py`:

```python
"""Manual cashflow endpoint.

POST /api/cashflows/manual — record deposit/withdraw events.
Per ADR-010: manual entry via REST API for accurate cashflow-adjusted APR.
"""

from __future__ import annotations

import json
import sqlite3
import time

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from api.deps import get_db_writable
from api.models.schemas import ManualCashflowRequest, ManualCashflowResponse

router = APIRouter(prefix="/api/cashflows", tags=["cashflows"])


@router.post("/manual", response_model=ManualCashflowResponse, status_code=201)
def record_manual_cashflow(
    body: ManualCashflowRequest,
    db: sqlite3.Connection = Depends(get_db_writable),
):
    """Record a manual deposit or withdrawal.

    Writes to pm_cashflows with meta_json {"source": "manual"}.
    Amount sign is determined by cf_type: DEPOSIT = positive, WITHDRAW = negative.
    """
    ts = body.ts or int(time.time() * 1000)

    # Sign convention: DEPOSIT = +amount, WITHDRAW = -amount
    signed_amount = body.amount if body.cf_type == "DEPOSIT" else -body.amount

    meta = json.dumps({"source": "manual"})

    cursor = db.execute(
        """
        INSERT INTO pm_cashflows (
            position_id, leg_id, venue, account_id,
            ts, cf_type, amount, currency, description, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            None,           # no position_id for deposits/withdrawals
            None,           # no leg_id
            body.venue,
            body.account_id,
            ts,
            body.cf_type,
            signed_amount,
            body.currency,
            body.description,
            meta,
        ),
    )
    db.commit()

    return ManualCashflowResponse(
        cashflow_id=cursor.lastrowid,
        message=f"{body.cf_type} of {body.amount} {body.currency} recorded",
    )
```

---

## Task 8: Health Router

**Files:**
- Create: `api/routers/health.py`

- [ ] **Step 1: Implement health endpoint**

Create `api/routers/health.py`:

```python
"""Health check endpoint.

GET /api/health — system status for monitoring.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends

from api.config import get_settings
from api.deps import get_db
from api.main import get_uptime
from api.models.schemas import HealthResponse

router = APIRouter(prefix="/api", tags=["health"])


def _ts_to_iso(ts_ms: Optional[int]) -> Optional[str]:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()


def _latest_ts(db: sqlite3.Connection, table: str, ts_col: str = "ts") -> Optional[int]:
    """Get the latest timestamp from a table."""
    try:
        row = db.execute(f"SELECT MAX({ts_col}) FROM {table}").fetchone()
        return row[0] if row and row[0] else None
    except sqlite3.OperationalError:
        return None


@router.get("/health", response_model=HealthResponse)
def health_check(
    db: sqlite3.Connection = Depends(get_db),
):
    """Return system health status."""
    settings = get_settings()

    # DB file size
    db_size_mb = 0.0
    if settings.db_path.exists():
        db_size_mb = round(settings.db_path.stat().st_size / (1024 * 1024), 1)

    # Latest timestamps from key tables
    last_fill = _latest_ts(db, "pm_fills")
    last_position = _latest_ts(db, "pm_leg_snapshots")
    last_portfolio = _latest_ts(db, "pm_portfolio_snapshots")

    # Felix JWT expiry (from vault or env)
    felix_jwt_expires = None
    try:
        from vault.vault import get_secret

        jwt_expiry_str = get_secret("felix_jwt_expires_at")
        if jwt_expiry_str:
            felix_jwt_expires = jwt_expiry_str
    except Exception:
        pass

    # Open positions
    open_count = db.execute(
        "SELECT COUNT(*) FROM pm_positions WHERE status IN ('OPEN', 'PAUSED')"
    ).fetchone()[0]

    return HealthResponse(
        status="ok",
        db_size_mb=db_size_mb,
        last_fill_ingestion=_ts_to_iso(last_fill),
        last_price_pull=_ts_to_iso(last_portfolio),  # portfolio snapshot includes price data
        last_position_pull=_ts_to_iso(last_position),
        felix_jwt_expires_at=felix_jwt_expires,
        open_positions=open_count,
        uptime_seconds=round(get_uptime(), 1),
    )
```

---

## Task 9: Integration Tests

**Files:**
- Create: `tests/test_api.py`

- [ ] **Step 1: Write comprehensive tests using FastAPI TestClient**

Create `tests/test_api.py`:

```python
#!/usr/bin/env python3
"""Integration tests for the Harmonix API.

Uses FastAPI TestClient to exercise all endpoints without a real server.
Requires a populated arbit_v3.db with the monitoring schema applied.

Run: source .arbit_env && .venv/bin/python -m pytest tests/test_api.py -v
  or: source .arbit_env && .venv/bin/python tests/test_api.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

# Ensure repo root is on sys.path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

# Set a test API key before importing the app
TEST_API_KEY = "test-key-12345"
os.environ["HARMONIX_API_KEY"] = TEST_API_KEY
# Override DB path for tests if needed
# os.environ["HARMONIX_DB_PATH"] = str(ROOT / "tracking" / "db" / "arbit_v3.db")

from fastapi.testclient import TestClient


def _headers() -> dict:
    return {"X-API-Key": TEST_API_KEY}


def _setup_test_db() -> Path:
    """Create a temporary SQLite DB with schema and test data."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = Path(tmp.name)
    tmp.close()

    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA foreign_keys = ON")

    # Apply pm_v3 schema
    schema_v3 = ROOT / "tracking" / "sql" / "schema_pm_v3.sql"
    if schema_v3.exists():
        con.executescript(schema_v3.read_text())

    # Apply monitoring schema
    schema_mon = ROOT / "tracking" / "sql" / "schema_monitoring_v1.sql"
    if schema_mon.exists():
        con.executescript(schema_mon.read_text())

    now_ms = int(time.time() * 1000)
    day_ago_ms = now_ms - 86400 * 1000

    # Insert test position
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pos_test_BTC",
            "hyperliquid",
            "SPOT_PERP",
            "OPEN",
            day_ago_ms,
            now_ms,
            json.dumps({"base": "BTC", "strategy_type": "SPOT_PERP", "amount_usd": 10000.0}),
        ),
    )

    # Insert test legs
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, entry_price, current_price,
                             unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_SPOT", "pos_test_BTC", "hyperliquid", "BTC/USDC", "LONG", 0.1,
         60000.0, 60500.0, 50.0, "OPEN", day_ago_ms, "0xtest123"),
    )
    con.execute(
        """
        INSERT INTO pm_legs (leg_id, position_id, venue, inst_id, side, size, entry_price, current_price,
                             unrealized_pnl, status, opened_at_ms, account_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_PERP", "pos_test_BTC", "hyperliquid", "BTC", "SHORT", 0.1,
         60050.0, 60500.0, -45.0, "OPEN", day_ago_ms, "0xtest123"),
    )

    # Insert test entry prices
    con.execute(
        """
        INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
                                     fill_count, first_fill_ts, last_fill_ts, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_SPOT", "pos_test_BTC", 60000.0, 0.1, 6000.0, 1, day_ago_ms, day_ago_ms, now_ms),
    )
    con.execute(
        """
        INSERT INTO pm_entry_prices (leg_id, position_id, avg_entry_price, total_filled_qty, total_cost,
                                     fill_count, first_fill_ts, last_fill_ts, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC_PERP", "pos_test_BTC", 60050.0, 0.1, 6005.0, 1, day_ago_ms, day_ago_ms, now_ms),
    )

    # Insert test spread
    con.execute(
        """
        INSERT INTO pm_spreads (position_id, long_leg_id, short_leg_id,
                                entry_spread, long_avg_entry, short_avg_entry,
                                exit_spread, long_exit_price, short_exit_price,
                                spread_pnl_bps, computed_at_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_SPOT", "pos_test_BTC_PERP",
         -0.0008, 60000.0, 60050.0,   # entry spread
         0.0005, 60500.0, 60470.0,     # exit spread
         13.0, now_ms),
    )

    # Insert test fills
    con.execute(
        """
        INSERT INTO pm_fills (venue, account_id, tid, inst_id, side, px, sz, fee, ts,
                              position_id, leg_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", "tid_001", "BTC/USDC", "BUY", 60000.0, 0.1,
         1.5, day_ago_ms, "pos_test_BTC", "pos_test_BTC_SPOT"),
    )
    con.execute(
        """
        INSERT INTO pm_fills (venue, account_id, tid, inst_id, side, px, sz, fee, ts,
                              position_id, leg_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", "tid_002", "BTC", "SELL", 60050.0, 0.1,
         1.2, day_ago_ms, "pos_test_BTC", "pos_test_BTC_PERP"),
    )

    # Insert test cashflows (funding + fee)
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_PERP", "hyperliquid", "0xtest123",
         now_ms - 3600000, "FUNDING", 5.25, "USDC"),
    )
    con.execute(
        """
        INSERT INTO pm_cashflows (position_id, leg_id, venue, account_id, ts, cf_type, amount, currency)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("pos_test_BTC", "pos_test_BTC_SPOT", "hyperliquid", "0xtest123",
         day_ago_ms, "FEE", -1.5, "USDC"),
    )

    # Insert account snapshot
    con.execute(
        """
        INSERT INTO pm_account_snapshots (venue, account_id, ts, total_balance)
        VALUES (?, ?, ?, ?)
        """,
        ("hyperliquid", "0xtest123", now_ms, 25000.50),
    )

    # Insert portfolio snapshot
    con.execute(
        """
        INSERT INTO pm_portfolio_snapshots (ts, total_equity_usd, equity_by_account_json,
                                            total_unrealized_pnl, total_funding_today,
                                            total_funding_alltime, total_fees_alltime,
                                            daily_change_usd, cashflow_adjusted_change,
                                            apr_daily, tracking_start_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (now_ms, 25000.50, json.dumps({"main": 25000.50}),
         5.0, 5.25, 120.50, -35.0,
         42.30, 42.30, 18.5, "2026-01-15"),
    )

    # Insert a closed position for /closed endpoint
    con.execute(
        """
        INSERT INTO pm_positions (position_id, venue, strategy, status, created_at_ms, updated_at_ms, closed_at_ms, meta_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pos_test_ETH",
            "hyperliquid",
            "SPOT_PERP",
            "CLOSED",
            day_ago_ms - 86400 * 7 * 1000,  # opened 8 days ago
            now_ms,
            now_ms,
            json.dumps({"base": "ETH", "strategy_type": "SPOT_PERP", "amount_usd": 5000.0}),
        ),
    )

    con.commit()
    con.close()
    return db_path


def _get_test_client(db_path: Path) -> TestClient:
    """Create a TestClient with the test DB."""
    os.environ["HARMONIX_DB_PATH"] = str(db_path)

    # Clear cached settings so it picks up the new DB path
    from api.config import get_settings
    get_settings.cache_clear()

    from api.main import app
    return TestClient(app)


# ===================================================================
# Tests
# ===================================================================

def test_auth_required():
    """Request without X-API-Key returns 401."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/health")
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    response = client.get("/api/health", headers={"X-API-Key": "wrong-key"})
    assert response.status_code == 401

    # With correct key
    response = client.get("/api/health", headers=_headers())
    assert response.status_code == 200

    os.unlink(db_path)
    print("PASS: test_auth_required")


def test_health():
    """GET /api/health returns expected shape."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/health", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "ok"
    assert data["db_size_mb"] >= 0
    assert data["open_positions"] >= 1
    assert data["uptime_seconds"] >= 0

    os.unlink(db_path)
    print("PASS: test_health")


def test_portfolio_overview():
    """GET /api/portfolio/overview returns aggregate metrics."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/portfolio/overview", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert "total_equity_usd" in data
    assert "equity_by_account" in data
    assert "daily_change_usd" in data
    assert "cashflow_adjusted_apr" in data
    assert "funding_today_usd" in data
    assert "funding_alltime_usd" in data
    assert "fees_alltime_usd" in data
    assert "open_positions_count" in data
    assert data["open_positions_count"] >= 1

    os.unlink(db_path)
    print("PASS: test_portfolio_overview")


def test_portfolio_overview_with_tracking_start():
    """GET /api/portfolio/overview?tracking_start=... overrides date."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/portfolio/overview?tracking_start=2026-03-01",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tracking_start_date"] == "2026-03-01"

    os.unlink(db_path)
    print("PASS: test_portfolio_overview_with_tracking_start")


def test_list_positions():
    """GET /api/positions returns open positions."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1

    pos = data[0]
    assert "position_id" in pos
    assert "base" in pos
    assert "legs" in pos
    assert "sub_pairs" in pos
    assert pos["status"] == "OPEN"

    os.unlink(db_path)
    print("PASS: test_list_positions")


def test_list_positions_all():
    """GET /api/positions?status=ALL returns all positions."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions?status=ALL", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2  # OPEN + CLOSED

    os.unlink(db_path)
    print("PASS: test_list_positions_all")


def test_position_detail():
    """GET /api/positions/{id} returns full detail."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/pos_test_BTC", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["position_id"] == "pos_test_BTC"
    assert "fills_summary" in data
    assert "cashflows" in data
    assert "daily_funding_series" in data
    assert len(data["legs"]) == 2

    os.unlink(db_path)
    print("PASS: test_position_detail")


def test_position_not_found():
    """GET /api/positions/{id} returns 404 for nonexistent."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/nonexistent", headers=_headers())
    assert response.status_code == 404

    os.unlink(db_path)
    print("PASS: test_position_not_found")


def test_position_fills():
    """GET /api/positions/{id}/fills returns paginated fills."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/pos_test_BTC/fills", headers=_headers())
    assert response.status_code == 200
    data = response.json()

    assert data["position_id"] == "pos_test_BTC"
    assert data["total"] == 2
    assert len(data["fills"]) == 2
    assert data["limit"] == 100
    assert data["offset"] == 0

    os.unlink(db_path)
    print("PASS: test_position_fills")


def test_position_fills_with_leg_filter():
    """GET /api/positions/{id}/fills?leg_id=... filters by leg."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/positions/pos_test_BTC/fills?leg_id=pos_test_BTC_SPOT",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["fills"][0]["leg_id"] == "pos_test_BTC_SPOT"

    os.unlink(db_path)
    print("PASS: test_position_fills_with_leg_filter")


def test_position_fills_pagination():
    """GET /api/positions/{id}/fills supports limit/offset."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get(
        "/api/positions/pos_test_BTC/fills?limit=1&offset=0",
        headers=_headers(),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["fills"]) == 1

    response2 = client.get(
        "/api/positions/pos_test_BTC/fills?limit=1&offset=1",
        headers=_headers(),
    )
    data2 = response2.json()
    assert len(data2["fills"]) == 1
    assert data2["fills"][0]["fill_id"] != data["fills"][0]["fill_id"]

    os.unlink(db_path)
    print("PASS: test_position_fills_pagination")


def test_closed_positions():
    """GET /api/positions/closed returns closed P&L analysis."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/api/positions/closed", headers=_headers())
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert data[0]["status"] == "CLOSED"
    assert "net_pnl" in data[0]
    assert "duration_days" in data[0]

    os.unlink(db_path)
    print("PASS: test_closed_positions")


def test_manual_cashflow_deposit():
    """POST /api/cashflows/manual creates a deposit record."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    body = {
        "account_id": "0xtest123",
        "venue": "hyperliquid",
        "cf_type": "DEPOSIT",
        "amount": 5000.0,
        "currency": "USDC",
        "description": "Test deposit",
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    data = response.json()
    assert "cashflow_id" in data
    assert data["cashflow_id"] > 0

    # Verify it was stored with positive amount
    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT amount, cf_type, meta_json FROM pm_cashflows WHERE cashflow_id = ?",
        (data["cashflow_id"],),
    ).fetchone()
    assert row is not None
    assert row[0] == 5000.0  # positive for DEPOSIT
    assert row[1] == "DEPOSIT"
    meta = json.loads(row[2])
    assert meta["source"] == "manual"
    con.close()

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_deposit")


def test_manual_cashflow_withdraw():
    """POST /api/cashflows/manual with WITHDRAW stores negative amount."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    body = {
        "account_id": "0xtest123",
        "venue": "hyperliquid",
        "cf_type": "WITHDRAW",
        "amount": 2000.0,
        "currency": "USDC",
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 201
    data = response.json()

    # Verify negative amount
    con = sqlite3.connect(str(db_path))
    row = con.execute(
        "SELECT amount FROM pm_cashflows WHERE cashflow_id = ?",
        (data["cashflow_id"],),
    ).fetchone()
    assert row[0] == -2000.0  # negative for WITHDRAW
    con.close()

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_withdraw")


def test_manual_cashflow_validation():
    """POST /api/cashflows/manual rejects invalid input."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    # Invalid cf_type
    body = {
        "account_id": "0xtest",
        "venue": "hyperliquid",
        "cf_type": "TRANSFER",
        "amount": 100.0,
    }
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    # Zero amount
    body["cf_type"] = "DEPOSIT"
    body["amount"] = 0
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    # Negative amount
    body["amount"] = -100
    response = client.post("/api/cashflows/manual", json=body, headers=_headers())
    assert response.status_code == 422

    os.unlink(db_path)
    print("PASS: test_manual_cashflow_validation")


def test_root_endpoint():
    """GET / returns welcome message (no auth needed)."""
    db_path = _setup_test_db()
    client = _get_test_client(db_path)

    response = client.get("/")
    assert response.status_code == 200
    assert "Harmonix" in response.json()["message"]

    os.unlink(db_path)
    print("PASS: test_root_endpoint")


# ===================================================================
# Runner
# ===================================================================

if __name__ == "__main__":
    tests = [
        test_auth_required,
        test_health,
        test_portfolio_overview,
        test_portfolio_overview_with_tracking_start,
        test_list_positions,
        test_list_positions_all,
        test_position_detail,
        test_position_not_found,
        test_position_fills,
        test_position_fills_with_leg_filter,
        test_position_fills_pagination,
        test_closed_positions,
        test_manual_cashflow_deposit,
        test_manual_cashflow_withdraw,
        test_manual_cashflow_validation,
        test_root_endpoint,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"FAIL: {test_fn.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed:
        sys.exit(1)
    print("All API tests passed!")
```

- [ ] **Step 2: Run tests**

Run:
```bash
source .arbit_env && .venv/bin/python tests/test_api.py
```

Expected:
```
PASS: test_auth_required
PASS: test_health
PASS: test_portfolio_overview
PASS: test_portfolio_overview_with_tracking_start
PASS: test_list_positions
PASS: test_list_positions_all
PASS: test_position_detail
PASS: test_position_not_found
PASS: test_position_fills
PASS: test_position_fills_with_leg_filter
PASS: test_position_fills_pagination
PASS: test_closed_positions
PASS: test_manual_cashflow_deposit
PASS: test_manual_cashflow_withdraw
PASS: test_manual_cashflow_validation
PASS: test_root_endpoint

========================================
Results: 16 passed, 0 failed, 16 total
All API tests passed!
```

- [ ] **Step 3: Fix any test failures and re-run**

---

## Task 10: Smoke Test Against Live DB

- [ ] **Step 1: Start the server locally**

Run:
```bash
source .arbit_env && .venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 &
sleep 2
```

- [ ] **Step 2: Test auth rejection**

Run:
```bash
curl -s http://127.0.0.1:8000/api/health | python3 -m json.tool
```

Expected: `{"detail": "Invalid or missing API key"}` with status 401.

- [ ] **Step 3: Test health endpoint**

Run:
```bash
curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://127.0.0.1:8000/api/health | python3 -m json.tool
```

Expected: JSON with `status: "ok"`, `db_size_mb`, `open_positions`.

- [ ] **Step 4: Test portfolio overview**

Run:
```bash
curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://127.0.0.1:8000/api/portfolio/overview | python3 -m json.tool
```

Expected: JSON with `total_equity_usd`, `equity_by_account`, etc.

- [ ] **Step 5: Test positions list**

Run:
```bash
curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://127.0.0.1:8000/api/positions | python3 -m json.tool
```

Expected: JSON array of positions with legs, sub_pairs, funding/fee data.

- [ ] **Step 6: Test single position detail**

Run (replace with a real position_id from step 5):
```bash
POSITION_ID=$(curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://127.0.0.1:8000/api/positions | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['position_id'])")
curl -s -H "X-API-Key: $HARMONIX_API_KEY" "http://127.0.0.1:8000/api/positions/${POSITION_ID}" | python3 -m json.tool
```

Expected: Extended position detail with `fills_summary`, `cashflows`, `daily_funding_series`.

- [ ] **Step 7: Test fills endpoint**

Run:
```bash
curl -s -H "X-API-Key: $HARMONIX_API_KEY" "http://127.0.0.1:8000/api/positions/${POSITION_ID}/fills?limit=5" | python3 -m json.tool
```

Expected: Paginated fills with `total`, `limit`, `offset`, `fills` array.

- [ ] **Step 8: Test closed positions**

Run:
```bash
curl -s -H "X-API-Key: $HARMONIX_API_KEY" http://127.0.0.1:8000/api/positions/closed | python3 -m json.tool
```

Expected: Array of closed positions with P&L breakdown.

- [ ] **Step 9: Test manual cashflow POST**

Run:
```bash
curl -s -X POST \
  -H "X-API-Key: $HARMONIX_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"account_id": "0xtest", "venue": "hyperliquid", "cf_type": "DEPOSIT", "amount": 100, "currency": "USDC", "description": "smoke test - delete me"}' \
  http://127.0.0.1:8000/api/cashflows/manual | python3 -m json.tool
```

Expected: `201` with `cashflow_id`. Then clean up the test record manually.

- [ ] **Step 10: Stop the server**

Run:
```bash
kill %1 2>/dev/null || true
```

- [ ] **Step 11: Commit**

```bash
git add api/ tests/test_api.py requirements.txt
git commit -m "feat: FastAPI REST API for monitoring dashboard (Phase 1c)

Endpoints: portfolio overview, positions (list/detail/fills/closed),
manual cashflow entry, health check. X-API-Key auth, CORS, SQLite
read-only connections for GET, writable for POST."
```

---

## Summary

| Task | Files | What it does |
|------|-------|-------------|
| 1 | requirements.txt, api/__init__.py, api/config.py | Dependencies + project scaffold + settings |
| 2 | api/models/schemas.py | All Pydantic request/response models |
| 3 | api/deps.py | SQLite connection dependency injection |
| 4 | api/main.py | FastAPI app, CORS, auth middleware, router registration |
| 5 | api/routers/portfolio.py | GET /api/portfolio/overview |
| 6 | api/routers/positions.py | GET /api/positions, /{id}, /{id}/fills, /closed |
| 7 | api/routers/cashflows.py | POST /api/cashflows/manual |
| 8 | api/routers/health.py | GET /api/health |
| 9 | tests/test_api.py | 16 integration tests with temp DB |
| 10 | (verification) | Live smoke test with curl |

**Execution order:** Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 (sequential — each builds on the previous).

**Key design decisions in this implementation:**
- `sqlite3.Row` row_factory for dict-like column access in all queries
- Read-only SQLite URI mode (`?mode=ro`) for GET endpoints prevents accidental writes
- `/api/positions/closed` route defined before `/{position_id}` to avoid path parameter collision
- Auth middleware applies to all `/api/*` routes; root `/` is unauthenticated
- Test DB is a temporary file with full schema + seed data, cleaned up after each test
- `_account_label()` resolves wallet addresses to human labels via `HYPERLIQUID_ACCOUNTS_JSON`
- Cashflow sign convention: amount is always positive in the request body; server applies sign based on `cf_type`
