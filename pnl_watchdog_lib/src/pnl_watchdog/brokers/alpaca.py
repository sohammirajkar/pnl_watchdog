import requests
from dateutil import parser
from .base import BrokerAdapter


class AlpacaAdapter(BrokerAdapter):
    def get_recent_orders(self, symbol: str, lookback_seconds: int):
        base_url = "https://paper-api.alpaca.markets" if self.is_paper else "https://api.alpaca.markets"

        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "accept": "application/json"
        }

        # Filter params to get relevant data efficiently
        params = {
            "status": "all",       # We need 'filled' orders, not just 'open'
            "limit": 20,           # Fetch enough recent orders
            "direction": "desc"    # Newest first
        }

        # Alpaca supports server-side symbol filtering
        if symbol:
            params["symbols"] = symbol

        # 1. Call Alpaca API
        try:
            resp = requests.get(f"{base_url}/v2/orders",
                                headers=headers, params=params)
            resp.raise_for_status()
            raw_orders = resp.json()
        except Exception as e:
            print(f"⚠️ Alpaca API Error: {e}")
            return []

        # 2. NORMALIZE data to standard format
        normalized = []
        for o in raw_orders:
            # Parse Timestamp (ISO 8601 -> Unix Milliseconds)
            # If filled, use fill time. If open, use creation time.
            time_str = o['filled_at'] if o['filled_at'] else o['created_at']

            try:
                timestamp_ms = parser.parse(time_str).timestamp() * 1000
            except:
                timestamp_ms = 0

            normalized.append({
                'symbol': o['symbol'],
                'side': o['side'],
                'qty': float(o['qty']),
                'price': float(o['filled_avg_price']) if o['filled_avg_price'] else 0.0,
                'status': o['status'],
                'id': o['id'],
                'timestamp': timestamp_ms
            })

        return normalized

    def get_candles(self, symbol: str, lookback_candles: int = 100):
        """
        Fetch historical OHLCV candle data from Alpaca.
        """
        base_url = "https://data.alpaca.markets"
        
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }
        
        # Use 5-minute bars
        try:
            resp = requests.get(
                f"{base_url}/v2/stocks/{symbol}/bars",
                headers=headers,
                params={
                    "timeframe": "5Min",
                    "limit": lookback_candles
                }
            )
            resp.raise_for_status()
            data = resp.json()
            
            if 'bars' not in data or not data['bars']:
                return []
            
            # Normalize to standard format
            candles = []
            for bar in data['bars']:
                candles.append({
                    'timestamp': parser.parse(bar['t']).timestamp(),
                    'open': float(bar['o']),
                    'high': float(bar['h']),
                    'low': float(bar['l']),
                    'close': float(bar['c']),
                    'volume': float(bar['v'])
                })
            
            return candles
            
        except Exception as e:
            print(f"⚠️ Alpaca Candle Data Error: {e}")
            return []

    def normalize_symbol(self, symbol: str):
        return symbol.upper()  # Alpaca just likes uppercase
