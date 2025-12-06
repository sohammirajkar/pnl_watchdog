"""
API Models - Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


# ==============================================================================
# REQUEST MODELS
# ==============================================================================

class CandleData(BaseModel):
    """Single OHLCV candle."""
    open: float = Field(..., description="Opening price")
    high: float = Field(..., description="High price")
    low: float = Field(..., description="Low price")
    close: float = Field(..., description="Closing price")
    volume: float = Field(..., description="Volume")
    timestamp: Optional[float] = Field(None, description="Unix timestamp")


class HuntScoreRequest(BaseModel):
    """Request for stop-loss hunt risk score."""
    symbol: str = Field(..., description="Trading symbol (e.g., NIFTY84900CE)")
    candles: List[CandleData] = Field(..., min_length=5, description="Historical OHLCV data")
    asset_class: str = Field("EQUITIES", description="Asset type: EQUITIES, FUTURES, FX, CRYPTO")
    order_size: float = Field(100.0, description="Intended order size")
    market_depth: float = Field(1_000_000.0, description="Estimated market depth")


class PreTradeCheckRequest(BaseModel):
    """Request for pre-trade safety check."""
    symbol: str
    qty: float = Field(..., gt=0, description="Order quantity")
    expected_price: float = Field(..., gt=0, description="Expected fill price")
    candles: List[CandleData] = Field(..., min_length=5)
    asset_class: str = Field("EQUITIES")
    market_depth: float = Field(1_000_000.0)
    max_acceptable_risk: int = Field(50, ge=0, le=100, description="Maximum acceptable hunt score")


class ExecutionPassportRequest(BaseModel):
    """Request to generate execution passport."""
    symbol: str
    side: str = Field(..., pattern="^(buy|sell)$", description="Order side: buy or sell")
    qty: float = Field(..., gt=0)
    expected_price: float = Field(..., gt=0)
    candles: List[CandleData] = Field(..., min_length=5)


# ==============================================================================
# RESPONSE MODELS
# ==============================================================================

class ComponentScores(BaseModel):
    """Individual risk component scores (each 0-25)."""
    lambda_risk: float
    imbalance_risk: float
    jump_risk: float
    time_risk: float


class RawMetrics(BaseModel):
    """Raw microstructure metrics."""
    kyles_lambda: float
    volume_imbalance: float
    jump_probability: float


class Recommendations(BaseModel):
    """Execution recommendations."""
    protective_collar: float
    recommended_slice_pct: float
    delay_seconds: int


class HuntScoreResponse(BaseModel):
    """Response with stop-loss hunt risk score."""
    symbol: str
    hunt_score: float = Field(..., ge=0, le=100, description="Composite risk score 0-100")
    safe_to_trade: bool
    verdict: str
    components: ComponentScores
    metrics: RawMetrics
    recommendations: Recommendations


class HuntRiskSummary(BaseModel):
    """Abbreviated hunt risk info for pre-trade check."""
    score: float
    verdict: str
    protective_collar: float
    recommended_slice_pct: float


class PreTradeCheckResponse(BaseModel):
    """Response for pre-trade safety check."""
    safe_to_execute: bool
    reason: str
    recommended_action: str
    hunt_risk: HuntRiskSummary


class ExecutionPassportResponse(BaseModel):
    """Execution passport audit record."""
    passport_id: str
    symbol: str
    side: str
    qty: float
    expected_price: float
    timestamp_ns: int
    hunt_score: float
    safe_to_trade: bool
    protective_collar: float
    verdict: str
    created_at: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    rust_core_available: bool
    timestamp: str
