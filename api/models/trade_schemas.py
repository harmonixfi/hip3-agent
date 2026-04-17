"""Pydantic request/response models for /api/trades and position create."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class TradeCreateRequest(BaseModel):
    position_id: str
    trade_type: Literal["OPEN", "CLOSE"]
    start_ts: int = Field(..., description="epoch ms UTC")
    end_ts: int = Field(..., description="epoch ms UTC, exclusive")
    note: Optional[str] = None


class TradePreviewRequest(TradeCreateRequest):
    pass


class TradeEditRequest(BaseModel):
    start_ts: Optional[int] = None
    end_ts: Optional[int] = None
    trade_type: Optional[Literal["OPEN", "CLOSE"]] = None
    note: Optional[str] = None


class TradeItem(BaseModel):
    trade_id: str
    position_id: str
    trade_type: Literal["OPEN", "CLOSE"]
    state: Literal["DRAFT", "FINALIZED"]
    start_ts: int
    end_ts: int
    note: Optional[str] = None

    long_leg_id: str
    long_size: Optional[float] = None
    long_notional: Optional[float] = None
    long_avg_px: Optional[float] = None
    long_fees: Optional[float] = None
    long_fill_count: Optional[int] = None

    short_leg_id: str
    short_size: Optional[float] = None
    short_notional: Optional[float] = None
    short_avg_px: Optional[float] = None
    short_fees: Optional[float] = None
    short_fill_count: Optional[int] = None

    spread_bps: Optional[float] = None
    realized_pnl_bps: Optional[float] = None

    created_at_ms: int
    finalized_at_ms: Optional[int] = None
    computed_at_ms: int

    unassigned_fills_count: Optional[int] = None


class TradeListResponse(BaseModel):
    items: list[TradeItem]
    total: int


class LinkedFillItem(BaseModel):
    fill_id: int
    leg_side: Literal["LONG", "SHORT"]
    inst_id: str
    side: Literal["BUY", "SELL"]
    px: float
    sz: float
    fee: Optional[float] = None
    ts: int


class TradeDetailResponse(TradeItem):
    fills: list[LinkedFillItem]


class PositionLegInput(BaseModel):
    leg_id: str
    venue: str
    inst_id: str
    side: Literal["LONG", "SHORT"]
    wallet_label: Optional[str] = None
    account_id: Optional[str] = None


class PositionCreateRequest(BaseModel):
    position_id: str
    base: str
    strategy_type: Literal["SPOT_PERP", "PERP_PERP"]
    venue: str
    long_leg: PositionLegInput
    short_leg: PositionLegInput
