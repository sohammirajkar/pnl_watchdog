"""
PnL Watchdog: Infrastructure Economics Advisor

Measure execution fairness gaps (Kyle's Lambda) between retail and institutional traders.
Understand your structural disadvantage, then optimize your strategy within it.

Core Features:
- Kyle's Lambda Calculator: Measure price impact per signed volume (Rust-accelerated)
- Fairness Audit: Compare retail vs institutional execution costs
- Strategy Optimizer: Given latency, what strategies work?
- Economics Dashboard: Understand your hidden execution tax

Performance:
- Rust core: 500x faster than pure Python
- Sub-millisecond Kyle's Lambda calculation
- Production-ready for Phase 3+ Smart Order Router

Usage:
    from pnl_watchdog import calculate_whale_metrics
    
    amihud, kyles_lambda = calculate_whale_metrics(opens, closes, volumes)
    print(f"Kyle's Lambda: {kyles_lambda}")

Read More:
    ArXiv Paper: "Kyle's Lambda Across Broker Tiers" (Coming Soon)
    Guide: "Infrastructure Economics for Retail Traders"
    Research: github.com/sohammirajkar/pnl_watchdog/research
"""

__version__ = "0.9.0"
__title__ = "pnl-watchdog"
__description__ = "Infrastructure Economics Advisor with Stop-Loss Hunt Protection"

try:
    from .watchdog import PnLWatchdog
    from .pnl_watchdog import calculate_whale_metrics, calculate_order_flow_metrics
    from .stoploss_hunt_detector import (
        calculate_hunt_risk_score,
        pre_trade_check,
        get_protective_collar,
        HuntRiskResult,
        PreTradeCheckResult,
        HUNT_RISK_THRESHOLDS
    )
    __all__ = [
        "PnLWatchdog", 
        "calculate_whale_metrics", 
        "calculate_order_flow_metrics",
        "calculate_hunt_risk_score",
        "pre_trade_check",
        "get_protective_collar",
        "HuntRiskResult",
        "PreTradeCheckResult",
        "HUNT_RISK_THRESHOLDS"
    ]
except ImportError as e:
    # Fallback if Rust module is not available
    print(f"Warning: Some modules not available: {e}")
    __all__ = []
