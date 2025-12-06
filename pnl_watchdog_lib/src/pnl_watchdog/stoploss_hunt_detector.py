"""
Stop-Loss Hunt Detector - PnL Watchdog v0.9.0

Detects stop-loss hunting patterns using a multi-factor risk scoring system.
Combines Kyle's Lambda, Jump Risk, Volume Imbalance, and Time-of-Day analysis.

Specifically tuned for Indian F&O markets (NSE/BSE) but works globally.
"""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger("PnLWatchdog.HuntDetector")

# Try importing Rust core
try:
    import pnl_core
    RUST_CORE_AVAILABLE = True
except ImportError:
    RUST_CORE_AVAILABLE = False
    logger.warning("⚠️ Rust Core not available. Hunt detection accuracy may be reduced.")


# ==============================================================================
# CONFIGURATION: Risk Thresholds
# ==============================================================================

# Hunt Risk Score Thresholds
HUNT_RISK_THRESHOLDS = {
    'SAFE': 30,           # Score < 30: Safe to execute
    'CAUTION': 50,        # Score 30-50: Proceed with smaller slices
    'HIGH_RISK': 70,      # Score 50-70: Delay execution or use limit orders
    'DANGER': 85,         # Score > 70: Do NOT execute
}

# Time-based risk for Indian markets (IST timezone)
# 3:00-3:30 PM is notorious for stop-loss hunting in NSE F&O
IST_HIGH_RISK_WINDOWS = [
    {'start': (14, 50), 'end': (15, 30), 'risk_multiplier': 2.0},  # Pre-close
    {'start': (9, 15), 'end': (9, 30), 'risk_multiplier': 1.5},   # Market open
    {'start': (15, 15), 'end': (15, 29), 'risk_multiplier': 2.5}, # Last 15 mins
]

# Lambda thresholds (price impact per unit)
LAMBDA_THRESHOLDS = {
    'LOW': 0.001,      # < 0.1% impact per unit
    'MEDIUM': 0.005,   # 0.1-0.5% impact
    'HIGH': 0.01,      # > 0.5% impact
}


# ==============================================================================
# DATA CLASSES
# ==============================================================================

@dataclass
class HuntRiskResult:
    """Result of stop-loss hunt risk analysis."""
    hunt_score: float              # 0-100 composite score
    safe_to_trade: bool            # Binary recommendation
    verdict: str                   # Human-readable verdict
    
    # Component scores (each 0-25)
    lambda_score: float            # Market impact risk
    imbalance_score: float         # Volume imbalance (order flow toxicity)
    jump_score: float              # Jump probability (fat tail risk)
    time_score: float              # Time-of-day risk
    
    # Raw metrics
    lambda_value: float            # Kyle's Lambda
    volume_imbalance: float        # -1 to 1 (negative = sell pressure)
    jump_probability: float        # 0-1 probability
    
    # Protective collar (max slippage tolerance)
    protective_collar: float       # Percentage (e.g., 0.005 = 0.5%)
    
    # Recommendations
    recommended_slice_pct: float   # Percentage of order to execute now
    delay_seconds: int             # Recommended delay before next slice


@dataclass  
class PreTradeCheckResult:
    """Result of pre-trade safety check."""
    safe_to_execute: bool
    reason: str
    hunt_risk: HuntRiskResult
    recommended_action: str


# ==============================================================================
# CORE FUNCTIONS
# ==============================================================================

def calculate_time_risk_score(current_time: Optional[datetime] = None) -> float:
    """
    Calculate time-of-day risk score (0-25).
    High risk during known stop-loss hunting windows.
    
    Args:
        current_time: Datetime in any timezone (will be converted to IST)
    
    Returns:
        Risk score 0-25 (higher = more dangerous)
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    # Convert to IST (UTC+5:30)
    ist = timezone(timedelta(hours=5, minutes=30))
    ist_time = current_time.astimezone(ist)
    
    hour = ist_time.hour
    minute = ist_time.minute
    current_minutes = hour * 60 + minute
    
    # Check if we're in a high-risk window
    max_multiplier = 1.0
    for window in IST_HIGH_RISK_WINDOWS:
        start_minutes = window['start'][0] * 60 + window['start'][1]
        end_minutes = window['end'][0] * 60 + window['end'][1]
        
        if start_minutes <= current_minutes <= end_minutes:
            max_multiplier = max(max_multiplier, window['risk_multiplier'])
    
    # Base time score is 5, multiplied by risk factor
    base_score = 5.0
    return min(25.0, base_score * max_multiplier)


def calculate_lambda_risk_score(lambda_value: float) -> float:
    """
    Calculate Lambda-based risk score (0-25).
    Higher Lambda = higher market impact = more vulnerable to stop hunts.
    
    Args:
        lambda_value: Kyle's Lambda (price change per unit volume)
    
    Returns:
        Risk score 0-25
    """
    if lambda_value <= 0:
        return 0.0
    
    if lambda_value < LAMBDA_THRESHOLDS['LOW']:
        # Low impact: 0-8 score
        return (lambda_value / LAMBDA_THRESHOLDS['LOW']) * 8.0
    elif lambda_value < LAMBDA_THRESHOLDS['MEDIUM']:
        # Medium impact: 8-16 score
        ratio = (lambda_value - LAMBDA_THRESHOLDS['LOW']) / (LAMBDA_THRESHOLDS['MEDIUM'] - LAMBDA_THRESHOLDS['LOW'])
        return 8.0 + ratio * 8.0
    elif lambda_value < LAMBDA_THRESHOLDS['HIGH']:
        # High impact: 16-22 score
        ratio = (lambda_value - LAMBDA_THRESHOLDS['MEDIUM']) / (LAMBDA_THRESHOLDS['HIGH'] - LAMBDA_THRESHOLDS['MEDIUM'])
        return 16.0 + ratio * 6.0
    else:
        # Extreme impact: 22-25 score
        return min(25.0, 22.0 + (lambda_value - LAMBDA_THRESHOLDS['HIGH']) * 100)


def calculate_imbalance_risk_score(volume_imbalance: float) -> float:
    """
    Calculate volume imbalance risk score (0-25).
    Extreme imbalance (all buy or all sell) = stop hunt setup.
    
    Args:
        volume_imbalance: -1 to 1 (negative = sell pressure, positive = buy pressure)
    
    Returns:
        Risk score 0-25
    """
    # Absolute imbalance matters (either direction is risky)
    abs_imbalance = abs(volume_imbalance)
    
    # Quadratic scaling: small imbalance = low risk, extreme = high risk
    return min(25.0, abs_imbalance * abs_imbalance * 25.0)


def calculate_jump_risk_score(jump_probability: float) -> float:
    """
    Calculate jump probability risk score (0-25).
    High jump probability = unstable market = easy to trigger stops.
    
    Args:
        jump_probability: 0-1 probability of jumps
    
    Returns:
        Risk score 0-25
    """
    # Linear scaling with cap
    return min(25.0, jump_probability * 250.0)  # 10% jump prob = 25 score


def calculate_hunt_risk_score(
    candles: List[Dict[str, float]],
    asset_class: str = "EQUITIES",
    order_size: float = 100.0,
    market_depth: float = 1_000_000.0,
    current_time: Optional[datetime] = None
) -> HuntRiskResult:
    """
    Calculate comprehensive stop-loss hunt risk score.
    
    Args:
        candles: List of OHLCV dicts with keys: open, high, low, close, volume
        asset_class: Asset type for Lambda calculation
        order_size: Your intended order size
        market_depth: Estimated market depth at best bid/ask
        current_time: Current time for time-based risk
    
    Returns:
        HuntRiskResult with all metrics and recommendations
    """
    # Extract data from candles
    opens = [float(c.get('open', c.get('o', 0))) for c in candles]
    closes = [float(c.get('close', c.get('c', 0))) for c in candles]
    volumes = [float(c.get('volume', c.get('v', 0))) for c in candles]
    
    # Default values for non-Rust fallback
    lambda_value = 0.001
    volume_imbalance = 0.0
    jump_probability = 0.0
    volatility = 0.02
    
    if RUST_CORE_AVAILABLE and len(candles) >= 5:
        try:
            # 1. Get market quality metrics (Lambda, imbalance)
            _, historical_lambda, imbalance = pnl_core.calculate_market_quality_metrics(
                opens, closes, volumes
            )
            volume_imbalance = imbalance
            
            # 2. Get asset-specific Lambda
            vol, jump_prob, _ = pnl_core.calculate_jump_risk(closes)
            volatility = vol
            jump_probability = jump_prob
            
            lambda_value = pnl_core.calculate_kyle_lambda_asset_specific(
                asset_class.upper(),
                float(order_size),
                volatility,
                float(market_depth)
            )
            
        except Exception as e:
            logger.warning(f"Rust calculation failed: {e}. Using Python fallback.")
    else:
        # Simple Python fallback
        if len(candles) >= 2:
            price_changes = [closes[i] - opens[i] for i in range(len(closes))]
            volatility = sum(abs(pc) for pc in price_changes) / len(price_changes) / (sum(closes) / len(closes))
            
            buy_vol = sum(v for o, c, v in zip(opens, closes, volumes) if c >= o)
            sell_vol = sum(v for o, c, v in zip(opens, closes, volumes) if c < o)
            total_vol = buy_vol + sell_vol
            if total_vol > 0:
                volume_imbalance = (buy_vol - sell_vol) / total_vol
    
    # Calculate component scores
    lambda_score = calculate_lambda_risk_score(lambda_value)
    imbalance_score = calculate_imbalance_risk_score(volume_imbalance)
    jump_score = calculate_jump_risk_score(jump_probability)
    time_score = calculate_time_risk_score(current_time)
    
    # Composite score (sum of components)
    hunt_score = lambda_score + imbalance_score + jump_score + time_score
    
    # Determine verdict
    if hunt_score < HUNT_RISK_THRESHOLDS['SAFE']:
        verdict = "SAFE - Normal market conditions"
        safe_to_trade = True
        recommended_slice = 1.0  # Execute full order
        delay_seconds = 0
    elif hunt_score < HUNT_RISK_THRESHOLDS['CAUTION']:
        verdict = "CAUTION - Proceed with smaller slices"
        safe_to_trade = True
        recommended_slice = 0.5  # Execute 50%
        delay_seconds = 30
    elif hunt_score < HUNT_RISK_THRESHOLDS['HIGH_RISK']:
        verdict = "HIGH RISK - Consider delaying execution"
        safe_to_trade = False
        recommended_slice = 0.25  # Execute 25%
        delay_seconds = 120
    elif hunt_score < HUNT_RISK_THRESHOLDS['DANGER']:
        verdict = "DANGER - Stop-loss hunt likely in progress"
        safe_to_trade = False
        recommended_slice = 0.1  # Execute only 10%
        delay_seconds = 300
    else:
        verdict = "EXTREME DANGER - DO NOT EXECUTE"
        safe_to_trade = False
        recommended_slice = 0.0  # Don't execute
        delay_seconds = 600
    
    # Calculate protective collar
    # Higher risk = tighter collar (reject bad fills faster)
    base_collar = 0.02  # 2% base slippage tolerance
    if hunt_score > HUNT_RISK_THRESHOLDS['SAFE']:
        protective_collar = base_collar * (1 - (hunt_score / 100) * 0.8)
    else:
        protective_collar = base_collar
    
    return HuntRiskResult(
        hunt_score=round(hunt_score, 2),
        safe_to_trade=safe_to_trade,
        verdict=verdict,
        lambda_score=round(lambda_score, 2),
        imbalance_score=round(imbalance_score, 2),
        jump_score=round(jump_score, 2),
        time_score=round(time_score, 2),
        lambda_value=round(lambda_value, 6),
        volume_imbalance=round(volume_imbalance, 4),
        jump_probability=round(jump_probability, 4),
        protective_collar=round(protective_collar, 4),
        recommended_slice_pct=round(recommended_slice * 100, 1),
        delay_seconds=delay_seconds
    )


def pre_trade_check(
    symbol: str,
    qty: float,
    expected_price: float,
    candles: List[Dict[str, float]],
    asset_class: str = "EQUITIES",
    market_depth: float = 1_000_000.0,
    max_acceptable_risk: int = 50
) -> PreTradeCheckResult:
    """
    Perform pre-trade safety check.
    
    Args:
        symbol: Trading symbol
        qty: Order quantity
        expected_price: Expected fill price
        candles: Historical OHLCV data
        asset_class: Asset type
        market_depth: Estimated market depth
        max_acceptable_risk: Maximum acceptable hunt score (default 50)
    
    Returns:
        PreTradeCheckResult with go/no-go decision
    """
    hunt_risk = calculate_hunt_risk_score(
        candles=candles,
        asset_class=asset_class,
        order_size=qty,
        market_depth=market_depth
    )
    
    if hunt_risk.hunt_score <= max_acceptable_risk:
        safe = True
        reason = f"Hunt score ({hunt_risk.hunt_score}) within acceptable range"
        action = f"Execute {hunt_risk.recommended_slice_pct}% now. Collar: ±{hunt_risk.protective_collar*100:.2f}%"
    else:
        safe = False
        reason = f"Hunt score ({hunt_risk.hunt_score}) exceeds threshold ({max_acceptable_risk})"
        action = f"WAIT {hunt_risk.delay_seconds}s. {hunt_risk.verdict}"
    
    return PreTradeCheckResult(
        safe_to_execute=safe,
        reason=reason,
        hunt_risk=hunt_risk,
        recommended_action=action
    )


def get_protective_collar(
    alpha_signal: float,
    total_qty: float,
    volatility: float,
    lambda_value: float,
    base_risk_aversion: float = 0.5,
    alpha_sensitivity: float = 5.0
) -> Dict[str, float]:
    """
    Calculate protective price collar for order execution.
    Wraps the Rust calculate_dynamic_execution_params function.
    
    Args:
        alpha_signal: Your edge/alpha (0.01 = 1% expected return)
        total_qty: Total order size
        volatility: Asset volatility (from jump risk calculation)
        lambda_value: Kyle's Lambda
        base_risk_aversion: Base urgency setting
        alpha_sensitivity: How much alpha affects urgency
    
    Returns:
        Dict with optimal_slice, effective_gamma, protective_collar
    """
    if not RUST_CORE_AVAILABLE:
        # Fallback calculation
        collar = volatility * 2  # Simple 2x volatility collar
        return {
            'optimal_slice': total_qty * 0.25,
            'effective_gamma': base_risk_aversion,
            'protective_collar': min(0.01, collar),
            'source': 'python_fallback'
        }
    
    try:
        optimal_slice, effective_gamma, collar = pnl_core.calculate_dynamic_execution_params(
            float(alpha_signal),
            float(total_qty),
            float(volatility),
            float(lambda_value),
            float(base_risk_aversion),
            float(alpha_sensitivity)
        )
        
        return {
            'optimal_slice': round(optimal_slice, 2),
            'effective_gamma': round(effective_gamma, 4),
            'protective_collar': round(collar, 4),
            'source': 'rust_core'
        }
    except Exception as e:
        logger.error(f"Protective collar calculation failed: {e}")
        return {
            'optimal_slice': total_qty * 0.1,
            'effective_gamma': base_risk_aversion,
            'protective_collar': 0.005,
            'source': 'error_fallback'
        }


# ==============================================================================
# EXPORTS
# ==============================================================================

__all__ = [
    'HuntRiskResult',
    'PreTradeCheckResult', 
    'calculate_hunt_risk_score',
    'pre_trade_check',
    'get_protective_collar',
    'calculate_time_risk_score',
    'HUNT_RISK_THRESHOLDS',
]
