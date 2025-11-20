
# 📘 Getting Started with PnL Watchdog

**PnL Watchdog** is a Python library that acts as an independent safety layer for your trading algorithms. It verifies that your code's intent matches your broker's reality.

## 1\. Prerequisites

Before you start, ensure you have:

* Python 3.7+ installed.
* An account with a supported broker (Currently supports: **Alpaca**).
* **API Keys:** We strongly recommend generating **Read-Only** API keys for this tool. It does not need trading permissions to verify the ledger.

## 2\. Installation

Install the package directly from PyPI:

```bash
pip install pnl-watchdog
```

## 3\. Configuration (Safety First)

To keep your keys safe, do not hardcode them in your script. Set them as environment variables in your terminal:

```bash
# Linux/Mac
export PNL_KEY="PK_YOUR_ALPACA_KEY"
export PNL_SECRET="YOUR_SECRET_HERE"

# Windows (PowerShell)
$env:PNL_KEY="PK_YOUR_ALPACA_KEY"
$env:PNL_SECRET="YOUR_SECRET_HERE"
```

## 4\. Usage Guide

### A. Basic Implementation

Add this logic immediately after your bot executes a trade.

```python
import os
import time
from pnl_watchdog import PnLWatchdog

# 1. Initialize the Watchdog
# Note: paper=True uses the Alpaca Paper Trading endpoint
dog = PnLWatchdog(
    api_key=os.getenv("PNL_KEY"),
    api_secret=os.getenv("PNL_SECRET"),
    paper=True 
)

# --- YOUR TRADING LOGIC HERE ---
symbol = "AAPL"
qty = 1
side = "buy"

print(f"🤖 Bot attempting to {side} {qty} {symbol}...")
# api.submit_order(...) <--- Your bot sends the order here

# 2. The Safety Check
# Wait a moment for network propagation (optional but recommended)
time.sleep(1) 

# 3. Ask Watchdog: "Did that trade actually happen?"
is_confirmed = dog.check_order(symbol=symbol, side=side, qty=qty)

if is_confirmed:
    print("✅ Trade Verified: It is on the ledger.")
else:
    print("🚨 CRITICAL FAILURE: The trade is MISSING on the broker side!")
    # STOP YOUR BOT HERE or trigger an emergency alert (SMS/Discord)
```

### B. How to Interpret Results

* **`True`**: The trade exists in the broker's "filled" or "new" orders list. Your state is synced.
* **`False`**: The trade was **not found** within the recent order history.
  * *Cause:* API Timeout, Insufficient Margin rejection, or Network disconnect.
  * *Action:* You should assume you are **not** in the position you think you are.

## 5\. Advanced: Integration with Discord

You can easily wrap the watchdog to send alerts to your phone via Discord Webhooks if a failure is detected.

```python
import requests

def alert_human(msg):
    url = "YOUR_DISCORD_WEBHOOK_URL"
    requests.post(url, json={"content": msg})

# In your bot loop:
if not dog.check_order("AAPL", "buy", 10):
    alert_human("🚨 ALERT: AAPL Buy Order Failed! Check Broker ASAP.")
```

-----

## FAQ

**Q: Does this slow down my trading?**
A: No. You should run the check *asynchronously* or after your order logic is complete. It performs a single lightweight GET request to the broker.

**Q: Is it safe?**
A: Yes. `pnl-watchdog` is designed to work with **Read-Only** API keys. It physically cannot execute trades or withdraw funds.

**Q: Which brokers are supported?**
A: Currently **Alpaca**. Support for Interactive Brokers (IBKR) and Binance is coming in v0.2.0.
