"""
Real-time Liquidity Surface Test using Binance API
Tests the Liquidity Surface feature with live BTC/USDT market data.
"""
import sys
import os
import requests
import pnl_core
from datetime import datetime

# Add the library to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pnl_watchdog_lib", "src"))

def fetch_binance_klines(symbol="BTCUSDT", interval="5m", limit=100):
    """
    Fetch candlestick data from Binance public API.
    
    :param symbol: Trading pair (e.g., BTCUSDT)
    :param interval: Candle interval (1m, 5m, 15m, 1h, etc.)
    :param limit: Number of candles (max 1000)
    :return: List of candle dictionaries
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Parse Binance kline format
        candles = []
        for kline in data:
            candles.append({
                "timestamp": kline[0] / 1000,  # Convert to seconds
                "open": float(kline[1]),
                "high": float(kline[2]),
                "low": float(kline[3]),
                "close": float(kline[4]),
                "volume": float(kline[5])
            })
        
        return candles
    
    except Exception as e:
        print(f"❌ Failed to fetch data from Binance: {e}")
        return []

def test_liquidity_surface_realtime():
    print("\n" + "="*70)
    print("🚀 REAL-TIME LIQUIDITY SURFACE TEST - BINANCE BTC/USDT")
    print("="*70)
    
    # 1. Fetch real data
    print("\n📡 Fetching live data from Binance...")
    candles = fetch_binance_klines(symbol="BTCUSDT", interval="5m", limit=100)
    
    if not candles:
        print("❌ Failed to fetch data. Exiting.")
        return
    
    print(f"✅ Fetched {len(candles)} candles")
    print(f"   Time range: {datetime.fromtimestamp(candles[0]['timestamp'])} to {datetime.fromtimestamp(candles[-1]['timestamp'])}")
    print(f"   Price range: ${candles[0]['open']:.2f} - ${candles[-1]['close']:.2f}")
    
    # 2. Prepare data for Rust core
    spreads = [c['high'] - c['low'] for c in candles]
    volumes = [c['volume'] for c in candles]
    timestamps = [c['timestamp'] for c in candles]
    
    print(f"\n📊 Data Statistics:")
    print(f"   Avg Spread: ${sum(spreads)/len(spreads):.2f}")
    print(f"   Avg Volume: {sum(volumes)/len(volumes):.2f} BTC")
    print(f"   Max Volume: {max(volumes):.2f} BTC")
    print(f"   Min Volume: {min(volumes):.2f} BTC")
    
    # 3. Call Rust Core
    time_bins = 10
    spread_bins = 5
    
    print(f"\n🔬 Calculating Liquidity Surface ({time_bins}x{spread_bins} grid)...")
    
    try:
        grid, time_bounds, spread_bounds = pnl_core.calculate_liquidity_surface(
            spreads, volumes, timestamps, time_bins, spread_bins
        )
        
        print("✅ Liquidity Surface calculated successfully!")
        
        # 4. Analyze Results
        print(f"\n📈 Surface Bounds:")
        print(f"   Time: {datetime.fromtimestamp(time_bounds[0])} to {datetime.fromtimestamp(time_bounds[1])}")
        print(f"   Spread: ${spread_bounds[0]:.2f} - ${spread_bounds[1]:.2f}")
        
        # 5. Display Grid
        print(f"\n🗺️  Liquidity Surface Grid (Volume in BTC):")
        print("   " + "-" * 60)
        
        for t in range(time_bins):
            row = []
            for s in range(spread_bins):
                idx = t * spread_bins + s
                row.append(f"{grid[idx]:8.1f}")
            
            # Calculate time for this bin
            time_start = time_bounds[0] + (t / time_bins) * (time_bounds[1] - time_bounds[0])
            time_str = datetime.fromtimestamp(time_start).strftime("%H:%M")
            print(f"   {time_str} | " + " ".join(row))
        
        print("   " + "-" * 60)
        
        # 6. Identify Liquidity Holes
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
                        "time_bin": t,
                        "spread_bin": s,
                        "time_range": (datetime.fromtimestamp(time_start).strftime("%H:%M"), 
                                      datetime.fromtimestamp(time_end).strftime("%H:%M")),
                        "volume": grid[idx]
                    })
        
        # 7. Generate Recommendations
        print(f"\n💡 Analysis:")
        print(f"   Average Volume per Bin: {avg_volume:.2f} BTC")
        print(f"   Liquidity Holes Detected: {len(liquidity_holes)}")
        
        if len(liquidity_holes) > 0:
            print(f"\n⚠️  LIQUIDITY HOLES (Volume < {threshold:.2f} BTC):")
            for i, hole in enumerate(liquidity_holes[:5], 1):
                print(f"   {i}. Time: {hole['time_range'][0]}-{hole['time_range'][1]}, "
                      f"Spread Bin: {hole['spread_bin']}, Volume: {hole['volume']:.2f} BTC")
            
            if len(liquidity_holes) > 5:
                print(f"   ... and {len(liquidity_holes) - 5} more")
            
            print(f"\n🎯 Recommendation: Avoid trading during the above periods.")
            print(f"   Consider splitting large orders across high-liquidity periods.")
        else:
            print(f"\n✅ No significant liquidity holes detected.")
            print(f"   Market appears to have consistent liquidity distribution.")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ Liquidity Surface calculation failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_liquidity_surface_realtime()
