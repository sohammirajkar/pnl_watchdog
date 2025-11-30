import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.abspath('src'))

# Test the Rust module directly
try:
    from pnl_watchdog import calculate_order_flow_metrics
    print("✅ Rust module imported successfully")
    
    # Test with sample data
    prices = [100.0, 101.0, 102.0, 101.5, 100.5]
    volumes = [1000.0, 2000.0, 1500.0, 500.0, 1200.0]
    bids = [99.9, 100.9, 101.9, 101.4, 100.4]
    asks = [100.1, 101.1, 102.1, 101.6, 100.6]
    
    result = calculate_order_flow_metrics(prices, volumes, bids, asks)
    print(f"✅ Rust function executed successfully: {result}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# Test the Databento adapter directly
try:
    from pnl_watchdog.brokers.databento import DatabentoAdapter
    print("✅ Databento adapter imported successfully")
    
    # Test with your key
    adapter = DatabentoAdapter('db-S4bRFNjiSvC8dB9HiKPCkSetmFVKK')
    print("✅ Databento adapter initialized successfully")
    
    # Test getting candles (this will show an error if the key is invalid)
    candles = adapter.get_candles('AAPL', 5)
    print(f"✅ Candles fetched: {len(candles)}")
    if candles:
        print(f"   First candle: {candles[0]}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()