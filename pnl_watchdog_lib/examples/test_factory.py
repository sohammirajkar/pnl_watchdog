from pnl_watchdog.brokers.ccxt_adapter import CCXTAdapter
from pnl_watchdog.brokers.alpaca import AlpacaAdapter
from pnl_watchdog import PnLWatchdog
import sys
import os

# Hack to import from src/ locally
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))


def test_factory():
    print("🏭 Testing Broker Factory...")

    # 1. Test Alpaca Loading
    print("   - Requesting 'alpaca'...")
    dog_alpaca = PnLWatchdog(
        broker="alpaca",
        api_key="dummy", api_secret="dummy"
    )

    if isinstance(dog_alpaca.adapter, AlpacaAdapter):
        print("   ✅ Success: Loaded AlpacaAdapter")
    else:
        print(f"   ❌ Failed: Got {type(dog_alpaca.adapter)}")

    # 2. Test Binance Loading (via CCXT)
    print("   - Requesting 'binance'...")
    try:
        dog_binance = PnLWatchdog(
            broker="binance",
            api_key="dummy", api_secret="dummy"
        )

        if isinstance(dog_binance.adapter, CCXTAdapter):
            print("   ✅ Success: Loaded CCXTAdapter for Binance")
        else:
            print(f"   ❌ Failed: Got {type(dog_binance.adapter)}")

    except Exception as e:
        print(f"   ❌ Error loading Binance: {e}")

    # 3. Test Invalid Broker
    print("   - Requesting 'fake_broker'...")
    try:
        dog_fake = PnLWatchdog(broker="fake_broker",
                               api_key="d", api_secret="d")
        print("   ❌ Failed: Should have raised an error but didn't.")
    except ValueError as e:
        print(f"   ✅ Success: Correctly rejected fake broker ({e})")
    except Exception as e:
        print(f"   ⚠️ Unexpected error: {e}")


if __name__ == "__main__":
    test_factory()
