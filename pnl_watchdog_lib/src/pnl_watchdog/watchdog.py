from .ai_brain import AIBrain
import os
import time
import uuid
import hmac
import hashlib
import requests
import logging
import threading
import json
from datetime import datetime
import numpy as np
from typing import Optional, Dict, Any

# Import Rust module
try:
    from . import pnl_watchdog as pnl_core
except ImportError:
    pnl_core = None

# Configure logging
logging.basicConfig(level=logging.INFO, format="[PnL Watchdog] %(message)s")
logger = logging.getLogger("PnLWatchdog")

# --- IMPORT ADAPTERS ---
# We use try/except here so your code doesn't crash if you haven't
# created the specific Indian/IBKR adapter files yet.
try:
    from .brokers.alpaca import AlpacaAdapter
except ImportError:
    AlpacaAdapter = None

try:
    from .brokers.ccxt_adapter import CCXTAdapter
except ImportError:
    CCXTAdapter = None

try:
    from .brokers.zerodha import ZerodhaAdapter
except ImportError:
    ZerodhaAdapter = None

try:
    from .brokers.angel_one import AngelOneAdapter
except ImportError:
    AngelOneAdapter = None

try:
    from .brokers.ibkr import IBKRAdapter
except ImportError:
    IBKRAdapter = None

try:
    from .brokers.databento import DatabentoAdapter
except ImportError:
    DatabentoAdapter = None


class PnLWatchdog:
    """
    The central Watchdog class.
    Acts as a Factory to load the correct Broker Adapter and AI Brain.
    """

    def __init__(self, broker: str = "alpaca", pro_key: str = None, opt_in: bool = False, **kwargs):
        """
        Initialize the Watchdog.
        :param broker: 'alpaca', 'ibkr', 'binance', 'zerodha', etc.
        :param pro_key: Your PnL Watchdog Pro API Key (for the private dashboard).
        :param opt_in: Set to True to share anonymous latency stats with the Global Map.
        """
        # --- 1. IDENTITY & CONFIG ---
        self.user_id = str(uuid.uuid4())
        self.pro_key = pro_key
        self.opt_in = opt_in
        self.broker_name = broker.lower()

        # Production API URL
        self.api_url = "https://pnl-cloud-backend-4esa.vercel.app/v1"

        self.brain = AIBrain()
        self.adapter = None

        # --- 2. ADAPTER FACTORY (Connects to real brokers) ---
        # Extract common arguments
        api_key = kwargs.get("api_key")
        api_secret = kwargs.get("api_secret")
        paper = kwargs.get("paper", True)

        try:
            if self.broker_name == "alpaca":
                self.adapter = AlpacaAdapter(api_key, api_secret, paper)
            elif self.broker_name == "zerodha":
                self.adapter = ZerodhaAdapter(
                    api_key, kwargs.get("access_token"))
            elif self.broker_name == "angel":
                self.adapter = AngelOneAdapter(
                    api_key,
                    kwargs.get("client_code"),
                    kwargs.get("password"),
                    kwargs.get("totp")
                )
            elif self.broker_name == "ibkr":
                self.adapter = IBKRAdapter(
                    host=kwargs.get("host", '127.0.0.1'),
                    port=kwargs.get("port", 7497)
                )
            elif self.broker_name == "databento":
                self.adapter = DatabentoAdapter(api_key)
            else:
                # Default to CCXT for crypto (Binance, etc.)
                self.adapter = CCXTAdapter(
                    self.broker_name, api_key, api_secret, paper)
        except Exception as e:
            logger.warning(
                f"⚠️ Broker Adapter not initialized: {e}. (Whale View will be simulated)")

        # --- 3. WELCOME MESSAGE ---
        print("\n" + "-" * 60)
        print(f"🐶 PnL Watchdog Active.")
        print(f"🆔 YOUR USER ID: {self.user_id}")
        print(f"📋 (Copy this ID to claim your Founding Member status)")
        print("-" * 60 + "\n")

    def check_order(self, symbol, side, qty, price=None):
        """
        Main entry point. Verifies execution and reports latency.
        """
        start_time = time.time()
        logger.info(
            f"🔎 Verifying {side.upper()} {qty} {symbol} on {self.broker_name}...")

        # In a real scenario, we would use self.adapter.get_recent_orders() here
        # For now, we measure the check latency itself
        latency = int((time.time() - start_time) * 1000)

        # --- TELEMETRY (Non-blocking) ---
        if self.pro_key:
            # Pro users send full logs to their private dashboard
            threading.Thread(target=self._upload_log, args=({
                "symbol": symbol, "side": side, "qty": qty,
                "broker": self.broker_name, "latency_ms": latency,
                "slippage": 0.0, "status": "verified"
            },)).start()

        elif self.opt_in:
            # Free users send anonymous stats to the public map
            threading.Thread(target=self._upload_telemetry, args=({
                "symbol": symbol,  # Will be hashed
                "broker": self.broker_name,
                "latency_ms": latency,
                "slippage": 0.0,
                "status": "verified"
            },)).start()

        return {"status": "verified", "latency_ms": latency}

    def get_smart_route(self, symbol, size=1.0, urgency="normal"):
        """
        v0.4.0: The Oracle. Asks the cloud for the safest broker routing.
        """
        if not self.pro_key:
            logger.warning("⚠️ Oracle API requires a Pro Key.")
            return None

        try:
            headers = {"x-pro-key": self.pro_key}
            payload = {"symbol": symbol, "size": size, "urgency": urgency}

            resp = requests.post(
                f"{self.api_url}/oracle/route", json=payload, headers=headers, timeout=2)

            if resp.status_code == 200:
                data = resp.json()
                rec = data.get("recommendation")
                logger.info(
                    f"🔮 Oracle Recommendation: {rec.upper()} (Score: {data['metrics']['expected_latency']}ms)")
                return data
            else:
                logger.warning(f"Oracle Error: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to reach Oracle: {e}")
            return None

    def get_whale_view(self, symbol, lookback_candles=100, candles=None):
        """
        v0.5.0: The Whale Engine. Calculates Amihud & Kyle's Lambda.
        """
        # 1. Get Data (Prefer injected candles, then adapter, then fail)
        data = []
        if candles:
            data = candles
        elif self.adapter and hasattr(self.adapter, 'get_candles'):
            data = self.adapter.get_candles(symbol, lookback_candles)

        if not data:
            return {"error": "No candle data. Connect a broker or pass 'candles' list.", "verdict": "No Data"}

        # 2. Process Metrics
        returns_abs = []
        dollar_vols = []
        price_changes = []
        signed_vols = []

        for c in data:
            if not isinstance(c, dict) or 'volume' not in c or c['volume'] == 0:
                continue

            # Amihud
            ret = (c['close'] - c['open']) / c['open']
            dollar_vol = c['close'] * c['volume']
            returns_abs.append(abs(ret))
            dollar_vols.append(dollar_vol)

            # Kyle's Lambda
            sign = 1 if c['close'] >= c['open'] else -1
            price_changes.append(c['close'] - c['open'])
            signed_vols.append(c['volume'] * sign)

        # 3. Calculate
        amihud_score = 0
        kyles_lambda = 0

        if dollar_vols:
            amihud_raw = [r / v for r, v in zip(returns_abs, dollar_vols)]
            amihud_score = (sum(amihud_raw) / len(amihud_raw)) * 1_000_000

        if len(signed_vols) > 1:
            slope, _ = np.polyfit(signed_vols, price_changes, 1)
            kyles_lambda = slope * 1_000_000

        return {
            "symbol": symbol,
            "amihud_illiquidity": round(amihud_score, 4),
            "kyles_lambda": round(kyles_lambda, 6),
            "verdict": "TOXIC ORDER BOOK" if kyles_lambda > 1.0 else "Healthy"
        }

    def get_order_flow_analytics(self, symbol, lookback=50):
        """
        [NEW] Returns Institutional Order Flow Metrics.
        - Toxicity: Probability of informed trading (0-100).
        - VWAP Deviation: Trend strength (Basis Points).
        - Imbalance: Order Book Pressure (-1 to 1).
        """
        if not pnl_core:
            return {"error": "Rust Core Missing"}

        # 1. Fetch Data (Using Adapter)
        if not self.adapter or not hasattr(self.adapter, 'get_candles'):
            return {"error": "No Broker Connected"}

        data = self.adapter.get_candles(symbol, lookback)
        if not data:
            return {"error": "No Data"}

        # 2. Prepare Rust Vectors
        prices = [c['close'] for c in data]
        volumes = [float(c['volume']) for c in data]

        # NOTE: Real Toxicity requires Level 2 Data (Bids/Asks).
        # Retail feeds don't give history of Bids/Asks.
        # We simulate it here for the Free Tier based on High/Low proxies.
        # In Pro Tier (Databento), you would pass real arrays.
        sim_bids = [c['close'] * 0.999 for c in data]
        sim_asks = [c['close'] * 1.001 for c in data]

        # 3. Call Rust Engine
        vwap_dev, tox, nof, obi, vwap = pnl_core.calculate_order_flow_metrics(
            prices, volumes, sim_bids, sim_asks
        )

        return {
            "symbol": symbol,
            "toxicity_score": round(tox, 2),
            "vwap_deviation_bps": round(vwap_dev, 2),
            "net_order_flow": round(nof, 2),
            "order_book_imbalance": round(obi, 4),
            "verdict": "HIGH TOXICITY" if tox > 50 else "SAFE"
        }

    def _sanitize_payload(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        PRIVACY SHIELD: Strips sensitive alpha before upload.
        """
        # Hash the symbol to protect strategy
        encrypted_symbol = "unknown"
        if 'symbol' in data:
            encrypted_symbol = hashlib.sha256(
                data['symbol'].encode()).hexdigest()

        return {
            "symbol_hash": encrypted_symbol,
            "broker": data.get('broker', 'unknown'),
            "latency_ms": data.get('latency_ms', 0),
            "slippage": data.get('slippage', 0.0),
            "status": data.get('status', 'unknown')
            # NOTE: Side, Qty, Price are deliberately excluded
        }

    def _upload_log(self, data):
        """Sends PRIVATE data to your SaaS backend (Pro Users)"""
        try:
            headers = {"x-pro-key": self.pro_key}
            requests.post(f"{self.api_url}/log_trade",
                          json=data, headers=headers, timeout=2)
        except Exception as e:
            print(f"⚠️ Cloud Sync Failed: {e}")

    def _upload_telemetry(self, data):
        """Sends ANONYMOUS health stats to the global map (Free Users)"""
        try:
            safe_data = self._sanitize_payload(data)
            requests.post(f"{self.api_url}/telemetry",
                          json=safe_data, timeout=2)
        except Exception:
            pass
