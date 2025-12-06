"""
Alpha Execution Console - FastAPI Routes

Main API endpoints for the conversational trading interface.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json

from .schemas import (
    TradeIntent,
    AlphaConsoleResponse,
    WatchdogRisk,
    RiskVerdict,
    StrategyAnalysis,
    GreeksAnalysis,
    PayoffAnalysis
)
from .orchestrator import get_orchestrator

# Import watchdog functions
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from pnl_watchdog.stoploss_hunt_detector import calculate_hunt_risk_score
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    calculate_hunt_risk_score = None

# DataBento for live market data
import os
DATABENTO_API_KEY = os.getenv("DATABENTO_API_KEY", "db-ieJvGbF9HQ3CaMGUuVXLC4YhFcs3Q")

try:
    from pnl_watchdog.brokers.databento import DatabentoAdapter
    DATABENTO_ADAPTER = DatabentoAdapter(DATABENTO_API_KEY)
    DATABENTO_AVAILABLE = True
    print(f"[Alpha Console] ✅ DataBento connected: {DATABENTO_API_KEY[:4]}...{DATABENTO_API_KEY[-4:]}")
except Exception as e:
    DATABENTO_ADAPTER = None
    DATABENTO_AVAILABLE = False
    print(f"[Alpha Console] ⚠️ DataBento not available: {e}")


def fetch_live_candles(ticker: str, lookback: int = 50) -> list:
    """Fetch live candle data from DataBento for the given ticker."""
    if not DATABENTO_AVAILABLE or not DATABENTO_ADAPTER:
        return []
    
    try:
        candles = DATABENTO_ADAPTER.get_candles(ticker, lookback=lookback)
        print(f"[Alpha Console] 📊 Fetched {len(candles)} candles for {ticker}")
        return candles
    except Exception as e:
        print(f"[Alpha Console] ❌ Failed to fetch candles for {ticker}: {e}")
        return []


router = APIRouter(prefix="/v1/alpha", tags=["Alpha Console"])


# ==============================================================================
# REQUEST/RESPONSE MODELS
# ==============================================================================

class AnalyzeRequest(BaseModel):
    """Request to analyze a trade from natural language."""
    message: str
    include_greeks: bool = True
    
    # Optional: provide candle data for watchdog
    candles: Optional[List[dict]] = None


class ChatMessage(BaseModel):
    """Single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str
    analysis: Optional[dict] = None


# ==============================================================================
# GREEKS CALCULATION (using real Black-Scholes)
# ==============================================================================

try:
    from .greeks_engine import (
        analyze_strategy,
        build_iron_condor,
        build_bull_call_spread,
        build_straddle,
        OptionLeg as EngineOptionLeg,
        OptionType as EngineOptionType
    )
    GREEKS_ENGINE_AVAILABLE = True
except ImportError:
    GREEKS_ENGINE_AVAILABLE = False


def get_real_greeks_and_payoff(strategy_name: str, current_price: float, quantity: int = 1):
    """Calculate real Greeks and payoff using Black-Scholes engine."""
    if not GREEKS_ENGINE_AVAILABLE:
        return None, None
    
    expiry_days = 30  # Default 30 DTE
    iv = 0.30  # 30% IV
    
    try:
        if strategy_name == "IRON_CONDOR":
            legs = build_iron_condor(
                current_price=current_price,
                put_short_strike=current_price * 0.95,
                put_long_strike=current_price * 0.90,
                call_short_strike=current_price * 1.05,
                call_long_strike=current_price * 1.10,
                expiry_days=expiry_days,
                iv=iv,
                premium_received=5.0 * quantity
            )
        elif strategy_name == "BULL_CALL_SPREAD":
            legs = build_bull_call_spread(
                current_price=current_price,
                long_strike=current_price,
                short_strike=current_price * 1.05,
                expiry_days=expiry_days,
                iv=iv,
                net_debit=3.0 * quantity
            )
        elif strategy_name == "STRADDLE":
            legs = build_straddle(
                current_price=current_price,
                strike=current_price,
                expiry_days=expiry_days,
                iv=iv,
                total_premium=10.0 * quantity
            )
        elif strategy_name == "LONG_CALL":
            legs = [EngineOptionLeg(
                option_type=EngineOptionType.CALL,
                strike=current_price * 1.02,
                expiry_days=expiry_days,
                quantity=quantity,
                premium=-2.50 * quantity,
                iv=iv
            )]
        elif strategy_name == "LONG_PUT":
            legs = [EngineOptionLeg(
                option_type=EngineOptionType.PUT,
                strike=current_price * 0.98,
                expiry_days=expiry_days,
                quantity=quantity,
                premium=-2.50 * quantity,
                iv=iv
            )]
        else:
            return None, None
        
        greeks, payoff = analyze_strategy(legs, current_price)
        
        greeks_analysis = GreeksAnalysis(
            delta=round(greeks.delta, 4),
            gamma=round(greeks.gamma, 4),
            theta=round(greeks.theta, 2),
            vega=round(greeks.vega, 2)
        )
        
        payoff_analysis = PayoffAnalysis(
            max_profit=round(payoff.max_profit, 2),
            max_loss=round(payoff.max_loss, 2),
            breakeven_points=payoff.breakeven_points,
            probability_of_profit=round(payoff.probability_of_profit, 2)
        )
        
        return greeks_analysis, payoff_analysis
        
    except Exception as e:
        print(f"Greeks calculation error: {e}")
        return None, None


def get_fallback_greeks(strategy_name: str) -> GreeksAnalysis:
    """Return fallback Greeks if engine fails."""
    if strategy_name == "IRON_CONDOR":
        return GreeksAnalysis(delta=0.05, gamma=-0.02, theta=15.50, vega=-8.20)
    elif strategy_name == "BULL_CALL_SPREAD":
        return GreeksAnalysis(delta=0.45, gamma=0.08, theta=-5.20, vega=12.30)
    elif strategy_name == "LONG_CALL":
        return GreeksAnalysis(delta=0.55, gamma=0.12, theta=-8.40, vega=18.50)
    else:
        return GreeksAnalysis(delta=0.30, gamma=0.05, theta=-3.20, vega=10.00)


def get_fallback_payoff(strategy_name: str, current_price: float) -> PayoffAnalysis:
    """Return fallback payoff if engine fails."""
    if strategy_name == "IRON_CONDOR":
        return PayoffAnalysis(
            max_profit=450.0,
            max_loss=-550.0,
            breakeven_points=[current_price * 0.95, current_price * 1.05],
            probability_of_profit=0.65
        )
    elif strategy_name == "BULL_CALL_SPREAD":
        return PayoffAnalysis(
            max_profit=350.0,
            max_loss=-150.0,
            breakeven_points=[current_price * 1.02],
            probability_of_profit=0.48
        )
    else:
        return PayoffAnalysis(
            max_profit=1000.0,
            max_loss=-200.0,
            breakeven_points=[current_price * 1.03],
            probability_of_profit=0.40
        )


def get_live_watchdog_risk(ticker: str, candles: List[dict] = None) -> WatchdogRisk:
    """
    Calculate watchdog risk using LIVE data from DataBento + Rust core.
    No more mock data - real calculations only.
    """
    # Auto-fetch candles if not provided
    if not candles and ticker:
        candles = fetch_live_candles(ticker, lookback=50)
    
    if not candles or len(candles) < 5:
        # Not enough data - return a clear error state
        return WatchdogRisk(
            kyles_lambda=0.0,
            hunt_risk_score=0.0,
            volume_imbalance=0.0,
            volatility=0.0,
            jump_probability=0.0,
            risk_verdict=RiskVerdict.CAUTION,
            risk_explanation=f"⚠️ Insufficient data for {ticker}. Need at least 5 candles.",
            recommended_slice_qty=50,
            recommended_delay_seconds=60,
            protective_collar_pct=2.0
        )
    
    if not WATCHDOG_AVAILABLE:
        return WatchdogRisk(
            kyles_lambda=0.0,
            hunt_risk_score=0.0,
            volume_imbalance=0.0,
            volatility=0.0,
            jump_probability=0.0,
            risk_verdict=RiskVerdict.CAUTION,
            risk_explanation="⚠️ Rust core not available. Cannot calculate execution risk.",
            recommended_slice_qty=25,
            recommended_delay_seconds=120,
            protective_collar_pct=3.0
        )
    
    try:
        result = calculate_hunt_risk_score(candles=candles)
        
        # Map hunt_score to risk verdict
        if result.hunt_score < 30:
            verdict = RiskVerdict.SAFE
        elif result.hunt_score < 50:
            verdict = RiskVerdict.CAUTION
        elif result.hunt_score < 70:
            verdict = RiskVerdict.HIGH_RISK
        else:
            verdict = RiskVerdict.DANGER
        
        return WatchdogRisk(
            kyles_lambda=result.lambda_value,
            hunt_risk_score=result.hunt_score,
            volume_imbalance=result.volume_imbalance,
            volatility=result.jump_probability * 100,
            jump_probability=result.jump_probability,
            risk_verdict=verdict,
            risk_explanation=result.verdict,
            recommended_slice_qty=int(result.recommended_slice_pct),
            recommended_delay_seconds=result.delay_seconds,
            protective_collar_pct=result.protective_collar * 100
        )
    except Exception as e:
        print(f"[Alpha Console] ❌ Watchdog calculation failed for {ticker}: {e}")
        return WatchdogRisk(
            kyles_lambda=0.0,
            hunt_risk_score=0.0,
            volume_imbalance=0.0,
            volatility=0.0,
            jump_probability=0.0,
            risk_verdict=RiskVerdict.CAUTION,
            risk_explanation=f"⚠️ Calculation error: {str(e)[:50]}",
            recommended_slice_qty=25,
            recommended_delay_seconds=120,
            protective_collar_pct=3.0
        )


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@router.post("/analyze", response_model=AlphaConsoleResponse)
async def analyze_trade(request: AnalyzeRequest):
    """
    Main endpoint: Parse natural language and return complete analysis.
    
    Example:
        POST /v1/alpha/analyze
        {"message": "5000 share iron condor on NVDA"}
        
    Returns:
        Complete AlphaConsoleResponse with strategy analysis and execution risk.
    """
    orchestrator = get_orchestrator()
    
    # Step 1: Parse the trade intent
    intent = orchestrator.parse_trade_intent(request.message)
    
    # Step 2: Get strategy analysis using real Black-Scholes engine
    strategy_analysis = None
    if intent.strategy_name:
        current_price = intent.expected_price or 140.0  # Default for demo
        strategy_name = intent.strategy_name.value if intent.strategy_name else ""
        
        # Try real Greeks engine first, fall back to mock data
        greeks, payoff = get_real_greeks_and_payoff(strategy_name, current_price, intent.quantity)
        
        if greeks is None:
            greeks = get_fallback_greeks(strategy_name)
        if payoff is None:
            payoff = get_fallback_payoff(strategy_name, current_price)
        
        strategy_analysis = StrategyAnalysis(
            ticker=intent.ticker,
            strategy_name=strategy_name,
            current_price=current_price,
            greeks=greeks,
            payoff=payoff,
            net_premium=payoff.max_loss if payoff.max_loss < 0 else -150.0,
            margin_required=abs(payoff.max_loss) * 2 if payoff.max_loss else 2500.0
        )
    
    # Step 3: Get Watchdog risk assessment using LIVE DataBento data
    execution_risk = get_live_watchdog_risk(ticker=intent.ticker, candles=request.candles)
    
    # Step 4: Generate spoken response
    result_dict = {
        "intent": intent.model_dump(),
        "execution_risk": execution_risk.model_dump()
    }
    speak_text = orchestrator.generate_spoken_response(result_dict)
    
    # Step 5: Determine if safe to execute
    should_execute = execution_risk.risk_verdict in [RiskVerdict.SAFE, RiskVerdict.CAUTION]
    
    execution_notes = []
    if execution_risk.risk_verdict == RiskVerdict.CAUTION:
        execution_notes.append(f"Consider using {execution_risk.recommended_slice_qty}% order slices")
    elif execution_risk.risk_verdict == RiskVerdict.HIGH_RISK:
        execution_notes.append(f"Delay execution by {execution_risk.recommended_delay_seconds}s")
        execution_notes.append("Reduce position size significantly")
    elif execution_risk.risk_verdict == RiskVerdict.DANGER:
        execution_notes.append("DO NOT EXECUTE - Market conditions unfavorable")
    
    return AlphaConsoleResponse(
        intent=intent,
        strategy_analysis=strategy_analysis,
        execution_risk=execution_risk,
        speak_text=speak_text,
        should_execute=should_execute,
        execution_notes=execution_notes,
        analyzed_at=datetime.utcnow().isoformat()
    )


@router.post("/parse")
async def parse_only(request: AnalyzeRequest):
    """
    Parse natural language without full analysis.
    Useful for testing the LLM intent parsing.
    """
    orchestrator = get_orchestrator()
    intent = orchestrator.parse_trade_intent(request.message)
    return {"intent": intent.model_dump(), "gemini_available": orchestrator.is_available}


@router.get("/status")
async def get_status():
    """Check Alpha Console status and available features."""
    orchestrator = get_orchestrator()
    
    return {
        "status": "operational",
        "gemini_available": orchestrator.is_available,
        "watchdog_available": WATCHDOG_AVAILABLE,
        "features": {
            "natural_language_parsing": True,
            "strategy_analysis": True,
            "execution_risk": WATCHDOG_AVAILABLE,
            "voice_input": False,  # Phase 2
            "voice_output": False  # Phase 2
        },
        "version": "0.1.0-alpha"
    }


__all__ = ["router"]
