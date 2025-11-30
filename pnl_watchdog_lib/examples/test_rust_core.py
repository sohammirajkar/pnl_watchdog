import sys
import os

# Fix import path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))

# API Keys - Replace with your actual keys
DATABENTO_API_KEY = "db-S4bRFNjiSvC8dB9HiKPCkSetmFVKK"
ALPACA_API_KEY = "PKKLANPTLU2MGY524PBHBTLZXB"
ALPACA_SECRET_KEY = "4kHf7KxrBVdtcXthRXEiHPndrW2MZvtpdAD1qbCS14y3"
try:
    from pnl_watchdog import calculate_order_flow_metrics, calculate_whale_metrics
    print("✅ Rust Core Loaded!")
except ImportError as e:
    print(f"❌ Rust Core Failed to Load: {e}")
    sys.exit(1)


def get_alpaca_data(symbol="AAPL", limit=10):
    """Fetch real-time data from Alpaca"""
    try:
        import alpaca_trade_api as tradeapi

        api = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET_KEY,
                            base_url='https://paper-api.alpaca.markets')

        # Get recent bar data
        bars = api.get_bars(symbol, tradeapi.TimeFrame.Minute, limit=limit)

        opens = [bar.open for bar in bars]
        closes = [bar.close for bar in bars]
        volumes = [bar.volume for bar in bars]

        # Get latest quotes for order book data
        quotes = api.get_latest_quotes([symbol])
        bid_prices = [quotes[symbol].bid_price] if symbol in quotes else [
            min(closes)]
        ask_prices = [quotes[symbol].ask_price] if symbol in quotes else [
            max(closes)]

        return opens, closes, volumes, bid_prices, ask_prices
    except Exception as e:
        print(f"❌ Error fetching Alpaca data: {e}")
        # Fallback to test data
        return [100.0, 101.0, 102.0, 101.5, 100.5], [101.0, 102.0, 101.5, 100.5, 101.0], [1000.0, 2000.0, 1500.0, 500.0, 1200.0], [99.9, 100.9, 101.9, 101.4, 100.4], [100.1, 101.1, 102.1, 101.6, 100.6]


def get_databento_data(symbol="ES.FUT", limit=10):
    """Fetch real-time data from Databento"""
    try:
        import databento as db

        client = db.Historical(DATABENTO_API_KEY)

        # Get recent data
        data = client.timeseries.get_range(
            dataset='GLBX.MDP3',
            symbols=[symbol],
            start=-limit,  # Last 'limit' records
            schema='ohlcv-1m'
        )

        opens = [item.open for item in data]
        closes = [item.close for item in data]
        volumes = [item.volume for item in data]

        # Simple bid/ask simulation
        bid_prices = [close * 0.999 for close in closes]
        ask_prices = [close * 1.001 for close in closes]

        return opens, closes, volumes, bid_prices, ask_prices
    except Exception as e:
        print(f"❌ Error fetching Databento data: {e}")
        # Fallback to test data
        return [100.0, 101.0, 102.0, 101.5, 100.5], [101.0, 102.0, 101.5, 100.5, 101.0], [1000.0, 2000.0, 1500.0, 500.0, 1200.0], [99.9, 100.9, 101.9, 101.4, 100.4], [100.1, 101.1, 102.1, 101.6, 100.6]

# Get real data (uncomment the one you want to use)
# opens, closes, volumes, bids, asks = get_alpaca_data("AAPL", 10)
# opens, closes, volumes, bids, asks = get_databento_data("ES.FUT", 10)


# For now, using test data until you provide API keys
opens, closes, volumes, bids, asks = [100.0, 101.0, 102.0, 101.5, 100.5], [101.0, 102.0, 101.5, 100.5, 101.0], [
    1000.0, 2000.0, 1500.0, 500.0, 1200.0], [99.9, 100.9, 101.9, 101.4, 100.4], [100.1, 101.1, 102.1, 101.6, 100.6]

# Run Rust - Order Flow Metrics
vwap_dev, tox, nof, obi, vwap = calculate_order_flow_metrics(
    closes, volumes, bids, asks)

# Run Rust - Whale Metrics
amihud, kyles_lambda = calculate_whale_metrics(opens, closes, volumes)

print("\n🦀 RUST METRICS OUTPUT:")
print(f"   Kyle's Lambda: {kyles_lambda:.6f}")
print(f"   Amihud Score: {amihud:.6f}")
print(f"   VWAP: {vwap:.2f}")
print(f"   Toxicity: {tox:.2f}")
print(f"   Net Order Flow: {nof:.2f}")
print(f"   Imbalance: {obi:.2f}")

if vwap > 0 and kyles_lambda >= 0:
    print("\n✅ All Calculations Successful. Engine is ready.")
else:
    print("\n❌ Calculation Error.")
