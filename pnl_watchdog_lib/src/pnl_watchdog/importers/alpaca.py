"""
Alpaca API Importer
Fetches trade history directly from Alpaca API.
"""

import os
from typing import List, Any
import aiohttp
from datetime import datetime
from dateutil import parser
from .base import BrokerImporter, TradeRecord

class AlpacaAPIImporter(BrokerImporter):
    
    def __init__(self, api_key: str, api_secret: str, base_url: str = "https://paper-api.alpaca.markets"):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        
    async def parse(self, source: Any = None) -> List[TradeRecord]:
        """
        Fetches orders from Alpaca API. 
        'source' argument is ignored (maintained for compatibility).
        """
        trades = []
        self.errors = []
        
        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret
        }
        
        # Get filled orders
        url = f"{self.base_url}/v2/orders"
        params = {
            "status": "closed",
            "limit": 500,
            "nested": True # for brackets
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status != 200:
                        self.errors.append(f"API Error: {resp.status} - {await resp.text()}")
                        return []
                        
                    orders = await resp.json()
                    
                    for order in orders:
                        try:
                            if order['status'] != 'filled':
                                continue
                                
                            # Basic trade info
                            symbol = order['symbol']
                            side = order['side']
                            # For simple orders, use filled_qty/filled_avg_price
                            qty = float(order['filled_qty'])
                            price = float(order['filled_avg_price']) if order['filled_avg_price'] else 0.0
                            
                            filled_at_str = order['filled_at']
                            if not filled_at_str:
                                continue
                                
                            timestamp = parser.parse(filled_at_str)
                            
                            trade = TradeRecord(
                                broker="alpaca",
                                symbol=symbol,
                                side=side,
                                qty=qty,
                                price=price,
                                timestamp=timestamp,
                                order_id=order['id'],
                                raw_data=order
                            )
                            
                            if self.validate(trade):
                                trades.append(trade)
                                
                        except Exception as e:
                            self.errors.append(f"Order error: {e}")
                            print(f"Alpaca parse error: {e}")
                            continue

        except Exception as e:
            self.errors.append(f"Connection error: {e}")
            
        return trades
