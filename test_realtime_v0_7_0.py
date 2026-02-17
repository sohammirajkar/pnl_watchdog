"""
Real-Time Test for PnL Watchdog v0.7.0
Tests Market Regime and Execution Plan with live Alpaca data.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))
from pnl_watchdog.watchdog import PnLWatchdog

# API keys are handled in the PnLWatchdog initialization below

def test_realtime_features():
    print("\n" + "="*70)
    print("🚀 REAL-TIME TEST: v0.7.0 FEATURES")
    print("="*70)
    
    # Initialize Watchdog
    dog = PnLWatchdog(
        broker="alpaca",
        api_key=os.getenv("ALPACA_API_KEY", "REPLACE_WITH_ALPACA_API_KEY"),
        api_secret=os.getenv("ALPACA_API_SECRET", "BrQS4dvqCNoGnXBg6iuGAkygYCQHvt23zbzbQxd7FU1n"),
        paper=True
    )
    
    symbol = "AAPL"
    print(f"\n📡 Fetching data for {symbol}...")
    
    # 1. Test Market Regime (Jump Risk)
    print(f"\n1. Market Regime Analysis (Jump Risk)")
    print("-" * 40)
    regime = dog.get_market_regime(symbol, lookback=200)
    
    if "error" in regime:
        print(f"❌ Error: {regime['error']}")
    else:
        print(f"   Status: {regime['regime']}")
        print(f"   Volatility: {regime['metrics']['volatility']:.4f}")
        print(f"   Jump Prob:  {regime['metrics']['jump_probability']}%")
        print(f"   Intensity:  {regime['metrics']['jump_intensity']}")
        
    # 2. Test Execution Plan (Optimal Slicer)
    print(f"\n2. Execution Plan (Almgren-Chriss)")
    print("-" * 40)
    plan = dog.get_execution_plan(symbol, total_qty=1000, risk_aversion=0.5)
    
    if "error" in plan:
        print(f"❌ Error: {plan['error']}")
    else:
        print(f"   Plan Type: {plan['plan']}")
        print(f"   Impact Cost (Lambda): {plan['parameters']['impact_cost_lambda']:.6f}")
        print(f"   Volatility: {plan['parameters']['volatility']:.4f}")
        print(f"   👉 Recommendation:")
        print(f"      TRADE NOW: {plan['recommendation']['trade_now']} shares")
        print(f"      WAIT:      {plan['recommendation']['wait']} shares")

    print("\n" + "="*70)
    print("✅ REAL-TIME TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_realtime_features()
