import asyncio
from pnl_watchdog.async_dog import AsyncPnLWatchdog
import sys
import os
# Add the parent directory (src) to the python path so we can import the library locally
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))

# Now this import will work correctly


# CONFIG
API_KEY = "REPLACE_WITH_ALPACA_API_KEY"
API_SECRET = "REPLACE_WITH_API_SECRET"


async def trading_bot_main():
    # 1. Initialize
    dog = AsyncPnLWatchdog(API_KEY, API_SECRET)

    print("🤖 Bot Running...")

    # --- SIMULATE A TRADE ---
    symbol = "AAPL"
    qty = 1
    print(f"⚡ EXECUTION: Bot sending BUY order for {symbol}...")
    # await broker_api.submit_order(...)

    # 2. Spawn the Watchdog (NON-BLOCKING)
    # This creates a background task. The code moves to the next line INSTANTLY.
    asyncio.create_task(
        dog.verify_execution(symbol, "buy", qty)
    )

    # 3. Continue Trading immediately
    for i in range(5):
        print(
            f"📈 Bot processing market data tick {i+1} (Watchdog is checking in background)...")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(trading_bot_main())
