"""
Alpha Execution Console - Trade Intent Schema

Defines the structured JSON schemas for Gemini LLM Function Calling.
These schemas translate natural language trading requests into structured data.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from enum import Enum


# ==============================================================================
# ENUMS
# ==============================================================================

class AssetClass(str, Enum):
    EQUITIES = "EQUITIES"
    OPTIONS = "OPTIONS"
    FUTURES = "FUTURES"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"


class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class OptionStrategy(str, Enum):
    # Single leg
    LONG_CALL = "LONG_CALL"
    LONG_PUT = "LONG_PUT"
    SHORT_CALL = "SHORT_CALL"
    SHORT_PUT = "SHORT_PUT"
    
    # Spreads
    BULL_CALL_SPREAD = "BULL_CALL_SPREAD"
    BEAR_PUT_SPREAD = "BEAR_PUT_SPREAD"
    BULL_PUT_SPREAD = "BULL_PUT_SPREAD"
    BEAR_CALL_SPREAD = "BEAR_CALL_SPREAD"
    
    # Neutral
    IRON_CONDOR = "IRON_CONDOR"
    IRON_BUTTERFLY = "IRON_BUTTERFLY"
    STRADDLE = "STRADDLE"
    STRANGLE = "STRANGLE"
    
    # Stock
    COVERED_CALL = "COVERED_CALL"
    PROTECTIVE_PUT = "PROTECTIVE_PUT"
    COLLAR = "COLLAR"


class RiskVerdict(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"
    DANGER = "DANGER"


# ==============================================================================
# INPUT SCHEMAS (User Intent → Structured)
# ==============================================================================

class OptionLeg(BaseModel):
    """Single option leg in a strategy."""
    option_type: OptionType
    strike: float
    expiry: str = Field(description="Expiry date in YYYY-MM-DD format")
    quantity: int = Field(description="Positive for long, negative for short")
    premium: Optional[float] = None


class TradeIntent(BaseModel):
    """
    Structured representation of a user's trading intent.
    This is what the Gemini LLM outputs after parsing natural language.
    """
    # Core identifiers
    ticker: str = Field(description="Underlying ticker symbol (e.g., NVDA, NIFTY)")
    asset_class: AssetClass = AssetClass.EQUITIES
    
    # Strategy details
    strategy_name: Optional[OptionStrategy] = None
    quantity: int = Field(description="Number of shares or contracts")
    
    # Option-specific (if applicable)
    option_legs: Optional[List[OptionLeg]] = None
    
    # Price expectations
    expected_price: Optional[float] = None
    limit_price: Optional[float] = None
    
    # User's stated intent
    action: Literal["BUY", "SELL", "ANALYZE", "ROLL", "MODIFY"] = "ANALYZE"
    
    # Raw input for logging
    raw_input: Optional[str] = None


# ==============================================================================
# ANALYSIS SCHEMAS (Strategy Analysis Output)
# ==============================================================================

class GreeksAnalysis(BaseModel):
    """Options Greeks for a position."""
    delta: float = Field(description="Position delta")
    gamma: float = Field(description="Position gamma")
    theta: float = Field(description="Time decay per day")
    vega: float = Field(description="Volatility sensitivity")
    rho: Optional[float] = None


class PayoffAnalysis(BaseModel):
    """Profit/Loss analysis for a strategy."""
    max_profit: float = Field(description="Maximum possible profit")
    max_loss: float = Field(description="Maximum possible loss")
    breakeven_points: List[float] = Field(description="Breakeven price levels")
    probability_of_profit: Optional[float] = None


class StrategyAnalysis(BaseModel):
    """
    Complete analysis of an options strategy.
    Opstra-style output.
    """
    ticker: str
    strategy_name: str
    current_price: float
    
    # Greeks
    greeks: GreeksAnalysis
    
    # Payoff
    payoff: PayoffAnalysis
    
    # Position summary
    net_premium: float = Field(description="Net premium paid/received")
    margin_required: Optional[float] = None


# ==============================================================================
# WATCHDOG RISK SCHEMAS (Execution Risk Output)
# ==============================================================================

class WatchdogRisk(BaseModel):
    """
    PnL Watchdog execution risk assessment.
    """
    # Core metrics
    kyles_lambda: float = Field(description="Price impact per unit volume")
    hunt_risk_score: float = Field(description="Hunt Risk Score (0-100) - composite of Lambda, Imbalance, Jump, and Time risk")
    volume_imbalance: float = Field(description="Buy/sell imbalance (-1 to +1)")
    volatility: float = Field(description="Recent volatility %")
    
    # Jump risk
    jump_probability: float = Field(description="Probability of price jump")
    
    # Verdict
    risk_verdict: RiskVerdict
    risk_explanation: str
    
    # Recommendations
    recommended_slice_qty: int = Field(description="Optimal order slice size")
    recommended_delay_seconds: int = Field(description="Suggested delay before execution")
    protective_collar_pct: float = Field(description="Max acceptable slippage %")


# ==============================================================================
# COMBINED OUTPUT SCHEMA
# ==============================================================================

class AlphaConsoleResponse(BaseModel):
    """
    Complete response from Alpha Execution Console.
    Combines strategy analysis with execution risk assessment.
    """
    # Original intent
    intent: TradeIntent
    
    # Strategy analysis (Opstra-style)
    strategy_analysis: Optional[StrategyAnalysis] = None
    
    # Execution risk (Watchdog)
    execution_risk: WatchdogRisk
    
    # Spoken summary for TTS
    speak_text: str = Field(description="Natural language summary for voice output")
    
    # Action recommendations
    should_execute: bool
    execution_notes: List[str] = Field(default_factory=list)
    
    # Timestamps
    analyzed_at: str


# ==============================================================================
# GEMINI FUNCTION CALLING SCHEMA
# ==============================================================================

# This is the JSON schema for Gemini's Function Calling feature
TRADE_INTENT_FUNCTION_SCHEMA = {
    "name": "parse_trade_intent",
    "description": "Parse a natural language trading request into structured data",
    "parameters": {
        "type": "object",
        "properties": {
            "ticker": {
                "type": "string",
                "description": "The stock/ETF ticker symbol (e.g., NVDA, SPY, NIFTY)"
            },
            "asset_class": {
                "type": "string",
                "enum": ["EQUITIES", "OPTIONS", "FUTURES", "FOREX", "CRYPTO"],
                "description": "Type of asset being traded"
            },
            "strategy_name": {
                "type": "string",
                "enum": [
                    "LONG_CALL", "LONG_PUT", "SHORT_CALL", "SHORT_PUT",
                    "BULL_CALL_SPREAD", "BEAR_PUT_SPREAD", "IRON_CONDOR",
                    "IRON_BUTTERFLY", "STRADDLE", "STRANGLE",
                    "COVERED_CALL", "PROTECTIVE_PUT", "COLLAR"
                ],
                "description": "Options strategy type (if applicable)"
            },
            "quantity": {
                "type": "integer",
                "description": "Number of shares or contracts"
            },
            "action": {
                "type": "string",
                "enum": ["BUY", "SELL", "ANALYZE", "ROLL", "MODIFY"],
                "description": "Intended action"
            },
            "expected_price": {
                "type": "number",
                "description": "Expected execution price"
            }
        },
        "required": ["ticker", "quantity", "action"]
    }
}


__all__ = [
    "AssetClass",
    "OptionType", 
    "OptionStrategy",
    "RiskVerdict",
    "OptionLeg",
    "TradeIntent",
    "GreeksAnalysis",
    "PayoffAnalysis",
    "StrategyAnalysis",
    "WatchdogRisk",
    "AlphaConsoleResponse",
    "TRADE_INTENT_FUNCTION_SCHEMA"
]
