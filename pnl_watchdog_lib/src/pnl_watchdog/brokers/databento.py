import databento as db
from typing import List, Dict, Any
from datetime import datetime, timedelta


class DatabentoAdapter:
    def __init__(self, api_key: str):
        """
        Initialize Databento adapter
        :param api_key: Your Databento API key
        """
        self.api_key = api_key
        self.client = db.Historical(key=api_key)

    def get_candles(self, symbol: str, lookback: int = 50) -> List[Dict[str, Any]]:
        """
        Get OHLCV data from Databento
        :param symbol: Symbol to fetch data for
        :param lookback: Number of periods to look back
        :return: List of candle dictionaries with open, close, volume keys
        """
        try:
            # Use a broader time range to ensure we get data
            end_time = datetime(2025, 11, 28, 23, 59, 59)
            # Get a full day of data
            start_time = end_time - timedelta(hours=24)

            # Fetch data
            data = self.client.timeseries.get_range(
                dataset='XNAS.ITCH',  # NASDAQ TotalView
                symbols=symbol,
                schema='ohlcv-1h',  # Use hourly data instead of minute data
                stype_in='raw_symbol',
                start=start_time.isoformat(),
                end=end_time.isoformat()
            )

            # Convert to list of dictionaries
            df = data.to_df()
            candles = []
            for _, row in df.iterrows():
                candles.append({
                    'open': float(row['open']),
                    'close': float(row['close']),
                    'volume': float(row['volume'])
                })

            # Return only the requested number of candles
            return candles[-lookback:] if len(candles) > lookback else candles
        except Exception as e:
            print(f"Error fetching Databento data: {e}")
            return []

    def get_order_book_data(self, symbol: str, lookback: int = 50) -> Dict[str, List[float]]:
        """
        Get order book data from Databento
        :param symbol: Symbol to fetch data for
        :param lookback: Number of periods to look back
        :return: Dictionary with bid_prices and ask_prices lists
        """
        try:
            # Use the last available date for data
            # Just before the end date
            end_time = datetime(2025, 11, 28, 23, 59, 59)
            start_time = end_time - timedelta(minutes=lookback)

            # Fetch order book data
            data = self.client.timeseries.get_range(
                dataset='XNAS.ITCH',  # NASDAQ TotalView
                symbols=symbol,
                schema='mbp-10',  # Market by price, 10 levels
                stype_in='raw_symbol',
                start=start_time.isoformat(),
                end=end_time.isoformat()
            )

            # Convert to lists of bid/ask prices
            df = data.to_df()
            bid_prices = []
            ask_prices = []

            for _, row in df.iterrows():
                # Extract bid and ask prices from the order book data
                # This is a simplified extraction - you might need to adjust based on actual data structure
                if 'bid_px' in row and 'ask_px' in row:
                    bid_prices.append(float(row['bid_px']))
                    ask_prices.append(float(row['ask_px']))

            return {
                'bid_prices': bid_prices,
                'ask_prices': ask_prices
            }
        except Exception as e:
            print(f"Error fetching Databento order book data: {e}")
            return {'bid_prices': [], 'ask_prices': []}
