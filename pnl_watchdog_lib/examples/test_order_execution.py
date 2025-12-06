#!/usr/bin/env python3
"""
Order Execution Test Script
===========================

Tests the new order execution capabilities with Alpaca paper trading.
Demonstrates:
1. Regime-gated execution (blocks SL_HUNT)
2. Auto-calculated TP/SL using Optimal Stopping
3. Bracket orders
"""
import os
import sys

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from pnl_watchdog.watchdog import PnLWatchdog

def print_header(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

def test_execution():
    print_header("🚀 QUANT OS ORDER EXECUTION TEST")
    
    # NOTE: Replace with your Alpaca paper trading credentials
    # Get free paper trading account at https://alpaca.markets
    ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "YOUR_API_KEY")
    ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET", "YOUR_API_SECRET")
    
    if ALPACA_API_KEY == "YOUR_API_KEY":
        print("⚠️ No Alpaca credentials found. Using DataBento for demo only.")
        print("   Set ALPACA_API_KEY and ALPACA_API_SECRET environment variables.")
        print("   Get free paper trading at: https://alpaca.markets")
        
        # Demo with DataBento (read-only)
        dog = PnLWatchdog(
            broker="databento",
            api_key="db-ieJvGbF9HQ3CaMGUuVXLC4YhFcs3Q"
        )
        
        # Show what would happen
        print_header("📊 Demo: Regime Check for AAPL")
        regime = dog.get_regime_state("AAPL")
        print(f"Regime: {regime.get('regime', 'UNKNOWN')}")
        print(f"Safe to Trade: {regime.get('safe_to_trade', 'N/A')}")
        print(f"Recommendation: {regime.get('order_recommendation', 'N/A')}")
        
        print_header("📊 Demo: Optimal Exit for $150 Entry")
        exit_plan = dog.get_optimal_exit("AAPL", entry_price=150.0)
        if 'error' not in exit_plan:
            print(f"Take Profit: ${exit_plan['take_profit']:.2f}")
            print(f"Stop Loss: ${exit_plan['stop_loss']:.2f}")
            print(f"Risk/Reward: {exit_plan['risk_reward_ratio']:.2f}")
        
        print("\n⚠️ To test actual order execution, set your Alpaca credentials!")
        return
    
    # Initialize with Alpaca (paper trading)
    print_header("Step 1: Initialize with Alpaca Paper Trading")
    dog = PnLWatchdog(
        broker="alpaca",
        api_key=ALPACA_API_KEY,
        api_secret=ALPACA_API_SECRET,
        paper=True  # IMPORTANT: Use paper trading!
    )
    print("✅ Connected to Alpaca Paper Trading")
    
    # Check account
    print_header("Step 2: Check Account Info")
    account = dog.get_account()
    print(f"Buying Power: ${account.get('buying_power', 0):,.2f}")
    print(f"Cash: ${account.get('cash', 0):,.2f}")
    print(f"Paper Mode: {account.get('is_paper', 'Unknown')}")
    
    # Check positions
    print_header("Step 3: Check Current Positions")
    positions = dog.get_positions()
    if positions.get('count', 0) > 0:
        for p in positions['positions']:
            print(f"  {p['symbol']}: {p['qty']} shares @ ${p['avg_entry']:.2f} (P&L: ${p['pnl']:.2f})")
    else:
        print("  No open positions")
    
    # Test regime check
    symbol = "AAPL"
    print_header(f"Step 4: Check Regime for {symbol}")
    regime = dog.get_regime_state(symbol)
    print(f"Regime: {regime.get('regime', 'UNKNOWN')}")
    print(f"Safe to Trade: {regime.get('safe_to_trade', False)}")
    
    # Test execute_trade (will be blocked if SL_HUNT, auto TP/SL calculated)
    print_header(f"Step 5: Execute Test Trade on {symbol}")
    print("⚠️ This is a PAPER trade - no real money!")
    
    result = dog.execute_trade(
        symbol=symbol,
        side="buy",
        qty=1,  # Small qty for testing
        use_optimal_exit=True,
        time_horizon_sec=600  # 10 minute hold
    )
    
    print(f"\nResult: {'✅ EXECUTED' if result.get('executed') else '❌ NOT EXECUTED'}")
    if result.get('executed'):
        print(f"Order ID: {result.get('order_id')}")
        print(f"Entry: ${result.get('entry_price', 0):.2f}")
        print(f"TP: ${result.get('take_profit', 0):.2f}")
        print(f"SL: ${result.get('stop_loss', 0):.2f}")
        print(f"Regime at Execution: {result.get('regime_at_execution')}")
    elif result.get('blocked'):
        print(f"BLOCKED: {result.get('reason')}")
        print(f"Recommendation: {result.get('recommendation')}")
    else:
        print(f"Error: {result.get('error') or result.get('message')}")
    
    print_header("🎯 TEST COMPLETE")

if __name__ == "__main__":
    test_execution()
