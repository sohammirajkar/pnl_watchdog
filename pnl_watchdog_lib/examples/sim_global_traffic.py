import time
import uuid
import random
import requests
import math

API_URL = "https://pnl-cloud-backend-4esa.vercel.app/v1/telemetry"
# API_URL = "http://127.0.0.1:8000/v1/telemetry" # Local testing

BROKERS = ["binance", "bybit", "ibkr",
           "alpaca", "kraken", "coinbase", "zerodha"]


def get_realistic_latency(broker):
    # 1. Base Latency (The "Normal" State)
    base = 35 if broker in ["binance", "bybit"] else 85

    # 2. Daily Sine Wave (Markets breathe)
    now = time.time()
    cycle = math.sin(now / 100) * 10

    # 3. The "Fat Tail" Event (Random Black Swan)
    # 3% chance of a massive spike (300ms - 2000ms)
    if random.random() < 0.03:
        return int(base + random.randint(300, 2000))

    # 4. Normal Jitter (Gaussian noise)
    jitter = random.normalvariate(0, 5)
    return int(max(10, base + cycle + jitter))


print(f"🚀 Launching Realistic Traffic Simulator to: {API_URL}")

while True:
    for broker in BROKERS:
        latency = get_realistic_latency(broker)

        # Slippage correlates with latency (usually)
        slippage = 0.0
        if latency > 200:
            slippage = random.uniform(0.01, 0.05)

        payload = {
            "broker": broker,
            "latency_ms": latency,
            "slippage": float(f"{slippage:.5f}"),
            "status": "verified"
        }

        try:
            requests.post(API_URL, json=payload, timeout=5)
            status_icon = "🔴" if latency > 300 else "🟢"
            print(f"{status_icon} Sent: {broker:<10} | {latency}ms")
        except Exception as e:
            print(f"❌ Failed: {e}")

    time.sleep(2)  # Send a batch every 2 seconds
