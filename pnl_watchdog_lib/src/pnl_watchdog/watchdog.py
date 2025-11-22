import time
from typing import Optional

# --- IMPORT ADAPTERS ---
# We use try/except here so your code doesn't crash if you haven't
# created the specific Indian/IBKR adapter files yet.
try:
    from .brokers.alpaca import AlpacaAdapter
    from .brokers.ccxt_adapter import CCXTAdapter
    from .brokers.zerodha import ZerodhaAdapter
    from .brokers.angel_one import AngelOneAdapter
    from .brokers.ibkr import IBKRAdapter
except ImportError:
    pass  # Ignore missing adapters for now

from .ai_brain import AIBrain


class PnLWatchdog:
    """
    The central Watchdog class.
    Acts as a Factory to load the correct Broker Adapter and AI Brain.
    """

    # FIX: Added **kwargs here so we can accept variable arguments
    def __init__(self, broker: str = "alpaca", **kwargs):
        self.broker = broker.lower()
        self.brain = AIBrain()

        # Extract common arguments safely
        api_key = kwargs.get("api_key")
        api_secret = kwargs.get("api_secret")
        paper = kwargs.get("paper", True)

        # --- ADAPTER FACTORY LOGIC ---

        # 1. US STOCKS (Alpaca)
        if self.broker == "alpaca":
            self.adapter = AlpacaAdapter(api_key, api_secret, paper)

        # 2. INDIA (Zerodha)
        elif self.broker == "zerodha":
            self.adapter = ZerodhaAdapter(api_key, kwargs.get("access_token"))

        # 3. INDIA (Angel One)
        elif self.broker == "angel":
            self.adapter = AngelOneAdapter(
                api_key,
                kwargs.get("client_code"),
                kwargs.get("password"),
                kwargs.get("totp")
            )

        # 4. GLOBAL (Interactive Brokers)
        elif self.broker == "ibkr":
            self.adapter = IBKRAdapter(
                host=kwargs.get("host", '127.0.0.1'),
                port=kwargs.get("port", 7497)
            )

        # 5. CRYPTO (Binance, Kraken, Coinbase via CCXT)
        else:
            # This handles 'binance', 'bybit', etc.
            self.adapter = CCXTAdapter(self.broker, api_key, api_secret, paper)

    def check_order(self, symbol: str, side: str, qty: float, lookback_seconds: int = 60) -> bool:
        """
        Polls the broker to see if a matching trade occurred.
        """
        try:
            clean_symbol = self.adapter.normalize_symbol(symbol)
            orders = self.adapter.get_recent_orders(
                clean_symbol, lookback_seconds)

            for order in orders:
                # Fuzzy match on float qty
                is_qty_match = abs(
                    float(order['qty']) - float(qty)) < 0.00000001

                if (order['symbol'] == clean_symbol and
                    order['side'] == side and
                        is_qty_match):
                    return True

            return False
        except Exception as e:
            print(f"❌ Watchdog Check Error: {e}")
            return False

    def check_slippage(self, symbol: str, expected_price: float, filled_qty: float, threshold_cents: float = 5.0):
        """
        Alerts if the execution price was significantly worse than expected.
        """
        try:
            clean_symbol = self.adapter.normalize_symbol(symbol)
            orders = self.adapter.get_recent_orders(
                clean_symbol, lookback_seconds=60)

            matched_order = None
            for o in orders:
                if abs(float(o['qty']) - filled_qty) < 0.00000001:
                    matched_order = o
                    break

            if not matched_order:
                return

            fill_price = float(matched_order.get('price', 0.0))
            if fill_price == 0:
                return

            slippage = abs(fill_price - expected_price)

            if slippage > (threshold_cents / 100):
                print(
                    f"⚠️ HIGH SLIPPAGE on {clean_symbol}: Expected ${expected_price}, Got ${fill_price}. Diff: ${slippage:.2f}")
            else:
                print(f"✅ Slippage OK: ${slippage:.2f}")

        except Exception as e:
            print(f"❌ Slippage Check Error: {e}")

    def check_and_analyze(self, symbol: str, side: str, qty: float, expected_price: float) -> bool:
        """
        The AI-Powered Super Check: Verification + Metrics + AI Anomaly Detection.
        """
        try:
            clean_symbol = self.adapter.normalize_symbol(symbol)
            orders = self.adapter.get_recent_orders(
                clean_symbol, lookback_seconds=60)

            # 1. VERIFICATION
            matched_order = None
            for o in orders:
                if (o['symbol'] == clean_symbol and
                    o['side'] == side and
                        abs(float(o['qty']) - qty) < 0.00000001):
                    matched_order = o
                    break

            if not matched_order:
                print(f"🚨 CRITICAL: Trade MISSING for {symbol}!")
                return False

            # 2. METRICS
            fill_price = float(matched_order.get('price', expected_price))
            slippage = abs(fill_price - expected_price)

            order_ts = matched_order.get('timestamp', time.time() * 1000)
            latency_ms = max(0, (time.time() * 1000) - order_ts)

            print(
                f"📊 Analysis: Slippage=${slippage:.2f} | Latency={latency_ms:.0f}ms")

            # 3. AI BRAIN
            self.brain.learn(slippage, latency_ms)
            ai_report = self.brain.analyze(slippage, latency_ms)

            if ai_report["is_anomaly"]:
                reasons = ", ".join(ai_report["reasons"])
                print(f"🤖 AI ALERT: Unusual execution detected! ({reasons})")

            return True

        except Exception as e:
            print(f"❌ Watchdog Error: {e}")
            return False
