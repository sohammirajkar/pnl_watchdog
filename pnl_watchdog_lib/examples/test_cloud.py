

from pnl_watchdog import PnLWatchdog
import sys
import os
import time

# This tells Python to look in the 'src' folder for the library
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))
# ------------------------


def test_connection():
    print("📡 Initializing Watchdog with Pro Key...")

    # 1. Initialize with a Fake Key
    # We use 'alpaca' as the broker just to init the class
    dog = PnLWatchdog(broker="alpaca", pro_key="sk_test_456",
                      api_key="dummy", api_secret="dummy")

    # 2. OVERRIDE URL (Critical step for local testing)
    # This points the library to your local FastAPI server instead of the real website
    dog.api_url = "http://127.0.0.1:8000/v1"

    # 3. Create fake trade data
    fake_data = {
        "symbol": "XRP/USD",
        "side": "buy",
        "qty": 0.5,
        "broker": "alpaca",
        "latency_ms": 45,
        "slippage": 0.01,
        "status": "verified"
    }

    print("📤 Sending Log to Local Cloud...")

    # 4. Trigger the upload manually
    # Note: We call the internal method directly for this test
    dog._upload_log(fake_data)

    # Wait a moment to ensure the background thread finishes (if using threads)
    time.sleep(1)
    print("🏁 Test Script Finished.")


if __name__ == "__main__":
    test_connection()
