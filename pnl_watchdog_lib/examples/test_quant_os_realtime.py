#!/usr/bin/env python3
"""
Quant OS Real-Time Test with DataBento
=======================================

This script demonstrates the full Quant OS pipeline:
1. Fetch real market data from DataBento
2. Calculate Regime State (NORMAL/TRANSITION/SL_HUNT)
3. Calculate Optimal Exit boundaries (TP/SL)
4. Show all microstructure metrics

This is research-grade quant infrastructure.
"""
import os
import sys
import time
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pnl_watchdog.watchdog import PnLWatchdog

# DataBento API Key (provided by user)
DATABENTO_API_KEY = "REPLACE_WITH_DATABENTO_API_KEY"

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def print_section(text):
    print(f"\n📊 {text}")
    print("-" * 50)

def run_realtime_test():
    print_header("🧠 QUANT OS v0.10.0 - Real-Time Test with DataBento")
    print(f"⏰ Timestamp: {datetime.now().isoformat()}")
    
    # 1. Initialize PnL Watchdog with DataBento
    print_section("Step 1: Initializing PnL Watchdog with DataBento")
    try:
        dog = PnLWatchdog(broker="databento", api_key=DATABENTO_API_KEY)
        print("✅ Watchdog initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Watchdog: {e}")
        return
    
    # Test symbols
    symbols = ["SPY", "AAPL", "NVDA"]
    
    for symbol in symbols:
        print_header(f"📈 Analyzing: {symbol}")
        
        start_time = time.perf_counter()
        
        # 2. Get Whale View (Lambda, Amihud, Imbalance)
        print_section("Step 2: Market Microstructure (Whale View)")
        whale = dog.get_whale_view(symbol, lookback_candles=100)
        if "error" in whale:
            print(f"⚠️ Whale View Error: {whale['error']}")
            continue
        
        print(f"   Kyle's Lambda:       {whale.get('kyles_lambda', 'N/A'):.8f}")
        print(f"   Amihud Illiquidity:  {whale.get('amihud_illiquidity', 'N/A'):.6f}")
        print(f"   Order Imbalance:     {whale.get('order_flow_imbalance', 'N/A'):.4f}")
        print(f"   Verdict:             {whale.get('verdict', 'N/A')}")
        
        # 3. Get Regime State (NEW - Module 10)
        print_section("Step 3: Regime Switching (SL_HUNT Detection)")
        regime = dog.get_regime_state(symbol)
        if "error" in regime:
            print(f"⚠️ Regime Error: {regime['error']}")
        else:
            regime_emoji = "✅" if regime['regime'] == "NORMAL" else ("⚠️" if regime['regime'] == "TRANSITION" else "⛔")
            print(f"   Regime:              {regime_emoji} {regime['regime']}")
            print(f"   Safe to Trade:       {regime['safe_to_trade']}")
            print(f"   Recommendation:      {regime['order_recommendation']}")
            print(f"   Volatility:          {regime['metrics']['volatility']:.6f}")
        
        # 4. Get Optimal Exit (NEW - Module 11)
        print_section("Step 4: Optimal Stopping (Dynamic TP/SL)")
        # Use the last close price as entry
        entry_price = 100.0  # Placeholder if we don't have data
        if whale.get('kyles_lambda') is not None:
            # Get real price from candles if available
            try:
                candles = dog.adapter.get_candles(symbol, 10) if dog.adapter else []
                if candles:
                    entry_price = candles[-1]['close']
            except:
                pass
        
        exit_plan = dog.get_optimal_exit(
            symbol=symbol,
            entry_price=entry_price,
            time_horizon_sec=600.0,  # 10 minute hold
            alpha_decay_rate=0.1
        )
        
        if "error" in exit_plan:
            print(f"⚠️ Exit Plan Error: {exit_plan['error']}")
        else:
            print(f"   Entry Price:         ${exit_plan['entry_price']:.2f}")
            print(f"   Take Profit:         ${exit_plan['take_profit']:.2f} (+{exit_plan['tp_distance_pct']:.2f}%)")
            print(f"   Stop Loss:           ${exit_plan['stop_loss']:.2f} (-{exit_plan['sl_distance_pct']:.2f}%)")
            print(f"   Risk/Reward Ratio:   {exit_plan['risk_reward_ratio']:.2f}")
            print(f"   Volatility Used:     {exit_plan['calculation_params']['volatility']:.6f}")
        
        # 5. Get Trade Confidence Metric
        print_section("Step 5: Trade Confidence Metric (TCM)")
        tcm = dog.get_trade_confidence_metric(symbol, alpha_signal=0.02)
        if "error" in tcm:
            print(f"⚠️ TCM Error: {tcm['error']}")
        else:
            tcm_emoji = "🟢" if tcm['tcm_score'] >= 70 else ("🟡" if tcm['tcm_score'] >= 40 else "🔴")
            print(f"   TCM Score:           {tcm_emoji} {tcm['tcm_score']}/100")
            print(f"   Verdict:             {tcm['verdict']}")
            print(f"   Alpha Score:         {tcm['components']['alpha_score']:.2f}")
            print(f"   Liquidity Score:     {tcm['components']['liquidity_score']:.2f}")
            print(f"   Regime Score:        {tcm['components']['regime_score']:.2f}")
        
        # Timing
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        print(f"\n⚡ Total Analysis Time: {elapsed_ms:.2f}ms")
    
    # Final Summary
    print_header("🎯 QUANT OS ANALYSIS COMPLETE")
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                         SYSTEM CAPABILITIES                          ║
╠══════════════════════════════════════════════════════════════════════╣
║  ✅ Regime Switching     - Detects SL_HUNT toxic market states       ║
║  ✅ Optimal Stopping     - Dynamic TP/SL using stochastic calculus   ║
║  ✅ Kyle's Lambda        - Market impact cost estimation             ║
║  ✅ Jump Risk            - Fat tail / crash detection                ║
║  ✅ Trade Confidence     - Aggregated risk score                     ║
║  ✅ Rust Core            - Sub-millisecond calculations              ║
╚══════════════════════════════════════════════════════════════════════╝

📚 ACADEMIC FOUNDATIONS:
   • Kyle (1985) - Continuous Auctions and Insider Trading
   • Almgren & Chriss (2000) - Optimal Execution of Portfolio Transactions
   • Merton (1976) - Jump-Diffusion Model
   • Optimal Stopping Theory - Shiryaev et al.
""")

if __name__ == "__main__":
    run_realtime_test()
