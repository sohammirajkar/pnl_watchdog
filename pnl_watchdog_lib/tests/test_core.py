import unittest
from unittest.mock import MagicMock, patch
from pnl_watchdog import PnLWatchdog


class TestWatchdogLogic(unittest.TestCase):
    def setUp(self):
        # 1. Mock the CCXT Adapter so we don't hit Binance
        self.mock_adapter = MagicMock()

        # 2. Inject the mock into the Watchdog
        self.dog = PnLWatchdog(
            api_key="dummy", api_secret="dummy", broker="binance")
        self.dog.adapter = self.mock_adapter  # Force replace the real adapter

    def test_check_order_found(self):
        """Test that we correctly identify a found trade."""
        # Setup the mock to return a "success" list
        self.mock_adapter.normalize_symbol.return_value = "BTC/USDT"
        self.mock_adapter.get_recent_orders.return_value = [
            {'symbol': 'BTC/USDT', 'side': 'buy', 'qty': 1.0,
                'price': 50000, 'timestamp': 1234567890}
        ]

        # Run the code
        found = self.dog.check_order("BTC/USDT", "buy", 1.0)

        # Assertions
        self.assertTrue(found)
        self.mock_adapter.get_recent_orders.assert_called_once()

    def test_check_order_missing(self):
        """Test that we scream if the trade is empty."""
        self.mock_adapter.get_recent_orders.return_value = []  # Empty list from broker

        found = self.dog.check_order("BTC/USDT", "buy", 1.0)

        self.assertFalse(found)

    def test_slippage_alert(self):
        """Test that high slippage triggers an alert."""
        # Bot expected $50,000. Broker filled at $50,500 (Huge slippage)
        self.mock_adapter.normalize_symbol.return_value = "BTC/USDT"
        self.mock_adapter.get_recent_orders.return_value = [
            {'symbol': 'BTC/USDT', 'side': 'buy', 'qty': 1.0,
                'price': 50500, 'timestamp': 1234567890}
        ]

        # We capture stdout (print) to verify the alert
        with patch('builtins.print') as mocked_print:
            self.dog.check_slippage(
                "BTC/USDT", expected_price=50000, filled_qty=1.0, threshold_cents=100)

            # Verify it printed a warning
            args, _ = mocked_print.call_args
            self.assertIn("HIGH SLIPPAGE", args[0])


if __name__ == '__main__':
    unittest.main()
