"""
Real-time Liquidity Surface Test using Alpaca API
Tests the Liquidity Surface feature with live US stock market data.

SETUP INSTRUCTIONS:
1. Create a free account at https://alpaca.markets
2. Get your Paper Trading API keys from the dashboard
3. Set environment variables:
   export ALPACA_API_KEY="your_key_here"
   export ALPACA_API_SECRET="your_secret_here"
4. Run: python3.11 test_realtime_alpaca.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

from pnl_watchdog import PnLWatchdog
from datetime import datetime

def test_liquidity_surface_alpaca():
    print("\n" + "="*70)
    print("🚀 REAL-TIME LIQUIDITY SURFACE TEST - ALPACA (US STOCKS)")
    print("="*70)
    
    # 1. Get API keys from environment
    api_key = os.getenv("ALPACA_API_KEY", "PKBTQZWTP75S23P5CX5MOWIXK2")
    api_secret = os.getenv("ALPACA_API_SECRET", "9LNtBAx1TzK233G3ARf6gX6M5AKbKEa2tknt3VM3mH9W")
    
    if not api_key or not api_secret:
        print("\n❌ ERROR: Alpaca API keys not found!")
        print("\nPlease set environment variables:")
        print("   export ALPACA_API_KEY='your_key_here'")
        print("   export ALPACA_API_SECRET='your_secret_here'")
        print("\nGet your keys at: https://alpaca.markets")
        return
    
    # 2. Initialize PnL Watchdog with Alpaca
    print("\n📡 Connecting to Alpaca Paper Trading...")
    try:
        dog = PnLWatchdog(
            broker="alpaca",
            api_key=api_key,
            api_secret=api_secret,
            paper=True  # Use paper trading
        )
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    # 3. Test with a popular stock
    symbol = "AAPL"  # Apple Inc.
    print(f"\n📊 Analyzing {symbol}...")
    
    try:
        # Get liquidity surface
        result = dog.get_liquidity_surface(
            symbol=symbol,
            lookback_candles=100,
            time_bins=10,
            spread_bins=5
        )
        
        if "error" in result:
            print(f"❌ Error: {result['error']}")
            return
        
        # 4. Display Results
        print(f"\n✅ Liquidity Surface calculated!")
        print(f"\n📈 Analysis for {result['symbol']}:")
        print(f"   Grid Size: {result['time_bins']}x{result['spread_bins']}")
        print(f"   Avg Volume: {result['avg_volume']:.2f}")
        print(f"   Min Volume: {result['min_volume']:.2f}")
        print(f"   Max Volume: {result['max_volume']:.2f}")
        
        # 5. Show liquidity holes
        if result['liquidity_holes']:
            print(f"\n⚠️  Liquidity Holes Detected: {len(result['liquidity_holes'])}")
            for i, hole in enumerate(result['liquidity_holes'], 1):
                print(f"   {i}. Time: {hole['time_range']}, "
                      f"Spread: {hole['spread_range']}, Volume: {hole['volume']}")
        else:
            print(f"\n✅ No liquidity holes detected")
        
        # 6. Show recommendation
        print(f"\n💡 {result['recommendation']}")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_liquidity_surface_alpaca()
