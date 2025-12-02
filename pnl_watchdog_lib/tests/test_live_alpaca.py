import os
import pytest
from pnl_watchdog import PnLWatchdog

# Skip this test if keys are missing (prevents CI/CD crashes)


@pytest.mark.skipif(not os.getenv("ALPACA_KEY"), reason="No Alpaca Keys Found")
def test_live_connection():
    print("\n🔌 Connecting to Alpaca Paper...")

    dog = PnLWatchdog(
        api_key=os.getenv("ALPACA_KEY"),
        api_secret=os.getenv("ALPACA_SECRET"),
        broker="alpaca"
    )

    # 1. Check Connection (Should not crash)
    # We look for a symbol that definitely has liquidity, e.g., AAPL
    # We expect False (Trade Missing) because we didn't actually trade,
    # but we want to ensure the API call itself succeeds (returns 200 OK).
    found = dog.check_order("AAPL", "buy", 0.0001)

    assert found is False  # Correct behavior (we didn't trade)
    print("✅ Live API Connection Successful (Returned valid empty list)")
