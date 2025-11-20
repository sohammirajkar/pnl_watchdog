import requests
import time
from typing import Optional, Dict, Any


class PnLWatchdog:
    """
    A local watchdog that verifies if your bot's orders actually hit the broker.
    """

    def __init__(self, api_key: str, api_secret: str, broker: str = "alpaca", paper: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.broker = broker.lower()

        if self.broker == "alpaca":
            self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        else:
            raise NotImplementedError("Currently only 'alpaca' is supported.")

    def check_order(self, symbol: str, side: str, qty: float, lookback_seconds: int = 30) -> bool:
        """
        Polls the broker to see if a matching trade occurred recently.
        Returns True if found, False if missing (Silent Failure).
        """
        # 1. Fetch recent orders
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "accept": "application/json"
        }

        try:
            response = requests.get(
                f"{self.base_url}/v2/orders",
                headers=headers,
                params={"status": "all", "limit": 10, "direction": "desc"}
            )
            response.raise_for_status()
            orders = response.json()

            # 2. Match logic
            for order in orders:
                # Check if order is recent enough (simplified for MVP)
                # In v2, parse order['filled_at'] against lookback_seconds
                if (order['symbol'] == symbol and
                    order['side'] == side and
                        float(order['qty']) == qty):
                    return True

            return False

        except Exception as e:
            print(f"Watchdog Connection Error: {e}")
            return False
