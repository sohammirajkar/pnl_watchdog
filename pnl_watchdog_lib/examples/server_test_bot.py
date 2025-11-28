from pnl_watchdog import PnLWatchdog
import sys
import os
import time
import json
from unittest.mock import MagicMock, patch

# Ensure we can import the library locally
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))


def run_privacy_audit():
    print("\n🕵️ STARTING FREE TIER PRIVACY AUDIT (Client Side)...")
    print("Goal: Verify that 'AAPL' is NOT sent to the server.")

    # 1. Initialize as Free User (No Pro Key, Opt-in = True)
    dog = PnLWatchdog(
        broker="alpaca",
        api_key="DUMMY",
        api_secret="DUMMY",
        pro_key=None,  # <--- NO KEY (Free Tier)
        opt_in=True    # <--- COMMUNITY MODE (Sharing Stats)
    )

    # Point to local for safety, though we will intercept before sending
    dog.api_url = "http://127.0.0.1:8000/v1"

    # 2. Mock Broker to simulate a successful trade
    dog.adapter = MagicMock()
    dog.adapter.normalize_symbol.return_value = "AAPL"
    dog.adapter.get_recent_orders.return_value = [{
        "symbol": "AAPL",
        "side": "buy",
        "qty": 10.0,
        "price": 150.05,
        "timestamp": (time.time() - 2) * 1000,
        "status": "filled",
        "id": "test_id_1"
    }]

    # 3. INTERCEPT the Network Request
    # We hook into requests.post to see exactly what leaves the machine
    with patch('requests.post') as mock_post:
        print("🤖 Bot: Verifying execution for 'AAPL'...")
        dog.check_and_analyze("AAPL", "buy", 10.0, 150.00)

        # Wait briefly for the background thread
        time.sleep(0.2)

        # 4. Analyze the Payload
        if mock_post.called:
            # Extract the arguments passed to requests.post
            args, kwargs = mock_post.call_args
            payload = kwargs['json']
            endpoint = args[0]

            print(f"\n📤 DESTINATION: {endpoint}")
            print("📦 PAYLOAD SENT (What you see):")
            print(json.dumps(payload, indent=2))

            print("\n🔎 PRIVACY VERIFICATION:")

            # Check 1: Is the raw symbol visible?
            if "AAPL" in payload.values():
                print("❌ FAILURE: 'AAPL' is visible in the payload!")
            else:
                print("✅ PASS: Raw Symbol 'AAPL' is HIDDEN.")

            # Check 2: Is the side/qty visible?
            if "buy" in payload or 10.0 in payload.values():
                print("❌ FAILURE: Side or Qty leaked!")
            else:
                print("✅ PASS: Trade details (Side/Qty) are STRIPPED.")

            # Check 3: Is the hash present?
            if "symbol_hash" in payload and len(payload["symbol_hash"]) == 64:
                print(
                    f"✅ PASS: Symbol is Hashed (SHA-256): {payload['symbol_hash'][:10]}...")
            else:
                print("❌ FAILURE: Symbol hash missing or invalid.")

        else:
            print("❌ Error: No network request was captured.")


if __name__ == "__main__":
    run_privacy_audit()
