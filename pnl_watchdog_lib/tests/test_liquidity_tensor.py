"""
Liquidity Surface Test - Visualizing & Validating the Tensor

This script tests and demonstrates the "Liquidity Surface" (or Liquidity Tensor):
- A 2D heatmap of Volume distribution over Time and Spread
- Uses real DataBento data to identify "liquidity holes"
- Provides actionable execution timing recommendations

What value does it provide to the trader?
1. WHEN to trade: Identifies time windows with thin liquidity
2. WHAT spread to expect: Shows spread ranges with low activity
3. RISK of slippage: Predicts where your order might get stuck
"""

import os
import sys
import time
import logging
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pnl_watchdog.watchdog import PnLWatchdog
from pnl_watchdog.brokers.databento import DatabentoAdapter

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("LiquidityTest")


def load_env():
    """Load API key from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), '../src/.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    os.environ[key] = val


def run_liquidity_surface_test():
    """
    Tests the Liquidity Surface functionality and outputs trader-actionable insights.
    """
    load_env()
    api_key = os.getenv("DATABENTO_API_KEY")
    
    if not api_key:
        logger.error("❌ DATABENTO_API_KEY not found. Please set it in .env")
        return
    
    logger.info(f"✅ Loaded API Key: {api_key[:4]}...{api_key[-4:]}")
    
    # Initialize components
    adapter = DatabentoAdapter(api_key)
    watchdog = PnLWatchdog(adapter=adapter)
    
    symbol = "AAPL"  # Liquid stock for testing
    
    logger.info(f"📥 Fetching candle data for {symbol}...")
    candles = adapter.get_candles(symbol, lookback=100)
    
    if not candles or len(candles) < 10:
        logger.error("❌ Not enough candle data fetched.")
        return
    
    logger.info(f"✅ Fetched {len(candles)} candles.")
    
    # -------------------------------------------------------------------
    # TEST 1: Liquidity Surface Calculation
    # -------------------------------------------------------------------
    logger.info("\n" + "="*60)
    logger.info("🔬 TEST 1: LIQUIDITY SURFACE (TENSOR) CALCULATION")
    logger.info("="*60)
    
    start_time = time.perf_counter()
    surface = watchdog.get_liquidity_surface(symbol, candles=candles, time_bins=5, spread_bins=5)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000
    logger.info(f"Calculation Latency: {latency_ms:.2f} ms")
    
    if "error" in surface:
        logger.error(f"Surface calculation failed: {surface['error']}")
    else:
        logger.info(f"Grid shape: {surface['time_bins']} x {surface['spread_bins']}")
        logger.info(f"Volume range: {surface['min_volume']} - {surface['max_volume']}")
        logger.info(f"Avg Volume: {surface['avg_volume']}")
        logger.info(f"Found {len(surface.get('liquidity_holes', []))} liquidity holes.")
        logger.info(f"Recommendation: {surface.get('recommendation', 'N/A')}")
    
    # -------------------------------------------------------------------
    # TEST 2: Whale View (Kyle's Lambda)
    # -------------------------------------------------------------------
    logger.info("\n" + "="*60)
    logger.info("🐋 TEST 2: WHALE VIEW (KYLE'S LAMBDA)")
    logger.info("="*60)
    
    start_time = time.perf_counter()
    whale = watchdog.get_whale_view(symbol, candles=candles)
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000
    logger.info(f"Calculation Latency: {latency_ms:.2f} ms")
    
    if "error" in whale:
        logger.error(f"Whale view failed: {whale['error']}")
    else:
        logger.info(f"Kyle's Lambda: {whale['kyles_lambda']}")
        logger.info(f"Amihud Illiquidity: {whale['amihud_illiquidity']}")
        logger.info(f"Order Flow Imbalance: {whale['order_flow_imbalance']}")
        logger.info(f"Verdict: {whale['verdict']}")
    
    # -------------------------------------------------------------------
    # TEST 3: Dynamic Execution Plan
    # -------------------------------------------------------------------
    logger.info("\n" + "="*60)
    logger.info("📊 TEST 3: DYNAMIC EXECUTION PLAN")
    logger.info("="*60)
    
    total_qty = 5000
    alpha = 0.02  # 2% expected edge
    
    start_time = time.perf_counter()
    plan = watchdog.get_dynamic_execution_plan(
        symbol=symbol,
        asset_class="EQUITIES",
        total_qty=total_qty,
        alpha_signal=alpha,
        candles=candles
    )
    end_time = time.perf_counter()
    
    latency_ms = (end_time - start_time) * 1000
    logger.info(f"Calculation Latency: {latency_ms:.2f} ms")
    
    if "error" in plan:
        logger.error(f"Execution plan failed: {plan['error']}")
    else:
        logger.info(f"Recommended Slice: {plan['recommended_slice']} (of {total_qty})")
        logger.info(f"Remaining Qty: {plan['remaining_qty']}")
        logger.info(f"Impact Cost Lambda: {plan['microstructure_params']['impact_cost_lambda']}")
        logger.info(f"Volatility Sigma: {plan['microstructure_params']['volatility_sigma']}")
        logger.info(f"Advice: {plan['advice']}")
    
    # -------------------------------------------------------------------
    # SUMMARY: TRADER VALUE
    # -------------------------------------------------------------------
    logger.info("\n" + "="*60)
    logger.info("💰 VALUE FOR THE TRADER")
    logger.info("="*60)
    
    logger.info("""
📌 WHAT THE LIQUIDITY TENSOR TELLS YOU:

1. LIQUIDITY SURFACE (Heatmap):
   - Shows WHERE and WHEN liquidity is thin
   - Identifies "holes" that can swallow your order (slippage)
   - Recommendation: Avoid trading during these windows OR slice smaller

2. KYLE'S LAMBDA (Market Impact):
   - Measures HOW MUCH your order will move the price
   - Higher Lambda = more slippage for large orders
   - Lambda > 0.001 = "Toxic liquidity" (predators may be active)

3. DYNAMIC EXECUTION PLAN (Almgren-Chriss):
   - Calculates the OPTIMAL slice size based on your edge (alpha)
   - Balances "trading fast to capture alpha" vs "minimizing market impact"
   - Adjusts for asset class (equities, futures, FX)

💡 IN PLAIN ENGLISH:
   "Don't dump 5000 shares at once. Start with 500, wait for the 
   liquidity to refill, then slice again. The tensor shows you 
   when the refill is likely to happen."
    """)


if __name__ == "__main__":
    run_liquidity_surface_test()
