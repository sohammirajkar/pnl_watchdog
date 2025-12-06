import sys
import os
import time
import random

# Add the current directory to the Python path to ensure 'from .ai_brain import AIBrain' 
# and other relative imports work, especially if the file is run directly.
# Note: In a real project, watchdog.py should be part of a package.
sys.path.insert(0, os.path.dirname(__file__))

# --- MOCK DEPENDENCIES ---
# Since we don't have the real pnl_core or AIBrain, we mock them for testing PnLWatchdog logic.
class MockAIBrain:
    """Mock for AIBrain to allow PnLWatchdog initialization."""
    def __init__(self):
        print("Mock AIBrain Initialized.")

class MockPnLCore:
    """Mock for the Rust library 'pnl_core' to test PnLWatchdog's integration logic."""
    
    # Mock for get_whale_view
    def calculate_market_quality_metrics(self, opens, closes, volumes):
        # Return sensible default values for testing the Python class logic
        amihud_score = 0.05
        kyles_lambda = 0.0005 * random.random() # Simulate a small lambda
        imbalance = 0.1
        return amihud_score, kyles_lambda, imbalance

    # Mock for get_jump_risk_profile
    def calculate_jump_risk(self, closes):
        # Return (vol, jump_prob, intensity)
        vol = 0.015
        jump_prob = 0.02 # 2% chance
        intensity = 0.5
        return vol, jump_prob, intensity

    # Mock for get_dynamic_execution_plan
    def calculate_kyle_lambda_asset_specific(self, asset_class, total_qty, vol, market_depth):
        # Simulate a calculated lambda
        return 0.0000001 + total_qty / market_depth * vol
    
    def calculate_dynamic_execution_params(self, alpha_signal, total_qty, vol, asset_specific_lambda, base_risk_aversion, alpha_sensitivity):
        # Simulate an optimal slice and effective gamma
        optimal_slice = total_qty * (0.1 + alpha_signal * alpha_sensitivity * 0.1)
        effective_gamma = base_risk_aversion + alpha_signal * alpha_sensitivity
        return optimal_slice, effective_gamma

    # Mock for generate_execution_passport
    def get_audit_timestamp(self):
        return int(time.time() * 1_000_000_000)

    # Mock for get_liquidity_surface
    def calculate_liquidity_surface(self, spreads, volumes, timestamps, time_bins, spread_bins):
        # Simulate a 10x10 grid of random volume data
        grid = [random.uniform(100.0, 5000.0) for _ in range(time_bins * spread_bins)]
        time_bounds = [0.0, 100.0]
        spread_bounds = [0.001, 0.05]
        return grid, time_bounds, spread_bounds

    # Mock for stream_lambda (just print the intent)
    def stream_lambda_udp(self, asset_class, lambda_value, ip, port):
        print(f"UDP MOCK: Streaming {lambda_value} to {ip}:{port}")
        
    # Mock for the new lambda_gap (from lib.rs)
    def calculate_lambda_gap(self, current_allocation, demand, lambda_factor):
        return (1.0 - current_allocation / demand).abs() * lambda_factor if demand > 0 else 0.0


# Overwrite the missing components with Mocks before importing PnLWatchdog
global AIBrain
AIBrain = MockAIBrain

global RUST_CORE_AVAILABLE
RUST_CORE_AVAILABLE = True # Assume Rust is working for the test

# Overwrite the pnl_core module import with the mock class
# This assumes the relative import in watchdog.py is handled correctly by the runtime
# When running this script, we must ensure MockPnLCore is used if the real Rust lib is missing.
try:
    import pnl_core
except ImportError:
    pnl_core = MockPnLCore()
    print("WARNING: Real pnl_core not found. Using MockPnLCore for testing.")


# Import the class after setting up mocks
from pnl_watchdog.watchdog import PnLWatchdog

# --- TEST DATA ---
SYMBOL = "NVDA"
PRICE = 800.0
QTY = 1000.0
ALPHA = 0.007 # 0.7% edge

# A set of mock candles for local testing
# Generate 100 mock candles
MOCK_CANDLES = []
base_price = 100.0
for i in range(100):
    change = random.uniform(-0.5, 0.5)
    close = base_price + change
    high = max(base_price, close) + random.uniform(0, 0.2)
    low = min(base_price, close) - random.uniform(0, 0.2)
    vol = random.uniform(1000, 50000)
    MOCK_CANDLES.append({
        'open': base_price,
        'close': close,
        'high': high,
        'low': low,
        'volume': vol
    })
    base_price = close


def run_tests():
    print("-" * 50)
    print(f"🚀 Running PnL Watchdog Integration Tests for {SYMBOL}")
    print("-" * 50)

    # 1. Configuration for Live Data
    use_live_data = os.getenv("USE_LIVE_DATA", "False").lower() == "true"
    broker_name = os.getenv("BROKER", "alpaca")
    api_key = os.getenv("API_KEY")
    api_secret = os.getenv("API_SECRET")

    watchdog = None
    candles_to_use = MOCK_CANDLES

    if use_live_data:
        print(f"\n[INIT] 🔌 Connecting to LIVE BROKER: {broker_name}...")
        try:
            # Initialize with credentials
            watchdog = PnLWatchdog(
                broker=broker_name, 
                api_key=api_key, 
                api_secret=api_secret
            )
            
            # Attempt to fetch live candles
            print(f"[DATA] 📥 Fetching live candles for {SYMBOL}...")
            if watchdog.adapter:
                live_candles = watchdog.adapter.get_candles(SYMBOL, 100)
                if live_candles and len(live_candles) > 0:
                    print(f"[DATA] ✅ Successfully fetched {len(live_candles)} live candles.")
                    candles_to_use = live_candles
                else:
                    print("[WARN] ⚠️ No candles returned from broker. Falling back to MOCK data.")
            else:
                print("[WARN] ⚠️ Adapter not initialized. Falling back to MOCK data.")
                
        except Exception as e:
            print(f"[ERROR] ❌ Failed to connect or fetch data: {e}")
            print("[INFO] Falling back to test_mode with MOCK data.")
            watchdog = PnLWatchdog(broker="test_mode")
    else:
        print("\n[INIT] 🧪 Running in TEST MODE (Mock Data).")
        print("       To use live data, set env vars: USE_LIVE_DATA=true, BROKER=..., API_KEY=...")
        watchdog = PnLWatchdog(broker="test_mode")

    print("\n[INIT] Watchdog initialized.")

    # 2. Test Whale View (Kyle's Lambda)
    print("\n[TEST 1] Whale View (Liquidity)")
    whale_result = watchdog.get_whale_view(SYMBOL, candles=MOCK_CANDLES)
    print(f"  Result: {whale_result.get('verdict')}")
    print(f"  Lambda: {whale_result.get('kyles_lambda')}")
    assert 'kyles_lambda' in whale_result, "Whale view failed."
    

    # 3. Test Market Regime (Jump Risk)
    print("\n[TEST 2] Market Regime (Jump Risk)")
    regime_result = watchdog.get_market_regime(SYMBOL, candles=candles_to_use)
    print(f"  Regime: {regime_result.get('regime')}")
    print(f"  Jump Prob: {regime_result.get('metrics', {}).get('jump_probability')}%")
    assert 'regime' in regime_result, "Regime check failed."
    

    # 4. Test Dynamic Execution Plan (Almgren-Chriss/Alpha)
    print("\n[TEST 3] Dynamic Execution Plan")
    exec_plan = watchdog.get_dynamic_execution_plan(
        symbol=SYMBOL, asset_class="EQUITIES", total_qty=QTY, alpha_signal=ALPHA, candles=candles_to_use
    )
    slice_qty = exec_plan.get('recommended_slice')
    print(f"  Slice: {slice_qty}")
    assert slice_qty is not None and slice_qty > 0, "Execution plan failed."


    # 5. Test NEW: Trade Confidence Metric (TCM)
    print("\n[TEST 4] Trade Confidence Metric (TCM)")
    tcm_result = watchdog.get_trade_confidence_metric(SYMBOL, alpha_signal=ALPHA, candles=candles_to_use)
    print(f"  Full Result: {tcm_result}")
    print(f"  TCM Score: {tcm_result.get('tcm_score')}")
    print(f"  Verdict: {tcm_result.get('verdict')}")
    assert 'tcm_score' in tcm_result and tcm_result.get('tcm_score') > 0, "TCM failed."


    # 6. Test NEW: Protective Collar
    print("\n[TEST 5] Protective Collar Recommender")
    collar_result = watchdog.apply_protective_collar(
        symbol=SYMBOL, current_price=PRICE, time_to_maturity_days=90, 
        target_downside_protection_pct=0.10, target_upside_cap_pct=0.03, candles=candles_to_use
    )
    net_cost = collar_result.get('collar_strategy', {}).get('net_premium')
    put_strike = collar_result.get('collar_strategy', {}).get('put_details', {}).get('strike')
    print(f"  Put Strike: {put_strike}")
    print(f"  Net Cost: {net_cost}")
    assert net_cost is not None and put_strike is not None, "Protective Collar failed."
    
    
    # 7. Test Liquidity Surface
    print("\n[TEST 6] Liquidity Surface")
    surface_result = watchdog.get_liquidity_surface(SYMBOL, candles=candles_to_use)
    print(f"  Recommendation: {surface_result.get('recommendation')}")
    assert 'grid' in surface_result, "Liquidity Surface failed."
    

    print("\n" + "=" * 50)
    print("✅ All Watchdog functions tested successfully!")
    print("=" * 50)


if __name__ == "__main__":
    # Temporarily replace sys.modules for a clean mock environment
    # This is a hack required because the import structure is non-standard for a test environment
    # sys.modules['pnl_core'] = MockPnLCore()
    
    # Reload the watchdog module to ensure it picks up the mock pnl_core correctly
    # Note: In a real project, use a proper testing framework like pytest.
    import importlib
    # importlib.reload(sys.modules['pnl_watchdog.watchdog'])

    run_tests()