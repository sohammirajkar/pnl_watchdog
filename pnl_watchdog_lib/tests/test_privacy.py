import unittest
from pnl_watchdog.watchdog import PnLWatchdog


class TestPrivacy(unittest.TestCase):
    def setUp(self):
        # Initialize with dummy keys
        self.dog = PnLWatchdog(
            api_key="test", api_secret="test", broker="alpaca")

    def test_sanitize_payload(self):
        """Ensure sensitive data is stripped and symbol is hashed."""
        raw_data = {
            "symbol": "AAPL",
            "side": "buy",
            "qty": 100,
            "price": 150.00,
            "broker": "alpaca",
            "latency_ms": 45,
            "slippage": 0.01,
            "status": "verified"
        }

        # Call the internal sanitizer method
        clean_data = self.dog._sanitize_payload(raw_data)

        # 1. VERIFY REMOVAL: Sensitive alpha fields must be gone
        self.assertNotIn("side", clean_data,
                         "Alpha Leak: Side (Buy/Sell) was not stripped!")
        self.assertNotIn("qty", clean_data,
                         "Alpha Leak: Qty was not stripped!")
        self.assertNotIn("price", clean_data,
                         "Alpha Leak: Price was not stripped!")
        self.assertNotIn("symbol", clean_data,
                         "Alpha Leak: Raw symbol was not stripped!")

        # 2. VERIFY HASHING: Symbol must be anonymized
        self.assertNotEqual(clean_data["symbol_hash"], "AAPL")
        self.assertTrue(len(clean_data["symbol_hash"]) ==
                        64, "Symbol hash should be SHA-256 (64 chars)")

        # 3. VERIFY METRICS: Infrastructure stats must remain
        self.assertEqual(clean_data["broker"], "alpaca")
        self.assertEqual(clean_data["latency_ms"], 45)
        self.assertEqual(clean_data["slippage"], 0.01)


if __name__ == '__main__':
    unittest.main()
