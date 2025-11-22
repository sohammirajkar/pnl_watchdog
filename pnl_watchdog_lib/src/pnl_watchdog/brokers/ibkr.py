from ib_insync import *
from .base import BrokerAdapter


class IBKRAdapter(BrokerAdapter):
    def __init__(self, host: str = '127.0.0.1', port: int = 7497, client_id: int = 99):
        # IBKR requires a running TWS or Gateway software
        self.ib = IB()
        try:
            self.ib.connect(host, port, clientId=client_id)
        except Exception as e:
            print(f"❌ IBKR Connection Error: {e}. Is TWS/Gateway running?")

    def get_recent_orders(self, symbol: str, lookback_seconds: int):
        # Fetch all open trades and recent fills
        trades = self.ib.trades()

        normalized = []
        for t in trades:
            normalized.append({
                'symbol': t.contract.localSymbol,  # e.g., "ESH3" or "RELIANCE"
                'side': t.order.action.lower(),
                'qty': float(t.order.totalQuantity),
                'status': t.orderStatus.status.lower(),
                'id': str(t.order.orderId),
                'price': float(t.orderStatus.avgFillPrice),
                'timestamp': t.log[-1].time.timestamp() * 1000 if t.log else time.time()*1000
            })
        return normalized

    def normalize_symbol(self, symbol: str) -> str:
        return symbol.upper()
