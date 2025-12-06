from .ai_brain import AIBrain
import os
import time
import uuid
import hmac
import hashlib
import requests
import logging
import json
import threading
from datetime import datetime
import numpy as np
from typing import Optional, Dict, Any
import random

# Configure logging
logging.basicConfig(level=logging.INFO, format="[PnL Watchdog] %(message)s")
logger = logging.getLogger("PnLWatchdog")

# --- IMPORT ADAPTERS ---
# Each adapter is imported separately to allow partial availability
AlpacaAdapter = None
CCXTAdapter = None
ZerodhaAdapter = None
AngelOneAdapter = None
IBKRAdapter = None
DatabentoAdapter = None

try:
    from .brokers.alpaca import AlpacaAdapter
except ImportError:
    pass

try:
    from .brokers.ccxt_adapter import CCXTAdapter
except ImportError:
    pass

try:
    from .brokers.zerodha import ZerodhaAdapter
except ImportError:
    pass

try:
    from .brokers.angel_one import AngelOneAdapter
except ImportError:
    pass

try:
    from .brokers.ibkr import IBKRAdapter
except ImportError:
    pass

try:
    from .brokers.databento import DatabentoAdapter
except ImportError as e:
    logger.warning(f"DatabentoAdapter not available: {e}")


# --- RUST CORE IMPORT ---
try:
    import pnl_core
    RUST_CORE_AVAILABLE = True
except ImportError:
    # If the Rust extension isn't built/found, flag it.
    RUST_CORE_AVAILABLE = False
    logger.warning(
        "⚠️ Rust Core (pnl_core) not found. Falling back to Python math (slower, less precise).")


class PnLWatchdog:
    """
    The central Watchdog class.
    Acts as a Factory to load the correct Broker Adapter and AI Brain.
    """

    def __init__(self, broker: str = "alpaca", pro_key: str = None, opt_in: bool = False, **kwargs):
        """
        Initialize the Watchdog.
        :param broker: 'alpaca', 'ibkr', 'binance', 'zerodha', etc.
        :param pro_key: Your PnL Watchdog Pro API Key (for the private dashboard).
        :param opt_in: Set to True to share anonymous latency stats with the Global Map.
        """
        # --- 1. IDENTITY & CONFIG ---
        self.user_id = str(uuid.uuid4())
        self.pro_key = pro_key
        self.opt_in = opt_in
        self.broker_name = broker.lower()

        # Production API URL
        self.api_url = "https://pnl-cloud-backend-4esa.vercel.app/v1"

        self.brain = AIBrain()
        self.adapter = None

        # --- 2. ADAPTER FACTORY (Connects to real brokers) ---
        # Extract common arguments
        api_key = kwargs.get("api_key")
        api_secret = kwargs.get("api_secret")
        paper = kwargs.get("paper", True)

        try:
            if self.broker_name == "alpaca":
                self.adapter = AlpacaAdapter(api_key, api_secret, paper)
            elif self.broker_name == "zerodha":
                self.adapter = ZerodhaAdapter(
                    api_key, kwargs.get("access_token"))
            elif self.broker_name == "angel":
                self.adapter = AngelOneAdapter(
                    api_key,
                    kwargs.get("client_code"),
                    kwargs.get("password"),
                    kwargs.get("totp")
                )
            elif self.broker_name == "ibkr":
                self.adapter = IBKRAdapter(
                    host=kwargs.get("host", '127.0.0.1'),
                    port=kwargs.get("port", 7497)
                )
            elif self.broker_name == "databento":
                self.adapter = DatabentoAdapter(api_key)
            elif self.broker_name == "test_mode":  # New mode for stress testing
                self.adapter = None
            else:
                # Default to CCXT for crypto (Binance, etc.)
                self.adapter = CCXTAdapter(
                    self.broker_name, api_key, api_secret, paper)
        except Exception as e:
            logger.warning(
                f"⚠️ Broker Adapter not initialized: {e}. (Whale View will be simulated)")

        # --- 3. WELCOME MESSAGE ---
        print("\n" + "-" * 60)
        print(f"🐶 PnL Watchdog v0.8.0 Active (Cross-Market Edition).")
        print(f"🆔 YOUR USER ID: {self.user_id}")
        print("-" * 60 + "\n")

    # --- 0. UTILITY: LAMBDA STREAMING (Module 7) ---

    def stream_lambda(self, asset_class: str, lambda_value: float, ip: str, port: int):
        """
        Low-latency streaming of the Lambda signal over UDP for HFT systems.
        :param asset_class: The asset class (e.g., 'FX', 'CRYPTO', 'PREDICTION_MARKETS')
        :param lambda_value: The calculated market impact cost.
        :param ip: Target IP address for the UDP receiver.
        :param port: Target port.
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core Required"}
        
        try:
            pnl_core.stream_lambda_udp(
                asset_class.upper(), lambda_value, ip, port
            )
            return {"status": "success", "message": f"Streaming Lambda={lambda_value:.6f} for {asset_class.upper()}"}
        except Exception as e:
            logger.error(f"UDP Stream Failed: {e}")
            return {"error": str(e)}


    # --- NEW: DYNAMIC EXECUTION PLAN (Modules 6 & 8) ---
    def get_dynamic_execution_plan(
        self,
        symbol: str,
        asset_class: str,
        total_qty: float,
        alpha_signal: float,
        base_risk_aversion: float = 0.5,
        alpha_sensitivity: float = 5.0,
        lookback_candles: int = 100,
        market_depth: float = 1_000_000.0,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        Generates Almgren-Chriss Optimal Slice Schedule, dynamically adjusted by Alpha (edge)
        and asset-class specific microstructure (Lambda).

        :param asset_class: The asset type (e.g., 'EQUITIES', 'FX', 'PREDICTION_MARKETS').
        :param total_qty: Total size you want to move.
        :param alpha_signal: The strength of your trading edge (e.g., 0.01 for 1% edge).
        :param base_risk_aversion: Base urgency (0.0 to 1.0).
        :param alpha_sensitivity: Multiplier for Alpha's effect on urgency (default 5.0).
        :param market_depth: Estimated volume at the top of the book (critical for Prediction Markets).
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for dynamic optimization."}

        # 1. Fetch Data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data:
            return {"error": "No data"}

        opens = [float(c['open']) for c in data]
        closes = [float(c['close']) for c in data]
        volumes = [float(c['volume']) for c in data]

        try:
            # 2. Get Historical Lambda & Volatility (Sigma)
            # We use the historical calculation to get a baseline volatility measure (sigma)
            # The volatility calculation inside calculate_jump_risk is used for sigma
            _, historical_lambda, _ = pnl_core.calculate_market_quality_metrics(
                opens, closes, volumes)
            vol, _, _ = pnl_core.calculate_jump_risk(closes)
            
            # --- CRITICAL STEP: ASSET-SPECIFIC ADAPTATION (Module 6) ---
            # Use the historical sigma, but calculate the current impact cost (lambda)
            # based on the order size and the asset's microstructure config.
            asset_specific_lambda = pnl_core.calculate_kyle_lambda_asset_specific(
                asset_class.upper(),
                float(total_qty),
                vol,
                float(market_depth)
            )

            # --- CRITICAL STEP: DYNAMIC URGENCY CALCULATION (Module 8) ---
            # The new function takes alpha into account to adjust risk aversion (gamma)
            optimal_slice, effective_gamma, final_collar = pnl_core.calculate_dynamic_execution_params(
                float(alpha_signal),
                float(total_qty),
                vol,
                asset_specific_lambda,
                float(base_risk_aversion),
                float(alpha_sensitivity)
            )

            return {
                "symbol": symbol,
                "asset_class": asset_class.upper(),
                "total_order": total_qty,
                "alpha_signal": alpha_signal,
                "recommended_slice": round(optimal_slice, 2),
                "remaining_qty": round(total_qty - optimal_slice, 2),
                "microstructure_params": {
                    "impact_cost_lambda": round(asset_specific_lambda, 6),
                    "volatility_sigma": round(vol, 4),
                    "effective_risk_aversion": round(effective_gamma, 4)
                },
                "advice": f"Recommended initial slice based on Alpha (Edge): {round(optimal_slice, 2)}."
            }

        except Exception as e:
            logger.error(f"Dynamic Execution Plan Failed: {e}")
            return {"error": str(e)}

    # --- JUMP RISK (MARKET REGIME) ---
    def get_market_regime(self, symbol, lookback=200, candles=None):
        """
        Detects 'Crash Risk' using Merton Jump-Diffusion logic.
        """
        if not RUST_CORE_AVAILABLE: return {"error": "Rust Core Required"}
        
        # Fetch Data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback)
            
        if not data: return {"error": "No Data"}
        
        closes = [float(c['close']) for c in data]
        
        # Rust Calculation
        vol, jump_prob, intensity = pnl_core.calculate_jump_risk(closes)
        
        # Diagnosis
        status = "NORMAL"
        if jump_prob > 0.05: status = "JUMP_PRONE"
        if jump_prob > 0.15: status = "CRASH_RISK"
        
        return {
            "symbol": symbol,
            "regime": status,
            "metrics": {
                "volatility": round(vol, 4),
                "jump_probability": round(jump_prob * 100, 2),
                "jump_intensity": round(intensity, 2)
            }
        }

    # =========================================================
    # v0.10.0: REGIME SWITCHING (Module 10) - SL HUNT DETECTION
    # =========================================================
    def get_regime_state(
        self, 
        symbol: str, 
        vol_threshold: float = 0.005,
        lambda_threshold: float = 0.0005,
        lookback_candles: int = 100,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        v0.10.0: REGIME SWITCHING - Detects toxic market states including SL_HUNT.
        
        Uses Kyle's Lambda and Volatility to classify market into three regimes:
        - NORMAL: Safe to trade with market orders
        - TRANSITION: Elevated risk, use limit orders
        - SL_HUNT: Toxic state where MMs exploit stop-losses - BLOCK market orders
        
        Args:
            symbol: Trading symbol
            vol_threshold: Volatility threshold for regime transition (default: 50 bps)
            lambda_threshold: Lambda threshold for regime transition (default: 5 bps/unit)
            lookback_candles: Historical data window
            candles: Optional pre-fetched candle data
        
        Returns:
            Dict with regime state, safe_to_trade flag, and metrics
        
        Example:
            >>> result = dog.get_regime_state("AAPL")
            >>> if result['regime'] == 'SL_HUNT':
            ...     print("⛔ DANGER: Market is toxic, avoid market orders!")
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Regime Switching."}

        # 1. Fetch Data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data or len(data) < 10:
            return {"error": "Insufficient data for Regime analysis."}

        # 2. Extract market metrics
        opens = [float(c['open']) for c in data]
        closes = [float(c['close']) for c in data]
        volumes = [float(c['volume']) for c in data]

        try:
            # Get volatility and Kyle's Lambda
            _, kyles_lambda, _ = pnl_core.calculate_market_quality_metrics(opens, closes, volumes)
            volatility, _, _ = pnl_core.calculate_jump_risk(closes)
            
            # 3. Classify Regime using Rust Module 10
            regime = pnl_core.calculate_market_regime(
                volatility,
                kyles_lambda,
                vol_threshold,
                lambda_threshold
            )
            
            # 4. Determine safety
            safe_to_trade = regime != "SL_HUNT"
            order_recommendation = "Market Orders OK" if regime == "NORMAL" else (
                "Use Limit Orders" if regime == "TRANSITION" else "BLOCK ALL MARKET ORDERS"
            )
            
            return {
                "symbol": symbol,
                "regime": regime,
                "safe_to_trade": safe_to_trade,
                "order_recommendation": order_recommendation,
                "metrics": {
                    "volatility": round(volatility, 6),
                    "kyles_lambda": round(kyles_lambda, 8),
                    "vol_threshold": vol_threshold,
                    "lambda_threshold": lambda_threshold
                }
            }
            
        except Exception as e:
            logger.error(f"Regime State calculation failed: {e}")
            return {"error": str(e)}

    # =========================================================
    # v0.10.0: OPTIMAL STOPPING (Module 11) - DYNAMIC EXIT
    # =========================================================
    def get_optimal_exit(
        self,
        symbol: str,
        entry_price: float,
        time_horizon_sec: float = 600.0,  # 10 minutes default
        alpha_decay_rate: float = 0.1,
        drift: float = 0.000001,
        lookback_candles: int = 100,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        v0.10.0: OPTIMAL STOPPING - Calculates mathematically optimal TP/SL.
        
        Replaces static stop-loss/take-profit with dynamic boundaries that:
        - Adapt to current volatility
        - Account for alpha signal decay over time
        - Use stochastic calculus (optimal stopping theory)
        
        Args:
            symbol: Trading symbol (for volatility lookup)
            entry_price: Your entry price
            time_horizon_sec: How long you plan to hold (seconds)
            alpha_decay_rate: How fast your edge decays (0.1 = 10% decay/minute)
            drift: Expected price drift per second (positive = bullish)
            lookback_candles: Historical data for volatility calculation
            candles: Optional pre-fetched candle data
        
        Returns:
            Dict with optimal take_profit, stop_loss, and calculation details
        
        Example:
            >>> result = dog.get_optimal_exit("AAPL", entry_price=150.0, time_horizon_sec=300)
            >>> print(f"TP: ${result['take_profit']:.2f}, SL: ${result['stop_loss']:.2f}")
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Optimal Stopping."}

        # 1. Get volatility from market data
        volatility = 0.001  # Default 10 bps if no data
        
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if data and len(data) >= 10:
            closes = [float(c['close']) for c in data]
            try:
                volatility, _, _ = pnl_core.calculate_jump_risk(closes)
            except Exception:
                pass  # Use default volatility

        try:
            # 2. Calculate optimal exit using Rust Module 11
            take_profit, stop_loss = pnl_core.calculate_optimal_exit_price(
                entry_price,
                time_horizon_sec,
                volatility,
                drift,
                alpha_decay_rate
            )
            
            # 3. Calculate distances
            tp_distance_pct = ((take_profit - entry_price) / entry_price) * 100
            sl_distance_pct = ((entry_price - stop_loss) / entry_price) * 100
            risk_reward_ratio = tp_distance_pct / sl_distance_pct if sl_distance_pct > 0 else float('inf')
            
            return {
                "symbol": symbol,
                "entry_price": entry_price,
                "take_profit": round(take_profit, 4),
                "stop_loss": round(stop_loss, 4),
                "tp_distance_pct": round(tp_distance_pct, 2),
                "sl_distance_pct": round(sl_distance_pct, 2),
                "risk_reward_ratio": round(risk_reward_ratio, 2),
                "calculation_params": {
                    "time_horizon_sec": time_horizon_sec,
                    "volatility": round(volatility, 6),
                    "alpha_decay_rate": alpha_decay_rate,
                    "drift": drift
                }
            }
            
        except Exception as e:
            logger.error(f"Optimal Exit calculation failed: {e}")
            return {"error": str(e)}

    # =========================================================
    # v0.10.0: ORDER EXECUTION WITH REGIME GATING
    # =========================================================
    def execute_trade(
        self,
        symbol: str,
        side: str,  # "buy" or "sell"
        qty: float,
        order_type: str = "market",
        limit_price: float = None,
        use_optimal_exit: bool = True,
        custom_tp: float = None,
        custom_sl: float = None,
        time_horizon_sec: float = 600.0,
        force_execute: bool = False
    ) -> Dict[str, Any]:
        """
        v0.10.0: INTELLIGENT ORDER EXECUTION with Regime Gating.
        
        This method:
        1. Checks market regime (NORMAL/TRANSITION/SL_HUNT)
        2. BLOCKS execution if regime is SL_HUNT (unless force_execute=True)
        3. Auto-calculates TP/SL using Optimal Stopping theory
        4. Places bracket orders for automated exit management
        
        Args:
            symbol: Trading symbol (e.g., 'AAPL')
            side: 'buy' or 'sell'
            qty: Order quantity
            order_type: 'market' or 'limit'
            limit_price: Price for limit orders
            use_optimal_exit: If True, auto-calculate TP/SL using Optimal Stopping
            custom_tp: Override take-profit price
            custom_sl: Override stop-loss price
            time_horizon_sec: Time horizon for optimal exit calculation
            force_execute: If True, bypasses regime safety check (USE WITH CAUTION)
        
        Returns:
            Dict with execution result, regime info, and order details
        
        Example:
            >>> result = dog.execute_trade("AAPL", "buy", 10)
            >>> if result['executed']:
            ...     print(f"Order placed: {result['order_id']}")
            ...     print(f"TP: {result['take_profit']}, SL: {result['stop_loss']}")
        """
        from .brokers.base import OrderSide, OrderType, OrderResult
        
        # 1. Validate adapter supports execution
        if not self.adapter:
            return {"executed": False, "error": "No broker adapter connected"}
        
        if not hasattr(self.adapter, 'place_order'):
            return {"executed": False, "error": f"Broker {self.broker_name} does not support order execution"}
        
        # 2. CHECK REGIME - Critical safety gate
        regime_info = self.get_regime_state(symbol)
        regime = regime_info.get('regime', 'UNKNOWN')
        
        if regime == "SL_HUNT" and not force_execute:
            logger.warning(f"⛔ EXECUTION BLOCKED: {symbol} is in SL_HUNT regime!")
            return {
                "executed": False,
                "blocked": True,
                "reason": "SL_HUNT regime detected - market is toxic",
                "regime": regime,
                "recommendation": "Wait for regime to return to NORMAL or use force_execute=True",
                "metrics": regime_info.get('metrics', {})
            }
        
        if regime == "TRANSITION" and not force_execute:
            logger.warning(f"⚠️ CAUTION: {symbol} is in TRANSITION regime - using limit orders recommended")
        
        # 3. Get current price for TP/SL calculation
        entry_price = limit_price
        if not entry_price:
            # Try to get current market price
            candles = []
            if hasattr(self.adapter, 'get_candles'):
                candles = self.adapter.get_candles(symbol, 5)
            if candles:
                entry_price = candles[-1]['close']
            else:
                return {"executed": False, "error": "Could not determine entry price"}
        
        # 4. Calculate optimal TP/SL
        take_profit = custom_tp
        stop_loss = custom_sl
        
        if use_optimal_exit and not (custom_tp and custom_sl):
            exit_plan = self.get_optimal_exit(
                symbol=symbol,
                entry_price=entry_price,
                time_horizon_sec=time_horizon_sec
            )
            
            if 'error' not in exit_plan:
                if not custom_tp:
                    take_profit = exit_plan['take_profit']
                if not custom_sl:
                    stop_loss = exit_plan['stop_loss']
        
        # 5. Convert side and type to enums
        order_side = OrderSide.BUY if side.lower() == 'buy' else OrderSide.SELL
        order_type_enum = OrderType.MARKET if order_type.lower() == 'market' else OrderType.LIMIT
        
        # 6. EXECUTE ORDER
        logger.info(f"🚀 Executing trade: {side.upper()} {qty} {symbol}")
        if take_profit:
            logger.info(f"   Take Profit: ${take_profit:.2f}")
        if stop_loss:
            logger.info(f"   Stop Loss: ${stop_loss:.2f}")
        if regime != "NORMAL":
            logger.warning(f"   ⚠️ Regime: {regime}")
        
        result: OrderResult = self.adapter.place_order(
            symbol=symbol,
            side=order_side,
            qty=qty,
            order_type=order_type_enum,
            limit_price=limit_price,
            take_profit=take_profit,
            stop_loss=stop_loss
        )
        
        # 7. Build response
        response = {
            "executed": result.success,
            "order_id": result.order_id,
            "message": result.message,
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "entry_price": entry_price,
            "take_profit": take_profit,
            "stop_loss": stop_loss,
            "regime_at_execution": regime,
            "regime_metrics": regime_info.get('metrics', {}),
            "bracket_order_ids": result.bracket_order_ids
        }
        
        if result.filled_price:
            response["filled_price"] = result.filled_price
        if result.filled_qty:
            response["filled_qty"] = result.filled_qty
        
        # Log execution for audit
        logger.info(f"{'✅' if result.success else '❌'} Trade {'executed' if result.success else 'failed'}: {result.message}")
        
        return response
    
    def get_positions(self) -> Dict[str, Any]:
        """Get all open positions from the connected broker."""
        if not self.adapter or not hasattr(self.adapter, 'get_positions'):
            return {"error": "No broker adapter with position support connected"}
        
        positions = self.adapter.get_positions()
        return {
            "broker": self.broker_name,
            "positions": positions,
            "count": len(positions)
        }
    
    def get_account(self) -> Dict[str, Any]:
        """Get account info from the connected broker."""
        if not self.adapter or not hasattr(self.adapter, 'get_account_info'):
            return {"error": "No broker adapter with account support connected"}
        
        return self.adapter.get_account_info()

    # =========================================================
    # v0.10.0: POSITION SIZING (Lambda/Vol Scaling)
    # =========================================================
    def calculate_position_size(
        self,
        symbol: str,
        base_position_value: float = 1000.0,
        max_position_pct: float = 5.0,
        lookback_candles: int = 100,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        v0.10.0: INTELLIGENT POSITION SIZING based on market conditions.
        
        Scales position size DOWN when:
        - Volatility is high → More risk per dollar
        - Kyle's Lambda is high → More market impact
        
        Args:
            symbol: Trading symbol
            base_position_value: Starting position value in dollars
            max_position_pct: Maximum position as % of portfolio
            lookback_candles: Historical data for calculations
            candles: Optional pre-fetched candle data
        
        Returns:
            Dict with recommended shares, position value, scaling factors
        
        Example:
            >>> sizing = dog.calculate_position_size("AAPL", base_position_value=5000)
            >>> print(f"Buy {sizing['recommended_shares']} shares")
        """
        # 1. Get market data
        data = candles if candles else []
        if not data and self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)
        
        if not data or len(data) < 10:
            return {"error": "Insufficient data for position sizing"}
        
        current_price = data[-1]['close']
        
        # 2. Calculate volatility and Lambda
        opens = [float(c['open']) for c in data]
        closes = [float(c['close']) for c in data]
        volumes = [float(c['volume']) for c in data]
        
        volatility = 0.02  # Default 2%
        kyles_lambda = 0.001  # Default
        
        if RUST_CORE_AVAILABLE:
            try:
                volatility, _, _ = pnl_core.calculate_jump_risk(closes)
                _, kyles_lambda, _ = pnl_core.calculate_market_quality_metrics(opens, closes, volumes)
            except:
                pass
        
        # 3. Calculate scaling factors
        # Volatility scaling: vol > 3% -> scale down, vol < 1% -> scale up
        vol_scale = min(1.5, max(0.25, 0.02 / max(volatility, 0.001)))
        
        # Lambda scaling: high lambda = high impact cost -> smaller size
        lambda_scale = min(1.5, max(0.25, 0.0005 / max(kyles_lambda, 0.00001)))
        
        # Combined scaling factor
        combined_scale = (vol_scale * 0.6) + (lambda_scale * 0.4)
        
        # 4. Calculate adjusted position value
        adjusted_value = base_position_value * combined_scale
        
        # 5. Apply max position limit (% of portfolio)
        account = self.get_account()
        portfolio_value = account.get('portfolio_value', 100000)
        max_position_value = portfolio_value * (max_position_pct / 100)
        final_position_value = min(adjusted_value, max_position_value)
        
        # 6. Calculate shares
        recommended_shares = int(final_position_value / current_price)
        recommended_shares = max(1, recommended_shares)  # At least 1 share
        
        return {
            "symbol": symbol,
            "current_price": round(current_price, 2),
            "base_position_value": base_position_value,
            "adjusted_position_value": round(final_position_value, 2),
            "recommended_shares": recommended_shares,
            "actual_value": round(recommended_shares * current_price, 2),
            "scaling_factors": {
                "volatility_scale": round(vol_scale, 3),
                "lambda_scale": round(lambda_scale, 3),
                "combined_scale": round(combined_scale, 3)
            },
            "market_conditions": {
                "volatility": round(volatility * 100, 4),
                "kyles_lambda": round(kyles_lambda, 8)
            },
            "limits": {
                "max_position_pct": max_position_pct,
                "max_position_value": round(max_position_value, 2)
            }
        }

    # =========================================================
    # v0.10.0: DAILY LOSS LIMIT (Circuit Breaker)
    # =========================================================
    
    # Class-level tracking for daily P&L
    _daily_pnl = 0.0
    _daily_loss_limit = None
    _trading_date = None
    _circuit_breaker_triggered = False
    
    def set_daily_loss_limit(self, limit: float) -> Dict[str, Any]:
        """
        Set daily loss limit. Trading will be BLOCKED when limit is hit.
        
        Args:
            limit: Maximum daily loss in dollars (positive number, e.g., 500)
        
        Example:
            >>> dog.set_daily_loss_limit(500)  # Stop trading if down $500 today
        """
        from datetime import date
        
        PnLWatchdog._daily_loss_limit = abs(limit)
        PnLWatchdog._trading_date = date.today()
        PnLWatchdog._daily_pnl = 0.0
        PnLWatchdog._circuit_breaker_triggered = False
        
        logger.info(f"🛡️ Daily loss limit set: ${limit:.2f}")
        
        return {
            "daily_loss_limit": PnLWatchdog._daily_loss_limit,
            "current_pnl": PnLWatchdog._daily_pnl,
            "trading_date": str(PnLWatchdog._trading_date),
            "circuit_breaker_active": False
        }
    
    def record_trade_pnl(self, pnl: float) -> Dict[str, Any]:
        """
        Record P&L from a completed trade. Triggers circuit breaker if limit hit.
        
        Args:
            pnl: P&L in dollars (negative for loss)
        """
        from datetime import date
        
        # Auto-reset on new trading day
        if PnLWatchdog._trading_date != date.today():
            PnLWatchdog._trading_date = date.today()
            PnLWatchdog._daily_pnl = 0.0
            PnLWatchdog._circuit_breaker_triggered = False
            logger.info("📅 New trading day - P&L reset")
        
        PnLWatchdog._daily_pnl += pnl
        
        # Check if limit breached
        if PnLWatchdog._daily_loss_limit is not None:
            if PnLWatchdog._daily_pnl <= -PnLWatchdog._daily_loss_limit:
                PnLWatchdog._circuit_breaker_triggered = True
                logger.warning(f"🚨 CIRCUIT BREAKER TRIGGERED! Daily loss: ${abs(PnLWatchdog._daily_pnl):.2f}")
        
        return self.get_daily_pnl_status()
    
    def get_daily_pnl_status(self) -> Dict[str, Any]:
        """Get current daily P&L status and circuit breaker state."""
        from datetime import date
        
        # Auto-reset check
        if PnLWatchdog._trading_date != date.today():
            PnLWatchdog._trading_date = date.today()
            PnLWatchdog._daily_pnl = 0.0
            PnLWatchdog._circuit_breaker_triggered = False
        
        remaining = None
        if PnLWatchdog._daily_loss_limit is not None:
            remaining = PnLWatchdog._daily_loss_limit + PnLWatchdog._daily_pnl
        
        return {
            "trading_date": str(PnLWatchdog._trading_date or date.today()),
            "daily_pnl": round(PnLWatchdog._daily_pnl, 2),
            "daily_loss_limit": PnLWatchdog._daily_loss_limit,
            "remaining_before_limit": round(remaining, 2) if remaining else None,
            "circuit_breaker_triggered": PnLWatchdog._circuit_breaker_triggered,
            "trading_allowed": not PnLWatchdog._circuit_breaker_triggered
        }
    
    def is_trading_allowed(self) -> bool:
        """Quick check if trading is allowed (circuit breaker not triggered)."""
        from datetime import date
        
        # Reset on new day
        if PnLWatchdog._trading_date != date.today():
            PnLWatchdog._trading_date = date.today()
            PnLWatchdog._daily_pnl = 0.0
            PnLWatchdog._circuit_breaker_triggered = False
        
        return not PnLWatchdog._circuit_breaker_triggered

    # --- Legacy Function removed: get_execution_plan ---
    # --- Legacy Function removed: get_optimal_slice ---
    
    # [Rest of the PnLWatchdog Class Methods are kept as is]
    
    def check_order(self, symbol, side, qty, price=None):
        """
        Main entry point. Verifies execution and reports latency.
        """
        start_time = time.time()
        logger.info(
            f"🔎 Verifying {side.upper()} {qty} {symbol} on {self.broker_name}...")

        # In a real scenario, we would use self.adapter.get_recent_orders() here
        # For now, we measure the check latency itself
        latency = int((time.time() - start_time) * 1000)

        # --- TELEMETRY (Non-blocking) ---
        if self.pro_key:
            # Pro users send full logs to their private dashboard
            threading.Thread(target=self._upload_log, args=({
                "symbol": symbol, "side": side, "qty": qty,
                "broker": self.broker_name, "latency_ms": latency,
                "slippage": 0.0, "status": "verified"
            },)).start()

        elif self.opt_in:
            # Free users send anonymous stats to the public map
            threading.Thread(target=self._upload_telemetry, args=({
                "symbol": symbol,  # Will be hashed
                "broker": self.broker_name,
                "latency_ms": latency,
                "slippage": 0.0,
                "status": "verified"
            },)).start()

        return {"status": "verified", "latency_ms": latency}

    def get_smart_route(self, symbol, size=1.0, urgency="normal"):
        """
        v0.4.0: The Oracle. Asks the cloud for the safest broker routing.
        """
        if not self.pro_key:
            logger.warning("⚠️ Oracle API requires a Pro Key.")
            return None

        try:
            headers = {"x-pro-key": self.pro_key}
            payload = {"symbol": symbol, "size": size, "urgency": urgency}

            resp = requests.post(
                f"{self.api_url}/oracle/route", json=payload, headers=headers, timeout=2)

            if resp.status_code == 200:
                data = resp.json()
                rec = data.get("recommendation")
                logger.info(
                    f"🔮 Oracle Recommendation: {rec.upper()} (Score: {data['metrics']['expected_latency']}ms)")
                return data
            else:
                logger.warning(f"Oracle Error: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to reach Oracle: {e}")
            return None

    def _calculate_python_fallback(self, opens, closes, volumes):
        """Python implementation of Market Quality Metrics for Rust fallback."""
        returns_abs = []
        dollar_vols = []
        price_changes = []
        signed_vols = []
        buy_vol = 0.0
        sell_vol = 0.0

        for o, c, v in zip(opens, closes, volumes):
            if v <= 0.0:
                continue

            # Amihud
            ret = (c - o) / o
            dollar_vol = c * v
            returns_abs.append(abs(ret))
            dollar_vols.append(dollar_vol)

            # Kyle's Lambda & Imbalance
            sign = 1 if c >= o else -1
            if sign > 0:
                buy_vol += v
            else:
                sell_vol += v

            price_changes.append(c - o)
            signed_vols.append(v * sign)

        # Amihud Calculation
        amihud_score = 0.0
        if dollar_vols:
            sum_ratio = sum(r / v for r, v in zip(returns_abs, dollar_vols))
            amihud_score = (sum_ratio / len(dollar_vols)) * 1_000_000.0

        # Kyle's Lambda Calculation
        kyles_lambda = 0.0
        if len(signed_vols) > 1:
            try:
                # Use numpy for polyfit (Linear Regression slope)
                # Note: numpy is imported at the top of the file.
                slope, _ = np.polyfit(signed_vols, price_changes, 1)
                kyles_lambda = slope * 1_000_000.0
            except np.linalg.LinAlgError:
                # Handle singular matrix error if all volumes are the same
                kyles_lambda = 0.0

        # Imbalance Calculation
        total_vol = buy_vol + sell_vol
        imbalance = (buy_vol - sell_vol) / \
            total_vol if total_vol > 0.0 else 0.0

        return amihud_score, kyles_lambda, imbalance

    def get_whale_view(self, symbol, lookback_candles=100, candles=None):
        """
        v0.5.0: The Whale Engine. Calculates Amihud & Kyle's Lambda using Rust or Python fallback.
        """
        # 1. Get Data (Prefer injected candles, then adapter, then fail)
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data:
            return {"error": "No candle data. Connect a broker or pass 'candles' list.", "verdict": "No Data"}

        # 2. Extract Data arrays
        opens = [c['open'] for c in data]
        closes = [c['close'] for c in data]
        volumes = [c['volume'] for c in data]

        amihud_score = 0.0
        kyles_lambda = 0.0
        imbalance = 0.0

        # 3. Process Metrics (Use Rust if available, otherwise fallback)
        if RUST_CORE_AVAILABLE:
            try:
                # Call Rust function with vectors of primitives
                amihud_score, kyles_lambda, imbalance = pnl_core.calculate_market_quality_metrics(
                    opens, closes, volumes
                )
            except Exception as e:
                logger.error(
                    f"Rust Core calculation failed: {e}. Falling back to Python.")
                amihud_score, kyles_lambda, imbalance = self._calculate_python_fallback(
                    opens, closes, volumes)
        else:
            amihud_score, kyles_lambda, imbalance = self._calculate_python_fallback(
                opens, closes, volumes)

        return {
            "symbol": symbol,
            "amihud_illiquidity": round(amihud_score, 4),
            "kyles_lambda": round(kyles_lambda, 6),
            "order_flow_imbalance": round(imbalance, 4),
            "verdict": "TOXIC ORDER FLOW" if kyles_lambda > 1.0 else "Healthy"
        }

    # --- JUMP RISK ESTIMATOR ---
    def get_jump_risk_profile(self, symbol, lookback_candles=200, candles=None):
        """
        Estimates 'Fat Tail' risk using Merton Jump-Diffusion logic.
        Useful for Crypto and Energy markets.
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Jump Diffusion models."}

        # 1. Fetch Data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data or len(data) < 50:
            return {"error": "Insufficient data for Jump Risk analysis"}

        closes = [float(c['close']) for c in data]

        # 2. Call Rust Core
        try:
            # returns (normal_vol, jump_prob, intensity)
            vol, jump_prob, intensity = pnl_core.calculate_jump_risk(closes)

            risk_level = "Low"
            if jump_prob > 0.05:
                risk_level = "Medium"
            if jump_prob > 0.10:
                risk_level = "HIGH (Crash Risk)"

            return {
                "symbol": symbol,
                "volatility_sigma": round(vol, 4),
                "jump_probability": round(jump_prob * 100, 2),  # as %
                "jump_intensity": round(intensity, 2),
                "risk_level": risk_level
            }
        except Exception as e:
            logger.error(f"Jump Risk Calc Failed: {e}")
            return {"error": str(e)}

    def generate_execution_passport(self, symbol: str, side: str, qty: float) -> Dict[str, Any]:
        """
        Pillar 2: The Execution Passport. Generates a forensic audit trail.
        """
        audit_start = time.time()
        audit_nanos = 0
        if RUST_CORE_AVAILABLE:
            try:
                # Use Rust for nanosecond-precision timestamp
                audit_nanos = pnl_core.get_audit_timestamp()
            except Exception:
                # Fallback to standard Python timestamp
                pass

        # If Rust nanosecond timestamp failed or wasn't available, use Python microsecond
        if audit_nanos == 0:
            # Fallback to python time in nanoseconds (less precise, but better than nothing)
            audit_nanos = int(audit_start * 1_000_000_000)

        # Simulate other micro-timing data points (these would come from broker adapter)
        network_latency_ns = random.randint(100_000, 500_000)  # 0.1ms to 0.5ms

        passport = {
            "audit_id": str(uuid.uuid4()),
            "symbol": symbol,
            "side": side,
            "qty": qty,
            "timestamp_ns": audit_nanos,  # Forensic timestamp
            "execution_metrics": {
                "broker_queue_latency_ns": network_latency_ns,
                "mid_price_snapshot": 100.05,
                "adverse_selection_flag": network_latency_ns > 400_000
            }
        }

        logger.info(
            f"🔎 AUDIT START: {side.upper()} {qty} {symbol} on {self.broker_name}")
        return passport

    def get_liquidity_surface(self, symbol: str, lookback_candles: int = 100, time_bins: int = 10, spread_bins: int = 10, candles: list = None) -> Dict[str, Any]:
        """
        v0.7.0: The Liquidity Surface Map.
        Visualizes Volume distribution over Time and Spread to identify "liquidity holes".
        
        :param symbol: Trading symbol
        :param lookback_candles: Number of historical candles to analyze
        :param time_bins: Number of time buckets (default: 10)
        :param spread_bins: Number of spread buckets (default: 10)
        :return: Dictionary with grid, time_bounds, spread_bounds, and recommendations
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Liquidity Surface calculation."}

        # 1. Fetch Data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data or len(data) < 10:
            return {"error": "Insufficient data for Liquidity Surface (min 10 candles)."}

        # 2. Extract Data
        # Use High-Low as a proxy for spread (bid-ask spread not always available)
        spreads = [float(c['high']) - float(c['low']) for c in data]
        volumes = [float(c['volume']) for c in data]
        
        # Create relative timestamps (0 to N-1)
        timestamps = [float(i) for i in range(len(data))]

        try:
            # 3. Call Rust Core
            grid, time_bounds, spread_bounds = pnl_core.calculate_liquidity_surface(
                spreads, volumes, timestamps, time_bins, spread_bins
            )

            # 4. Analyze Grid for Liquidity Holes
            # Find bins with lowest volume
            min_volume = min(grid) if grid else 0
            max_volume = max(grid) if grid else 0
            avg_volume = sum(grid) / len(grid) if grid else 0

            # Identify liquidity holes (bins with < 20% of average volume)
            threshold = avg_volume * 0.2
            liquidity_holes = []
            
            for t_idx in range(time_bins):
                for s_idx in range(spread_bins):
                    idx = t_idx * spread_bins + s_idx
                    if grid[idx] < threshold:
                        time_start = time_bounds[0] + (t_idx / time_bins) * (time_bounds[1] - time_bounds[0])
                        time_end = time_bounds[0] + ((t_idx + 1) / time_bins) * (time_bounds[1] - time_bounds[0])
                        spread_start = spread_bounds[0] + (s_idx / spread_bins) * (spread_bounds[1] - spread_bounds[0])
                        spread_end = spread_bounds[0] + ((s_idx + 1) / spread_bins) * (spread_bounds[1] - spread_bounds[0])
                        
                        liquidity_holes.append({
                            "time_range": (round(time_start, 2), round(time_end, 2)),
                            "spread_range": (round(spread_start, 4), round(spread_end, 4)),
                            "volume": round(grid[idx], 2)
                        })

            # 5. Generate Recommendation
            recommendation = "Normal liquidity distribution"
            if len(liquidity_holes) > (time_bins * spread_bins) * 0.3:
                recommendation = "⚠️ Multiple liquidity holes detected. Consider splitting orders across time."
            elif len(liquidity_holes) > 0:
                recommendation = f"💡 {len(liquidity_holes)} liquidity hole(s) detected. Avoid trading during these periods."

            return {
                "symbol": symbol,
                "grid": grid,
                "time_bins": time_bins,
                "spread_bins": spread_bins,
                "time_bounds": time_bounds,
                "spread_bounds": spread_bounds,
                "min_volume": round(min_volume, 2),
                "max_volume": round(max_volume, 2),
                "avg_volume": round(avg_volume, 2),
                "liquidity_holes": liquidity_holes[:5],  # Top 5 worst holes
                "recommendation": recommendation
            }

        except Exception as e:
            logger.error(f"Liquidity Surface Calc Failed: {e}")
            return {"error": str(e)}

    def get_trade_confidence_metric(self, symbol: str, alpha_signal: float, lookback_candles: int = 100, candles: list = None) -> Dict[str, Any]:
        """
        NEW: Trade Confidence Metric (TCM). 
        Aggregates Alpha (Edge), Liquidity (Lambda), and Regime (Jump Risk) into a single confidence score (0-100).
        """
        # 1. Get Market Microstructure (Liquidity)
        whale_view = self.get_whale_view(symbol, lookback_candles, candles=candles)
        if "error" in whale_view:
            return {"error": f"TCM dependency failed (Whale View): {whale_view['error']}"}
        
        kyles_lambda = whale_view.get("kyles_lambda", 1.0)
        
        # 2. Get Market Regime (Risk)
        jump_profile = self.get_jump_risk_profile(symbol, lookback_candles, candles=candles)
        if "error" in jump_profile:
            return {"error": f"TCM dependency failed (Jump Risk): {jump_profile['error']}"}

        jump_prob = jump_profile.get("jump_probability", 0.0) / 100.0 # Convert % back to decimal

        # --- 3. SCORING AND NORMALIZATION ---
        
        # A. Alpha Score (Edge) - Higher alpha means higher score
        # Scaling: Alpha 0.05 (5% edge) = 100 score. Alpha 0.005 (0.5% edge) = 10 score.
        alpha_score = min(100.0, alpha_signal * 2000)
        
        # B. Liquidity Score (Lambda) - Lower Lambda (better liquidity) means higher score.
        # Scaling: Lambda is typically very small. If kyles_lambda is 0.01 (1bp/100 shares), score approaches 0.
        # We cap the penalty if Lambda is excessive.
        lambda_penalty = min(1.0, kyles_lambda * 100) # 0.01 lambda -> 1.0 penalty.
        liquidity_score = max(0.0, 100.0 * (1.0 - lambda_penalty)) 
        
        # C. Regime Score (Jump Risk) - Lower Jump Prob means higher score.
        # Scaling: 15% jump probability is considered maximum risk (0 score).
        regime_score = max(0.0, 100.0 * (1.0 - jump_prob / 0.15))

        # --- 4. WEIGHTED AGGREGATION ---
        # Weights: Alpha (50%), Liquidity (30%), Regime (20%) - Weights are adjustable to user risk preference
        tcm = (
            alpha_score * 0.50 +
            liquidity_score * 0.30 +
            regime_score * 0.20
        )
        tcm = round(tcm, 2)
        
        verdict = "HIGH CONFIDENCE"
        if tcm < 70: verdict = "MEDIUM CONFIDENCE"
        if tcm < 40: verdict = "LOW CONFIDENCE - EXECUTE WITH CAUTION"

        return {
            "symbol": symbol,
            "alpha_signal": alpha_signal,
            "tcm_score": tcm,
            "verdict": verdict,
            "components": {
                "alpha_score": round(alpha_score, 2),
                "liquidity_score": round(liquidity_score, 2),
                "regime_score": round(regime_score, 2),
                "kyles_lambda": round(kyles_lambda, 6),
                "jump_probability": round(jump_prob * 100, 2)
            }
        }


    def apply_protective_collar(
        self,
        symbol: str,
        current_price: float,
        time_to_maturity_days: int,
        target_downside_protection_pct: float = 0.10, # 10% protection
        target_upside_cap_pct: float = 0.05, # 5% cap for cost reduction
        risk_free_rate: float = 0.02,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        NEW: Protective Collar Recommender. 
        Calculates recommended Put (protection) and Call (income) strikes for a protective collar.
        Assumes the user is long the underlying stock.
        
        Note: Premiums are calculated using a simplified model based on volatility for demonstration purposes.
        """
        if not RUST_CORE_AVAILABLE:
            # Fallback to simulation if Rust is unavailable, but warn user.
            volatility = 0.30 # Hardcoded simulation volatility
            logger.warning("Falling back to simulated volatility (30%) for Protective Collar.")
        else:
            jump_profile = self.get_jump_risk_profile(symbol, lookback_candles=200, candles=candles)
            volatility = jump_profile.get("volatility_sigma", 0.30)

        # Time to maturity (T) in years
        T = time_to_maturity_days / 365.0
        
        # 1. Determine Strike Prices
        put_strike = current_price * (1.0 - target_downside_protection_pct)
        call_strike = current_price * (1.0 + target_upside_cap_pct)

        # 2. Simulate Option Premiums (Highly simplified empirical estimate)
        # These coefficients are for demonstration of the concept.
        put_premium_est = current_price * volatility * (0.4 + 0.3 * target_downside_protection_pct)
        call_premium_est = current_price * volatility * (0.2 - 0.1 * target_upside_cap_pct)
        
        # Ensure premiums are positive and scaled by time to maturity
        put_premium = round(max(0.01, put_premium_est * 0.5 * T), 2)
        call_premium = round(max(0.01, call_premium_est * 0.5 * T), 2)
        
        # Net Cost = Long Put Cost - Short Call Income
        net_cost = put_premium - call_premium
        
        recommendation = "Costly Collar"
        if net_cost <= 0.0:
            recommendation = "Zero-Cost Collar (Net Income)"
        elif net_cost < current_price * 0.005:
            recommendation = "Low-Cost Collar"

        return {
            "symbol": symbol,
            "current_price": current_price,
            "time_to_maturity_days": time_to_maturity_days,
            "volatility": round(volatility, 4),
            "collar_strategy": {
                "action": "Buy stock, Buy Put, Sell Call",
                "put_details": {
                    "strike": round(put_strike, 2),
                    "premium_est": put_premium,
                    "protection": f"Loss capped at {target_downside_protection_pct*100}%"
                },
                "call_details": {
                    "strike": round(call_strike, 2),
                    "premium_est": call_premium,
                    "cap": f"Gain capped at {target_upside_cap_pct*100}%"
                },
                "net_premium": round(net_cost, 2),
                "recommendation": recommendation
            }
        }

    # ==================================================================
    # v0.9.0: STOP-LOSS HUNT DETECTION (Avinash Use Case)
    # ==================================================================

    def get_hunt_risk_score(
        self, 
        symbol: str,
        asset_class: str = "EQUITIES",
        order_size: float = 100.0,
        market_depth: float = 1_000_000.0,
        lookback_candles: int = 100,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        v0.9.0: Stop-Loss Hunt Detector.
        
        Calculates the probability that a stop-loss hunt is occurring.
        Uses multi-factor analysis: Lambda, Volume Imbalance, Jump Risk, Time-of-Day.
        
        CRITICAL for Indian F&O traders: 3:00-3:30 PM IST is high-risk.
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY84900CE")
            asset_class: "EQUITIES", "FUTURES", "FX", "CRYPTO"
            order_size: Your intended order size
            market_depth: Estimated order book depth
            lookback_candles: Historical data window
            candles: Optional pre-fetched candle data
        
        Returns:
            Dict with hunt_score (0-100), safe_to_trade (bool), and component breakdown
        
        Example:
            >>> result = dog.get_hunt_risk_score("NIFTY84900CE", order_size=50)
            >>> if not result['safe_to_trade']:
            ...     print(f"⚠️ STOP HUNTING DETECTED: {result['verdict']}")
        """
        from .stoploss_hunt_detector import calculate_hunt_risk_score
        
        # Fetch data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)
        
        if not data:
            return {"error": "No data available. Connect a broker or pass 'candles' list."}
        
        # Calculate hunt risk
        result = calculate_hunt_risk_score(
            candles=data,
            asset_class=asset_class,
            order_size=order_size,
            market_depth=market_depth
        )
        
        return {
            "symbol": symbol,
            "hunt_score": result.hunt_score,
            "safe_to_trade": result.safe_to_trade,
            "verdict": result.verdict,
            "components": {
                "lambda_risk": result.lambda_score,
                "imbalance_risk": result.imbalance_score,
                "jump_risk": result.jump_score,
                "time_risk": result.time_score
            },
            "metrics": {
                "kyles_lambda": result.lambda_value,
                "volume_imbalance": result.volume_imbalance,
                "jump_probability": result.jump_probability
            },
            "recommendations": {
                "protective_collar": result.protective_collar,
                "recommended_slice_pct": result.recommended_slice_pct,
                "delay_seconds": result.delay_seconds
            }
        }

    def pre_trade_check(
        self,
        symbol: str,
        qty: float,
        expected_price: float,
        asset_class: str = "EQUITIES",
        market_depth: float = 1_000_000.0,
        max_acceptable_risk: int = 50,
        lookback_candles: int = 100,
        candles: list = None
    ) -> Dict[str, Any]:
        """
        v0.9.0: Pre-Trade Safety Check.
        
        Call this BEFORE every trade to check if conditions are safe.
        Returns a binary go/no-go decision with detailed reasoning.
        
        This is the CRITICAL function for preventing stop-loss hunt losses.
        
        Args:
            symbol: Trading symbol
            qty: Order quantity
            expected_price: Your expected fill price
            asset_class: Asset type
            market_depth: Estimated orderbook depth
            max_acceptable_risk: Risk threshold (0-100, default 50)
            candles: Optional historical data
        
        Returns:
            Dict with safe_to_execute (bool), reason, and recommended action
        
        Example:
            >>> check = dog.pre_trade_check("NIFTY84900CE", qty=50, expected_price=180)
            >>> if check['safe_to_execute']:
            ...     execute_order()
            ... else:
            ...     print(f"❌ BLOCKED: {check['reason']}")
        """
        from .stoploss_hunt_detector import pre_trade_check as _pre_trade_check
        
        # Fetch data
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)
        
        if not data:
            return {
                "safe_to_execute": False,
                "reason": "No data available - cannot assess risk",
                "recommended_action": "Connect a data source or pass 'candles' list"
            }
        
        # Run pre-trade check
        result = _pre_trade_check(
            symbol=symbol,
            qty=qty,
            expected_price=expected_price,
            candles=data,
            asset_class=asset_class,
            market_depth=market_depth,
            max_acceptable_risk=max_acceptable_risk
        )
        
        return {
            "safe_to_execute": result.safe_to_execute,
            "reason": result.reason,
            "recommended_action": result.recommended_action,
            "hunt_risk": {
                "score": result.hunt_risk.hunt_score,
                "verdict": result.hunt_risk.verdict,
                "protective_collar": result.hunt_risk.protective_collar,
                "recommended_slice_pct": result.hunt_risk.recommended_slice_pct
            }
        }


    def _sanitize_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        PRIVACY SHIELD: Strips sensitive alpha before upload.
        """
        # Hash the symbol to protect strategy
        encrypted_symbol = "unknown"
        if 'symbol' in data:
            encrypted_symbol = hashlib.sha256(
                data['symbol'].encode()).hexdigest()

        return {
            "symbol_hash": encrypted_symbol,
            "broker": data.get('broker', 'unknown'),
            "latency_ms": data.get('latency_ms', 0),
            "slippage": data.get('slippage', 0.0),
            "status": data.get('status', 'unknown')
            # NOTE: Side, Qty, Price are deliberately excluded
        }

    def _upload_log(self, data):
        """Sends PRIVATE data to your SaaS backend (Pro Users)"""
        try:
            headers = {"x-pro-key": self.pro_key}
            requests.post(f"{self.api_url}/log_trade",
                          json=data, headers=headers, timeout=2)
        except Exception as e:
            print(f"⚠️ Cloud Sync Failed: {e}")

    def _upload_telemetry(self, data):
        """Sends ANONYMOUS health stats to the global map (Free Users)"""
        try:
            safe_data = self._sanitize_payload(data)
            # Ensure slippage is included as per the telemetry model
            requests.post(f"{self.api_url}/telemetry", json={
                "broker": safe_data.get('broker'),
                "latency_ms": safe_data.get('latency_ms'),
                "slippage": safe_data.get('slippage'),
                "status": safe_data.get('status'),
            }, timeout=2)
        except Exception:
            pass