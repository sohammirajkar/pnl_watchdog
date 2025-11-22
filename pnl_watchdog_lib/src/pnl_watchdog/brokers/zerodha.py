from kiteconnect import KiteConnect
from .base import BrokerAdapter


class ZerodhaAdapter(BrokerAdapter):
    def __init__(self, api_key: str, access_token: str):
        # Zerodha requires an 'access_token' which you get after login
        self.kite = KiteConnect(api_key=api_key)
        self.kite.set_access_token(access_token)

    def get_recent_orders(self, symbol: str, lookback_seconds: int):
        try:
            # Fetch order book
            orders = self.kite.orders()

            normalized = []
            for o in orders:
                normalized.append({
                    'symbol': o['tradingsymbol'],  # e.g., "INFY"
                    'side': o['transaction_type'].lower(),  # "buy"/"sell"
                    'qty': float(o['quantity']),
                    'status': o['status'].lower(),  # "complete", "rejected"
                    'id': str(o['order_id']),
                    'price': float(o['average_price']) if o['average_price'] > 0 else 0.0,
                    'timestamp': ts
                })
            return normalized
        except Exception as e:
            print(f"❌ Zerodha Error: {e}")
            return []

    def normalize_symbol(self, symbol: str) -> str:
        # Zerodha expects "INFY" or "NIFTY23OCTFUT"
        return symbol.upper()
