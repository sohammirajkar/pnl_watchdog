from pnl_watchdog import PnLWatchdog
import os

# 1. Initialize (Read-Only Keys recommended)
dog = PnLWatchdog(api_key="PK_...", api_secret="...", paper=True)

# ... Your bot places a trade ...
api.submit_order("AAPL", 1, "buy")

# 2. Verify it actually happened
is_safe = dog.check_order(symbol="AAPL", side="buy", qty=1)

if not is_safe:
    print("🚨 CRITICAL: Broker did not receive the order! Halting bot.")
    # Add your emergency logic here (e.g., Twilio SMS, retry)

# After your bot trades...
# dog.check_order(symbol, side, qty) returns True if found, False if missing
if not dog.check_order("AAPL", "buy", 1):
    print("🚨 CRITICAL: Trade missing! Stopping bot.")


# 1. Load keys (Best practice: use Environment Variables)
API_KEY = os.getenv("ALPACA_KEY", "PK_YOUR_KEY_HERE")
API_SECRET = os.getenv("ALPACA_SECRET", "YOUR_SECRET_HERE")


def run_demo():
    print("🐶 Starting Watchdog Demo...")

    # Initialize the library
    try:
        dog = PnLWatchdog(api_key=API_KEY, api_secret=API_SECRET, paper=True)
    except Exception as e:
        print(f"❌ Error initializing: {e}")
        return

    # Simulate a check for a trade that DOESN'T exist (The "Sad Path")
    print("\n1. Checking for a fake trade (expecting failure)...")
    found = dog.check_order(symbol="TSLA", side="buy", qty=9999)

    if found:
        print("⚠️ Weird... found a trade that shouldn't exist.")
    else:
        print("✅ Correctly detected missing trade! (Silent Failure caught)")

    # Simulate a check for a trade that DOES exist (The "Happy Path")
    # Instructions: Manually buy 1 share of AAPL on Alpaca Paper first!
    print("\n2. Checking for real AAPL trade (make sure you bought 1 share first)...")
    found_real = dog.check_order(symbol="AAPL", side="buy", qty=1)

    if found_real:
        print("✅ Verified real trade found on ledger.")
    else:
        print("❌ Could not find AAPL trade. Did you buy it manually first?")


if __name__ == "__main__":
    run_demo()
