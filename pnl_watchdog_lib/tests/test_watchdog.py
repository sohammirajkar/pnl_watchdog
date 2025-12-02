from pnl_watchdog.watchdog import PnLWatchdog, RUST_CORE_AVAILABLE
import sys
import os
import unittest
import time
from unittest.mock import MagicMock, patch
import requests

# --- CRITICAL FIX: Add 'src' to Python Path ---
# This allows the test runner to find the 'pnl_watchdog' package inside the 'src' directory.
# This must be done before the failing import.
sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../src')))

# The import that was failing:


class TestPnLWatchdogCore(unittest.TestCase):
    def setUp(self):
        # Initialize with dummy keys for testing purposes
        self.dog = PnLWatchdog(
            api_key="test", api_secret="test", broker="dummy_broker")

    def test_initialization(self):
        """Ensure the watchdog initializes with core settings."""
        self.assertIsNotNone(self.dog.broker)
        self.assertEqual(self.dog.api_key, "test")
        self.assertEqual(self.dog.api_secret, "test")
        self.assertFalse(self.dog.opt_in, "Default opt-in should be False")

    @patch('pnl_watchdog.watchdog.requests.post')
    def test_telemetry_upload(self, mock_post):
        """Test that telemetry is correctly uploaded when opt-in is True."""
        # Change opt-in status and simulate a payload
        self.dog.opt_in = True
        test_payload = {
            "symbol": "BTC",
            "latency_ms": 120,
            "slippage": 0.005,
            "status": "filled",
            "broker": "dummy_broker",
            "side": "buy",  # Added necessary fields for sanitization logic to work
            "qty": 1.0,
            "price": 100.0
        }

        # Directly call the internal upload function
        # Note: _upload_telemetry typically runs in a thread, but calling it directly tests the logic.
        self.dog._upload_telemetry(test_payload)
        time.sleep(0.1)

        # Check if requests.post was called
        mock_post.assert_called_once()

        # Verify the endpoint used
        call_url = mock_post.call_args[0][0]
        self.assertTrue(call_url.endswith("/telemetry"),
                        "Should call the public telemetry endpoint")

        # Verify sensitive data is sanitized (symbol should be hashed)
        sent_data = mock_post.call_args[1]['json']
        self.assertNotIn("symbol", sent_data)
        self.assertIn("symbol_hash", sent_data)
        self.assertNotIn("side", sent_data)
        self.assertEqual(sent_data["latency_ms"], 120)


if __name__ == '__main__':
    unittest.main()
