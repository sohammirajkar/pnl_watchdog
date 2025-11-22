from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BrokerAdapter(ABC):
    def __init__(self, api_key: str, api_secret: str, is_paper: bool):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_paper = is_paper

    @abstractmethod
    def get_recent_orders(self, symbol: str, lookback_seconds: int) -> List[Dict[str, Any]]:
        """
        Returns a list of normalized dicts: 
        [{'symbol': 'AAPL', 'side': 'buy', 'qty': 1.0, 'price': 150.00}, ...]
        """
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """
        Converts user symbol to broker symbol (e.g. 'btc/usd' -> 'BTC/USD')
        """
        pass
