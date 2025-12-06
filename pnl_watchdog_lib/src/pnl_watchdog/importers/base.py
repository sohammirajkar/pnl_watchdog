"""
Base Broker Importer
Abstract base class for all trade importers to ensure consistent output format.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
from decimal import Decimal
import logging

logger = logging.getLogger("PnLWatchdog.Importer")

class TradeRecord:
    """Normalized trade record structure for import."""
    def __init__(
        self,
        broker: str,
        symbol: str,
        side: str,
        qty: float,
        price: float,
        timestamp: datetime,
        order_id: Optional[str] = None,
        raw_data: Optional[Dict] = None
    ):
        self.broker = broker
        self.symbol = symbol.upper()
        self.side = side.lower()
        self.qty = Decimal(str(qty))
        self.price = Decimal(str(price))
        self.timestamp = timestamp
        self.order_id = order_id
        self.raw_data = raw_data or {}
        
    def to_dict(self):
        return {
            "broker": self.broker,
            "symbol": self.symbol,
            "side": self.side,
            "qty": float(self.qty),
            "price": float(self.price),
            "timestamp": self.timestamp.isoformat(),
            "order_id": self.order_id,
            "raw_data": self.raw_data
        }

class BrokerImporter(ABC):
    """Abstract base class for broker importers."""
    
    def __init__(self):
        self.errors = []
        
    @abstractmethod
    async def parse(self, source: Any) -> List[TradeRecord]:
        """
        Parse the source (file path or API response) into normalized TradeRecords.
        """
        pass
    
    def validate(self, trade: TradeRecord) -> bool:
        """Basic validation."""
        if trade.qty <= 0:
            self.errors.append(f"Invalid quantity {trade.qty} for {trade.symbol}")
            return False
        if trade.price <= 0:
            self.errors.append(f"Invalid price {trade.price} for {trade.symbol}")
            return False
        return True
