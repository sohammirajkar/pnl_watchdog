"""
Zerodha CSV Importer
Parses Kite tradebook CSV exports.
"""

import csv
from datetime import datetime
from typing import List, Any
from .base import BrokerImporter, TradeRecord

class ZerodhaCSVImporter(BrokerImporter):
    
    async def parse(self, file_path: str) -> List[TradeRecord]:
        trades = []
        self.errors = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    try:
                        # Extract fields using potential column names
                        symbol = row.get('symbol') or row.get('Symbol') or row.get('tradingsymbol')
                        trade_type = row.get('trade_type') or row.get('Trade Type') or row.get('type')
                        qty = row.get('quantity') or row.get('Quantity') or row.get('qty')
                        price = row.get('price') or row.get('Price') or row.get('average_price')
                        
                        # Date handling
                        date_str = row.get('trade_date') or row.get('Trade Date')
                        time_str = row.get('trade_time') or row.get('Trade Time')
                        
                        if not (symbol and qty and price and date_str):
                            continue
                            
                        # Parse Timestamp
                        if time_str:
                            dt_str = f"{date_str} {time_str}"
                            # Try common formats
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%d-%m-%Y %H:%M:%S']:
                                try:
                                    timestamp = datetime.strptime(dt_str, fmt)
                                    break
                                except ValueError:
                                    continue
                        else:
                            timestamp = datetime.strptime(date_str, '%Y-%m-%d')
                            
                        # Determine Side
                        side = 'buy' if 'buy' in str(trade_type).lower() else 'sell'
                        
                        trade = TradeRecord(
                            broker="zerodha",
                            symbol=symbol,
                            side=side,
                            qty=float(qty),
                            price=float(price),
                            timestamp=timestamp,
                            order_id=row.get('order_id') or row.get('Order ID'),
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
