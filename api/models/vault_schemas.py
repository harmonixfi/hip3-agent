"""Pydantic models for vault API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class StrategySummary(BaseModel):
    strategy_id: str
    name: str
    type: str
    status: str
    equity_usd: Optional[float] = None
    weight_pct: Optional[float] = Field(None, description="Actual weight = equity / total * 100")
    target_weight_pct: Optional[float] = None
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None


class VaultOverview(BaseModel):
    vault_name: str
    total_equity_usd: float
    total_apr: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    net_deposits_alltime: Optional[float] = None
    strategies: List[StrategySummary]
    as_of: Optional[str] = None


class StrategyDetail(BaseModel):
    strategy_id: str
    name: str
    type: str
    status: str
    target_weight_pct: Optional[float] = None
    equity_usd: Optional[float] = None
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    equity_breakdown: Optional[Dict[str, Any]] = None
    wallets: Optional[List[Dict[str, str]]] = None


class StrategySnapshot(BaseModel):
    ts: int
    equity_usd: float
    apr_since_inception: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None


class VaultSnapshot(BaseModel):
    ts: int
    total_equity_usd: float
    total_apr: Optional[float] = None
    apr_30d: Optional[float] = None
    apr_7d: Optional[float] = None
    strategy_weights: Optional[Dict[str, float]] = None


class VaultCashflowRequest(BaseModel):
    cf_type: str = Field(..., description="DEPOSIT, WITHDRAW, or TRANSFER")
    amount: float = Field(..., gt=0, description="Always positive; sign derived from cf_type")
    strategy_id: Optional[str] = Field(None, description="Target for DEPOSIT/WITHDRAW")
    from_strategy_id: Optional[str] = Field(None, description="Source for TRANSFER")
    to_strategy_id: Optional[str] = Field(None, description="Destination for TRANSFER")
    ts: Optional[int] = Field(None, description="Epoch ms; defaults to now")
    currency: str = "USDC"
    description: str = ""


class VaultCashflowResponse(BaseModel):
    cashflow_id: int
    recalculated: bool = False
    recalc_snapshots_affected: int = 0
    message: str
    snapshot_refreshed: bool = False
    snapshot_error: Optional[str] = None


class VaultCashflowItem(BaseModel):
    cashflow_id: int
    ts: int
    cf_type: str
    amount: float
    currency: str
    strategy_id: Optional[str] = None
    from_strategy_id: Optional[str] = None
    to_strategy_id: Optional[str] = None
    description: Optional[str] = None
