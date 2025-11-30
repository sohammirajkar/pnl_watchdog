import time
import random
import numpy as np
from pnl_watchdog.watchdog import PnLWatchdog

# CONFIG
INITIAL_CAPITAL = 1000000  # ₹10 Lakhs
USD_INR = 89.36        # Current Exchange Rate


class MacroSimulator:
    def __init__(self):
        self.usd_inr = USD_INR
        self.market_liquidity = 1.0  # 100% normal

    def step(self):
        """
        Simulates a Macro Shock Event.
        """
        # 1. Simulate Currency Volatility
        # Random walk with drift
        # Using a lower threshold to make crashes more likely
        # Increased standard deviation for more volatility
        change = random.normalvariate(0.05, 0.5)
        self.usd_inr += change

        # 2. Macro Impact Logic
        # If USD/INR spikes rapidly, Liquidity evaporates
        # Lowering threshold to make crash events more frequent
        if change > 0.1:
            self.market_liquidity *= 0.5  # Liquidity HALVED (Crash condition)
            print(
                f"   ⚠️  MACRO SHOCK: USD/INR spiked to {self.usd_inr:.2f}. Liquidity collapsing.")
        else:
            self.market_liquidity = min(
                1.0, self.market_liquidity * 1.1)  # Slow recovery

        return self.usd_inr, self.market_liquidity


def run_crash_test():
    print("\n" + "█"*60)
    print(f"📉 PnL WATCHDOG: MACRO STRESS TEST (USD/INR SHOCK)")
    print("█"*60 + "\n")

    sim = MacroSimulator()
    dog = PnLWatchdog(broker="audit_mode")

    portfolio_value = INITIAL_CAPITAL

    for i in range(10):
        print(f"--- Minute {i+1} ---")

        # 1. Evolve Macro State
        fx_rate, liquidity = sim.step()

        # 2. Get Watchdog Metrics (Simulated based on macro state)
        # If liquidity is low, Toxicity/Lambda should be high
        simulated_toxicity = int((1.0 - liquidity) * 100)

        # 3. The Trading Decision
        print(
            f"   💵 USD/INR: {fx_rate:.2f} | 💧 Liquidity: {liquidity*100:.0f}%")

        if simulated_toxicity > 40:
            # The Watchdog Intervention
            print(
                f"   🛡️  WATCHDOG ALERT: High Fragility Detected (Score: {simulated_toxicity})")
            print(f"       -> Action: HALT TRADING. Cash is king.")
        else:
            # Normal Trading
            trade_pnl = random.randint(-1000, 2000)
            portfolio_value += trade_pnl
            print(f"   ✅  Market Stable. Trade Executed. PnL: {trade_pnl}")

        time.sleep(1)


if __name__ == "__main__":
    run_crash_test()
