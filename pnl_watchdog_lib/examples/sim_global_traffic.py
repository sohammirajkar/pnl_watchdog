import asyncio
import aiohttp
import random
import math
import time

# Configuration
API_URL = "https://pnl-cloud-backend-4esa.vercel.app/v1/telemetry"
BROKERS = ["binance", "bybit", "ibkr",
           "alpaca", "kraken", "coinbase", "zerodha"]


class MarketSimulator:
    """
    Simulates a live market feed (like Databento or Alpaca WebSocket).
    In a real app, this would be replaced by the actual WebSocket client.
    """

    async def stream_trades(self):
        while True:
            # Simulate random trade arrival times (Poisson process-like)
            # Real markets aren't perfectly timed every 2 seconds
            await asyncio.sleep(random.uniform(0.1, 0.5))

            # Yield a mock trade event
            yield {
                "symbol": random.choice(["BTC/USD", "AAPL", "TSLA", "ES"]),
                "price": random.uniform(100, 50000),
                "timestamp": time.time()
            }


async def calculate_metrics(broker):
    """
    The 'Strategy Handler': Calculates latency and slippage based on market conditions.
    """
    # 1. Base Latency (The "Normal" State)
    base = 35 if broker in ["binance", "bybit"] else 85

    # 2. Daily Sine Wave (Markets breathe)
    now = time.time()
    cycle = math.sin(now / 100) * 10

    # 3. The "Fat Tail" Event (Random Black Swan)
    # 3% chance of a massive spike (300ms - 2000ms)
    if random.random() < 0.03:
        latency = int(base + random.randint(300, 2000))
    else:
        # 4. Normal Jitter (Gaussian noise)
        jitter = random.normalvariate(0, 5)
        latency = int(max(10, base + cycle + jitter))

    # Slippage correlates with latency (Liquidity Holes)
    slippage = 0.0
    if latency > 200:
        slippage = random.uniform(0.01, 0.05)

    return latency, float(f"{slippage:.5f}")


async def send_telemetry(session, broker, latency, slippage):
    """
    Sends data to the Cloud Oracle (Non-blocking).
    """
    payload = {
        "broker": broker,
        "latency_ms": latency,
        "slippage": slippage,
        "status": "verified"
    }

    try:
        # Non-blocking POST request
        async with session.post(API_URL, json=payload, timeout=5) as response:
            # Status visualizer for terminal
            status_icon = "🔴" if latency > 300 else "🟢"
            if response.status == 200:
                print(f"{status_icon} Sent: {broker:<10} | {latency}ms")
            else:
                print(f"⚠️ Server Error: {response.status}")
    except Exception as e:
        print(f"❌ Network Failed: {e}")


async def main():
    print(f"🚀 Launching Event-Driven Simulator -> {API_URL}")
    print("   (Mimicking High-Frequency Data Ingestion)")

    # Initialize Market Feed
    market = MarketSimulator()

    # Create a persistent HTTP session (faster than opening new ones)
    async with aiohttp.ClientSession() as session:
        # THE EVENT LOOP (Replaces 'while True')
        # We react to market events as they happen
        async for trade in market.stream_trades():

            # Simulate processing this trade on ALL brokers simultaneously
            # (Like a Smart Router checking prices)
            tasks = []
            for broker in BROKERS:
                # Calculate metrics for this broker
                latency, slippage = await calculate_metrics(broker)

                # Schedule the upload task immediately (Fire & Forget)
                task = asyncio.create_task(send_telemetry(
                    session, broker, latency, slippage))
                tasks.append(task)

            # Wait for all broker checks for this tick to complete
            await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        # Run the async loop
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Simulation stopped.")
