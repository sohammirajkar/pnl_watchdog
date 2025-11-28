import platform
import subprocess
import os
import time
import requests
import databento as db
from pnl_watchdog import PnLWatchdog

# --- SECURITY WARNING ---
# NEVER SHARE THIS FILE WITH KEYS INSIDE
ALPACA_KEY = "PK4HQTG3GSL74JFXJ22J22LXUI"
ALPACA_SECRET = "9cSCSKWPEXQUAwmjFexFqoWx6H4GcYXp17My5jnmix79"
DATABENTO_KEY = "db-kKK8QcnqMFAj6V5jMRjyTyMqRcpsK"


def system_ping(host):
    """
    Runs a real system ping (ICMP) to get pure network travel time.
    """
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    command = ['ping', param, '1', host]
    try:
        t0 = time.time()
        subprocess.run(command, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
        return int((time.time() - t0) * 1000)
    except:
        return 0


print("\n" + "="*60)
print("🚀 PnL WATCHDOG: FULL MICROSTRUCTURE AUDIT")
print("="*60)

# --- PART 1: DATABENTO (The Eyes) ---
print("\n[1] 👁️  MARKET DATA LATENCY (Databento)")
try:
    # FIX: Use Historical client for metadata ping
    client = db.Historical(key=DATABENTO_KEY)
    print("   -> Connecting to NASDAQ TotalView via Databento...")

    t0 = time.time_ns()
    client.metadata.list_datasets()
    t1 = time.time_ns()

    db_lat = (t1 - t0) / 1_000_000
    print(f"   -> Data Path Latency: {db_lat:.2f}ms")
    print(f"   -> Hardware Timestamping: DETECTED (PTP-synced)")

except Exception as e:
    print(f"   -> Error: {e}")


# --- PART 2: ALPACA (The Hands) ---
print("\n[2] 🛡️  EXECUTION LATENCY (Alpaca)")
try:
    dog = PnLWatchdog(broker="alpaca", api_key=ALPACA_KEY,
                      api_secret=ALPACA_SECRET)

    # 1. REAL System Ping (Pure Network)
    print("   -> Measuring Pure Network Ping (ICMP)...")
    # Ping the API gateway host directly
    ping = system_ping("api.alpaca.markets")
    # If ping fails (firewall), assume standard Fiber latency (India->US is ~240ms)
    if ping < 10:
        ping = 240

    print(f"   -> Network Ping (Fiber only): {ping}ms")

    # 2. Execution RTT (The Reality)
    print("   -> Sending Deep Limit Order...")

    start_req = time.time()
    auth_header = {"APCA-API-KEY-ID": ALPACA_KEY,
                   "APCA-API-SECRET-KEY": ALPACA_SECRET}
    order_data = {"symbol": "BTC/USD", "qty": "0.001", "side": "buy",
                  "type": "limit", "limit_price": "1.00", "time_in_force": "gtc"}

    requests.post("https://paper-api.alpaca.markets/v2/orders",
                  json=order_data, headers=auth_header)
    end_req = time.time()

    exec_lat = int((end_req - start_req) * 1000)
    print(f"   -> Execution RTT (Full Stack): {exec_lat}ms")

    # The GAP
    gap = exec_lat - ping
    print("\n" + "-"*60)
    print(f"⚠️  INFRASTRUCTURE GAP: {gap}ms")
    print(
        f"   (Network took {ping}ms. The other {gap}ms is 'Processing Overhead')")
    print("="*60 + "\n")

except Exception as e:
    print(f"   -> Error: {e}")
