"""
Real-time Liquidity Surface Test using DataBento API
Tests the Liquidity Surface feature with professional-grade market data.

SETUP INSTRUCTIONS:
1. Create account at https://databento.com (free tier available)
2. Get your API key from the dashboard
3. Set environment variable:
   export DATABENTO_API_KEY="your_key_here"
4. Run: python3.11 test_realtime_databento.py

DataBento provides institutional-grade tick data for stocks, futures, and options.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

import databento as db
import pnl_core
from datetime import datetime, timedelta

def test_liquidity_surface_databento():
    print("\n" + "="*70)
    print("🚀 REAL-TIME LIQUIDITY SURFACE TEST - DATABENTO")
    print("="*70)
    
    # 1. Get API key
    api_key = os.getenv("DATABENTO_API_KEY", "db-invkRfqfBTspVudMSgA3qHEDJYH4W")
    
    if not api_key:
        print("\n❌ ERROR: DataBento API key not found!")
        print("\nPlease set environment variable:")
        print("   export DATABENTO_API_KEY='your_key_here'")
        print("\nGet your key at: https://databento.com")
        return
    
    # 2. Initialize DataBento client
    print("\n📡 Connecting to DataBento...")
    try:
        client = db.Historical(api_key)
        print("✅ Connected successfully!")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return
    
    # 3. Fetch historical OHLCV data
    symbol = "AAPL"
    dataset = "XNAS.ITCH"  # Nasdaq ITCH feed
    
    # Get data for the last trading day
    end_date = datetime.now()
    start_date = end_date - timedelta(days=1)
    
    print(f"\n📊 Fetching {symbol} data from DataBento...")
    print(f"   Dataset: {dataset}")
    print(f"   Date range: {start_date.date()} to {end_date.date()}")
    
    try:
        # Fetch OHLCV-1m bars (1-minute candles)
        data = client.timeseries.get_range(
            dataset=dataset,
            symbols=[symbol],
            schema="ohlcv-1m",
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            limit=100  # Last 100 candles
        )
        
        # Convert to list of candles
        candles = []
        for record in data:
            candles.append({
                "timestamp": record.ts_event / 1e9,  # Convert nanoseconds to seconds
                "open": record.open / 1e9,  # DataBento uses fixed-point prices
                "high": record.high / 1e9,
                "low": record.low / 1e9,
                "close": record.close / 1e9,
                "volume": record.volume
            })
        
        if not candles:
            print("❌ No data returned. Market may be closed or symbol unavailable.")
            print("\nTrying with a different approach (historical replay)...")
            return
        
        print(f"✅ Fetched {len(candles)} candles")
        print(f"   Time range: {datetime.fromtimestamp(candles[0]['timestamp'])} to {datetime.fromtimestamp(candles[-1]['timestamp'])}")
        print(f"   Price range: ${candles[0]['open']:.2f} - ${candles[-1]['close']:.2f}")
        
        # 4. Prepare data for Rust core
        spreads = [c['high'] - c['low'] for c in candles]
        volumes = [float(c['volume']) for c in candles]
        timestamps = [c['timestamp'] for c in candles]
        
        print(f"\n📊 Data Statistics:")
        print(f"   Avg Spread: ${sum(spreads)/len(spreads):.2f}")
        print(f"   Avg Volume: {sum(volumes)/len(volumes):.0f} shares")
        print(f"   Max Volume: {max(volumes):.0f} shares")
        print(f"   Min Volume: {min(volumes):.0f} shares")
        
        # 5. Call Rust Core
        time_bins = 10
        spread_bins = 5
        
        print(f"\n🔬 Calculating Liquidity Surface ({time_bins}x{spread_bins} grid)...")
        
        grid, time_bounds, spread_bounds = pnl_core.calculate_liquidity_surface(
            spreads, volumes, timestamps, time_bins, spread_bins
        )
        
        print("✅ Liquidity Surface calculated successfully!")
        
        # 6. Display Grid
        print(f"\n🗺️  Liquidity Surface Grid (Volume in shares):")
        print("   " + "-" * 60)
        
        for t in range(time_bins):
            row = []
            for s in range(spread_bins):
                idx = t * spread_bins + s
                row.append(f"{grid[idx]:10.0f}")
            
            time_start = time_bounds[0] + (t / time_bins) * (time_bounds[1] - time_bounds[0])
            time_str = datetime.fromtimestamp(time_start).strftime("%H:%M")
            print(f"   {time_str} | " + " ".join(row))
        
        print("   " + "-" * 60)
        
        # 7. Analyze
        avg_volume = sum(grid) / len(grid)
        threshold = avg_volume * 0.2
        
        liquidity_holes = []
        for t in range(time_bins):
            for s in range(spread_bins):
                idx = t * spread_bins + s
                if grid[idx] < threshold:
                    time_start = time_bounds[0] + (t / time_bins) * (time_bounds[1] - time_bounds[0])
                    time_end = time_bounds[0] + ((t + 1) / time_bins) * (time_bounds[1] - time_bounds[0])
                    liquidity_holes.append({
                        "time_range": (datetime.fromtimestamp(time_start).strftime("%H:%M"), 
                                      datetime.fromtimestamp(time_end).strftime("%H:%M")),
                        "volume": grid[idx]
                    })
        
        print(f"\n💡 Analysis:")
        print(f"   Average Volume per Bin: {avg_volume:.0f} shares")
        print(f"   Liquidity Holes Detected: {len(liquidity_holes)}")
        
        if liquidity_holes:
            print(f"\n⚠️  LIQUIDITY HOLES (Volume < {threshold:.0f} shares):")
            for i, hole in enumerate(liquidity_holes[:5], 1):
                print(f"   {i}. Time: {hole['time_range'][0]}-{hole['time_range'][1]}, "
                      f"Volume: {hole['volume']:.0f} shares")
            
            if len(liquidity_holes) > 5:
                print(f"   ... and {len(liquidity_holes) - 5} more")
        else:
            print(f"\n✅ No significant liquidity holes detected.")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("\nNote: DataBento requires a subscription for real-time data.")
        print("Free tier may have limited access to recent data.")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_liquidity_surface_databento()
