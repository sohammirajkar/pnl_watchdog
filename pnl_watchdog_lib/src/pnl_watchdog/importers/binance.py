"""
Binance CSV Importer
Parses Binance "Trade History" CSV exports.
"""

import csv
from datetime import datetime
from typing import List
from .base import BrokerImporter, TradeRecord

class BinanceCSVImporter(BrokerImporter):
    
    async def parse(self, file_path: str) -> List[TradeRecord]:
        trades = []
        self.errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Binance Format: Date(UTC), Pair, Side, Price, Executed, Amount, Total
                        timestamp_str = row.get('Date(UTC)')
                        symbol = row.get('Pair')
                        side = row.get('Side')
                        price = row.get('Price')
                        qty = row.get('Executed')
                        # Sometimes quantity is 'Amount', sometimes 'Executed'
                        if not qty:
                            qty = row.get('Amount')
                            
                        if not (timestamp_str and symbol and price and qty):
                            continue
                            
                        # Parse Timestamp (Binance usually uses YYYY-MM-DD HH:MM:SS)
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                        
                        trade = TradeRecord(
                            broker="binance",
                            symbol=symbol,
                            side=side,
                            qty=float(qty.replace(',','')), # Remove commas
                            price=float(price.replace(',','')),
                            timestamp=timestamp,
                            order_id=None, # CSV often doesn't have Order ID
                            raw_data=row
                        )
                        
                        if self.validate(trade):
                            trades.append(trade)
                            
                    except Exception as e:
                        self.errors.append(f"Row error: {e}")
                        continue
                        
        except Exception as e:
            self.errors.append(f"File error: {e}")
            
        return trades
