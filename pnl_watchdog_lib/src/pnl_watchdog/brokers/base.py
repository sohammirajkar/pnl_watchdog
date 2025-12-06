from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class OrderResult:
    """Result of an order placement"""
    success: bool
    order_id: Optional[str] = None
    message: str = ""
    filled_price: Optional[float] = None
    filled_qty: Optional[float] = None
    bracket_order_ids: Optional[Dict[str, str]] = None  # {'tp': 'id', 'sl': 'id'}


class BrokerAdapter(ABC):
    def __init__(self, api_key: str, api_secret: str = "", is_paper: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.is_paper = is_paper

    # =========================================================================
    # READ METHODS (Existing)
    # =========================================================================
    
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
    
    def get_candles(self, symbol: str, lookback: int = 100) -> List[Dict[str, Any]]:
        """
        Optional: Fetch OHLCV candle data. Override in subclasses.
        """
        return []

    # =========================================================================
    # EXECUTION METHODS (New - v0.10.0)
    # =========================================================================
    
    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: OrderSide,
        qty: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        take_profit: Optional[float] = None,
        stop_loss: Optional[float] = None,
        time_in_force: str = "gtc"
    ) -> OrderResult:
        """
        Place an order with optional bracket orders (TP/SL).
        
        Args:
            symbol: Trading symbol
            side: BUY or SELL
            qty: Order quantity
            order_type: MARKET, LIMIT, STOP, STOP_LIMIT
            limit_price: Price for limit orders
            take_profit: Take profit price (creates bracket order)
            stop_loss: Stop loss price (creates bracket order)
            time_in_force: 'gtc' (good till cancel), 'day', 'ioc', 'fok'
        
        Returns:
            OrderResult with success status and order details
        """
        pass
    
    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an open order by ID.
        Returns True if successful.
        """
        pass
    
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.
        Returns: [{'symbol': 'AAPL', 'qty': 10, 'avg_entry': 150.0, 'pnl': 50.0}, ...]
        """
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """
        Get account info (balance, buying power, etc).
        """
        pass
