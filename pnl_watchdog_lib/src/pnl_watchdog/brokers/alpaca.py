"""
Alpaca Broker Adapter - Full Execution Support
==============================================

Supports:
- Market/Limit/Stop orders
- Bracket orders (entry + TP + SL)
- Position management
- Paper trading mode
"""
import requests
from dateutil import parser
from typing import List, Dict, Any, Optional
from .base import BrokerAdapter, OrderSide, OrderType, OrderResult


class AlpacaAdapter(BrokerAdapter):
    """
    Alpaca Trading API adapter with full execution support.
    Supports both paper and live trading.
    """
    
    def __init__(self, api_key: str, api_secret: str, is_paper: bool = True):
        super().__init__(api_key, api_secret, is_paper)
        self.base_url = "https://paper-api.alpaca.markets" if is_paper else "https://api.alpaca.markets"
        self.data_url = "https://data.alpaca.markets"
        self.headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
            "accept": "application/json",
            "content-type": "application/json"
        }
    
    # =========================================================================
    # READ METHODS
    # =========================================================================
    
    def get_recent_orders(self, symbol: str, lookback_seconds: int) -> List[Dict[str, Any]]:
        params = {"status": "all", "limit": 20, "direction": "desc"}
        if symbol:
            params["symbols"] = symbol

        try:
            resp = requests.get(f"{self.base_url}/v2/orders", headers=self.headers, params=params)
            resp.raise_for_status()
            raw_orders = resp.json()
        except Exception as e:
            print(f"⚠️ Alpaca API Error: {e}")
            return []

        normalized = []
        for o in raw_orders:
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

    def get_candles(self, symbol: str, lookback_candles: int = 100) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                f"{self.data_url}/v2/stocks/{symbol}/bars",
                headers=self.headers,
                params={"timeframe": "5Min", "limit": lookback_candles, "start": "2025-11-01T00:00:00Z"}
            )
            resp.raise_for_status()
            data = resp.json()
            
            if 'bars' not in data or not data['bars']:
                return []
            
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

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()
    
    # =========================================================================
    # EXECUTION METHODS (v0.10.0)
    # =========================================================================
    
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
        Place an order on Alpaca with optional bracket orders.
        
        If both take_profit and stop_loss are provided, creates a bracket order
        (OCO - One Cancels Other) for automated TP/SL management.
        """
        symbol = self.normalize_symbol(symbol)
        
        # Build order payload
        order_data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side.value,
            "type": order_type.value,
            "time_in_force": time_in_force
        }
        
        # Add limit price if applicable
        if order_type in [OrderType.LIMIT, OrderType.STOP_LIMIT] and limit_price:
            order_data["limit_price"] = str(limit_price)
        
        if order_type in [OrderType.STOP, OrderType.STOP_LIMIT] and limit_price:
            order_data["stop_price"] = str(limit_price)
        
        # Create bracket order if TP and SL provided
        # IMPORTANT: Round to 2 decimal places (Alpaca rejects sub-penny prices)
        if take_profit and stop_loss:
            order_data["order_class"] = "bracket"
            order_data["take_profit"] = {"limit_price": str(round(take_profit, 2))}
            order_data["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        elif take_profit:
            order_data["order_class"] = "oto"  # One-Triggers-Other
            order_data["take_profit"] = {"limit_price": str(round(take_profit, 2))}
        elif stop_loss:
            order_data["order_class"] = "oto"
            order_data["stop_loss"] = {"stop_price": str(round(stop_loss, 2))}
        
        try:
            print(f"📤 Placing order: {side.value.upper()} {qty} {symbol}")
            if take_profit:
                print(f"   Take Profit: ${take_profit:.2f}")
            if stop_loss:
                print(f"   Stop Loss: ${stop_loss:.2f}")
            
            resp = requests.post(
                f"{self.base_url}/v2/orders",
                headers=self.headers,
                json=order_data
            )
            
            if resp.status_code in [200, 201]:
                data = resp.json()
                print(f"✅ Order placed: {data['id']}")
                
                # Extract bracket order IDs if present
                bracket_ids = None
                if 'legs' in data and data['legs']:
                    bracket_ids = {}
                    for leg in data['legs']:
                        if leg.get('order_class') == 'take_profit':
                            bracket_ids['tp'] = leg['id']
                        elif leg.get('order_class') == 'stop_loss':
                            bracket_ids['sl'] = leg['id']
                
                return OrderResult(
                    success=True,
                    order_id=data['id'],
                    message=f"Order {data['status']}",
                    filled_price=float(data['filled_avg_price']) if data.get('filled_avg_price') else None,
                    filled_qty=float(data['filled_qty']) if data.get('filled_qty') else None,
                    bracket_order_ids=bracket_ids
                )
            else:
                error_msg = resp.json().get('message', resp.text)
                print(f"❌ Order failed: {error_msg}")
                return OrderResult(success=False, message=error_msg)
                
        except Exception as e:
            print(f"❌ Order error: {e}")
            return OrderResult(success=False, message=str(e))
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order by ID."""
        try:
            resp = requests.delete(
                f"{self.base_url}/v2/orders/{order_id}",
                headers=self.headers
            )
            if resp.status_code in [200, 204]:
                print(f"✅ Order {order_id} cancelled")
                return True
            else:
                print(f"❌ Failed to cancel order: {resp.text}")
                return False
        except Exception as e:
            print(f"❌ Cancel error: {e}")
            return False
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        try:
            resp = requests.get(f"{self.base_url}/v2/positions", headers=self.headers)
            resp.raise_for_status()
            positions = resp.json()
            
            return [{
                'symbol': p['symbol'],
                'qty': float(p['qty']),
                'side': 'long' if float(p['qty']) > 0 else 'short',
                'avg_entry': float(p['avg_entry_price']),
                'current_price': float(p['current_price']),
                'market_value': float(p['market_value']),
                'pnl': float(p['unrealized_pl']),
                'pnl_pct': float(p['unrealized_plpc']) * 100
            } for p in positions]
        except Exception as e:
            print(f"⚠️ Positions error: {e}")
            return []
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account info."""
        try:
            resp = requests.get(f"{self.base_url}/v2/account", headers=self.headers)
            resp.raise_for_status()
            acc = resp.json()
            
            return {
                'buying_power': float(acc['buying_power']),
                'cash': float(acc['cash']),
                'portfolio_value': float(acc['portfolio_value']),
                'equity': float(acc['equity']),
                'currency': acc['currency'],
                'status': acc['status'],
                'is_paper': self.is_paper
            }
        except Exception as e:
            print(f"⚠️ Account error: {e}")
            return {'error': str(e)}

