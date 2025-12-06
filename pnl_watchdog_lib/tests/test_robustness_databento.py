"""
Robustness and Scale Test for PnL Watchdog using DataBento

This script simulates a high-frequency trading environment by replaying
historical market data from DataBento as if it were a live stream.

It tests:
1. Robustness: Can the system handle a continuous stream of data without crashing?
2. Scale: What is the latency per calculation? Can it handle high throughput?
3. Adaptation: Does the risk score adapt to changing market conditions (volatility)?
"""

import os
import sys
import time
import statistics
import logging
from datetime import datetime
# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pnl_watchdog.brokers.databento import DatabentoAdapter
from pnl_watchdog.stoploss_hunt_detector import calculate_hunt_risk_score, HuntRiskResult

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('robustness_test.log')
    ]
)
logger = logging.getLogger("RobustnessTest")

def load_env_file(filepath):
    """Manually load .env file"""
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()
    except Exception as e:
        logger.error(f"Error loading .env file: {e}")

def run_stress_test():
    # 1. Load Configuration
    env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../src/.env'))
    load_env_file(env_path)
    
    api_key = os.getenv("DATABENTO_API_KEY")
    
    if not api_key:
        logger.error("❌ DATABENTO_API_KEY not found in environment.")
        return

    logger.info(f"✅ Loaded DataBento API Key: {api_key[:4]}...{api_key[-4:]}")
    
    # 2. Initialize Adapter
    adapter = DatabentoAdapter(api_key)
    symbol = "SPY"  # Highly liquid ETF, good for stress testing
    
    logger.info(f"📥 Fetching data for {symbol}...")
    try:
        # Fetch 200 candles to have enough history for the sliding window
        all_candles = adapter.get_candles(symbol, lookback=200)
    except Exception as e:
        logger.error(f"❌ Failed to fetch data: {e}")
        return

    if not all_candles:
        logger.error("❌ No data returned from DataBento.")
        return

    logger.info(f"✅ Fetched {len(all_candles)} candles.")

    # 3. Run Simulation
    logger.info("🚀 Starting Stress Test (Simulating Live Feed)...")
    
    latencies = []
    risk_scores = []
    verdicts = {}
    
    # Sliding window simulation
    window_size = 50
    
    start_time = time.time()
    
    for i in range(window_size, len(all_candles)):
        # Simulate receiving a new candle
        current_window = all_candles[i-window_size : i]
        current_candle = current_window[-1]
        
        # Measure calculation latency
        calc_start = time.perf_counter()
        
        result: HuntRiskResult = calculate_hunt_risk_score(
            candles=current_window,
            asset_class="EQUITIES",
            order_size=1000,
            market_depth=1000000
        )
        
        calc_end = time.perf_counter()
        latency_ms = (calc_end - calc_start) * 1000
        latencies.append(latency_ms)
        
        # Store results
        risk_scores.append(result.hunt_score)
        verdicts[result.verdict] = verdicts.get(result.verdict, 0) + 1
        
        # Log adaptation (only if score changes significantly or periodically)
        if i % 10 == 0 or result.hunt_score > 50:
            logger.info(
                f"Tick {i}: Price={current_candle['close']:.2f} | "
                f"Score={result.hunt_score:.1f} ({result.verdict}) | "
                f"Lambda={result.lambda_value:.6f} | "
                f"Latency={latency_ms:.3f}ms"
            )

    total_duration = time.time() - start_time
    
    # 4. Analyze Results
    avg_latency = statistics.mean(latencies)
    max_latency = max(latencies)
    p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
    score_variance = statistics.variance(risk_scores) if len(risk_scores) > 1 else 0
    
    logger.info("\n" + "="*50)
    logger.info("📊 STRESS TEST RESULTS")
    logger.info("="*50)
    logger.info(f"Total Ticks Processed: {len(latencies)}")
    logger.info(f"Total Duration:        {total_duration:.2f}s")
    logger.info("-" * 30)
    logger.info("⚡ SCALE / PERFORMANCE")
    logger.info(f"Average Latency:       {avg_latency:.3f} ms")
    logger.info(f"Max Latency:           {max_latency:.3f} ms")
    logger.info(f"99th %ile Latency:     {p99_latency:.3f} ms")
    logger.info(f"Throughput:            {len(latencies)/total_duration:.1f} ticks/sec")
    logger.info("-" * 30)
    logger.info("🛡️ ADAPTATION / ROBUSTNESS")
    logger.info(f"Risk Score Variance:   {score_variance:.2f}")
    logger.info(f"Min Risk Score:        {min(risk_scores):.1f}")
    logger.info(f"Max Risk Score:        {max(risk_scores):.1f}")
    logger.info("Verdict Distribution:")
    for v, count in verdicts.items():
        logger.info(f"  - {v}: {count}")
    logger.info("="*50)
    
    # Assertions for CI/CD
    if avg_latency > 50:
        logger.error("❌ FAILED: Average latency > 50ms")
    else:
        logger.info("✅ PASSED: Latency check (<50ms)")
        
    if score_variance == 0:
        logger.warning("⚠️ WARNING: No score variation. System might be static.")
    else:
        logger.info("✅ PASSED: Adaptation check (score variance > 0)")

if __name__ == "__main__":
    run_stress_test()
