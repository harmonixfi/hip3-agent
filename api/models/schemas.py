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
    daily_change_usd: Optional[float]
    daily_change_pct: Optional[float]
    cashflow_adjusted_apr: Optional[float]
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
    long_leg_id: str
    short_leg_id: str
    entry_spread_bps: Optional[float] = None
    exit_spread_bps: Optional[float] = None
    spread_pnl_bps: Optional[float] = None


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


class PositionSummary(BaseModel):
    position_id: str
    base: str
    strategy: str
    status: str
    amount_usd: Optional[float] = Field(
        None,
        description=(
            "Open positions: sum of abs(size * price) per leg (current_price, else VWAP, else entry). "
            "CLOSED: registry meta amount_usd."
        ),
    )
    unrealized_pnl: Optional[float] = None
    unrealized_pnl_pct: Optional[float] = None
    funding_earned: Optional[float] = None
    fees_paid: Optional[float] = None
    net_carry: Optional[float] = None
    carry_apr: Optional[float] = None
    sub_pairs: list[SubPairSpread] = []
    legs: list[LegDetail] = []
    opened_at: Optional[str] = None  # ISO 8601
    windowed: Optional[WindowedMetrics] = None  # None if amount_usd unavailable


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
    """Returned after POST /api/cashflows/manual. `message` is always set by the handler."""

    cashflow_id: int
    message: str = Field(
        ...,
        description="Human-readable confirmation (e.g. cf_type, amount, currency).",
    )


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


# ============================================================
# Candidates — GET /api/candidates
# ============================================================

class Candidate(BaseModel):
    rank: int
    symbol: str
    venue: str
    apr_14d: Optional[float]
    apr_7d: Optional[float]
    apr_1d: Optional[float]
    apr_3d: Optional[float]
    stability_score: Optional[float]
    flags: str
    tradeability_status: str


class CandidatesResponse(BaseModel):
    general: list[Candidate]
    equities: list[Candidate]
    as_of: str   # ISO 8601 — CSV file mtime
    total: int
