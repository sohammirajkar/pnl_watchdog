from pnl_watchdog.watchdog import PnLWatchdog
import sys
import os
import time
import random

# Fix import path
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))


def run_ai_simulation():
    print("🧠 Starting AI Training Simulation...")

    # Initialize (Using dummy keys for demo, but structure is real)
    # Note: In a real run, use valid keys to connect to Alpaca Paper
    dog = PnLWatchdog(api_key="TEST", api_secret="TEST", broker="alpaca")

    # 1. TRAINING PHASE (Simulate 50 normal trades)
    print("\n--- Phase 1: Training the Brain (Simulating 50 trades) ---")
    for i in range(50):
        # Normal trade: Low slippage ($0.01), Fast latency (50-100ms)
        slip = random.uniform(0.00, 0.02)
        lat = random.uniform(50, 100)
        dog.brain.learn(slippage=slip, latency_ms=lat)
        if i % 10 == 0:
            print(f"   ...learned {i} trades")

    print("✅ Training Complete. Model Saved.")

    # 2. ANOMALY TEST
    print("\n--- Phase 2: Testing Anomalies ---")

    # Scenario A: High Latency (The "Lag Spike")
    print("\n[Test A] Lag Spike (500ms latency)")
    report_a = dog.brain.analyze(slippage=0.01, latency_ms=500)
    if report_a['is_anomaly']:
        print(f"   ✅ CAUGHT: {report_a['reasons']}")
    else:
        print("   ❌ MISSED")

    # Scenario B: High Slippage (The "Bad Fill")
    print("\n[Test B] Bad Fill ($0.50 slippage)")
    report_b = dog.brain.analyze(slippage=0.50, latency_ms=80)
    if report_b['is_anomaly']:
        print(f"   ✅ CAUGHT: {report_b['reasons']}")
    else:
        print("   ❌ MISSED")

    # Scenario C: Normal Trade
    print("\n[Test C] Normal Trade")
    report_c = dog.brain.analyze(slippage=0.01, latency_ms=75)
    if not report_c['is_anomaly']:
        print("   ✅ CORRECT: Marked as normal")
    else:
        print("   ❌ FALSE POSITIVE")


if __name__ == "__main__":
    run_ai_simulation()
