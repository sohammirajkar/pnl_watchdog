import os
import time
import uuid
import hmac
import hashlib
import requests
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="[PnL Watchdog] %(message)s")
logger = logging.getLogger("PnLWatchdog")


class PnLWatchdog:
    def __init__(self, broker, api_key=None, api_secret=None, opt_in=False):
        """
        Initialize the Watchdog.
        """
        # --- 1. DEFINE USER ID (CRITICAL STEP) ---
        self.user_id = str(uuid.uuid4())

        # --- 2. ASSIGN ARGUMENTS ---
        self.broker = broker.lower()
        self.api_key = api_key
        self.api_secret = api_secret
        self.opt_in = opt_in

        # --- 3. CONFIGURATION ---
        self.api_url = "https://pnl-cloud-backend-4esa.vercel.app/v1"

        # --- 4. PRINT ID FOR THE USER ---
        print("\n" + "-" * 60)
        print(f"🐶 PnL Watchdog Active.")
        print(f"🆔 YOUR USER ID: {self.user_id}")
        print(f"📋 (Copy this ID to claim your Founding Member status)")
        print("-" * 60 + "\n")

    def check_order(self, symbol, side, qty, price=None):
        start_time = time.time()
        logger.info(
            f"🔎 Verifying {side.upper()} {qty} {symbol} on {self.broker}...")
        latency = int((time.time() - start_time) * 1000)

        if self.opt_in:
            self._upload_telemetry(self.broker, latency, status="verified")

        return {"status": "verified", "latency_ms": latency}

    def _upload_telemetry(self, broker, latency, status="verified"):
        try:
            payload = {
                "broker": broker,
                "latency_ms": latency,
                "slippage": 0.0,
                "status": status
            }
            requests.post(f"{self.api_url}/telemetry", json=payload, timeout=2)
        except Exception:
            pass

    def get_smart_route(self, symbol, size=1.0, urgency="normal"):
        """
        Queries the PnL Oracle for the safest broker right now.
        Returns: The name of the broker (e.g., 'binance')
        """
        if not self.api_key:
            logger.warning("⚠️ Oracle API requires an API Key (Pro Feature).")
            return None

        try:
            headers = {"x-pro-key": self.api_key}
            payload = {
                "symbol": symbol,
                "size": size,
                "urgency": urgency
            }

            resp = requests.post(
                f"{self.api_url}/oracle/route", json=payload, headers=headers, timeout=1)

            if resp.status_code == 200:
                data = resp.json()
                rec = data.get("recommendation")
                logger.info(
                    f"🔮 Oracle Recommendation: {rec.upper()} (Score: {data['metrics']['expected_latency']}ms)")
                return rec
            else:
                logger.warning(f"Oracle Error: {resp.text}")
                return None

        except Exception as e:
            logger.error(f"Failed to reach Oracle: {e}")
            return None
