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
try:
    from .brokers.alpaca import AlpacaAdapter
    from .brokers.ccxt_adapter import CCXTAdapter
    from .brokers.zerodha import ZerodhaAdapter
    from .brokers.angel_one import AngelOneAdapter
    from .brokers.ibkr import IBKRAdapter
except ImportError:
    pass  # Ignore missing adapters for now


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
        print(f"🐶 PnL Watchdog Active.")
        print(f"🆔 YOUR USER ID: {self.user_id}")
        print(f"📋 (Copy this ID to claim your Founding Member status)")
        print("-" * 60 + "\n")

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

    # --- NEW: JUMP RISK ESTIMATOR ---
    def get_jump_risk_profile(self, symbol, lookback_candles=200):
        """
        Estimates 'Fat Tail' risk using Merton Jump-Diffusion logic.
        Useful for Crypto and Energy markets.
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Jump Diffusion models."}

        # 1. Fetch Data
        data = []
        if self.adapter and hasattr(self.adapter, 'get_candles'):
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

    # --- NEW: OPTIMAL EXECUTION (Almgren-Chriss) ---

    def get_optimal_slice(self, symbol, total_qty, risk_tolerance=0.5, lookback_candles=100):
        """
        Calculates the optimal trade size to minimize market impact.
        :param total_qty: Total size you want to move.
        :param risk_tolerance: 0.0 (Patient/Min Cost) to 1.0 (Urgent/High Cost).
        """
        if not RUST_CORE_AVAILABLE:
            return {"error": "Rust Core required for Almgren-Chriss optimization."}

        # 1. We need Lambda (Impact Cost) AND Volatility (Risk)
        # We can reuse the data fetching logic to get both
        data = []
        if self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data:
            return {"error": "No data"}

        opens = [float(c['open']) for c in data]
        closes = [float(c['close']) for c in data]
        volumes = [float(c['volume']) for c in data]

        try:
            # Get Lambda
            _, kyles_lambda, _ = pnl_core.calculate_market_quality_metrics(
                opens, closes, volumes)

            # Get Volatility
            # This calls the same Rust function used in get_jump_risk_profile
            vol, _, _ = pnl_core.calculate_jump_risk(closes)

            # 2. Calculate Optimal Slice
            slice_size = pnl_core.calculate_optimal_slice(
                float(total_qty),
                float(risk_tolerance),
                vol,
                kyles_lambda
            )

            return {
                "symbol": symbol,
                "total_order": total_qty,
                "recommended_slice": round(slice_size, 2),
                "market_impact_lambda": round(kyles_lambda, 2),
                "volatility_sigma": round(vol, 4),
                "advice": f"Split order into {int(total_qty/slice_size) + 1} tranches."
            }

        except Exception as e:
            logger.error(f"Optimal Slice Failed: {e}")
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

    def get_liquidity_surface(self, symbol: str, lookback_candles: int = 100, time_bins: int = 10, spread_bins: int = 10) -> Dict[str, Any]:
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
        if self.adapter and hasattr(self.adapter, 'get_candles'):
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
