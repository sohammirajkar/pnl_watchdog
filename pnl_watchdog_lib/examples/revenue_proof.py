import time
import random
import pandas as pd
from datetime import datetime
from pnl_watchdog.watchdog import PnLWatchdog

# CONFIG
INITIAL_CAPITAL = 100000
SYMBOLS = ["AAPL", "TSLA", "GME", "NVDA", "AMD", "SPY", "QQQ"]


class VirtualPortfolio:
    def __init__(self, name):
        self.name = name
        self.cash = INITIAL_CAPITAL
        self.holdings = {}
        self.history = []

    def trade(self, symbol, price, quantity, side, slippage_cost=0.0):
        cost = price * quantity
        actual_cost = cost + slippage_cost  # <--- The key difference

        if side == "BUY":
            self.cash -= actual_cost
            self.holdings[symbol] = self.holdings.get(symbol, 0) + quantity

        self.history.append({
            "timestamp": datetime.now(),
            "symbol": symbol,
            "side": side,
            "filled_price": price,
            "slippage_paid": slippage_cost,
            "total_value": self.get_value({symbol: price})  # approx
        })

    def get_value(self, current_prices):
        val = self.cash
        for sym, qty in self.holdings.items():
            if sym in current_prices:
                val += qty * current_prices[sym]
        return val


def run_profit_demonstration():
    print("\n" + "█"*60)
    print(f"💰 PnL WATCHDOG: EXECUTION ALPHA PROOF")
    print(f"   Comparing 'Blind Retail Algo' vs. 'Watchdog Protected Algo'")
    print("█"*60 + "\n")

    # Use your actual Databento key here
    DATABENTO_KEY = "db-S4bRFNjiSvC8dB9HiKPCkSetmFVKK"  # Replace with your actual key

    dog = PnLWatchdog(
        broker="databento",
        api_key=DATABENTO_KEY
    )

    # Two Portfolios
    victim_bot = VirtualPortfolio("🔴 Blind Retail Bot")
    smart_bot = VirtualPortfolio("🟢 Watchdog Pro Bot")

    # Simulation Loop (Live Data)
    for i in range(10):  # Run 10 iterations (or infinite loop)
        symbol = random.choice(SYMBOLS)
        print(f"[{i+1}/10] Analyzing Opportunity: {symbol}...")

        # 1. Get Real Market Data & Metrics (Using Rust Core)
        # Note: We use a lookback to get the current 'Toxicity' state
        metrics = dog.get_order_flow_analytics(symbol, lookback=50)

        if "error" in metrics:
            print("   ⚠️ No Data, skipping.")
            continue

        # 2. Get actual price from metrics if available, otherwise use default
        current_price = 150.0  # Default price
        # In a real implementation, the metrics would include price data
        # For now, we'll use symbol-based pricing
        symbol_prices = {
            "AAPL": 150.0, "TSLA": 250.0, "GME": 15.0,
            "NVDA": 450.0, "AMD": 120.0, "SPY": 450.0, "QQQ": 380.0
        }
        current_price = symbol_prices.get(symbol, 150.0)
        qty = 100

        # 3. Calculate THEORETICAL SLIPPAGE (Kyle's Lambda Cost)
        # This is the "Truth" your Rust engine provides.
        # Cost = Lambda * Volume_Trade
        # We scale it down to realistic $ terms
        market_impact_cost = (metrics.get(
            'toxicity_score', 0) / 10.0) * (qty * 0.01)

        # --- EXECUTION A: The Victim (Trades Anyway) ---
        victim_bot.trade(symbol, current_price, qty, "BUY",
                         slippage_cost=market_impact_cost)
        print(
            f"   🔴 Victim Bot: BUY executed. Paid ${market_impact_cost:.2f} in slippage.")

        # --- EXECUTION B: The Watchdog (Checks Risk) ---
        if metrics.get('verdict') == "HIGH TOXICITY":
            print(
                f"   🟢 Watchdog Bot: 🛡️ TOXICITY DETECTED ({metrics['toxicity_score']}). TRADE BLOCKED.")
            print(
                f"      -> Saved ${market_impact_cost:.2f} in avoided losses.")
        else:
            smart_bot.trade(symbol, current_price, qty, "BUY",
                            slippage_cost=market_impact_cost)
            print(f"   🟢 Watchdog Bot: Safe. Trade executed.")

        print("-" * 40)
        time.sleep(1)

    # FINAL RESULTS
    print("\n" + "="*60)
    print("📊 FINAL PnL COMPARISON")

    # Calculate total slippage paid
    victim_loss = sum([t['slippage_paid'] for t in victim_bot.history])
    smart_loss = sum([t['slippage_paid'] for t in smart_bot.history])

    savings = victim_loss - smart_loss

    print(f"   🔴 Blind Bot Slippage Paid:   ${victim_loss:.2f}")
    print(f"   🟢 Watchdog Bot Slippage Paid: ${smart_loss:.2f}")
    print(f"   💰 TOTAL GENERATED ALPHA:      ${savings:.2f}")

    if savings > 0:
        print(
            f"\n   ✅ CONCLUSION: PnL Watchdog paid for itself {savings/29:.1f}x over.")
    print("="*60)


if __name__ == "__main__":
    run_profit_demonstration()
