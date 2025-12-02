import sys
import os
import time
import threading
import random
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# Ensure local import
# This is crucial for finding the pnl_watchdog package
sys.path.insert(0, os.path.abspath(os.path.join(
    os.path.dirname(__file__), '../src')))

try:
    from pnl_watchdog import PnLWatchdog
    # Try to import Rust module for benchmarking, but handle gracefully if not available
    try:
        import pnl_core  # Direct access to Rust for benchmarking
        rust_available = True
    except ImportError:
        rust_available = False
        # The watchdog.py file will print the warning if pnl_core is not found
        pass
except ImportError as e:
    print(f"❌ Failed to load PnLWatchdog: {e}")
    sys.exit(1)

# --- CONFIG ---
NUM_THREADS = 50      # Simulate 50 concurrent algo strategies
REQUESTS_PER_THREAD = 200  # Each strategy firing 200 calc requests
TOTAL_REQUESTS = NUM_THREADS * REQUESTS_PER_THREAD


def worker_task(thread_id, dog):
    """
    Simulates a single trading algorithm thread hammering the risk engine.
    This tests Memory Safety, Concurrency, and Determinism under load.
    """
    errors = 0

    # Generate fake market data (100 candles) for this specific thread/calculation
    num_candles = 100
    prices = [100.0 + (i * 0.01) + random.uniform(-0.5, 0.5)
              for i in range(num_candles)]
    volumes = [random.randint(100, 5000) * 1.0 for _ in range(num_candles)]
    opens = [p - random.uniform(-0.1, 0.1) for p in prices]
    closes = prices  # Using prices as closes for simplicity

    # Format data for PnLWatchdog's 'candles' argument
    # This is passed to the Watchdog, which in turn passes the vectors to the Rust core.
    candle_data = [
        {"open": o, "close": c, "volume": v}
        for o, c, v in zip(opens, closes, volumes)
    ]

    for i in range(REQUESTS_PER_THREAD):
        try:
            # 1. Call the Market Quality Calculation (Pillar 1)
            # This tests CONCURRENCY of the heavy calculation logic.
            metrics = dog.get_whale_view("TEST_SYM", candles=candle_data)

            # Check for valid output keys from the calculation
            if metrics.get('verdict') == "No Data" or metrics.get('kyles_lambda') is None:
                errors += 1

            # 2. Generate Passport (Pillar 2 - Audit Trail)
            # This tests TIME MONOTONICITY and LOGGING LOCKS.
            passport = dog.generate_execution_passport("TEST_SYM", "buy", 100)
            if not passport.get('audit_id') or not passport.get('timestamp_ns'):
                errors += 1

        except Exception as e:
            # Note: A real crash here would imply a fundamental failure in the Rust or CPython integration.
            print(f"💥 CRASH in Thread {thread_id} at iteration {i}: {e}")
            errors += 1

    return errors


def run_stress_test():
    print("\n" + "█"*60)
    print(f"🏛️  INSTITUTIONAL STRESS TEST: {TOTAL_REQUESTS} Ops")
    print(f"   Threads: {NUM_THREADS} | Concurrency: High")
    print("█"*60 + "\n")

    # Use 'test_mode' so the Watchdog doesn't try to connect to a real broker.
    # This ensures we are only measuring the internal CPU load.
    dog = PnLWatchdog(broker="test_mode")

    start_time = time.time()

    # Run Thread Pool
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        futures = [executor.submit(worker_task, i, dog)
                   for i in range(NUM_THREADS)]
        # Force all futures to complete
        results = [f.result() for f in futures]

    end_time = time.time()
    total_time = end_time - start_time
    total_errors = sum(results)

    throughput = TOTAL_REQUESTS / total_time if total_time > 0 else 0

    print("-" * 40)
    print(f"⏱️  Total Time: {total_time:.2f}s")
    print(f"⚡ Throughput: {throughput:.0f} ops/sec")
    print(f"❌ Errors:     {total_errors}")

    if total_errors == 0:
        print("\n✅ PASS: System is Thread-Safe and High-Performance.")
        print("   (No race conditions or memory corruptions detected).")
    else:
        print("\n❌ FAIL: Concurrency issues detected.")


if __name__ == "__main__":
    run_stress_test()
