"""
Alpha Execution Console - Options Greeks Engine

Calculates Black-Scholes Greeks and payoff analysis for options strategies.
This is the Opstra-style analytics layer.
"""

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime, date
from enum import Enum


# ==============================================================================
# CONSTANTS
# ==============================================================================

# Standard normal distribution functions
def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


# ==============================================================================
# DATA CLASSES
# ==============================================================================

class OptionType(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


@dataclass
class OptionLeg:
    """Single option leg in a strategy."""
    option_type: OptionType
    strike: float
    expiry_days: int  # Days to expiry
    quantity: int  # Positive for long, negative for short
    premium: float = 0.0  # Current premium per contract
    iv: float = 0.25  # Implied volatility (default 25%)


@dataclass
class Greeks:
    """Options Greeks for a position."""
    delta: float
    gamma: float
    theta: float  # Per day
    vega: float
    rho: float = 0.0


@dataclass
class PayoffPoint:
    """Single point on payoff diagram."""
    price: float
    pnl: float


@dataclass 
class StrategyPayoff:
    """Complete payoff analysis for a strategy."""
    max_profit: float
    max_loss: float
    breakeven_points: List[float]
    probability_of_profit: float
    payoff_curve: List[PayoffPoint]
    risk_reward_ratio: float


# ==============================================================================
# BLACK-SCHOLES GREEKS
# ==============================================================================

def calculate_d1_d2(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float]:
    """
    Calculate d1 and d2 for Black-Scholes.
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiry (in years)
        r: Risk-free rate
        sigma: Implied volatility
    """
    if T <= 0 or sigma <= 0:
        return 0.0, 0.0
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    return d1, d2


def calculate_option_price(
    S: float, 
    K: float, 
    T: float, 
    r: float, 
    sigma: float, 
    option_type: OptionType
) -> float:
    """
    Black-Scholes option price.
    
    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiry (years)
        r: Risk-free rate
        sigma: Implied volatility
        option_type: CALL or PUT
    """
    if T <= 0:
        # At expiry
        if option_type == OptionType.CALL:
            return max(0, S - K)
        else:
            return max(0, K - S)
    
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    
    if option_type == OptionType.CALL:
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    
    return max(0, price)


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType,
    quantity: int = 1
) -> Greeks:
    """
    Calculate all Greeks for an option.
    
    Returns:
        Greeks object with delta, gamma, theta, vega, rho
    """
    if T <= 0:
        # At expiry, only delta matters
        if option_type == OptionType.CALL:
            delta = 1.0 if S > K else 0.0
        else:
            delta = -1.0 if S < K else 0.0
        return Greeks(delta=delta * quantity, gamma=0, theta=0, vega=0)
    
    d1, d2 = calculate_d1_d2(S, K, T, r, sigma)
    sqrt_T = math.sqrt(T)
    
    # Delta
    if option_type == OptionType.CALL:
        delta = norm_cdf(d1)
    else:
        delta = norm_cdf(d1) - 1
    
    # Gamma (same for calls and puts)
    gamma = norm_pdf(d1) / (S * sigma * sqrt_T)
    
    # Theta (per day)
    first_term = -(S * norm_pdf(d1) * sigma) / (2 * sqrt_T)
    if option_type == OptionType.CALL:
        theta = (first_term - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365
    else:
        theta = (first_term + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365
    
    # Vega (per 1% change in IV)
    vega = S * sqrt_T * norm_pdf(d1) / 100
    
    # Rho
    if option_type == OptionType.CALL:
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100
    else:
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100
    
    return Greeks(
        delta=delta * quantity,
        gamma=gamma * abs(quantity),
        theta=theta * quantity,
        vega=vega * abs(quantity),
        rho=rho * quantity
    )


# ==============================================================================
# STRATEGY ANALYSIS
# ==============================================================================

def analyze_strategy(
    legs: List[OptionLeg],
    current_price: float,
    risk_free_rate: float = 0.05,
    price_range_pct: float = 0.20
) -> Tuple[Greeks, StrategyPayoff]:
    """
    Analyze a complete options strategy.
    
    Args:
        legs: List of option legs
        current_price: Current underlying price
        risk_free_rate: Annual risk-free rate
        price_range_pct: Range for payoff curve (e.g., 0.20 = ±20%)
    
    Returns:
        Combined Greeks and payoff analysis
    """
    # Calculate combined Greeks
    total_delta = 0.0
    total_gamma = 0.0
    total_theta = 0.0
    total_vega = 0.0
    total_rho = 0.0
    net_premium = 0.0
    
    for leg in legs:
        T = leg.expiry_days / 365.0
        greeks = calculate_greeks(
            S=current_price,
            K=leg.strike,
            T=T,
            r=risk_free_rate,
            sigma=leg.iv,
            option_type=leg.option_type,
            quantity=leg.quantity
        )
        
        total_delta += greeks.delta
        total_gamma += greeks.gamma
        total_theta += greeks.theta
        total_vega += greeks.vega
        total_rho += greeks.rho
        
        # Net premium (negative for long positions)
        net_premium += leg.premium * leg.quantity
    
    combined_greeks = Greeks(
        delta=total_delta,
        gamma=total_gamma,
        theta=total_theta,
        vega=total_vega,
        rho=total_rho
    )
    
    # Calculate payoff curve at expiry
    min_price = current_price * (1 - price_range_pct)
    max_price = current_price * (1 + price_range_pct)
    
    payoff_curve = []
    min_pnl = float('inf')
    max_pnl = float('-inf')
    
    for i in range(100):
        price = min_price + (max_price - min_price) * i / 99
        pnl = net_premium  # Start with premium received/paid
        
        for leg in legs:
            if leg.option_type == OptionType.CALL:
                intrinsic = max(0, price - leg.strike)
            else:
                intrinsic = max(0, leg.strike - price)
            
            pnl += intrinsic * leg.quantity
        
        payoff_curve.append(PayoffPoint(price=price, pnl=pnl))
        min_pnl = min(min_pnl, pnl)
        max_pnl = max(max_pnl, pnl)
    
    # Find breakeven points (where PnL crosses zero)
    breakevens = []
    for i in range(1, len(payoff_curve)):
        prev_pnl = payoff_curve[i-1].pnl
        curr_pnl = payoff_curve[i].pnl
        
        if prev_pnl * curr_pnl < 0:  # Sign change
            # Linear interpolation
            prev_price = payoff_curve[i-1].price
            curr_price = payoff_curve[i].price
            breakeven = prev_price + (curr_price - prev_price) * abs(prev_pnl) / (abs(prev_pnl) + abs(curr_pnl))
            breakevens.append(round(breakeven, 2))
    
    # Probability of profit (simplified - assumes normal distribution)
    # Count points where PnL > 0
    profitable_points = sum(1 for p in payoff_curve if p.pnl > 0)
    pop = profitable_points / len(payoff_curve)
    
    # Risk-reward ratio
    if abs(min_pnl) > 0:
        risk_reward = abs(max_pnl / min_pnl)
    else:
        risk_reward = float('inf') if max_pnl > 0 else 0
    
    payoff = StrategyPayoff(
        max_profit=max_pnl,
        max_loss=min_pnl,
        breakeven_points=breakevens,
        probability_of_profit=pop,
        payoff_curve=payoff_curve,
        risk_reward_ratio=round(risk_reward, 2)
    )
    
    return combined_greeks, payoff


# ==============================================================================
# STRATEGY BUILDERS
# ==============================================================================

def build_iron_condor(
    current_price: float,
    put_short_strike: float,
    put_long_strike: float,
    call_short_strike: float,
    call_long_strike: float,
    expiry_days: int,
    iv: float = 0.25,
    premium_received: float = 5.0
) -> List[OptionLeg]:
    """Build an iron condor strategy."""
    return [
        OptionLeg(OptionType.PUT, put_long_strike, expiry_days, 1, -premium_received * 0.2, iv),
        OptionLeg(OptionType.PUT, put_short_strike, expiry_days, -1, premium_received * 0.4, iv),
        OptionLeg(OptionType.CALL, call_short_strike, expiry_days, -1, premium_received * 0.4, iv),
        OptionLeg(OptionType.CALL, call_long_strike, expiry_days, 1, -premium_received * 0.2, iv),
    ]


def build_bull_call_spread(
    current_price: float,
    long_strike: float,
    short_strike: float,
    expiry_days: int,
    iv: float = 0.25,
    net_debit: float = 3.0
) -> List[OptionLeg]:
    """Build a bull call spread."""
    return [
        OptionLeg(OptionType.CALL, long_strike, expiry_days, 1, -net_debit * 0.7, iv),
        OptionLeg(OptionType.CALL, short_strike, expiry_days, -1, net_debit * 0.3, iv - 0.02),
    ]


def build_straddle(
    current_price: float,
    strike: float,
    expiry_days: int,
    iv: float = 0.30,
    total_premium: float = 10.0
) -> List[OptionLeg]:
    """Build a long straddle."""
    return [
        OptionLeg(OptionType.CALL, strike, expiry_days, 1, -total_premium * 0.5, iv),
        OptionLeg(OptionType.PUT, strike, expiry_days, 1, -total_premium * 0.5, iv),
    ]


__all__ = [
    "OptionType",
    "OptionLeg",
    "Greeks",
    "StrategyPayoff",
    "calculate_option_price",
    "calculate_greeks",
    "analyze_strategy",
    "build_iron_condor",
    "build_bull_call_spread",
    "build_straddle"
]
