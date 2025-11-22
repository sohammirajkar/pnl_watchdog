from SmartApi import SmartConnect
from .base import BrokerAdapter


class AngelOneAdapter(BrokerAdapter):
    def __init__(self, api_key: str, client_code: str, password: str, totp: str):
        # Angel One requires a full login flow to generate a session
        self.smartApi = SmartConnect(api_key=api_key)
        data = self.smartApi.generateSession(client_code, password, totp)

        if not data['status']:
            raise ValueError(f"Angel One Login Failed: {data['message']}")

        self.auth_token = data['data']['jwtToken']

    def get_recent_orders(self, symbol: str, lookback_seconds: int):
        try:
            # Angel uses 'orderBook' to fetch recent orders
            orders = self.smartApi.orderBook()

            # If no orders exist, API returns None
            if orders['data'] is None:
                return []

            normalized = []
            for o in orders['data']:
                normalized.append({
                    'symbol': o['tradingsymbol'],  # e.g., "SBIN-EQ"
                    'side': o['transactiontype'].lower(),
                    'qty': float(o['quantity']),
                    'status': o['status'].lower(),  # "complete"
                    'id': o['orderid'],
                    'price': float(o['averageprice']),
                    'timestamp': time.time() * 1000
                })
            return normalized
        except Exception as e:
            print(f"❌ Angel One Error: {e}")
            return []

    def normalize_symbol(self, symbol: str) -> str:
        # Angel usually wants "SBIN-EQ"
        return symbol.upper()
