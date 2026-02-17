from pnl_watchdog import PnLWatchdog
import sys
import os

# Add the source directory to the path
sys.path.insert(0, os.path.abspath('src'))


def test_databento_connection():
    print("Testing Databento connection...")

    # Use your actual Databento key here
    DATABENTO_KEY = "REPLACE_WITH_DATABENTO_API_KEY"  # Replace with your actual key

    try:
        dog = PnLWatchdog(
            broker="databento",
            api_key=DATABENTO_KEY
        )
        print("PnLWatchdog initialized successfully")
        print(f"Adapter type: {type(dog.adapter)}")

        # Test getting order flow analytics
        metrics = dog.get_order_flow_analytics("AAPL", lookback=50)
        print(f"Metrics: {metrics}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    test_databento_connection()
