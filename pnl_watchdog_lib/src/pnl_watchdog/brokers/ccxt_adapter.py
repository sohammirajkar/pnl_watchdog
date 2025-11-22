import ccxt
import time
from typing import List, Dict, Any
from .base import BrokerAdapter


class CCXTAdapter(BrokerAdapter):
    def __init__(self, broker_name: str, api_key: str, api_secret: str, is_paper: bool):
        # Initialize parent class
        super().__init__(api_key, api_secret, is_paper)

        # 1. Dynamically load the exchange class (e.g., ccxt.binance)
        if not hasattr(ccxt, broker_name):
            raise ValueError(f"Broker '{broker_name}' not supported by CCXT.")

        exchange_class = getattr(ccxt, broker_name)

        # 2. Initialize with config
        self.exchange = exchange_class({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,  # Crucial to avoid bans
        })

        # 3. Enable Testnet/Paper Mode if requested
        if is_paper:
            if 'test' in self.exchange.urls:
                self.exchange.set_sandbox_mode(True)
            else:
                print(
                    f"⚠️ Warning: {broker_name} does not support Sandbox/Paper mode via CCXT.")

    # --- MAKE SURE THIS IS INDENTED TO THE LEFT (SAME AS __init__) ---
    def get_recent_orders(self, symbol: str, lookback_seconds: int) -> List[Dict[str, Any]]:
        # Ensure market metadata is loaded so symbols are recognized
        self.exchange.load_markets()

        # Normalize symbol (e.g. "btc/usdt" -> "BTC/USDT")
        target_symbol = self.normalize_symbol(symbol) if symbol else None

        # Calculate 'since' timestamp (Current Time - Lookback) in Milliseconds
        since_ts = int((time.time() - lookback_seconds) * 1000)

        try:
            # CCXT Standardizes this call across ALL exchanges
            orders = self.exchange.fetch_orders(
                target_symbol, since=since_ts, limit=10)

            normalized = []
            for o in orders:
                # Handle Price: Market orders might have 'price': None, but 'average': 123.45
                price = o.get('price')
                if price is None:
                    price = o.get('average')

                normalized.append({
                    'symbol': o['symbol'],       # CCXT standard: "BTC/USDT"
                    'side': o['side'],           # "buy" or "sell"
                    'qty': float(o['amount']),   # CCXT standard: "amount"
                    'status': o['status'],       # "open", "closed", "canceled"
                    'id': str(o['id']),
                    'timestamp': o['timestamp'],  # Unix Timestamp in MS
                    'price': float(price) if price else 0.0
                })
            return normalized

        except Exception as e:
            print(f"❌ CCXT Error on {self.exchange.id}: {e}")
            return []

    # --- MAKE SURE THIS IS INDENTED TO THE LEFT TOO ---
    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()
