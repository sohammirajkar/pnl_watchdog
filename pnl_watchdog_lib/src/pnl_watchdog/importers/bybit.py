"""
Bybit API Importer
Fetches authenticated trade history using read-only API credentials.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from .base import BrokerImporter, TradeRecord

try:
    import ccxt.async_support as ccxt_async
except Exception:
    ccxt_async = None


class BybitAPIImporter(BrokerImporter):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        *,
        market_type: str = "swap",
        symbol: Optional[str] = None,
        lookback_days: int = 7,
        limit: int = 500,
        testnet: bool = False,
    ):
        super().__init__()
        self.api_key = api_key
        self.api_secret = api_secret
        self.market_type = market_type
        self.symbol = symbol
        self.lookback_days = lookback_days
        self.limit = limit
        self.testnet = testnet

    async def parse(self, source: Any = None) -> List[TradeRecord]:
        """
        Fetch account trades from Bybit.
        'source' is unused and kept for interface compatibility.
        """
        self.errors = []
        trades: List[TradeRecord] = []

        if ccxt_async is None:
            self.errors.append("ccxt async support is not available.")
            return []

        exchange = ccxt_async.bybit({
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "enableRateLimit": True,
            "options": {
                "defaultType": self.market_type,
            },
        })

        try:
            if self.testnet:
                exchange.set_sandbox_mode(True)

            since_ts = int(
                (datetime.now(timezone.utc) - timedelta(days=self.lookback_days)).timestamp() * 1000
            )

            fetched = await exchange.fetch_my_trades(
                symbol=self.symbol,
                since=since_ts,
                limit=self.limit,
            )

            for row in fetched:
                try:
                    symbol = row.get("symbol")
                    side = (row.get("side") or "").lower()
                    amount = row.get("amount")
                    price = row.get("price")
                    ts = row.get("timestamp")

                    if not (symbol and side and amount and price and ts):
                        continue

                    timestamp = datetime.fromtimestamp(float(ts) / 1000, tz=timezone.utc)
                    trade = TradeRecord(
                        broker="bybit",
                        symbol=symbol,
                        side=side,
                        qty=float(amount),
                        price=float(price),
                        timestamp=timestamp,
                        order_id=str(row.get("order") or row.get("id") or ""),
                        raw_data=row,
                    )

                    if self.validate(trade):
                        trades.append(trade)
                except Exception as exc:
                    self.errors.append(f"Trade parse error: {exc}")

        except Exception as exc:
            self.errors.append(f"Bybit API error: {exc}")
        finally:
            try:
                await exchange.close()
            except Exception:
                pass

        return trades
