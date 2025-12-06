"""
Real-Time Test for PnL Watchdog v0.8.0 with DataBento
Tests Dynamic Execution Plan and Market Regime with high-fidelity market data.
"""
import os
import sys
# Ensure we can import the library
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

from pnl_watchdog.watchdog import PnLWatchdog

def test_databento_features():
    print("\n" + "="*70)
    print("🚀 REAL-TIME TEST: v0.8.0 with DATABENTO")
    print("="*70)
    
    # 1. Initialize Watchdog with DataBento
    # API Key provided by user
    API_KEY = "db-ieJvGbF9HQ3CaMGUuVXLC4YhFcs3Q"
    
    print(f"\n📡 Connecting to DataBento (NASDAQ TotalView)...")
    try:
        dog = PnLWatchdog(
            broker="databento",
            api_key=API_KEY
        )
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return

    symbol = "AAPL" # DataBento uses raw symbols usually, but adapter handles it?
    # Adapter uses 'XNAS.ITCH' dataset and 'raw_symbol' stype.
    # AAPL should work.
    
    print(f"\n📊 Analyzing {symbol}...")
    
    # 2. Test Market Regime (Jump Risk)
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

    # 3. Test Dynamic Execution Plan (v0.8.0 New Feature)
    print(f"\n2. Dynamic Execution Plan (Alpha-Adjusted)")
    print("-" * 40)
    
    # Scenario: We have a strong alpha signal (0.05 = 5% edge) and want to move 5000 shares
    total_qty = 5000.0
    alpha_signal = 0.05
    
    plan = dog.get_dynamic_execution_plan(
        symbol=symbol,
        asset_class="EQUITIES",
        total_qty=total_qty,
        alpha_signal=alpha_signal,
        base_risk_aversion=0.5,
        alpha_sensitivity=5.0
    )
    
    if "error" in plan:
        print(f"❌ Error: {plan['error']}")
    else:
        print(f"   Asset Class: {plan['asset_class']}")
        print(f"   Alpha Signal: {plan['alpha_signal']}")
        print(f"   Microstructure:")
        print(f"     - Lambda (Impact Cost): {plan['microstructure_params']['impact_cost_lambda']:.6f}")
        print(f"     - Volatility (Sigma):   {plan['microstructure_params']['volatility_sigma']:.4f}")
        print(f"     - Eff. Risk Aversion:   {plan['microstructure_params']['effective_risk_aversion']:.4f}")
        print(f"   👉 Recommendation:")
        print(f"      SLICE SIZE: {plan['recommended_slice']} shares")
        print(f"      REMAINING:  {plan['remaining_qty']} shares")
        print(f"      ADVICE:     {plan['advice']}")

    print("\n" + "="*70)
    print("✅ DATABENTO TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_databento_features()
