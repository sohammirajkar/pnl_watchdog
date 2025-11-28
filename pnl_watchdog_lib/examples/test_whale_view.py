import random
import numpy as np
from pnl_watchdog import PnLWatchdog

# --- 1. MOCK BROKER (To simulate data) ---

import pnl_watchdog
print(f"📂 Python is using this file: {pnl_watchdog.__file__}")


class MockBroker:
    def get_candles(self, symbol, lookback):
        """
        Generates fake OHLCV data to test the math.
        """
        candles = []
        price = 100.0

        # Scenario Logic:
        # If symbol is "TOXIC_COIN", we simulate Insider Buying (Price rises on Volume)
        is_toxic = "TOXIC" in symbol

        for _ in range(lookback):
            # 1. Generate Volume (Random)
            vol = random.randint(100, 1000)

            # 2. Generate Price Move
            if is_toxic:
                # TOXIC LOGIC: Price is correlated with Volume
                # (Big volume = Price goes UP)
                change = (vol / 5000)  # Positive correlation
            else:
                # SAFE LOGIC: Random walk (No correlation)
                change = random.uniform(-0.01, 0.01)

            open_p = price
            close_p = price * (1 + change)
            price = close_p

            candles.append({
                "open": open_p,
                "close": close_p,
                "volume": vol
            })

        return candles


# --- 2. THE TEST ---
print("\n" + "="*50)
print("🐳 PnL WATCHDOG: WHALE VIEW DIAGNOSTIC")
print("="*50)

# Initialize Dog
dog = PnLWatchdog(broker="mock")
# Inject our Mock Broker so the function has data to eat
dog.broker = MockBroker()

# TEST A: Safe Asset
print("\n[1] Testing Healthy Market (Random Walk)...")
res_safe = dog.get_whale_view("AAPL", lookback_candles=100)
print(f"   -> Amihud Score: {res_safe['amihud_illiquidity']} (Cost)")
print(f"   -> Kyle's Lambda: {res_safe['kyles_lambda']} (Insider Activity)")
print(f"   -> Verdict: {res_safe['verdict']}")

# TEST B: Toxic Asset
print("\n[2] Testing Toxic Market (Insider Buying)...")
res_toxic = dog.get_whale_view("TOXIC_COIN", lookback_candles=100)
print(f"   -> Amihud Score: {res_toxic['amihud_illiquidity']} (Cost)")
print(f"   -> Kyle's Lambda: {res_toxic['kyles_lambda']} (Insider Activity)")
print(f"   -> Verdict: {res_toxic['verdict']}")

print("\n" + "="*50)
