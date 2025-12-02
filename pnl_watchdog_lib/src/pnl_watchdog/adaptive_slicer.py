"""
Adaptive Slicer - Phase 2 Module
Adjusts execution parameters based on real-time Kyle's Lambda signals.
"""
from typing import Dict, Any

# Risk thresholds for Lambda signal interpretation
LAMBDA_RISK_THRESHOLDS = {
    'LOW_RISK_MAX_LAMBDA': 2.5,      # Normalized Lambda < 2.5: Low Impact Cost
    'HIGH_RISK_MIN_LAMBDA': 5.0,     # Normalized Lambda > 5.0: High Impact Cost
    'KILL_SWITCH_LAMBDA': 8.0,       # Emergency kill switch threshold
}

# Base execution parameters before Lambda adjustment
BASE_EXECUTION_PARAMS = {
    'MAX_SLICE_SIZE': 500,            # Maximum shares/contracts per order
    'TARGET_PARTICIPATION': 0.20,     # 20% of market volume (VWAP style)
    'DEFAULT_ORDER_TYPE': 'IOC',      # Immediate or Cancel
}


def adjust_execution_params(normalized_lambda_signal: float, asset_class: str) -> Dict[str, Any]:
    """
    Adjusts order slicing and routing parameters based on the real-time Lambda signal.
    
    This implements adaptive risk management by dynamically adjusting:
    - Slice size (smaller when impact is high)
    - Market participation rate
    - Order routing (lit market vs dark pool)
    
    Args:
        normalized_lambda_signal: The Lambda value scaled for readability (typically 0.5-10.0)
        asset_class: 'EQUITIES', 'FUTURES', or 'FX'
    
    Returns:
        Dictionary with adjusted execution parameters
    """
    adjusted_params = BASE_EXECUTION_PARAMS.copy()
    L_NORM = normalized_lambda_signal
    
    # 1. Emergency Kill Switch
    if L_NORM >= LAMBDA_RISK_THRESHOLDS['KILL_SWITCH_LAMBDA']:
        adjusted_params['MAX_SLICE_SIZE'] = 0
        adjusted_params['TARGET_PARTICIPATION'] = 0.0
        adjusted_params['DEFAULT_ORDER_TYPE'] = 'PAUSE_ORDER_FORCE_DARK_LIMIT'
        adjusted_params['STATUS'] = 'EMERGENCY_PAUSE'
        adjusted_params['REASON'] = 'Extreme projected impact cost - Lambda >= 8.0'
        return adjusted_params
    
    # 2. High Risk (High Impact Cost) - Conservative Execution
    elif L_NORM >= LAMBDA_RISK_THRESHOLDS['HIGH_RISK_MIN_LAMBDA']:
        # Reduce slice size aggressively
        adjustment_factor = 1.0 - (L_NORM - LAMBDA_RISK_THRESHOLDS['HIGH_RISK_MIN_LAMBDA']) / 3.0
        adjustment_factor = max(0.2, adjustment_factor)  # Minimum 20% of base size
        
        adjusted_params['MAX_SLICE_SIZE'] = int(BASE_EXECUTION_PARAMS['MAX_SLICE_SIZE'] * adjustment_factor)
        adjusted_params['TARGET_PARTICIPATION'] = BASE_EXECUTION_PARAMS['TARGET_PARTICIPATION'] * 0.4  # 40% of target
        adjusted_params['DEFAULT_ORDER_TYPE'] = 'NON_MARKETABLE_LIMIT'  # Route to dark pool/passive
        adjusted_params['STATUS'] = 'HIGH_RISK'
        adjusted_params['REASON'] = f'High impact cost detected (Lambda={L_NORM:.2f})'
        
    # 3. Low Risk (Low Impact Cost) - Aggressive Execution
    elif L_NORM <= LAMBDA_RISK_THRESHOLDS['LOW_RISK_MAX_LAMBDA']:
        # Increase slice size to capitalize on liquidity
        adjusted_params['MAX_SLICE_SIZE'] = int(BASE_EXECUTION_PARAMS['MAX_SLICE_SIZE'] * 1.5)
        adjusted_params['TARGET_PARTICIPATION'] = BASE_EXECUTION_PARAMS['TARGET_PARTICIPATION'] * 1.5
        adjusted_params['DEFAULT_ORDER_TYPE'] = 'MARKET_IOC_LIT'  # Route to lit market
        adjusted_params['STATUS'] = 'LOW_RISK'
        adjusted_params['REASON'] = f'Low impact cost - increasing aggression (Lambda={L_NORM:.2f})'
        
    # 4. Moderate Risk - Baseline Execution
    else:
        adjusted_params['STATUS'] = 'MODERATE_RISK'
        adjusted_params['REASON'] = f'Normal liquidity conditions (Lambda={L_NORM:.2f})'
    
    # Add metadata
    adjusted_params['ASSET_CLASS'] = asset_class
    adjusted_params['LAMBDA_SIGNAL'] = L_NORM
    
    return adjusted_params


def calculate_optimal_tranching(total_order_size: int, lambda_signal: float, time_horizon_seconds: int = 3600) -> Dict[str, Any]:
    """
    Calculates optimal tranching strategy based on Lambda signal.
    
    Implements Almgren-Chriss style optimal execution by breaking large orders
    into smaller tranches over time.
    
    Args:
        total_order_size: Total shares/contracts to execute
        lambda_signal: Current Kyle's Lambda value
        time_horizon_seconds: Total execution window (default: 1 hour)
    
    Returns:
        Dictionary with tranching recommendations
    """
    # Base parameters
    params = adjust_execution_params(lambda_signal, 'EQUITIES')
    slice_size = params['MAX_SLICE_SIZE']
    
    if slice_size == 0:
        # Emergency pause
        return {
            'num_tranches': 0,
            'tranche_size': 0,
            'interval_seconds': 0,
            'status': 'PAUSED',
            'recommendation': 'Wait for liquidity to improve'
        }
    
    # Calculate number of tranches needed
    num_tranches = max(1, int(total_order_size / slice_size))
    actual_tranche_size = total_order_size // num_tranches
    interval_seconds = time_horizon_seconds // num_tranches
    
    return {
        'num_tranches': num_tranches,
        'tranche_size': actual_tranche_size,
        'interval_seconds': interval_seconds,
        'total_time_minutes': time_horizon_seconds / 60,
        'status': params['STATUS'],
        'order_type': params['DEFAULT_ORDER_TYPE'],
        'recommendation': f"Split order into {num_tranches} tranches of {actual_tranche_size} units, "
                         f"executed every {interval_seconds}s ({params['REASON']})"
    }


# Export public API
__all__ = ['adjust_execution_params', 'calculate_optimal_tranching', 'LAMBDA_RISK_THRESHOLDS', 'BASE_EXECUTION_PARAMS']
